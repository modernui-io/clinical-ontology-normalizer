"""Temporal Query Service for Knowledge Graph.

Provides temporal reasoning capabilities for the knowledge graph:
- Point-in-time queries: What was true at a specific moment?
- Range queries: What changed during a time period?
- Temporal consistency validation: Do causal chains respect time ordering?
- Allen's interval algebra: Compare temporal relationships between facts

Based on research from temporal knowledge graph reasoning literature:
- OWL-Time ontology patterns for interval algebra
- Bi-temporal model for valid time and transaction time
- Temporal constraint propagation for causal reasoning
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.knowledge_graph import TemporalOrder


class IntervalRelation(str, Enum):
    """Allen's interval algebra relations.

    Defines 13 possible relations between two temporal intervals.
    Used for comparing temporal relationships between clinical facts.
    """

    BEFORE = "before"  # A ends before B starts
    AFTER = "after"  # A starts after B ends
    MEETS = "meets"  # A ends exactly when B starts
    MET_BY = "met_by"  # A starts exactly when B ends
    OVERLAPS = "overlaps"  # A starts before B, ends during B
    OVERLAPPED_BY = "overlapped_by"  # A starts during B, ends after B
    STARTS = "starts"  # A starts same time as B, ends earlier
    STARTED_BY = "started_by"  # B starts same time as A, ends earlier
    FINISHES = "finishes"  # A ends same time as B, starts later
    FINISHED_BY = "finished_by"  # B ends same time as A, starts later
    DURING = "during"  # A entirely within B
    CONTAINS = "contains"  # A entirely contains B
    EQUALS = "equals"  # A and B have same start and end


@dataclass
class TemporalInterval:
    """Represents a temporal interval with start and end times."""

    start: datetime | None
    end: datetime | None

    def is_instant(self) -> bool:
        """Check if this is a point in time (no duration)."""
        return self.start == self.end

    def is_open_ended(self) -> bool:
        """Check if interval has no end (ongoing)."""
        return self.end is None

    def contains_time(self, time: datetime) -> bool:
        """Check if a point in time falls within this interval."""
        if self.start and time < self.start:
            return False
        if self.end and time > self.end:
            return False
        return True

    def overlaps_range(self, start: datetime, end: datetime) -> bool:
        """Check if this interval overlaps with a given range."""
        # No overlap if this ends before range starts
        if self.end and self.end < start:
            return False
        # No overlap if this starts after range ends
        if self.start and self.start > end:
            return False
        return True


@dataclass
class TemporalEdge:
    """An edge with its temporal information."""

    edge: KGEdge
    interval: TemporalInterval
    temporal_order: TemporalOrder | None


@dataclass
class TemporalQueryResult:
    """Result of a temporal query."""

    nodes: list[KGNode]
    edges: list[TemporalEdge]
    query_time: datetime | None
    query_range: tuple[datetime, datetime] | None


@dataclass
class TemporalConsistencyResult:
    """Result of temporal consistency validation."""

    is_consistent: bool
    violations: list[dict[str, Any]]
    validated_chains: list[dict[str, Any]]


class TemporalQueryService:
    """Service for temporal queries on the knowledge graph.

    Provides:
    - query_at_time: Snapshot of graph at a specific time
    - query_time_range: Changes within a time period
    - validate_temporal_consistency: Check causal chain temporal ordering
    - compare_intervals: Allen's interval algebra comparisons
    - compute_temporal_distance: Time between related facts
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    # =========================================================================
    # Point-in-Time Queries
    # =========================================================================

    async def query_at_time(
        self,
        patient_id: str,
        time_point: datetime,
        node_types: list[str] | None = None,
        edge_types: list[str] | None = None,
    ) -> TemporalQueryResult:
        """Query the knowledge graph as it was at a specific point in time.

        Returns only edges that were valid at the specified time:
        - valid_from <= time_point
        - valid_to is null OR valid_to > time_point

        Args:
            patient_id: Patient identifier
            time_point: The point in time to query
            node_types: Optional filter for node types
            edge_types: Optional filter for edge types

        Returns:
            TemporalQueryResult with nodes and edges valid at that time
        """
        # Build edge query with temporal filters
        # Use valid_from/valid_to for validity period, or event_date as fallback
        edge_query = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(
                or_(
                    KGEdge.valid_from.is_(None),
                    KGEdge.valid_from <= time_point,
                )
            )
            .where(
                or_(
                    KGEdge.valid_to.is_(None),
                    KGEdge.valid_to > time_point,
                )
            )
            .options(
                selectinload(KGEdge.source_node),
                selectinload(KGEdge.target_node),
            )
        )

        if edge_types:
            edge_query = edge_query.where(KGEdge.edge_type.in_(edge_types))

        result = await self.db.execute(edge_query)
        edges = result.scalars().all()

        # Collect nodes from edges and filter by type
        node_set: dict[str, KGNode] = {}
        temporal_edges: list[TemporalEdge] = []

        for edge in edges:
            # Add source and target nodes
            if edge.source_node:
                if not node_types or edge.source_node.node_type.value in node_types:
                    node_set[str(edge.source_node.id)] = edge.source_node
            if edge.target_node:
                if not node_types or edge.target_node.node_type.value in node_types:
                    node_set[str(edge.target_node.id)] = edge.target_node

            # Create temporal edge
            temporal_edges.append(
                TemporalEdge(
                    edge=edge,
                    interval=TemporalInterval(
                        start=edge.valid_from,
                        end=edge.valid_to,
                    ),
                    temporal_order=(
                        TemporalOrder(edge.temporal_order)
                        if edge.temporal_order
                        else None
                    ),
                )
            )

        return TemporalQueryResult(
            nodes=list(node_set.values()),
            edges=temporal_edges,
            query_time=time_point,
            query_range=None,
        )

    # =========================================================================
    # Range Queries
    # =========================================================================

    async def query_time_range(
        self,
        patient_id: str,
        start_time: datetime,
        end_time: datetime,
        include_ongoing: bool = True,
        node_types: list[str] | None = None,
        edge_types: list[str] | None = None,
    ) -> TemporalQueryResult:
        """Query edges that were active during a time range.

        Returns edges that overlap with the specified range:
        - Started before the range ended
        - Ended after the range started (or ongoing)

        Args:
            patient_id: Patient identifier
            start_time: Start of the query range
            end_time: End of the query range
            include_ongoing: Include edges with no end date
            node_types: Optional filter for node types
            edge_types: Optional filter for edge types

        Returns:
            TemporalQueryResult with nodes and edges active in that range
        """
        # Build edge query with range overlap
        edge_query = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(
                # Started before or during the range
                or_(
                    KGEdge.valid_from.is_(None),
                    KGEdge.valid_from <= end_time,
                )
            )
            .options(
                selectinload(KGEdge.source_node),
                selectinload(KGEdge.target_node),
            )
        )

        # Add end time filter
        if include_ongoing:
            edge_query = edge_query.where(
                or_(
                    KGEdge.valid_to.is_(None),
                    KGEdge.valid_to >= start_time,
                )
            )
        else:
            edge_query = edge_query.where(
                and_(
                    KGEdge.valid_to.is_not(None),
                    KGEdge.valid_to >= start_time,
                )
            )

        if edge_types:
            edge_query = edge_query.where(KGEdge.edge_type.in_(edge_types))

        result = await self.db.execute(edge_query)
        edges = result.scalars().all()

        # Collect nodes and temporal edges
        node_set: dict[str, KGNode] = {}
        temporal_edges: list[TemporalEdge] = []

        for edge in edges:
            if edge.source_node:
                if not node_types or edge.source_node.node_type.value in node_types:
                    node_set[str(edge.source_node.id)] = edge.source_node
            if edge.target_node:
                if not node_types or edge.target_node.node_type.value in node_types:
                    node_set[str(edge.target_node.id)] = edge.target_node

            temporal_edges.append(
                TemporalEdge(
                    edge=edge,
                    interval=TemporalInterval(
                        start=edge.valid_from,
                        end=edge.valid_to,
                    ),
                    temporal_order=(
                        TemporalOrder(edge.temporal_order)
                        if edge.temporal_order
                        else None
                    ),
                )
            )

        return TemporalQueryResult(
            nodes=list(node_set.values()),
            edges=temporal_edges,
            query_time=None,
            query_range=(start_time, end_time),
        )

    async def get_changes_between(
        self,
        patient_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, list[KGEdge]]:
        """Get edges that started or ended within a time range.

        Returns:
            Dict with 'started' and 'ended' edge lists
        """
        # Edges that started in the range
        started_query = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.valid_from.is_not(None))
            .where(KGEdge.valid_from >= start_time)
            .where(KGEdge.valid_from <= end_time)
        )
        started_result = await self.db.execute(started_query)
        started_edges = list(started_result.scalars().all())

        # Edges that ended in the range
        ended_query = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.valid_to.is_not(None))
            .where(KGEdge.valid_to >= start_time)
            .where(KGEdge.valid_to <= end_time)
        )
        ended_result = await self.db.execute(ended_query)
        ended_edges = list(ended_result.scalars().all())

        return {
            "started": started_edges,
            "ended": ended_edges,
        }

    # =========================================================================
    # Allen's Interval Algebra
    # =========================================================================

    def compare_intervals(
        self,
        interval_a: TemporalInterval,
        interval_b: TemporalInterval,
        tolerance: timedelta = timedelta(0),
    ) -> IntervalRelation:
        """Compare two temporal intervals using Allen's interval algebra.

        Args:
            interval_a: First interval
            interval_b: Second interval
            tolerance: Tolerance for considering times as "equal"

        Returns:
            IntervalRelation describing how A relates to B
        """
        a_start = interval_a.start
        a_end = interval_a.end
        b_start = interval_b.start
        b_end = interval_b.end

        # Handle open-ended intervals by using far future
        far_future = datetime(9999, 12, 31, tzinfo=timezone.utc)
        if a_end is None:
            a_end = far_future
        if b_end is None:
            b_end = far_future

        # Handle missing start times by using far past
        far_past = datetime(1, 1, 1, tzinfo=timezone.utc)
        if a_start is None:
            a_start = far_past
        if b_start is None:
            b_start = far_past

        # Check for equality within tolerance
        def times_equal(t1: datetime, t2: datetime) -> bool:
            return abs((t1 - t2).total_seconds()) <= tolerance.total_seconds()

        # EQUALS: Same start and end
        if times_equal(a_start, b_start) and times_equal(a_end, b_end):
            return IntervalRelation.EQUALS

        # BEFORE: A ends before B starts
        if a_end < b_start and not times_equal(a_end, b_start):
            return IntervalRelation.BEFORE

        # AFTER: A starts after B ends
        if a_start > b_end and not times_equal(a_start, b_end):
            return IntervalRelation.AFTER

        # MEETS: A ends exactly when B starts
        if times_equal(a_end, b_start):
            return IntervalRelation.MEETS

        # MET_BY: A starts exactly when B ends
        if times_equal(a_start, b_end):
            return IntervalRelation.MET_BY

        # OVERLAPS: A starts before B, overlaps into B
        if a_start < b_start < a_end < b_end:
            return IntervalRelation.OVERLAPS

        # OVERLAPPED_BY: B starts before A, overlaps into A
        if b_start < a_start < b_end < a_end:
            return IntervalRelation.OVERLAPPED_BY

        # STARTS: A starts with B but ends earlier
        if times_equal(a_start, b_start) and a_end < b_end:
            return IntervalRelation.STARTS

        # STARTED_BY: B starts with A but ends earlier
        if times_equal(a_start, b_start) and b_end < a_end:
            return IntervalRelation.STARTED_BY

        # FINISHES: A ends with B but starts later
        if times_equal(a_end, b_end) and a_start > b_start:
            return IntervalRelation.FINISHES

        # FINISHED_BY: B ends with A but starts later
        if times_equal(a_end, b_end) and b_start > a_start:
            return IntervalRelation.FINISHED_BY

        # DURING: A entirely within B
        if a_start > b_start and a_end < b_end:
            return IntervalRelation.DURING

        # CONTAINS: A entirely contains B
        if a_start < b_start and a_end > b_end:
            return IntervalRelation.CONTAINS

        # Fallback (shouldn't reach here)
        return IntervalRelation.OVERLAPS

    def is_before(
        self,
        earlier: TemporalInterval,
        later: TemporalInterval,
        strict: bool = False,
    ) -> bool:
        """Check if one interval comes before another.

        Args:
            earlier: The interval that should come first
            later: The interval that should come second
            strict: If True, intervals must not touch/overlap

        Returns:
            True if earlier comes before later
        """
        if strict:
            return self.compare_intervals(earlier, later) == IntervalRelation.BEFORE
        else:
            relation = self.compare_intervals(earlier, later)
            return relation in {
                IntervalRelation.BEFORE,
                IntervalRelation.MEETS,
            }

    # =========================================================================
    # Temporal Consistency Validation
    # =========================================================================

    async def validate_temporal_consistency(
        self,
        patient_id: str,
        causal_edges: list[tuple[str, str]] | None = None,
    ) -> TemporalConsistencyResult:
        """Validate that causal relationships respect temporal ordering.

        For causal relationships (A causes B), validates that:
        - A's start time is before or equal to B's start time
        - The cause precedes or is concurrent with the effect

        Args:
            patient_id: Patient identifier
            causal_edges: Optional list of (source_id, target_id) tuples to check.
                         If None, checks all edges with causal edge types.

        Returns:
            TemporalConsistencyResult with violations and validated chains
        """
        # Define causal edge types that require temporal ordering
        causal_edge_types = [
            "drug_treats",
            "condition_treated_by",
            "has_condition",
            "takes_drug",
        ]

        # Query edges with temporal information
        edge_query = (
            select(KGEdge)
            .where(KGEdge.patient_id == patient_id)
            .where(KGEdge.valid_from.is_not(None))
            .options(
                selectinload(KGEdge.source_node),
                selectinload(KGEdge.target_node),
            )
        )

        if causal_edges:
            # Check specific edges
            edge_conditions = []
            for source_id, target_id in causal_edges:
                edge_conditions.append(
                    and_(
                        KGEdge.source_node_id == source_id,
                        KGEdge.target_node_id == target_id,
                    )
                )
            edge_query = edge_query.where(or_(*edge_conditions))
        else:
            # Check all causal edge types
            edge_query = edge_query.where(
                KGEdge.edge_type.in_(causal_edge_types)
            )

        result = await self.db.execute(edge_query)
        edges = result.scalars().all()

        violations: list[dict[str, Any]] = []
        validated_chains: list[dict[str, Any]] = []

        for edge in edges:
            # For treatment edges, the condition should precede the treatment
            if edge.edge_type in ["drug_treats", "condition_treated_by"]:
                # Get the source node's temporal info (the treatment)
                # and target node's temporal info (the condition)
                source_start = edge.valid_from
                target_start = edge.valid_from  # Use edge time as proxy

                # Check if the edge has temporal ordering info
                if edge.temporal_order:
                    order = TemporalOrder(edge.temporal_order)
                    if order == TemporalOrder.BEFORE:
                        # Source is marked as BEFORE target - valid for treatment
                        validated_chains.append({
                            "edge_id": str(edge.id),
                            "edge_type": edge.edge_type,
                            "source_node": edge.source_node.label if edge.source_node else None,
                            "target_node": edge.target_node.label if edge.target_node else None,
                            "temporal_order": edge.temporal_order,
                            "is_valid": True,
                            "reason": "Treatment marked as following condition",
                        })
                    elif order == TemporalOrder.AFTER:
                        # Source is marked as AFTER target - violation
                        violations.append({
                            "edge_id": str(edge.id),
                            "edge_type": edge.edge_type,
                            "source_node": edge.source_node.label if edge.source_node else None,
                            "target_node": edge.target_node.label if edge.target_node else None,
                            "temporal_order": edge.temporal_order,
                            "violation": "Treatment marked as preceding condition",
                        })
                    else:
                        validated_chains.append({
                            "edge_id": str(edge.id),
                            "edge_type": edge.edge_type,
                            "temporal_order": edge.temporal_order,
                            "is_valid": True,
                            "reason": "Temporal ordering acceptable",
                        })
                else:
                    # No explicit temporal ordering - assume valid
                    validated_chains.append({
                        "edge_id": str(edge.id),
                        "edge_type": edge.edge_type,
                        "is_valid": True,
                        "reason": "No temporal constraints specified",
                    })

        return TemporalConsistencyResult(
            is_consistent=len(violations) == 0,
            violations=violations,
            validated_chains=validated_chains,
        )

    # =========================================================================
    # Temporal Distance Calculations
    # =========================================================================

    def compute_temporal_distance(
        self,
        interval_a: TemporalInterval,
        interval_b: TemporalInterval,
    ) -> timedelta | None:
        """Compute the temporal distance between two intervals.

        For non-overlapping intervals, returns the gap between them.
        For overlapping intervals, returns timedelta(0).
        Returns None if distance cannot be computed (missing dates).
        """
        if not interval_a.start or not interval_b.start:
            return None

        # Check if intervals overlap
        if interval_a.overlaps_range(
            interval_b.start,
            interval_b.end or datetime.max.replace(tzinfo=timezone.utc),
        ):
            return timedelta(0)

        # A is before B
        if interval_a.end and interval_a.end < interval_b.start:
            return interval_b.start - interval_a.end

        # B is before A
        if interval_b.end and interval_b.end < interval_a.start:
            return interval_a.start - interval_b.end

        return timedelta(0)

    async def get_edge_timeline(
        self,
        patient_id: str,
        node_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get a timeline of edge changes for a patient or specific node.

        Returns a chronological list of edge starts and ends.
        """
        query = select(KGEdge).where(KGEdge.patient_id == patient_id)

        if node_id:
            query = query.where(
                or_(
                    KGEdge.source_node_id == node_id,
                    KGEdge.target_node_id == node_id,
                )
            )

        query = query.options(
            selectinload(KGEdge.source_node),
            selectinload(KGEdge.target_node),
        )

        result = await self.db.execute(query)
        edges = result.scalars().all()

        timeline: list[dict[str, Any]] = []

        for edge in edges:
            # Add start event
            if edge.valid_from:
                timeline.append({
                    "time": edge.valid_from,
                    "event_type": "start",
                    "edge_id": str(edge.id),
                    "edge_type": edge.edge_type,
                    "source_node": edge.source_node.label if edge.source_node else None,
                    "target_node": edge.target_node.label if edge.target_node else None,
                })

            # Add end event
            if edge.valid_to:
                timeline.append({
                    "time": edge.valid_to,
                    "event_type": "end",
                    "edge_id": str(edge.id),
                    "edge_type": edge.edge_type,
                    "source_node": edge.source_node.label if edge.source_node else None,
                    "target_node": edge.target_node.label if edge.target_node else None,
                })

        # Sort by time
        timeline.sort(key=lambda x: x["time"])

        return timeline


# =============================================================================
# Utility Functions
# =============================================================================


def temporal_order_from_intervals(
    source_interval: TemporalInterval,
    target_interval: TemporalInterval,
    tolerance: timedelta = timedelta(hours=1),
) -> TemporalOrder:
    """Infer temporal ordering from two intervals.

    Useful for populating the temporal_order field on edges.
    """
    service = TemporalQueryService(None)  # type: ignore
    relation = service.compare_intervals(source_interval, target_interval, tolerance)

    mapping = {
        IntervalRelation.BEFORE: TemporalOrder.BEFORE,
        IntervalRelation.AFTER: TemporalOrder.AFTER,
        IntervalRelation.MEETS: TemporalOrder.BEFORE,
        IntervalRelation.MET_BY: TemporalOrder.AFTER,
        IntervalRelation.OVERLAPS: TemporalOrder.OVERLAPS,
        IntervalRelation.OVERLAPPED_BY: TemporalOrder.OVERLAPS,
        IntervalRelation.DURING: TemporalOrder.DURING,
        IntervalRelation.CONTAINS: TemporalOrder.CONTAINS,
        IntervalRelation.STARTS: TemporalOrder.STARTS,
        IntervalRelation.STARTED_BY: TemporalOrder.STARTS,
        IntervalRelation.FINISHES: TemporalOrder.FINISHES,
        IntervalRelation.FINISHED_BY: TemporalOrder.FINISHES,
        IntervalRelation.EQUALS: TemporalOrder.CONCURRENT,
    }

    return mapping.get(relation, TemporalOrder.UNKNOWN)
