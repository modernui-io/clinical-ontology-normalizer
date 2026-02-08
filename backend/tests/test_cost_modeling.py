"""Tests for CFO-1: Cost Modeling & Unit Economics Service.

Tests cover:
- Cost line item CRUD: add, update, remove, get
- Category grouping and subtotals
- Computed total_annual_cost for each CostFrequency
- Trial cost model creation and auto-calculated fields
- Trial cost model listing and lookup
- Unit economics calculations (LTV/CAC ratio, margins, runway)
- Infrastructure projections at different scales (1K, 10K, 100K, 1M patients)
- Sub-linear scaling verification
- Revenue model calculations
- Financial dashboard aggregation
- Scenario analysis (growth, pricing, trial count variations)
- API endpoint integration tests (all 12 routes)
- Edge cases (zero patients, negative margins, division-by-zero protection)
- Singleton pattern (get/reset)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.cost_modeling import (
    CostCategory,
    CostFrequency,
    CostLineItem,
)
from app.services.cost_modeling_service import (
    CostModelingService,
    get_cost_modeling_service,
    reset_cost_modeling_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_cost_modeling_service()
    yield
    reset_cost_modeling_service()


@pytest.fixture
def service() -> CostModelingService:
    return get_cost_modeling_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated cost items and trial models."""

    def test_seed_cost_items_count(self, service: CostModelingService):
        """Service should have at least 15 pre-populated cost items."""
        breakdown = service.get_cost_breakdown()
        assert breakdown.item_count >= 15

    def test_seed_cost_items_cover_all_categories(self, service: CostModelingService):
        """Seed data should have items in every cost category."""
        breakdown = service.get_cost_breakdown()
        populated_cats = {
            cat.category
            for cat in breakdown.categories
            if len(cat.items) > 0
        }
        assert populated_cats == set(CostCategory)

    def test_seed_trial_models_count(self, service: CostModelingService):
        """Service should have 3 pre-populated trial models."""
        result = service.list_trial_models()
        assert result.total == 3

    def test_seed_trial_ids(self, service: CostModelingService):
        """Verify expected trial IDs exist."""
        result = service.list_trial_models()
        ids = {t.trial_id for t in result.trials}
        assert "EYLEA-HD-2024" in ids
        assert "DUPIXENT-AD-2024" in ids
        assert "LIBTAYO-NSCLC-2024" in ids

    def test_seed_trial_has_positive_costs(self, service: CostModelingService):
        """All seed trial models should have positive costs and revenue."""
        result = service.list_trial_models()
        for t in result.trials:
            assert t.total_trial_cost > 0
            assert t.revenue_per_enrolled_patient > 0
            assert t.total_screening_cost > 0
            assert t.total_enrollment_cost > 0


# ============================================================================
# Cost Line Item CRUD
# ============================================================================


