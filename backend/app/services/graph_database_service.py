"""Neo4j Knowledge Graph Database Service.

Provides connection management and query execution for the Neo4j
graph database used to store clinical ontology relationships.

Features:
- Connection pool management with neo4j-driver
- Cypher query execution helpers
- Transaction management
- Health check and connection testing
- Graceful fallback with mock data when Neo4j is unavailable
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionStatus(str, Enum):
    """Neo4j connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    MOCK_MODE = "mock_mode"


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: int = 60
    connection_timeout: int = 30
    encrypted: bool = False


@dataclass
class QueryResult:
    """Result of a Cypher query execution."""

    records: list[dict[str, Any]]
    summary: dict[str, Any]
    execution_time_ms: float
    query: str
    parameters: dict[str, Any] | None = None


@dataclass
class HealthCheckResult:
    """Result of Neo4j health check."""

    status: ConnectionStatus
    latency_ms: float | None = None
    server_version: str | None = None
    database: str | None = None
    error_message: str | None = None
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# Singleton instance
_graph_database_service: "GraphDatabaseService | None" = None
_service_lock = Lock()


class GraphDatabaseService:
    """Service for Neo4j graph database operations.

    Provides connection pooling, query execution, and transaction
    management for the clinical ontology knowledge graph.

    This service gracefully handles Neo4j being unavailable by
    providing mock data for demo purposes.
    """

    def __init__(self, config: Neo4jConfig | None = None) -> None:
        """Initialize the graph database service.

        Args:
            config: Neo4j configuration. If None, loads from environment.
        """
        self._config = config or self._load_config_from_env()
        self._driver: Any = None  # neo4j.Driver when connected
        self._connected = False
        self._mock_mode = False
        self._lock = Lock()
        self._query_count = 0
        self._total_query_time_ms = 0.0
        self._last_health_check: HealthCheckResult | None = None

        # Try to establish connection
        self._initialize_driver()

    def _load_config_from_env(self) -> Neo4jConfig:
        """Load configuration from environment variables."""
        import os

        return Neo4jConfig(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )

    def _initialize_driver(self) -> None:
        """Initialize the Neo4j driver with connection pooling."""
        try:
            # Try to import neo4j driver
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                self._config.uri,
                auth=(self._config.user, self._config.password),
                max_connection_lifetime=self._config.max_connection_lifetime,
                max_connection_pool_size=self._config.max_connection_pool_size,
                connection_acquisition_timeout=self._config.connection_acquisition_timeout,
                connection_timeout=self._config.connection_timeout,
                encrypted=self._config.encrypted,
            )

            # Test connection
            with self._driver.session(database=self._config.database) as session:
                result = session.run("RETURN 1 AS test")
                result.single()

            self._connected = True
            self._mock_mode = False
            logger.info(f"Connected to Neo4j at {self._config.uri}")

        except ImportError:
            logger.warning("neo4j-driver not installed, running in mock mode")
            self._mock_mode = True
            self._connected = False

        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j: {e}, running in mock mode")
            self._mock_mode = True
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._connected and not self._mock_mode

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return self._mock_mode

    def health_check(self) -> HealthCheckResult:
        """Perform a health check on the Neo4j connection.

        Returns:
            HealthCheckResult with connection status and details.
        """
        if self._mock_mode:
            result = HealthCheckResult(
                status=ConnectionStatus.MOCK_MODE,
                error_message="Running in mock mode - Neo4j not available",
            )
            self._last_health_check = result
            return result

        if not self._driver:
            result = HealthCheckResult(
                status=ConnectionStatus.DISCONNECTED,
                error_message="Driver not initialized",
            )
            self._last_health_check = result
            return result

        start_time = time.perf_counter()
        try:
            with self._driver.session(database=self._config.database) as session:
                result = session.run("CALL dbms.components() YIELD name, versions RETURN name, versions[0] AS version")
                record = result.single()

                latency = (time.perf_counter() - start_time) * 1000

                health_result = HealthCheckResult(
                    status=ConnectionStatus.CONNECTED,
                    latency_ms=round(latency, 2),
                    server_version=record["version"] if record else None,
                    database=self._config.database,
                )
                self._last_health_check = health_result
                return health_result

        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            result = HealthCheckResult(
                status=ConnectionStatus.ERROR,
                latency_ms=round(latency, 2),
                error_message=str(e),
            )
            self._last_health_check = result
            return result

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        write: bool = False,
    ) -> QueryResult:
        """Execute a Cypher query.

        Args:
            query: The Cypher query to execute.
            parameters: Optional query parameters.
            write: If True, executes as a write transaction.

        Returns:
            QueryResult with records and execution details.
        """
        start_time = time.perf_counter()

        if self._mock_mode:
            # Return mock data based on query patterns
            mock_records = self._generate_mock_response(query, parameters)
            execution_time = (time.perf_counter() - start_time) * 1000

            return QueryResult(
                records=mock_records,
                summary={"mock": True},
                execution_time_ms=round(execution_time, 2),
                query=query,
                parameters=parameters,
            )

        if not self._driver:
            raise ConnectionError("Neo4j driver not initialized")

        try:
            with self._driver.session(database=self._config.database) as session:
                if write:
                    result = session.execute_write(
                        lambda tx: list(tx.run(query, parameters or {}))
                    )
                else:
                    result = session.execute_read(
                        lambda tx: list(tx.run(query, parameters or {}))
                    )

                execution_time = (time.perf_counter() - start_time) * 1000

                # Convert records to dicts
                records = [dict(record) for record in result]

                with self._lock:
                    self._query_count += 1
                    self._total_query_time_ms += execution_time

                return QueryResult(
                    records=records,
                    summary={"counters": {}},
                    execution_time_ms=round(execution_time, 2),
                    query=query,
                    parameters=parameters,
                )

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a write query.

        Args:
            query: The Cypher query to execute.
            parameters: Optional query parameters.

        Returns:
            QueryResult with execution details.
        """
        return self.execute_query(query, parameters, write=True)

    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a read query.

        Args:
            query: The Cypher query to execute.
            parameters: Optional query parameters.

        Returns:
            QueryResult with records.
        """
        return self.execute_query(query, parameters, write=False)

    def run_transaction(
        self,
        queries: list[tuple[str, dict[str, Any] | None]],
    ) -> list[QueryResult]:
        """Execute multiple queries in a single transaction.

        Args:
            queries: List of (query, parameters) tuples.

        Returns:
            List of QueryResult for each query.
        """
        if self._mock_mode:
            return [
                self.execute_query(query, params)
                for query, params in queries
            ]

        if not self._driver:
            raise ConnectionError("Neo4j driver not initialized")

        results = []
        start_time = time.perf_counter()

        try:
            with self._driver.session(database=self._config.database) as session:
                def run_all(tx: Any) -> list[list[Any]]:
                    return [
                        list(tx.run(query, params or {}))
                        for query, params in queries
                    ]

                tx_results = session.execute_write(run_all)

                for i, (query, params) in enumerate(queries):
                    records = [dict(r) for r in tx_results[i]]
                    results.append(QueryResult(
                        records=records,
                        summary={"transaction": True},
                        execution_time_ms=0,  # Set total at end
                        query=query,
                        parameters=params,
                    ))

                total_time = (time.perf_counter() - start_time) * 1000
                for r in results:
                    r.execution_time_ms = round(total_time / len(results), 2)

                return results

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise

    def _generate_mock_response(
        self,
        query: str,
        parameters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Generate mock response data based on query patterns.

        Args:
            query: The Cypher query.
            parameters: Query parameters.

        Returns:
            List of mock records.
        """
        query_lower = query.lower()

        # Health check query
        if "dbms.components" in query_lower:
            return [{"name": "Neo4j Kernel", "version": "5.x (mock)"}]

        # Concept neighbors query
        if "neighbors" in query_lower or ("match" in query_lower and "relationship" in query_lower):
            return self._mock_concept_neighbors(parameters)

        # Concept ancestors query
        if "ancestor" in query_lower or "is_a" in query_lower:
            return self._mock_concept_ancestors(parameters)

        # Path finding query
        if "shortestpath" in query_lower or "path" in query_lower:
            return self._mock_concept_path(parameters)

        # Patient similarity query
        if "patient" in query_lower and "similar" in query_lower:
            return self._mock_similar_patients(parameters)

        # Generic concept query
        if "concept" in query_lower:
            return self._mock_concepts(parameters)

        # Default empty response
        return []

    def _mock_concept_neighbors(
        self, parameters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate mock concept neighbors."""
        concept_id = parameters.get("concept_id", 0) if parameters else 0

        return [
            {
                "concept": {
                    "concept_id": 201826,
                    "concept_name": "Type 2 diabetes mellitus",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "relationship": "Has associated finding",
                "direction": "outgoing",
            },
            {
                "concept": {
                    "concept_id": 4329847,
                    "concept_name": "Diabetic retinopathy",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "relationship": "Has complication",
                "direction": "outgoing",
            },
            {
                "concept": {
                    "concept_id": 1503297,
                    "concept_name": "Metformin",
                    "vocabulary_id": "RxNorm",
                    "domain_id": "Drug",
                },
                "relationship": "Treated by",
                "direction": "outgoing",
            },
            {
                "concept": {
                    "concept_id": 4058243,
                    "concept_name": "Hemoglobin A1c measurement",
                    "vocabulary_id": "LOINC",
                    "domain_id": "Measurement",
                },
                "relationship": "Measured by",
                "direction": "outgoing",
            },
        ]

    def _mock_concept_ancestors(
        self, parameters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate mock concept ancestors."""
        return [
            {
                "ancestor": {
                    "concept_id": 4154314,
                    "concept_name": "Diabetes mellitus",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "distance": 1,
            },
            {
                "ancestor": {
                    "concept_id": 4027384,
                    "concept_name": "Disorder of glucose metabolism",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "distance": 2,
            },
            {
                "ancestor": {
                    "concept_id": 4266367,
                    "concept_name": "Metabolic disease",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "distance": 3,
            },
            {
                "ancestor": {
                    "concept_id": 4028741,
                    "concept_name": "Disorder of endocrine system",
                    "vocabulary_id": "SNOMED",
                    "domain_id": "Condition",
                },
                "distance": 4,
            },
        ]

    def _mock_concept_path(
        self, parameters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate mock concept path."""
        return [
            {
                "path": [
                    {"concept_id": 201826, "concept_name": "Type 2 diabetes mellitus"},
                    {"concept_id": 4329847, "concept_name": "Diabetic retinopathy"},
                    {"concept_id": 4326594, "concept_name": "Retinal disorder"},
                ],
                "relationships": ["Has complication", "Is a"],
                "length": 2,
            }
        ]

    def _mock_similar_patients(
        self, parameters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate mock similar patients."""
        return [
            {
                "patient_id": "P001",
                "similarity_score": 0.92,
                "shared_conditions": ["Type 2 diabetes mellitus", "Hypertension"],
                "shared_medications": ["Metformin", "Lisinopril"],
                "shared_procedures": ["HbA1c test"],
            },
            {
                "patient_id": "P002",
                "similarity_score": 0.85,
                "shared_conditions": ["Type 2 diabetes mellitus", "Hyperlipidemia"],
                "shared_medications": ["Metformin", "Atorvastatin"],
                "shared_procedures": ["Lipid panel"],
            },
            {
                "patient_id": "P003",
                "similarity_score": 0.78,
                "shared_conditions": ["Type 2 diabetes mellitus"],
                "shared_medications": ["Metformin", "Sitagliptin"],
                "shared_procedures": ["Eye exam"],
            },
        ]

    def _mock_concepts(
        self, parameters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate mock concepts."""
        return [
            {
                "concept_id": 201826,
                "concept_name": "Type 2 diabetes mellitus",
                "vocabulary_id": "SNOMED",
                "domain_id": "Condition",
                "concept_class_id": "Clinical Finding",
            },
            {
                "concept_id": 1503297,
                "concept_name": "Metformin",
                "vocabulary_id": "RxNorm",
                "domain_id": "Drug",
                "concept_class_id": "Ingredient",
            },
            {
                "concept_id": 4058243,
                "concept_name": "Hemoglobin A1c measurement",
                "vocabulary_id": "LOINC",
                "domain_id": "Measurement",
                "concept_class_id": "Lab Test",
            },
        ]

    def close(self) -> None:
        """Close the database connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Neo4j connection closed")

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats.
        """
        return {
            "connected": self._connected,
            "mock_mode": self._mock_mode,
            "uri": self._config.uri if not self._mock_mode else "N/A",
            "database": self._config.database,
            "total_queries": self._query_count,
            "avg_query_time_ms": (
                round(self._total_query_time_ms / self._query_count, 2)
                if self._query_count > 0
                else 0
            ),
            "last_health_check": (
                self._last_health_check.status.value
                if self._last_health_check
                else "never"
            ),
        }


def get_graph_database_service() -> GraphDatabaseService:
    """Get the singleton GraphDatabaseService instance.

    Returns:
        The GraphDatabaseService singleton.
    """
    global _graph_database_service

    if _graph_database_service is None:
        with _service_lock:
            if _graph_database_service is None:
                _graph_database_service = GraphDatabaseService()

    return _graph_database_service


def reset_graph_database_service() -> None:
    """Reset the singleton for testing."""
    global _graph_database_service

    with _service_lock:
        if _graph_database_service is not None:
            _graph_database_service.close()
            _graph_database_service = None
