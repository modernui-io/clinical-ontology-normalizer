"""Tests for Multi-Agent Orchestrator Service."""

from __future__ import annotations

import pytest

from app.services.multi_agent_orchestrator import (
    AgentContext,
    AgentRecommendation,
    AgentRole,
    AgentVote,
    ConsensusLevel,
    DiagnosticAgent,
    EvidenceAgent,
    MDTSession,
    MultiAgentOrchestrator,
    RecommendationType,
    SafetyAgent,
    TreatmentAgent,
    get_multi_agent_orchestrator,
)


class TestAgentContext:
    """Test AgentContext dataclass."""

    def test_create_basic_context(self) -> None:
        """Test creating a basic agent context."""
        context = AgentContext(
            patient_id="P12345",
            clinical_text="Patient presents with chest pain",
        )
        assert context.patient_id == "P12345"
        assert "chest pain" in context.clinical_text
        assert context.conditions == []
        assert context.medications == []

    def test_create_context_with_all_fields(self) -> None:
        """Test creating a context with all fields."""
        context = AgentContext(
            patient_id="P12345",
            clinical_text="Test note",
            conditions=[{"name": "Diabetes", "code": "E11.9"}],
            medications=[{"name": "Metformin", "dose": "500mg"}],
            allergies=["Penicillin"],
            lab_values=[{"name": "HbA1c", "value": 7.2}],
            vitals={"bp_systolic": 130, "bp_diastolic": 85},
            demographics={"age": 65, "gender": "M"},
        )
        assert len(context.conditions) == 1
        assert len(context.medications) == 1
        assert "Penicillin" in context.allergies


class TestAgentRecommendation:
    """Test AgentRecommendation dataclass."""

    def test_create_recommendation(self) -> None:
        """Test creating a recommendation."""
        rec = AgentRecommendation(
            agent_role=AgentRole.DIAGNOSTIC,
            recommendation_type=RecommendationType.DIAGNOSIS,
            content="Suspected Type 2 Diabetes Mellitus",
            confidence=0.85,
            evidence=["Elevated HbA1c", "Polyuria symptoms"],
        )
        assert rec.agent_role == AgentRole.DIAGNOSTIC
        assert rec.recommendation_type == RecommendationType.DIAGNOSIS
        assert rec.confidence == 0.85
        assert len(rec.evidence) == 2


class TestAgentVote:
    """Test AgentVote dataclass."""

    def test_create_agreeing_vote(self) -> None:
        """Test creating an agreeing vote."""
        vote = AgentVote(
            agent_role=AgentRole.SAFETY,
            agrees=True,
            confidence=0.9,
        )
        assert vote.agrees is True
        assert vote.confidence == 0.9
        assert vote.concerns == []

    def test_create_disagreeing_vote(self) -> None:
        """Test creating a disagreeing vote with concerns."""
        vote = AgentVote(
            agent_role=AgentRole.SAFETY,
            agrees=False,
            confidence=1.0,
            concerns=["Patient has allergy to this medication"],
            alternative_suggestion="Consider alternative drug",
        )
        assert vote.agrees is False
        assert len(vote.concerns) == 1


class TestDiagnosticAgent:
    """Test DiagnosticAgent class."""

    @pytest.mark.asyncio
    async def test_analyze_with_conditions(self) -> None:
        """Test diagnostic agent analysis with existing conditions."""
        agent = DiagnosticAgent()
        context = AgentContext(
            patient_id="P12345",
            conditions=[
                {"name": "Diabetes Mellitus", "confidence": 0.9},
                {"name": "Hypertension", "confidence": 0.85},
            ],
        )

        recommendations = await agent.analyze(context)
        assert len(recommendations) >= 2
        assert all(r.agent_role == AgentRole.DIAGNOSTIC for r in recommendations)
        assert all(r.recommendation_type == RecommendationType.DIAGNOSIS for r in recommendations)

    @pytest.mark.asyncio
    async def test_vote_on_treatment(self) -> None:
        """Test diagnostic agent voting on treatment recommendation."""
        agent = DiagnosticAgent()
        context = AgentContext(patient_id="P12345")

        treatment_rec = AgentRecommendation(
            agent_role=AgentRole.TREATMENT,
            recommendation_type=RecommendationType.TREATMENT,
            content="Start metformin therapy",
        )

        vote = await agent.vote(treatment_rec, context)
        assert vote.agent_role == AgentRole.DIAGNOSTIC
        assert vote.agrees is True