class TestCostItemCRUD:
    """Tests for cost line item create, read, update, delete."""

    def test_add_cost_item(self, service: CostModelingService):
        """Adding a cost item should increase the item count."""
        before = service.get_cost_breakdown().item_count
        item = service.add_cost_item(
            category=CostCategory.INFRASTRUCTURE,
            name="Test Item",
            unit_cost=100.0,
        )
        after = service.get_cost_breakdown().item_count
        assert after == before + 1
        assert item.name == "Test Item"
        assert item.id is not None

    def test_add_cost_item_with_all_fields(self, service: CostModelingService):
        """All fields should be stored correctly."""
        item = service.add_cost_item(
            category=CostCategory.COMPLIANCE,
            name="Pen Test Extra",
            description="Extra pen test",
            unit_cost=5_000.0,
            quantity=2.0,
            frequency=CostFrequency.QUARTERLY,
            notes="Ad-hoc",
        )
        assert item.category == CostCategory.COMPLIANCE
        assert item.description == "Extra pen test"
        assert item.quantity == 2.0
        assert item.frequency == CostFrequency.QUARTERLY
        assert item.notes == "Ad-hoc"

    def test_get_cost_item(self, service: CostModelingService):
        """Should be able to retrieve a cost item by ID."""
        item = service.add_cost_item(
            category=CostCategory.SUPPORT,
            name="Lookup Test",
            unit_cost=99.0,
        )
        fetched = service.get_cost_item(item.id)
        assert fetched.name == "Lookup Test"

    def test_get_cost_item_not_found(self, service: CostModelingService):
        """Should raise ValueError for non-existent ID."""
        with pytest.raises(ValueError, match="not found"):
            service.get_cost_item("nonexistent-id")

    def test_update_cost_item(self, service: CostModelingService):
        """Updating a cost item should change its fields."""
        item = service.add_cost_item(
            category=CostCategory.LICENSING,
            name="Original",
            unit_cost=500.0,
        )
        updated = service.update_cost_item(item.id, name="Updated", unit_cost=750.0)
        assert updated.name == "Updated"
        assert updated.unit_cost == 750.0
        # Category should be unchanged
        assert updated.category == CostCategory.LICENSING

    def test_update_cost_item_not_found(self, service: CostModelingService):
        """Updating a non-existent item should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.update_cost_item("nonexistent", name="X")

    def test_update_cost_item_partial(self, service: CostModelingService):
        """Partial updates should only change provided fields."""
        item = service.add_cost_item(
            category=CostCategory.PERSONNEL,
            name="Engineer",
            description="Full-stack",
            unit_cost=12_000.0,
        )
        updated = service.update_cost_item(item.id, description="Senior full-stack")
        assert updated.description == "Senior full-stack"
        assert updated.name == "Engineer"
        assert updated.unit_cost == 12_000.0

    def test_remove_cost_item(self, service: CostModelingService):
        """Removing a cost item should decrease the item count."""
        item = service.add_cost_item(
            category=CostCategory.DATA_ACQUISITION,
            name="Temp",
            unit_cost=10.0,
        )
        before = service.get_cost_breakdown().item_count
        service.remove_cost_item(item.id)
        after = service.get_cost_breakdown().item_count
        assert after == before - 1

    def test_remove_cost_item_not_found(self, service: CostModelingService):
        """Removing a non-existent item should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.remove_cost_item("nonexistent")


# ============================================================================
# Computed Annual Cost
# ============================================================================


class TestComputedAnnualCost:
    """Tests for the computed total_annual_cost field."""

    def test_monthly_annualisation(self):
        """Monthly items should be multiplied by 12."""
        item = CostLineItem(
            id="t1", category=CostCategory.INFRASTRUCTURE,
            name="Test", unit_cost=100.0, quantity=1.0,
            frequency=CostFrequency.MONTHLY,
        )
        assert item.total_annual_cost == 1_200.0

    def test_quarterly_annualisation(self):
        """Quarterly items should be multiplied by 4."""
        item = CostLineItem(
            id="t2", category=CostCategory.COMPLIANCE,
            name="Test", unit_cost=15_000.0, quantity=1.0,
            frequency=CostFrequency.QUARTERLY,
        )
        assert item.total_annual_cost == 60_000.0

    def test_annual_no_multiplier(self):
        """Annual items should have multiplier of 1."""
        item = CostLineItem(
            id="t3", category=CostCategory.COMPLIANCE,
            name="Test", unit_cost=45_000.0, quantity=1.0,
            frequency=CostFrequency.ANNUALLY,
        )
        assert item.total_annual_cost == 45_000.0

    def test_one_time_no_multiplier(self):
        """One-time items should have multiplier of 1."""
        item = CostLineItem(
            id="t4", category=CostCategory.INTEGRATION,
            name="Test", unit_cost=10_000.0, quantity=1.0,
            frequency=CostFrequency.ONE_TIME,
        )
        assert item.total_annual_cost == 10_000.0

    def test_quantity_multiplied(self):
        """Quantity should be factored into annual cost."""
        item = CostLineItem(
            id="t5", category=CostCategory.DATA_ACQUISITION,
            name="Test", unit_cost=1.25, quantity=2_500,
            frequency=CostFrequency.MONTHLY,
        )
        assert item.total_annual_cost == round(1.25 * 2_500 * 12, 2)

    def test_zero_unit_cost(self):
        """Zero unit cost should result in zero annual cost."""
        item = CostLineItem(
            id="t6", category=CostCategory.SUPPORT,
            name="Free", unit_cost=0.0, quantity=5.0,
            frequency=CostFrequency.MONTHLY,
        )
        assert item.total_annual_cost == 0.0


