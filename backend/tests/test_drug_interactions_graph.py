"""Tests for Neo4j-enhanced drug interaction lookups."""

from app.services.drug_interactions import (
    DrugInteractionService,
    InteractionSeverity,
    InteractionType,
    DIRECT_INTERACTION_QUERY,
    PATHWAY_INTERACTION_QUERY,
    QT_PROLONGATION_QUERY,
)
from app.services.graph_database_service import QueryResult


class FakeGraphService:
    """Fake graph service to simulate Neo4j interaction lookups."""

    def __init__(self) -> None:
        self.read_calls: list[tuple[str, dict | None]] = []
        self.write_calls: list[tuple[str, dict | None]] = []

    @property
    def is_connected(self) -> bool:
        return True

    def execute_read(self, query: str, parameters: dict | None = None) -> QueryResult:
        self.read_calls.append((query, parameters))
        query_lower = query.lower()

        if "count(" in query_lower and "interacts_with" in query_lower:
            return QueryResult(
                records=[{"count": 1}],
                summary={},
                execution_time_ms=0,
                query=query,
                parameters=parameters,
            )

        # Direct drug interaction lookup
        if "d1:drug" in query_lower and "d2:drug" in query_lower:
            pair = {parameters.get("drug1"), parameters.get("drug2")} if parameters else set()
            if pair == {"metformin", "acetaminophen"}:
                return QueryResult(
                    records=[{
                        "rel_type": "INTERACTS_WITH",
                        "severity": "moderate",
                        "interaction_type": "pharmacodynamic",
                        "description": "Mock interaction",
                        "clinical_effect": "Mock effect",
                        "management": "Mock management",
                        "references": ["Mock ref"],
                    }],
                    summary={},
                    execution_time_ms=0,
                    query=query,
                    parameters=parameters,
                )

        # Pathway interaction lookup (CYP450)
        if "metabolized_by" in query_lower and "enzyme" in query_lower:
            pair = {parameters.get("drug1"), parameters.get("drug2")} if parameters else set()
            if pair == {"simvastatin", "ketoconazole"}:
                return QueryResult(
                    records=[{
                        "drug1": "simvastatin",
                        "drug2": "ketoconazole",
                        "enzyme": "CYP3A4",
                        "effect": "inhibitor",
                        "interaction_type": "pharmacokinetic",
                        "severity": "moderate",
                        "description": "CYP-mediated pathway interaction: ketoconazole inhibits metabolism of simvastatin via CYP3A4",
                    }],
                    summary={},
                    execution_time_ms=0,
                    query=query,
                    parameters=parameters,
                )
            return QueryResult(
                records=[],
                summary={},
                execution_time_ms=0,
                query=query,
                parameters=parameters,
            )

        # QT prolongation pair lookup
        if "has_effect" in query_lower and "qt_prolongation" in query_lower and "drug1" in (parameters or {}):
            pair = {parameters.get("drug1"), parameters.get("drug2")} if parameters else set()
            if pair == {"amiodarone", "sotalol"}:
                return QueryResult(
                    records=[{
                        "drug1": "amiodarone",
                        "drug2": "sotalol",
                        "drug1_qt_risk": "known",
                        "drug2_qt_risk": "known",
                        "combined_severity": "major",
                        "clinical_effect": "Both drugs prolong QT interval; additive risk of torsades de pointes",
                    }],
                    summary={},
                    execution_time_ms=0,
                    query=query,
                    parameters=parameters,
                )
            return QueryResult(
                records=[],
                summary={},
                execution_time_ms=0,
                query=query,
                parameters=parameters,
            )

        # QT drugs in list lookup
        if "has_effect" in query_lower and "drug_names" in (parameters or {}):
            drug_names = parameters.get("drug_names", []) if parameters else []
            records = []
            if "amiodarone" in drug_names:
                records.append({
                    "drug_name": "amiodarone",
                    "risk_level": "known",
                    "mechanism": "IKr blockade",
                })
            if "sotalol" in drug_names:
                records.append({
                    "drug_name": "sotalol",
                    "risk_level": "known",
                    "mechanism": "IKr blockade",
                })
            return QueryResult(
                records=records,
                summary={},
                execution_time_ms=0,
                query=query,
                parameters=parameters,
            )

        return QueryResult(
            records=[],
            summary={},
            execution_time_ms=0,
            query=query,
            parameters=parameters,
        )

    def execute_write(self, query: str, parameters: dict | None = None) -> QueryResult:
        self.write_calls.append((query, parameters))
        return QueryResult(
            records=[],
            summary={},
            execution_time_ms=0,
            query=query,
            parameters=parameters,
        )


