"""Cost Modeling & Unit Economics Service (CFO-1).

Provides financial analytics for a pharma-regulated clinical trial
patient recruitment platform:
- Cost line item management (CRUD)
- Trial-specific cost models (EYLEA HD, Dupixent, Libtayo)
- Platform unit economics (CAC, LTV, margins, runway)
- Infrastructure cost projections with sub-linear scaling
- Revenue modelling and scenario analysis
- Aggregated financial dashboard

All data lives in-memory; in production this would be backed by a
financial data warehouse or billing service.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.cost_modeling import (
    CategorySubtotal,
    ComponentCostProjection,
    CostBreakdownResponse,
    CostCategory,
    CostFrequency,
    CostLineItem,
    FinancialDashboard,
    InfrastructureCostProjection,
    PlatformUnitEconomics,
    RevenueModel,
    ScenarioRequest,
    ScenarioResult,
    TrialCostModel,
    TrialCostModelListResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton plumbing
# ---------------------------------------------------------------------------

_service: CostModelingService | None = None
_service_lock = threading.Lock()


def get_cost_modeling_service() -> CostModelingService:
    """Return the singleton CostModelingService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = CostModelingService()
    return _service


def reset_cost_modeling_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    with _service_lock:
        _service = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CostModelingService:
    """In-memory cost modelling and unit economics engine."""

    # Platform-level assumptions
    CURRENT_PATIENTS: int = 2_500
    CASH_ON_HAND: float = 4_500_000.0  # seed + Series A balance
    AVG_PATIENT_LIFETIME_MONTHS: int = 18
    MONTHLY_PATIENTS_ACQUIRED: int = 350

    def __init__(self) -> None:
        self._cost_items: dict[str, CostLineItem] = {}
        self._trial_models: dict[str, TrialCostModel] = {}
        self._populate_cost_items()
        self._populate_trial_models()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _populate_cost_items(self) -> None:
        """Pre-populate ~18 realistic cost line items."""
        seed: list[dict[str, Any]] = [
            # INFRASTRUCTURE
            {
                "category": CostCategory.INFRASTRUCTURE,
                "name": "AWS ECS / Fargate Hosting",
                "description": "Application compute (API + workers) on AWS Fargate",
                "unit_cost": 3_200.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.INFRASTRUCTURE,
                "name": "PostgreSQL RDS (db.r6g.xlarge)",
                "description": "Primary OMOP CDM database, Multi-AZ",
                "unit_cost": 1_800.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.INFRASTRUCTURE,
                "name": "Redis ElastiCache",
                "description": "Job queue and caching layer (r6g.large)",
                "unit_cost": 450.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.INFRASTRUCTURE,
                "name": "S3 + CloudFront Storage",
                "description": "Document storage and CDN for frontend assets",
                "unit_cost": 280.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.INFRASTRUCTURE,
                "name": "Neo4j AuraDB Professional",
                "description": "Knowledge graph persistence (optional)",
                "unit_cost": 650.0,
                "frequency": CostFrequency.MONTHLY,
            },
            # PERSONNEL
            {
                "category": CostCategory.PERSONNEL,
                "name": "Engineering Team (5 FTE)",
                "description": "Backend, frontend, infra, ML engineers",
                "unit_cost": 62_500.0,
                "frequency": CostFrequency.MONTHLY,
                "notes": "Avg $150K/yr base + benefits",
            },
            {
                "category": CostCategory.PERSONNEL,
                "name": "Clinical Operations (2 FTE)",
                "description": "Trial protocol analysts and medical affairs",
                "unit_cost": 25_000.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.PERSONNEL,
                "name": "Product & Design (1 FTE)",
                "description": "Product manager + contract UX designer",
                "unit_cost": 14_500.0,
                "frequency": CostFrequency.MONTHLY,
            },
            # DATA_ACQUISITION
            {
                "category": CostCategory.DATA_ACQUISITION,
                "name": "Metriport FHIR API Usage",
                "description": "Per-patient medical record retrieval via Metriport",
                "unit_cost": 1.25,
                "quantity": 2_500,
                "frequency": CostFrequency.MONTHLY,
                "notes": "Volume-tiered pricing kicks in at 5K patients",
            },
            {
                "category": CostCategory.DATA_ACQUISITION,
                "name": "OMOP Vocabulary Licensing",
                "description": "Annual ATHENA vocabulary bundle refresh",
                "unit_cost": 12_000.0,
                "frequency": CostFrequency.ANNUALLY,
            },
            # COMPLIANCE
            {
                "category": CostCategory.COMPLIANCE,
                "name": "SOC 2 Type II Audit",
                "description": "Annual SOC 2 Type II audit by independent firm",
                "unit_cost": 45_000.0,
                "frequency": CostFrequency.ANNUALLY,
            },
            {
                "category": CostCategory.COMPLIANCE,
                "name": "HITRUST CSF Certification",
                "description": "HITRUST r2 assessment and certification (biennial, amortised)",
                "unit_cost": 35_000.0,
                "frequency": CostFrequency.ANNUALLY,
                "notes": "Biennial cost amortised annually",
            },
            {
                "category": CostCategory.COMPLIANCE,
                "name": "Penetration Testing",
                "description": "Quarterly external pen test (21 CFR Part 11 scope)",
                "unit_cost": 15_000.0,
                "frequency": CostFrequency.QUARTERLY,
            },
            # INTEGRATION
            {
                "category": CostCategory.INTEGRATION,
                "name": "Metriport Platform Fee",
                "description": "Monthly SaaS fee for FHIR connectivity platform",
                "unit_cost": 2_500.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.INTEGRATION,
                "name": "EHR Integration Middleware",
                "description": "HL7v2/FHIR translation layer (Mirth Connect hosted)",
                "unit_cost": 800.0,
                "frequency": CostFrequency.MONTHLY,
            },
            # SUPPORT
            {
                "category": CostCategory.SUPPORT,
                "name": "Customer Success Team (1 FTE)",
                "description": "Dedicated pharma account manager / CSM",
                "unit_cost": 10_000.0,
                "frequency": CostFrequency.MONTHLY,
            },
            {
                "category": CostCategory.SUPPORT,
                "name": "PagerDuty + Datadog Observability",
                "description": "Monitoring, alerting, and incident management tooling",
                "unit_cost": 1_200.0,
                "frequency": CostFrequency.MONTHLY,
            },
            # LICENSING
            {
                "category": CostCategory.LICENSING,
                "name": "OpenAI / LLM API Credits",
                "description": "GPT-4o for clinical note summarisation and agent chat",
                "unit_cost": 2_000.0,
                "frequency": CostFrequency.MONTHLY,
            },
        ]

        for item_data in seed:
            item_id = str(uuid4())
            item = CostLineItem(id=item_id, **item_data)
            self._cost_items[item_id] = item

    def _populate_trial_models(self) -> None:
        """Pre-populate 3 trial cost models with realistic pharma economics."""
        trials: list[dict[str, Any]] = [
            {
                "trial_id": "EYLEA-HD-2024",
                "trial_name": "EYLEA HD (aflibercept 8mg) - wAMD Phase III",
                "patient_target": 450,
                "cost_per_patient_screened": 85.0,
                "cost_per_patient_enrolled": 1_200.0,
                "screening_to_enrollment_ratio": 6.5,
                "overhead_allocation": 45_000.0,
                "revenue_per_enrolled_patient": 48_000.0,
            },
            {
                "trial_id": "DUPIXENT-AD-2024",
                "trial_name": "Dupixent (dupilumab) - Atopic Dermatitis Phase IV",
                "patient_target": 800,
                "cost_per_patient_screened": 65.0,
                "cost_per_patient_enrolled": 950.0,
                "screening_to_enrollment_ratio": 5.0,
                "overhead_allocation": 60_000.0,
                "revenue_per_enrolled_patient": 35_000.0,
            },
            {
                "trial_id": "LIBTAYO-NSCLC-2024",
                "trial_name": "Libtayo (cemiplimab) - NSCLC Phase III",
                "patient_target": 300,
                "cost_per_patient_screened": 120.0,
                "cost_per_patient_enrolled": 2_500.0,
                "screening_to_enrollment_ratio": 10.0,
                "overhead_allocation": 55_000.0,
                "revenue_per_enrolled_patient": 72_000.0,
            },
        ]

        for t in trials:
            model = self._build_trial_model(**t)
            self._trial_models[model.trial_id] = model

    @staticmethod
    def _build_trial_model(
        *,
        trial_id: str,
        trial_name: str,
        patient_target: int,
        cost_per_patient_screened: float,
        cost_per_patient_enrolled: float,
        screening_to_enrollment_ratio: float,
        overhead_allocation: float = 0.0,
        revenue_per_enrolled_patient: float = 0.0,
    ) -> TrialCostModel:
        """Compute derived fields for a trial cost model."""
        total_screened = int(patient_target * screening_to_enrollment_ratio)
        total_screening_cost = round(total_screened * cost_per_patient_screened, 2)
        total_enrollment_cost = round(patient_target * cost_per_patient_enrolled, 2)
        total_trial_cost = round(
            total_screening_cost + total_enrollment_cost + overhead_allocation, 2
        )
        total_revenue = round(patient_target * revenue_per_enrolled_patient, 2)
        margin_percent = (
            round((total_revenue - total_trial_cost) / total_revenue * 100, 2)
            if total_revenue > 0
            else 0.0
        )

        return TrialCostModel(
            trial_id=trial_id,
            trial_name=trial_name,
            patient_target=patient_target,
            cost_per_patient_screened=cost_per_patient_screened,
            cost_per_patient_enrolled=cost_per_patient_enrolled,
            screening_to_enrollment_ratio=screening_to_enrollment_ratio,
            total_screening_cost=total_screening_cost,
            total_enrollment_cost=total_enrollment_cost,
            overhead_allocation=overhead_allocation,
            total_trial_cost=total_trial_cost,
            margin_percent=margin_percent,
            revenue_per_enrolled_patient=revenue_per_enrolled_patient,
        )

    # ------------------------------------------------------------------
    # Cost Item CRUD
    # ------------------------------------------------------------------

    def get_cost_breakdown(self) -> CostBreakdownResponse:
        """Return all cost items grouped by category with subtotals."""
        by_category: dict[CostCategory, list[CostLineItem]] = {}
        for item in self._cost_items.values():
            by_category.setdefault(item.category, []).append(item)

        categories: list[CategorySubtotal] = []
        total_annual = 0.0
        for cat in CostCategory:
            items = by_category.get(cat, [])
            subtotal = round(sum(i.total_annual_cost for i in items), 2)
            total_annual += subtotal
            categories.append(
                CategorySubtotal(category=cat, items=items, subtotal_annual=subtotal)
            )

        return CostBreakdownResponse(
            categories=categories,
            total_annual_cost=round(total_annual, 2),
            total_monthly_cost=round(total_annual / 12, 2),
            item_count=len(self._cost_items),
        )

    def add_cost_item(
        self,
        *,
        category: CostCategory,
        name: str,
        description: str = "",
        unit_cost: float,
        quantity: float = 1.0,
        frequency: CostFrequency = CostFrequency.MONTHLY,
        notes: str = "",
    ) -> CostLineItem:
        """Add a new cost line item and return it."""
        item_id = str(uuid4())
        item = CostLineItem(
            id=item_id,
            category=category,
            name=name,
            description=description,
            unit_cost=unit_cost,
            quantity=quantity,
            frequency=frequency,
            notes=notes,
        )
        self._cost_items[item_id] = item
        return item

    def update_cost_item(self, item_id: str, **updates: Any) -> CostLineItem:
        """Update an existing cost item. Raises ValueError if not found."""
        existing = self._cost_items.get(item_id)
        if existing is None:
            raise ValueError(f"Cost item not found: {item_id}")

        data = existing.model_dump()
        for key, value in updates.items():
            if value is not None and key in data:
                data[key] = value

        updated = CostLineItem(**data)
        self._cost_items[item_id] = updated
        return updated

    def remove_cost_item(self, item_id: str) -> bool:
        """Remove a cost item. Returns True if removed, raises ValueError if not found."""
        if item_id not in self._cost_items:
            raise ValueError(f"Cost item not found: {item_id}")
        del self._cost_items[item_id]
        return True

    def get_cost_item(self, item_id: str) -> CostLineItem:
        """Get a single cost item by ID."""
        item = self._cost_items.get(item_id)
        if item is None:
            raise ValueError(f"Cost item not found: {item_id}")
        return item

    # ------------------------------------------------------------------
    # Trial Cost Models
    # ------------------------------------------------------------------

    def get_trial_cost_model(self, trial_id: str) -> TrialCostModel:
        """Get a trial cost model by trial_id. Raises ValueError if not found."""
        model = self._trial_models.get(trial_id)
        if model is None:
            raise ValueError(f"Trial cost model not found: {trial_id}")
        return model

    def list_trial_models(self) -> TrialCostModelListResponse:
        """Return all trial cost models."""
        trials = list(self._trial_models.values())
        return TrialCostModelListResponse(total=len(trials), trials=trials)

    def create_trial_model(
        self,
        *,
        trial_id: str,
        trial_name: str,
        patient_target: int,
        cost_per_patient_screened: float,
        cost_per_patient_enrolled: float,
        screening_to_enrollment_ratio: float,
        overhead_allocation: float = 0.0,
        revenue_per_enrolled_patient: float = 0.0,
    ) -> TrialCostModel:
        """Create a new trial cost model with auto-calculated fields."""
        if trial_id in self._trial_models:
            raise ValueError(f"Trial cost model already exists: {trial_id}")

        model = self._build_trial_model(
            trial_id=trial_id,
            trial_name=trial_name,
            patient_target=patient_target,
            cost_per_patient_screened=cost_per_patient_screened,
            cost_per_patient_enrolled=cost_per_patient_enrolled,
            screening_to_enrollment_ratio=screening_to_enrollment_ratio,
            overhead_allocation=overhead_allocation,
            revenue_per_enrolled_patient=revenue_per_enrolled_patient,
        )
        self._trial_models[trial_id] = model
        return model

    # ------------------------------------------------------------------
    # Unit Economics
    # ------------------------------------------------------------------

    def get_unit_economics(self) -> PlatformUnitEconomics:
        """Calculate platform-level unit economics."""
        breakdown = self.get_cost_breakdown()
        total_monthly_cost = breakdown.total_monthly_cost

        # Revenue from active trials (amortised monthly)
        revenue = self.get_revenue_model()
        total_monthly_revenue = revenue.monthly_recurring_revenue

        # Gross margin
        gross_margin = (
            round((total_monthly_revenue - total_monthly_cost) / total_monthly_revenue, 4)
            if total_monthly_revenue > 0
            else 0.0
        )

        # CAC: total monthly cost / new patients acquired per month
        patients_acquired = max(self.MONTHLY_PATIENTS_ACQUIRED, 1)
        patient_acquisition_cost = round(total_monthly_cost / patients_acquired, 2)

        # LTV: avg revenue per patient * lifetime months
        revenue_per_patient_month = (
            total_monthly_revenue / max(self.CURRENT_PATIENTS, 1)
        )
        lifetime_value = round(
            revenue_per_patient_month * self.AVG_PATIENT_LIFETIME_MONTHS, 2
        )

        ltv_to_cac = (
            round(lifetime_value / patient_acquisition_cost, 2)
            if patient_acquisition_cost > 0
            else 0.0
        )

        # Burn rate and runway
        burn_rate = round(max(total_monthly_cost - total_monthly_revenue, 0), 2)
        runway_months = (
            round(self.CASH_ON_HAND / burn_rate, 1) if burn_rate > 0 else 9999.0
        )

        # Break-even patients
        if total_monthly_revenue > 0 and self.CURRENT_PATIENTS > 0:
            revenue_per_patient = total_monthly_revenue / self.CURRENT_PATIENTS
            break_even = (
                math.ceil(total_monthly_cost / revenue_per_patient)
                if revenue_per_patient > 0
                else 0
            )
        else:
            break_even = 0

        return PlatformUnitEconomics(
            total_monthly_cost=round(total_monthly_cost, 2),
            total_monthly_revenue=round(total_monthly_revenue, 2),
            gross_margin=gross_margin,
            patient_acquisition_cost=patient_acquisition_cost,
            lifetime_value_per_patient=lifetime_value,
            ltv_to_cac_ratio=ltv_to_cac,
            burn_rate=burn_rate,
            runway_months=runway_months,
            break_even_patients=break_even,
        )

    # ------------------------------------------------------------------
    # Infrastructure Cost Projection
    # ------------------------------------------------------------------

    # Component scaling factors (exponents): < 1 means sub-linear scaling
    INFRA_COMPONENTS: list[dict[str, Any]] = [
        {"name": "PostgreSQL RDS", "base_cost": 1_800.0, "scaling_factor": 0.7},
        {"name": "AWS ECS / Fargate", "base_cost": 3_200.0, "scaling_factor": 0.8},
        {"name": "Redis ElastiCache", "base_cost": 450.0, "scaling_factor": 0.6},
        {"name": "S3 + CloudFront", "base_cost": 280.0, "scaling_factor": 0.5},
        {"name": "Neo4j AuraDB", "base_cost": 650.0, "scaling_factor": 0.65},
        {"name": "Monitoring (Datadog)", "base_cost": 1_200.0, "scaling_factor": 0.55},
    ]

    def project_infrastructure_costs(
        self, target_patients: int
    ) -> InfrastructureCostProjection:
        """Project infrastructure costs at *target_patients* using sub-linear scaling.

        For each component the projected cost is::

            projected = base_cost * (target / current) ^ scaling_factor

        A scaling_factor of 0.7 means that doubling patients only
        increases cost by 2^0.7 ~ 1.62x.
        """
        current = max(self.CURRENT_PATIENTS, 1)
        target = max(target_patients, 1)
        ratio = target / current

        components: list[ComponentCostProjection] = []
        current_total = 0.0
        projected_total = 0.0

        for comp in self.INFRA_COMPONENTS:
            base = comp["base_cost"]
            sf = comp["scaling_factor"]
            projected = round(base * (ratio ** sf), 2)
            components.append(
                ComponentCostProjection(
                    name=comp["name"],
                    current_cost=base,
                    projected_cost=projected,
                    scaling_factor=sf,
                )
            )
            current_total += base
            projected_total += projected

        cost_ratio = projected_total / current_total if current_total > 0 else 1.0
        scaling_efficiency = round(1.0 - (cost_ratio / ratio), 4) if ratio > 1 else 0.0

        return InfrastructureCostProjection(
            current_patients=current,
            projected_patients=target,
            current_monthly_cost=round(current_total, 2),
            projected_monthly_cost=round(projected_total, 2),
            cost_per_patient_at_scale=round(projected_total / target, 4),
            scaling_efficiency=scaling_efficiency,
            components=components,
        )

    # ------------------------------------------------------------------
    # Revenue Model
    # ------------------------------------------------------------------

    def get_revenue_model(self) -> RevenueModel:
        """Current and projected revenue based on active trials."""
        trials = list(self._trial_models.values())
        active_trials = len(trials)

        if active_trials == 0:
            return RevenueModel()

        # Total expected revenue across all trials, amortised over 12 months
        total_trial_revenue = sum(
            t.patient_target * t.revenue_per_enrolled_patient for t in trials
        )
        avg_revenue_per_trial = round(total_trial_revenue / active_trials, 2)
        # Assume trial duration = 12 months for MRR
        mrr = round(total_trial_revenue / 12, 2)
        arr = round(total_trial_revenue, 2)

        growth_rate = 0.08  # 8% MoM assumed
        # Projected ARR in 12 months with compound growth
        projected_arr = round(arr * ((1 + growth_rate) ** 12), 2)

        return RevenueModel(
            active_trials=active_trials,
            avg_revenue_per_trial=avg_revenue_per_trial,
            monthly_recurring_revenue=mrr,
            annual_recurring_revenue=arr,
            growth_rate_monthly=growth_rate,
            projected_arr_12months=projected_arr,
        )

    # ------------------------------------------------------------------
    # Financial Dashboard
    # ------------------------------------------------------------------

    def get_financial_dashboard(self) -> FinancialDashboard:
        """Aggregate all financial data into a single dashboard."""
        breakdown = self.get_cost_breakdown()
        all_items = list(self._cost_items.values())
        trial_models = list(self._trial_models.values())

        return FinancialDashboard(
            unit_economics=self.get_unit_economics(),
            infrastructure_projection=self.project_infrastructure_costs(
                self.CURRENT_PATIENTS * 4
            ),
            revenue=self.get_revenue_model(),
            cost_breakdown=all_items,
            trial_models=trial_models,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Scenario Analysis
    # ------------------------------------------------------------------

    def scenario_analysis(
        self,
        patient_growth_rate: float = 0.0,
        trial_count: int | None = None,
        pricing_change: float = 0.0,
    ) -> ScenarioResult:
        """What-if modelling.

        Args:
            patient_growth_rate: Monthly patient growth rate (e.g. 0.15 = 15%).
            trial_count: Override active trial count; None keeps current.
            pricing_change: Fractional change in pricing (e.g. 0.10 = +10%).
        """
        # Projected patients in 12 months
        current_patients = self.CURRENT_PATIENTS
        if patient_growth_rate > 0:
            projected_patients = int(current_patients * ((1 + patient_growth_rate) ** 12))
        else:
            projected_patients = current_patients

        # Infrastructure at projected scale
        infra = self.project_infrastructure_costs(projected_patients)

        # Revenue adjustments
        base_revenue = self.get_revenue_model()
        effective_trials = trial_count if trial_count is not None else base_revenue.active_trials
        pricing_multiplier = 1.0 + pricing_change

        # Adjust MRR based on trial count change and pricing
        if base_revenue.active_trials > 0:
            trial_ratio = effective_trials / base_revenue.active_trials
        else:
            trial_ratio = 1.0

        adjusted_mrr = round(
            base_revenue.monthly_recurring_revenue * trial_ratio * pricing_multiplier, 2
        )
        adjusted_arr = round(adjusted_mrr * 12, 2)
        growth = base_revenue.growth_rate_monthly
        projected_arr = round(adjusted_arr * ((1 + growth) ** 12), 2)

        projected_revenue = RevenueModel(
            active_trials=effective_trials,
            avg_revenue_per_trial=(
                round(adjusted_arr / effective_trials, 2) if effective_trials > 0 else 0.0
            ),
            monthly_recurring_revenue=adjusted_mrr,
            annual_recurring_revenue=adjusted_arr,
            growth_rate_monthly=growth,
            projected_arr_12months=projected_arr,
        )

        # Projected unit economics
        total_monthly_cost = infra.projected_monthly_cost + (
            self.get_cost_breakdown().total_monthly_cost - sum(
                c["base_cost"] for c in self.INFRA_COMPONENTS
            )
        )
        gross_margin = (
            round((adjusted_mrr - total_monthly_cost) / adjusted_mrr, 4)
            if adjusted_mrr > 0
            else 0.0
        )
        patients_acquired = max(int(self.MONTHLY_PATIENTS_ACQUIRED * (1 + patient_growth_rate)), 1)
        cac = round(total_monthly_cost / patients_acquired, 2)
        rev_per_patient_month = adjusted_mrr / max(projected_patients, 1)
        ltv = round(rev_per_patient_month * self.AVG_PATIENT_LIFETIME_MONTHS, 2)
        ltv_cac = round(ltv / cac, 2) if cac > 0 else 0.0
        burn = round(max(total_monthly_cost - adjusted_mrr, 0), 2)
        runway = round(self.CASH_ON_HAND / burn, 1) if burn > 0 else 9999.0
        break_even = (
            math.ceil(total_monthly_cost / rev_per_patient_month)
            if rev_per_patient_month > 0
            else 0
        )

        projected_ue = PlatformUnitEconomics(
            total_monthly_cost=round(total_monthly_cost, 2),
            total_monthly_revenue=adjusted_mrr,
            gross_margin=gross_margin,
            patient_acquisition_cost=cac,
            lifetime_value_per_patient=ltv,
            ltv_to_cac_ratio=ltv_cac,
            burn_rate=burn,
            runway_months=runway,
            break_even_patients=break_even,
        )

        scenario = ScenarioRequest(
            patient_growth_rate=patient_growth_rate,
            trial_count=trial_count,
            pricing_change=pricing_change,
        )

        summary_parts = []
        if patient_growth_rate:
            summary_parts.append(f"{patient_growth_rate*100:.0f}% monthly patient growth")
        if trial_count is not None:
            summary_parts.append(f"{trial_count} active trials")
        if pricing_change:
            summary_parts.append(f"{pricing_change*100:+.0f}% pricing change")
        summary = (
            f"Scenario: {', '.join(summary_parts)}. "
            f"Projected {projected_patients:,} patients, "
            f"${adjusted_mrr:,.0f} MRR, "
            f"{gross_margin*100:.1f}% gross margin."
        )

        return ScenarioResult(
            scenario=scenario,
            projected_unit_economics=projected_ue,
            projected_revenue=projected_revenue,
            projected_infrastructure=infra,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Stats (for prewarm compat)
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        return {
            "cost_items": len(self._cost_items),
            "trial_models": len(self._trial_models),
            "current_patients": self.CURRENT_PATIENTS,
        }