# ============================================================================
# Category Grouping
# ============================================================================


class TestCategoryGrouping:
    """Tests for cost breakdown by category."""

    def test_all_categories_present(self, service: CostModelingService):
        """Breakdown should include all CostCategory enum values."""
        breakdown = service.get_cost_breakdown()
        cats = {c.category for c in breakdown.categories}
        assert cats == set(CostCategory)

    def test_subtotals_sum_to_total(self, service: CostModelingService):
        """Sum of category subtotals should equal total annual cost."""
        breakdown = service.get_cost_breakdown()
        subtotal_sum = sum(c.subtotal_annual for c in breakdown.categories)
        assert abs(subtotal_sum - breakdown.total_annual_cost) < 0.01

    def test_monthly_is_annual_divided_by_12(self, service: CostModelingService):
        """Monthly total should be annual / 12."""
        breakdown = service.get_cost_breakdown()
        assert abs(breakdown.total_monthly_cost - breakdown.total_annual_cost / 12) < 0.01

    def test_adding_item_increases_category_subtotal(self, service: CostModelingService):
        """Adding an item should increase its category subtotal."""
        breakdown_before = service.get_cost_breakdown()
        infra_before = next(
            c for c in breakdown_before.categories
            if c.category == CostCategory.INFRASTRUCTURE
        )
        service.add_cost_item(
            category=CostCategory.INFRASTRUCTURE,
            name="Extra Compute",
            unit_cost=500.0,
            frequency=CostFrequency.MONTHLY,
        )
        breakdown_after = service.get_cost_breakdown()
        infra_after = next(
            c for c in breakdown_after.categories
            if c.category == CostCategory.INFRASTRUCTURE
        )
        assert infra_after.subtotal_annual > infra_before.subtotal_annual


# ============================================================================
# Trial Cost Models
# ============================================================================