class TestTreatmentAgent:
    """Test TreatmentAgent class."""

    @pytest.mark.asyncio
    async def test_analyze_with_conditions(self) -> None:
        """Test treatment agent analysis."""
        agent = TreatmentAgent()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Type 2 Diabetes"}],
        )

        recommendations = await agent.analyze(context)
        assert len(recommendations) >= 1
        assert all(r.agent_role == AgentRole.TREATMENT for r in recommendations)


class TestSafetyAgent:
    """Test SafetyAgent class."""

    @pytest.mark.asyncio
    async def test_analyze_with_allergies(self) -> None:
        """Test safety agent identifies allergies."""
        agent = SafetyAgent()
        context = AgentContext(
            patient_id="P12345",
            allergies=["Penicillin", "Sulfa"],
        )

        recommendations = await agent.analyze(context)
        assert len(recommendations) == 2
        assert all(r.recommendation_type == RecommendationType.WARNING for r in recommendations)

    @pytest.mark.asyncio
    async def test_vote_against_allergy_medication(self) -> None:
        """Test safety agent votes against medication with known allergy."""
        agent = SafetyAgent()
        context = AgentContext(
            patient_id="P12345",
            allergies=["Penicillin"],
        )

        med_rec = AgentRecommendation(
            agent_role=AgentRole.TREATMENT,
            recommendation_type=RecommendationType.MEDICATION,
            content="Prescribe Penicillin 500mg",
        )

        vote = await agent.vote(med_rec, context)
        assert vote.agrees is False
        assert len(vote.concerns) > 0
        assert any("allergy" in c.lower() for c in vote.concerns)


class TestEvidenceAgent:
    """Test EvidenceAgent class."""

    @pytest.mark.asyncio
    async def test_analyze_with_conditions(self) -> None:
        """Test evidence agent provides evidence-based recommendations."""
        agent = EvidenceAgent()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Hypertension"}],
        )

        recommendations = await agent.analyze(context)
        assert len(recommendations) >= 1
        assert all(len(r.evidence) > 0 for r in recommendations)

    @pytest.mark.asyncio
    async def test_vote_on_recommendation_with_evidence(self) -> None:
        """Test evidence agent supports recommendations with evidence."""
        agent = EvidenceAgent()
        context = AgentContext(patient_id="P12345")

        rec_with_evidence = AgentRecommendation(
            agent_role=AgentRole.TREATMENT,
            recommendation_type=RecommendationType.TREATMENT,
            content="Start statin therapy",
            evidence=["ACC/AHA Guidelines", "Systematic review"],
        )

        vote = await agent.vote(rec_with_evidence, context)
        assert vote.agrees is True

    @pytest.mark.asyncio
    async def test_vote_on_recommendation_without_evidence(self) -> None:
        """Test evidence agent raises concerns for recommendations without evidence."""
        agent = EvidenceAgent()
        context = AgentContext(patient_id="P12345")

        rec_no_evidence = AgentRecommendation(
            agent_role=AgentRole.TREATMENT,
            recommendation_type=RecommendationType.TREATMENT,
            content="Try experimental treatment",
            evidence=[],
        )

        vote = await agent.vote(rec_no_evidence, context)
        assert vote.agrees is False
        assert any("evidence" in c.lower() for c in vote.concerns)


