"""Tests for Neo4j-enhanced drug interaction lookups."""

from app.services.drug_interactions import DrugInteractionService, InteractionSeverity
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