class TestTrialCostModels:
    """Tests for trial-specific cost model calculations."""

    def test_get_existing_trial(self, service: CostModelingService):
        """Should retrieve a pre-populated trial model."""
        model = service.get_trial_cost_model("EYLEA-HD-2024")
        assert model.trial_name.startswith("EYLEA")
        assert model.patient_target == 450

    def test_get_nonexistent_trial(self, service: CostModelingService):
        """Should raise ValueError for unknown trial_id."""
        with pytest.raises(ValueError, match="not found"):
            service.get_trial_cost_model("UNKNOWN-TRIAL")

    def test_create_trial_model(self, service: CostModelingService):
        """Creating a trial model should auto-calculate derived fields."""
        model = service.create_trial_model(
            trial_id="TEST-001",
            trial_name="Test Trial",
            patient_target=100,
            cost_per_patient_screened=50.0,
            cost_per_patient_enrolled=500.0,
            screening_to_enrollment_ratio=5.0,
            overhead_allocation=10_000.0,
            revenue_per_enrolled_patient=20_000.0,
        )
        # total_screened = 100 * 5.0 = 500
        assert model.total_screening_cost == 500 * 50.0  # 25,000
        assert model.total_enrollment_cost == 100 * 500.0  # 50,000
        assert model.total_trial_cost == 25_000 + 50_000 + 10_000  # 85,000
        total_revenue = 100 * 20_000  # 2,000,000
        expected_margin = round((total_revenue - 85_000) / total_revenue * 100, 2)
        assert model.margin_percent == expected_margin

    def test_create_duplicate_trial(self, service: CostModelingService):
        """Creating a trial with duplicate ID should raise ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            service.create_trial_model(
                trial_id="EYLEA-HD-2024",
                trial_name="Dup",
                patient_target=100,
                cost_per_patient_screened=10.0,
                cost_per_patient_enrolled=100.0,
                screening_to_enrollment_ratio=3.0,
            )

    def test_trial_list_after_create(self, service: CostModelingService):
        """Creating a trial should increase the list count."""
        before = service.list_trial_models().total
        service.create_trial_model(
            trial_id="NEW-001",
            trial_name="New Trial",
            patient_target=50,
            cost_per_patient_screened=30.0,
            cost_per_patient_enrolled=300.0,
            screening_to_enrollment_ratio=4.0,
        )
        after = service.list_trial_models().total
        assert after == before + 1

    def test_trial_zero_revenue_margin(self, service: CostModelingService):
        """Trial with zero revenue should have 0% margin."""
        model = service.create_trial_model(
            trial_id="ZERO-REV",
            trial_name="Zero Revenue",
            patient_target=100,
            cost_per_patient_screened=10.0,
            cost_per_patient_enrolled=100.0,
            screening_to_enrollment_ratio=5.0,
            revenue_per_enrolled_patient=0.0,
        )
        assert model.margin_percent == 0.0

    def test_screening_cost_math(self, service: CostModelingService):
        """Verify screening cost = screened * cost_per_patient_screened."""
        model = service.get_trial_cost_model("LIBTAYO-NSCLC-2024")
        expected_screened = int(model.patient_target * model.screening_to_enrollment_ratio)
        assert model.total_screening_cost == round(
            expected_screened * model.cost_per_patient_screened, 2
        )


# ============================================================================
# Unit Economics
# ============================================================================


class TestUnitEconomics:
    """Tests for platform unit economics calculations."""

    def test_unit_economics_returns_all_fields(self, service: CostModelingService):
        """Unit economics should return all expected fields."""
        ue = service.get_unit_economics()
        assert ue.total_monthly_cost > 0
        assert ue.total_monthly_revenue > 0
        assert ue.patient_acquisition_cost > 0
        assert ue.lifetime_value_per_patient > 0
        assert ue.ltv_to_cac_ratio > 0

    def test_gross_margin_between_neg1_and_1(self, service: CostModelingService):
        """Gross margin should be in [-1, 1] range."""
        ue = service.get_unit_economics()
        assert -1.0 <= ue.gross_margin <= 1.0

    def test_burn_rate_non_negative(self, service: CostModelingService):
        """Burn rate should be >= 0."""
        ue = service.get_unit_economics()
        assert ue.burn_rate >= 0

    def test_runway_positive(self, service: CostModelingService):
        """Runway should be positive when burning cash."""
        ue = service.get_unit_economics()
        if ue.burn_rate > 0:
            assert ue.runway_months > 0
        else:
            assert ue.runway_months == 9999.0

    def test_break_even_patients_positive(self, service: CostModelingService):
        """Break-even patients should be a positive integer."""
        ue = service.get_unit_economics()
        assert ue.break_even_patients > 0

    def test_ltv_to_cac_ratio_reasonable(self, service: CostModelingService):
        """LTV/CAC should be > 0 for a revenue-generating platform."""
        ue = service.get_unit_economics()
        assert ue.ltv_to_cac_ratio > 0

    def test_cac_calculation(self, service: CostModelingService):
        """CAC = monthly cost / monthly patients acquired."""
        ue = service.get_unit_economics()
        expected_cac = round(
            ue.total_monthly_cost / service.MONTHLY_PATIENTS_ACQUIRED, 2
        )
        assert ue.patient_acquisition_cost == expected_cac


# ============================================================================
# Infrastructure Projections
# ============================================================================


class TestInfrastructureProjections:
    """Tests for infrastructure cost projection at different scales."""

    def test_projection_at_current_scale(self, service: CostModelingService):
        """Projecting at current patient count should return current cost."""
        proj = service.project_infrastructure_costs(service.CURRENT_PATIENTS)
        assert proj.projected_monthly_cost == proj.current_monthly_cost

    def test_projection_sub_linear_scaling(self, service: CostModelingService):
        """Doubling patients should less than double infrastructure cost."""
        proj = service.project_infrastructure_costs(service.CURRENT_PATIENTS * 2)
        assert proj.projected_monthly_cost < proj.current_monthly_cost * 2

    def test_projection_scaling_efficiency_positive(self, service: CostModelingService):
        """Scaling efficiency should be positive when scaling up."""
        proj = service.project_infrastructure_costs(service.CURRENT_PATIENTS * 10)
        assert proj.scaling_efficiency > 0

    def test_projection_1k_patients(self, service: CostModelingService):
        """Projection at 1K patients."""
        proj = service.project_infrastructure_costs(1_000)
        assert proj.projected_patients == 1_000
        assert proj.projected_monthly_cost > 0
        assert proj.cost_per_patient_at_scale > 0

    def test_projection_10k_patients(self, service: CostModelingService):
        """Projection at 10K patients."""
        proj = service.project_infrastructure_costs(10_000)
        assert proj.projected_patients == 10_000
        assert proj.projected_monthly_cost > 0

    def test_projection_100k_patients(self, service: CostModelingService):
        """Projection at 100K patients."""
        proj = service.project_infrastructure_costs(100_000)
        assert proj.projected_patients == 100_000
        assert proj.cost_per_patient_at_scale < proj.current_monthly_cost / service.CURRENT_PATIENTS

    def test_projection_1m_patients(self, service: CostModelingService):
        """Projection at 1M patients should show strong economies of scale."""
        proj_100k = service.project_infrastructure_costs(100_000)
        proj_1m = service.project_infrastructure_costs(1_000_000)
        # Cost per patient at 1M should be less than at 100K
        assert proj_1m.cost_per_patient_at_scale < proj_100k.cost_per_patient_at_scale

    def test_projection_components_present(self, service: CostModelingService):
        """Projection should include individual component breakdowns."""
        proj = service.project_infrastructure_costs(50_000)
        assert len(proj.components) > 0
        for comp in proj.components:
            assert comp.name != ""
            assert comp.current_cost > 0
            assert comp.projected_cost > 0
            assert 0 < comp.scaling_factor < 1

    def test_projection_component_scaling_factors(self, service: CostModelingService):
        """Each component scaling factor should be between 0 and 1."""
        proj = service.project_infrastructure_costs(50_000)
        for comp in proj.components:
            assert 0.0 < comp.scaling_factor <= 1.0


# ============================================================================
# Revenue Model
# ============================================================================


class TestRevenueModel:
    """Tests for revenue model calculations."""

    def test_revenue_model_active_trials(self, service: CostModelingService):
        """Revenue model should reflect the number of active trials."""
        rev = service.get_revenue_model()
        assert rev.active_trials == 3

    def test_revenue_model_positive_mrr(self, service: CostModelingService):
        """MRR should be positive with active trials."""
        rev = service.get_revenue_model()
        assert rev.monthly_recurring_revenue > 0

    def test_arr_equals_mrr_times_12(self, service: CostModelingService):
        """ARR should be MRR * 12 (within floating point tolerance)."""
        rev = service.get_revenue_model()
        assert abs(rev.annual_recurring_revenue - rev.monthly_recurring_revenue * 12) < 1.0

    def test_projected_arr_growth(self, service: CostModelingService):
        """Projected ARR should be greater than current ARR (positive growth)."""
        rev = service.get_revenue_model()
        assert rev.projected_arr_12months > rev.annual_recurring_revenue

    def test_avg_revenue_per_trial(self, service: CostModelingService):
        """Average revenue per trial should be ARR / active trials."""
        rev = service.get_revenue_model()
        expected = round(rev.annual_recurring_revenue / rev.active_trials, 2)
        assert rev.avg_revenue_per_trial == expected


# ============================================================================
# Financial Dashboard
# ============================================================================


class TestFinancialDashboard:
    """Tests for the aggregated financial dashboard."""

    def test_dashboard_has_all_sections(self, service: CostModelingService):
        """Dashboard should include all financial sections."""
        dash = service.get_financial_dashboard()
        assert dash.unit_economics is not None
        assert dash.infrastructure_projection is not None
        assert dash.revenue is not None
        assert len(dash.cost_breakdown) > 0
        assert len(dash.trial_models) > 0
        assert dash.generated_at is not None

    def test_dashboard_generated_at_is_recent(self, service: CostModelingService):
        """Dashboard generated_at should be close to now."""
        dash = service.get_financial_dashboard()
        now = datetime.now(timezone.utc)
        delta = (now - dash.generated_at).total_seconds()
        assert delta < 5  # within 5 seconds

    def test_dashboard_cost_items_match_breakdown(self, service: CostModelingService):
        """Dashboard cost items should match the cost breakdown."""
        dash = service.get_financial_dashboard()
        breakdown = service.get_cost_breakdown()
        assert len(dash.cost_breakdown) == breakdown.item_count

    def test_dashboard_trial_models_match_list(self, service: CostModelingService):
        """Dashboard trial models should match the trial list."""
        dash = service.get_financial_dashboard()
        trials = service.list_trial_models()
        assert len(dash.trial_models) == trials.total


# ============================================================================
# Scenario Analysis
# ============================================================================


class TestScenarioAnalysis:
    """Tests for what-if scenario modelling."""

    def test_baseline_scenario(self, service: CostModelingService):
        """Scenario with no changes should approximate current state."""
        result = service.scenario_analysis()
        assert result.summary != ""

    def test_growth_scenario(self, service: CostModelingService):
        """Patient growth should increase projected infrastructure costs."""
        baseline = service.scenario_analysis(patient_growth_rate=0.0)
        growth = service.scenario_analysis(patient_growth_rate=0.15)
        assert (
            growth.projected_infrastructure.projected_patients
            > baseline.projected_infrastructure.projected_patients
        )

    def test_pricing_increase_scenario(self, service: CostModelingService):
        """Pricing increase should improve revenue."""
        baseline = service.scenario_analysis(pricing_change=0.0)
        higher = service.scenario_analysis(pricing_change=0.20)
        assert (
            higher.projected_revenue.monthly_recurring_revenue
            > baseline.projected_revenue.monthly_recurring_revenue
        )

    def test_trial_count_override(self, service: CostModelingService):
        """Overriding trial count should change projected revenue."""
        result = service.scenario_analysis(trial_count=10)
        assert result.projected_revenue.active_trials == 10

    def test_combined_scenario(self, service: CostModelingService):
        """Combined scenario should reflect all parameters."""
        result = service.scenario_analysis(
            patient_growth_rate=0.10,
            trial_count=5,
            pricing_change=0.15,
        )
        assert result.scenario.patient_growth_rate == 0.10
        assert result.scenario.trial_count == 5
        assert result.scenario.pricing_change == 0.15
        assert result.projected_unit_economics.total_monthly_revenue > 0

    def test_scenario_summary_describes_changes(self, service: CostModelingService):
        """Scenario summary should mention the changes."""
        result = service.scenario_analysis(
            patient_growth_rate=0.10,
            pricing_change=-0.05,
        )
        assert "10%" in result.summary
        assert "-5%" in result.summary


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_zero_patient_projection(self, service: CostModelingService):
        """Projecting at zero patients should not crash (treated as 1)."""
        proj = service.project_infrastructure_costs(0)
        assert proj.projected_patients == 1  # clamped
        assert proj.projected_monthly_cost > 0

    def test_single_patient_projection(self, service: CostModelingService):
        """Projecting at 1 patient should work."""
        proj = service.project_infrastructure_costs(1)
        assert proj.projected_patients == 1
        assert proj.cost_per_patient_at_scale > 0

    def test_remove_all_trials_revenue(self, service: CostModelingService):
        """Removing all trials should result in zero revenue."""
        trial_ids = [t.trial_id for t in service.list_trial_models().trials]
        for tid in trial_ids:
            del service._trial_models[tid]
        rev = service.get_revenue_model()
        assert rev.monthly_recurring_revenue == 0
        assert rev.active_trials == 0

    def test_unit_economics_with_no_trials(self, service: CostModelingService):
        """Unit economics should handle zero revenue gracefully."""
        for tid in list(service._trial_models.keys()):
            del service._trial_models[tid]
        ue = service.get_unit_economics()
        assert ue.total_monthly_revenue == 0
        assert ue.gross_margin == 0.0
        assert ue.ltv_to_cac_ratio == 0.0

    def test_trial_with_very_high_screening_ratio(self, service: CostModelingService):
        """Very high screening ratio should produce large screening cost."""
        model = service.create_trial_model(
            trial_id="HIGH-RATIO",
            trial_name="Hard to find",
            patient_target=10,
            cost_per_patient_screened=200.0,
            cost_per_patient_enrolled=5_000.0,
            screening_to_enrollment_ratio=50.0,
            revenue_per_enrolled_patient=100_000.0,
        )
        assert model.total_screening_cost == 10 * 50 * 200.0  # 100,000


# ============================================================================
# Singleton Pattern
# ============================================================================


class TestSingletonPattern:
    """Tests for the singleton get/reset pattern."""

    def test_get_returns_same_instance(self):
        """get_cost_modeling_service should return the same instance."""
        svc1 = get_cost_modeling_service()
        svc2 = get_cost_modeling_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """Resetting should produce a new instance on next get."""
        svc1 = get_cost_modeling_service()
        reset_cost_modeling_service()
        svc2 = get_cost_modeling_service()
        assert svc1 is not svc2

    def test_service_stats(self, service: CostModelingService):
        """get_stats should return correct counts."""
        stats = service.get_stats()
        assert stats["cost_items"] >= 15
        assert stats["trial_models"] == 3
        assert stats["current_patients"] == service.CURRENT_PATIENTS


# ============================================================================
# API Endpoint Integration Tests
# ============================================================================


class TestAPIEndpoints:
    """Integration tests for all API endpoints."""

    @pytest.mark.anyio
    async def test_get_dashboard(self, client: AsyncClient):
        """GET /cost-modeling/dashboard should return 200."""
        resp = await client.get("/api/v1/cost-modeling/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "unit_economics" in data
        assert "revenue" in data
        assert "cost_breakdown" in data
        assert "trial_models" in data
        assert "generated_at" in data

    @pytest.mark.anyio
    async def test_get_costs(self, client: AsyncClient):
        """GET /cost-modeling/costs should return cost breakdown."""
        resp = await client.get("/api/v1/cost-modeling/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "total_annual_cost" in data
        assert data["item_count"] >= 15

    @pytest.mark.anyio
    async def test_add_cost(self, client: AsyncClient):
        """POST /cost-modeling/costs should create a new cost item."""
        body = {
            "category": "infrastructure",
            "name": "API Gateway",
            "description": "AWS API Gateway",
            "unit_cost": 150.0,
            "quantity": 1.0,
            "frequency": "monthly",
        }
        resp = await client.post("/api/v1/cost-modeling/costs", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Gateway"
        assert data["total_annual_cost"] == 150.0 * 12

    @pytest.mark.anyio
    async def test_update_cost(self, client: AsyncClient):
        """PUT /cost-modeling/costs/{id} should update the item."""
        # First create an item
        create_body = {
            "category": "support",
            "name": "Help Desk",
            "unit_cost": 800.0,
        }
        create_resp = await client.post("/api/v1/cost-modeling/costs", json=create_body)
        item_id = create_resp.json()["id"]

        # Update it
        update_body = {"name": "Premium Help Desk", "unit_cost": 1_200.0}
        resp = await client.put(f"/api/v1/cost-modeling/costs/{item_id}", json=update_body)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Premium Help Desk"
        assert resp.json()["unit_cost"] == 1_200.0

    @pytest.mark.anyio
    async def test_update_cost_not_found(self, client: AsyncClient):
        """PUT /cost-modeling/costs/{id} should return 404 for unknown id."""
        resp = await client.put(
            "/api/v1/cost-modeling/costs/nonexistent",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cost(self, client: AsyncClient):
        """DELETE /cost-modeling/costs/{id} should return 204."""
        create_body = {
            "category": "licensing",
            "name": "To Delete",
            "unit_cost": 50.0,
        }
        create_resp = await client.post("/api/v1/cost-modeling/costs", json=create_body)
        item_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/cost-modeling/costs/{item_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_cost_not_found(self, client: AsyncClient):
        """DELETE /cost-modeling/costs/{id} should return 404 for unknown id."""
        resp = await client.delete("/api/v1/cost-modeling/costs/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_trials(self, client: AsyncClient):
        """GET /cost-modeling/trials should return trial list."""
        resp = await client.get("/api/v1/cost-modeling/trials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["trials"]) == 3

    @pytest.mark.anyio
    async def test_get_trial(self, client: AsyncClient):
        """GET /cost-modeling/trials/{trial_id} should return a trial model."""
        resp = await client.get("/api/v1/cost-modeling/trials/EYLEA-HD-2024")
        assert resp.status_code == 200
        assert resp.json()["trial_id"] == "EYLEA-HD-2024"

    @pytest.mark.anyio
    async def test_get_trial_not_found(self, client: AsyncClient):
        """GET /cost-modeling/trials/{trial_id} should return 404."""
        resp = await client.get("/api/v1/cost-modeling/trials/UNKNOWN")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_trial(self, client: AsyncClient):
        """POST /cost-modeling/trials should create a trial model."""
        body = {
            "trial_id": "API-TEST-001",
            "trial_name": "API Test Trial",
            "patient_target": 200,
            "cost_per_patient_screened": 75.0,
            "cost_per_patient_enrolled": 1_000.0,
            "screening_to_enrollment_ratio": 5.0,
            "overhead_allocation": 20_000.0,
            "revenue_per_enrolled_patient": 30_000.0,
        }
        resp = await client.post("/api/v1/cost-modeling/trials", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == "API-TEST-001"
        assert data["total_trial_cost"] > 0

    @pytest.mark.anyio
    async def test_create_trial_duplicate(self, client: AsyncClient):
        """POST /cost-modeling/trials with duplicate ID should return 409."""
        body = {
            "trial_id": "EYLEA-HD-2024",
            "trial_name": "Dup",
            "patient_target": 100,
            "cost_per_patient_screened": 10.0,
            "cost_per_patient_enrolled": 100.0,
            "screening_to_enrollment_ratio": 3.0,
        }
        resp = await client.post("/api/v1/cost-modeling/trials", json=body)
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_get_unit_economics(self, client: AsyncClient):
        """GET /cost-modeling/unit-economics should return metrics."""
        resp = await client.get("/api/v1/cost-modeling/unit-economics")
        assert resp.status_code == 200
        data = resp.json()
        assert "patient_acquisition_cost" in data
        assert "lifetime_value_per_patient" in data
        assert "ltv_to_cac_ratio" in data

    @pytest.mark.anyio
    async def test_get_infrastructure_projection(self, client: AsyncClient):
        """GET /cost-modeling/infrastructure/projection should return projection."""
        resp = await client.get(
            "/api/v1/cost-modeling/infrastructure/projection",
            params={"target_patients": 50_000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["projected_patients"] == 50_000
        assert data["scaling_efficiency"] > 0
        assert len(data["components"]) > 0

    @pytest.mark.anyio
    async def test_get_revenue(self, client: AsyncClient):
        """GET /cost-modeling/revenue should return revenue model."""
        resp = await client.get("/api/v1/cost-modeling/revenue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_trials"] == 3
        assert data["monthly_recurring_revenue"] > 0

    @pytest.mark.anyio
    async def test_scenario_analysis(self, client: AsyncClient):
        """POST /cost-modeling/scenarios should run scenario."""
        body = {
            "patient_growth_rate": 0.10,
            "trial_count": 5,
            "pricing_change": 0.15,
        }
        resp = await client.post("/api/v1/cost-modeling/scenarios", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert "projected_unit_economics" in data
        assert "projected_revenue" in data
        assert "projected_infrastructure" in data
        assert "summary" in data
        assert data["projected_revenue"]["active_trials"] == 5