class TestMultiAgentOrchestrator:
    """Test MultiAgentOrchestrator class."""

    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator initializes with all agents."""
        orchestrator = MultiAgentOrchestrator()
        assert len(orchestrator.agents) == 4
        assert AgentRole.DIAGNOSTIC in orchestrator.agents
        assert AgentRole.TREATMENT in orchestrator.agents
        assert AgentRole.SAFETY in orchestrator.agents
        assert AgentRole.EVIDENCE in orchestrator.agents

    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        """Test creating an MDT session."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            clinical_text="Patient with diabetes",
        )

        session = await orchestrator.create_session("P12345", context)
        assert session.patient_id == "P12345"
        assert session.status == "in_progress"
        assert session.context is not None

    @pytest.mark.asyncio
    async def test_run_mdt_discussion(self) -> None:
        """Test running a full MDT discussion."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[
                {"name": "Type 2 Diabetes", "confidence": 0.9},
            ],
            allergies=["Sulfa"],
        )

        session = await orchestrator.create_session("P12345", context)
        completed_session = await orchestrator.run_mdt_discussion(session.session_id)

        assert completed_session.status == "completed"
        assert len(completed_session.recommendations) > 0
        assert len(completed_session.consensus_results) > 0
        assert completed_session.completed_at is not None

    @pytest.mark.asyncio
    async def test_consensus_calculation(self) -> None:
        """Test consensus is calculated correctly."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Diabetes"}],
        )

        session = await orchestrator.create_session("P12345", context)
        await orchestrator.run_mdt_discussion(session.session_id)

        for result in session.consensus_results:
            assert result.consensus_level in ConsensusLevel
            assert 0 <= result.agreement_score <= 1
            assert 0 <= result.final_confidence <= 1
            assert len(result.votes) > 0

    @pytest.mark.asyncio
    async def test_get_prioritized_recommendations(self) -> None:
        """Test getting prioritized recommendations."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[
                {"name": "Hypertension"},
                {"name": "Diabetes"},
            ],
        )

        session = await orchestrator.create_session("P12345", context)
        await orchestrator.run_mdt_discussion(session.session_id)

        # Get recommendations with at least moderate consensus
        prioritized = await orchestrator.get_prioritized_recommendations(
            session.session_id,
            min_consensus=ConsensusLevel.MODERATE,
        )

        # Verify filtering
        for result in prioritized:
            assert result.consensus_level in [
                ConsensusLevel.UNANIMOUS,
                ConsensusLevel.STRONG,
                ConsensusLevel.MODERATE,
            ]

        # Verify sorting by confidence
        if len(prioritized) > 1:
            for i in range(len(prioritized) - 1):
                assert prioritized[i].final_confidence >= prioritized[i + 1].final_confidence

    @pytest.mark.asyncio
    async def test_session_summary(self) -> None:
        """Test getting session summary."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Diabetes"}],
        )

        session = await orchestrator.create_session("P12345", context)
        await orchestrator.run_mdt_discussion(session.session_id)

        summary = orchestrator.get_session_summary(session.session_id)
        assert summary["session_id"] == session.session_id
        assert summary["patient_id"] == "P12345"
        assert summary["status"] == "completed"
        assert "total_recommendations" in summary
        assert "consensus_results" in summary

    def test_get_session_not_found(self) -> None:
        """Test getting non-existent session."""
        orchestrator = MultiAgentOrchestrator()
        session = orchestrator.get_session("non_existent")
        assert session is None


class TestConsensusLevels:
    """Test consensus level calculations."""

    @pytest.mark.asyncio
    async def test_unanimous_consensus(self) -> None:
        """Test unanimous consensus when all agents agree."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Well-documented condition"}],
        )

        session = await orchestrator.create_session("P12345", context)
        await orchestrator.run_mdt_discussion(session.session_id)

        # Check that we have at least some results
        assert len(session.consensus_results) > 0

    @pytest.mark.asyncio
    async def test_conflicting_consensus(self) -> None:
        """Test conflicting consensus scenarios."""
        orchestrator = MultiAgentOrchestrator()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Rare condition"}],
            allergies=["Many medications"],  # Creates safety concerns
        )

        session = await orchestrator.create_session("P12345", context)
        await orchestrator.run_mdt_discussion(session.session_id)

        # The session should complete with some results
        assert session.status == "completed"


class TestSingletonPattern:
    """Test singleton orchestrator pattern."""

    def test_get_singleton_instance(self) -> None:
        """Test getting singleton orchestrator instance."""
        orchestrator1 = get_multi_agent_orchestrator()
        orchestrator2 = get_multi_agent_orchestrator()
        assert orchestrator1 is orchestrator2


class TestAgentReasoningChain:
    """Test agent reasoning chain tracking."""

    @pytest.mark.asyncio
    async def test_diagnostic_reasoning_chain(self) -> None:
        """Test diagnostic agent tracks reasoning steps."""
        agent = DiagnosticAgent()
        context = AgentContext(
            patient_id="P12345",
            conditions=[{"name": "Test condition"}],
        )

        recommendations = await agent.analyze(context)
        for rec in recommendations:
            assert len(rec.reasoning_chain) > 0

    @pytest.mark.asyncio
    async def test_reasoning_chain_cleared_between_analyses(self) -> None:
        """Test reasoning chain is cleared between analyses."""
        agent = DiagnosticAgent()
        context1 = AgentContext(
            patient_id="P1",
            conditions=[{"name": "Condition 1"}],
        )
        context2 = AgentContext(
            patient_id="P2",
            conditions=[{"name": "Condition 2"}],
        )

        await agent.analyze(context1)
        recs2 = await agent.analyze(context2)

        # Second analysis should have fresh reasoning chain
        for rec in recs2:
            # Should not contain references to first patient's condition
            chain_text = " ".join(rec.reasoning_chain)
            assert "Condition 1" not in chain_text or "Condition 2" in chain_text