def test_graph_interaction_fallback() -> None:
    """Test direct interaction lookup via Neo4j graph."""
    graph_service = FakeGraphService()
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=True,
        graph_service=graph_service,
    )

    interaction = service.check_pair("Metformin", "Tylenol")

    assert interaction is not None
    assert interaction.severity == InteractionSeverity.MODERATE
    assert interaction.description == "Mock interaction"


def test_pathway_interaction_query() -> None:
    """Test CYP450 pathway-based interaction inference."""
    graph_service = FakeGraphService()
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=True,
        graph_service=graph_service,
    )

    interactions = service.check_pathway_interactions("simvastatin", "ketoconazole")

    assert len(interactions) == 1
    assert interactions[0].drug1 == "simvastatin"
    assert interactions[0].drug2 == "ketoconazole"
    assert interactions[0].interaction_type == InteractionType.PHARMACOKINETIC
    assert "CYP3A4" in interactions[0].clinical_effect


def test_qt_prolongation_pair_query() -> None:
    """Test QT prolongation pair interaction check."""
    graph_service = FakeGraphService()
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=True,
        graph_service=graph_service,
    )

    interaction = service.check_qt_pair_interaction("amiodarone", "sotalol")

    assert interaction is not None
    assert interaction.severity == InteractionSeverity.MAJOR
    assert interaction.interaction_type == InteractionType.QT_PROLONGATION
    assert "torsades" in interaction.clinical_effect.lower()


def test_qt_drugs_in_list() -> None:
    """Test identification of QT-prolonging drugs in a medication list."""
    graph_service = FakeGraphService()
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=True,
        graph_service=graph_service,
    )

    qt_drugs = service.check_qt_prolongation_risk(["amiodarone", "metoprolol", "sotalol"])

    assert len(qt_drugs) == 2
    drug_names = [d["drug"] for d in qt_drugs]
    assert "amiodarone" in drug_names
    assert "sotalol" in drug_names
    assert all(d["risk_level"] == "known" for d in qt_drugs)


def test_check_interactions_enhanced() -> None:
    """Test enhanced interaction check combining multiple sources."""
    graph_service = FakeGraphService()
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=True,
        graph_service=graph_service,
    )

    # Include drugs with known curated interaction
    result = service.check_interactions_enhanced(
        ["warfarin", "aspirin", "lisinopril"],
        include_pathway=True,
        include_qt_check=True,
    )

    assert result.total_interactions > 0
    assert result.has_major is True  # warfarin + aspirin is MAJOR


def test_check_interactions_enhanced_without_graph() -> None:
    """Test enhanced check falls back to curated when graph unavailable."""
    service = DrugInteractionService(
        use_rxnorm=False,
        use_graph=False,
    )

    result = service.check_interactions_enhanced(
        ["warfarin", "aspirin"],
        include_pathway=True,
        include_qt_check=True,
    )

    # Should still find curated interaction
    assert result.total_interactions >= 1


def test_cypher_query_constants_defined() -> None:
    """Test that named Cypher query constants are properly defined."""
    assert "MATCH" in DIRECT_INTERACTION_QUERY
    assert "INTERACTS_WITH" in DIRECT_INTERACTION_QUERY

    assert "METABOLIZED_BY" in PATHWAY_INTERACTION_QUERY
    assert "CYP450" in PATHWAY_INTERACTION_QUERY

    assert "HAS_EFFECT" in QT_PROLONGATION_QUERY
    assert "qt_prolongation" in QT_PROLONGATION_QUERY
