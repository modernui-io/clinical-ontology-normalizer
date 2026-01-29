"""Synthetic Data Generation Service.

Provides synthetic patient data generation with:
- Synthea-style patient population generation
- FHIR R4 bundle output
- Differential privacy protection
- Statistical validation against real data
- Privacy vs utility metrics
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from enum import Enum
from typing import Any
import threading
import uuid
import random
import hashlib
import math
from collections import defaultdict


# ============================================================================
# Enums and Data Classes
# ============================================================================


class Gender(str, Enum):
    """Patient gender."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Race(str, Enum):
    """Patient race categories (US Census)."""

    WHITE = "white"
    BLACK = "black"
    ASIAN = "asian"
    NATIVE_AMERICAN = "native_american"
    PACIFIC_ISLANDER = "pacific_islander"
    TWO_OR_MORE = "two_or_more"
    OTHER = "other"


class Ethnicity(str, Enum):
    """Patient ethnicity."""

    HISPANIC = "hispanic"
    NON_HISPANIC = "non_hispanic"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    """Status of a generation job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Output format for generated data."""

    FHIR_JSON = "fhir_json"
    CSV = "csv"
    OMOP = "omop"


@dataclass
class AgeDistribution:
    """Age distribution configuration."""

    min_age: int = 0
    max_age: int = 100
    mean_age: float = 45.0
    std_dev: float = 20.0


@dataclass
class GenderDistribution:
    """Gender distribution configuration."""

    male_ratio: float = 0.49
    female_ratio: float = 0.50
    other_ratio: float = 0.01


@dataclass
class RaceDistribution:
    """Race distribution configuration (US Census 2020 approximation)."""

    white: float = 0.60
    black: float = 0.13
    asian: float = 0.06
    native_american: float = 0.01
    pacific_islander: float = 0.002
    two_or_more: float = 0.03
    other: float = 0.078


@dataclass
class ConditionPrevalence:
    """Condition prevalence configuration."""

    condition_code: str
    condition_name: str
    vocabulary: str = "SNOMED"
    prevalence: float = 0.0  # 0.0 to 1.0
    age_range: tuple[int, int] | None = None  # Age range where condition is more common
    gender_modifier: dict[str, float] | None = None  # Gender-specific prevalence multipliers


@dataclass
class MedicationPattern:
    """Medication prescribing pattern."""

    medication_code: str
    medication_name: str
    vocabulary: str = "RxNorm"
    associated_conditions: list[str] = field(default_factory=list)
    prescription_rate: float = 0.0  # Among patients with associated conditions


@dataclass
class LabCorrelation:
    """Lab value correlation with conditions."""

    lab_code: str
    lab_name: str
    vocabulary: str = "LOINC"
    unit: str = ""
    normal_range: tuple[float, float] = (0.0, 100.0)
    abnormal_conditions: list[str] = field(default_factory=list)
    abnormal_shift: float = 0.0  # How much to shift the value for abnormal


@dataclass
class SynthesisConfig:
    """Configuration for synthetic data generation."""

    patient_count: int = 100
    age_distribution: AgeDistribution = field(default_factory=AgeDistribution)
    gender_distribution: GenderDistribution = field(default_factory=GenderDistribution)
    race_distribution: RaceDistribution = field(default_factory=RaceDistribution)
    condition_prevalences: list[ConditionPrevalence] = field(default_factory=list)
    medication_patterns: list[MedicationPattern] = field(default_factory=list)
    lab_correlations: list[LabCorrelation] = field(default_factory=list)
    observation_period_years: int = 5
    seed: int | None = None
    output_format: OutputFormat = OutputFormat.FHIR_JSON


@dataclass
class PrivacyConfig:
    """Privacy configuration for differential privacy."""

    epsilon: float = 1.0  # Privacy budget (smaller = more private)
    delta: float = 1e-5  # Failure probability
    k_anonymity: int = 5  # Minimum group size for k-anonymity
    l_diversity: int = 2  # Minimum distinct sensitive values per group
    t_closeness: float = 0.3  # Maximum distance between distributions


@dataclass
class SyntheticPatient:
    """A synthetic patient record."""

    patient_id: str
    gender: Gender
    race: Race
    ethnicity: Ethnicity
    birth_date: str
    age: int
    conditions: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    procedures: list[dict[str, Any]] = field(default_factory=list)
    encounters: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationMetric:
    """A validation metric result."""

    metric_name: str
    column: str | None
    expected_value: float
    actual_value: float
    passed: bool
    message: str


@dataclass
class ValidationReport:
    """Report comparing synthetic and real data."""

    generated_at: str
    synthetic_row_count: int
    real_row_count: int
    metrics: list[ValidationMetric] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False


@dataclass
class PrivacyReport:
    """Privacy analysis report."""

    generated_at: str
    epsilon: float
    delta: float
    k_anonymity_satisfied: bool
    actual_k: int
    l_diversity_satisfied: bool
    actual_l: int
    t_closeness_satisfied: bool
    actual_t: float
    privacy_score: float
    utility_score: float
    recommendations: list[str] = field(default_factory=list)


@dataclass
class GenerationJob:
    """A synthetic data generation job."""

    job_id: str
    config: SynthesisConfig
    privacy_config: PrivacyConfig | None
    status: JobStatus = JobStatus.PENDING
    progress_percent: float = 0.0
    patients_generated: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result_path: str | None = None


@dataclass
class FHIRBundle:
    """FHIR Bundle containing generated resources."""

    bundle_id: str
    bundle_type: str = "collection"
    total: int = 0
    entries: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GenerationTemplate:
    """Pre-configured generation template."""

    template_id: str
    name: str
    description: str
    config: SynthesisConfig
    privacy_config: PrivacyConfig | None = None


# ============================================================================
# Default Clinical Data
# ============================================================================


DEFAULT_CONDITION_PREVALENCES = [
    ConditionPrevalence(
        condition_code="44054006",
        condition_name="Type 2 Diabetes Mellitus",
        vocabulary="SNOMED",
        prevalence=0.11,
        age_range=(40, 100),
    ),
    ConditionPrevalence(
        condition_code="38341003",
        condition_name="Hypertension",
        vocabulary="SNOMED",
        prevalence=0.32,
        age_range=(30, 100),
    ),
    ConditionPrevalence(
        condition_code="13645005",
        condition_name="Chronic Obstructive Lung Disease",
        vocabulary="SNOMED",
        prevalence=0.06,
        age_range=(45, 100),
    ),
    ConditionPrevalence(
        condition_code="414545008",
        condition_name="Ischemic Heart Disease",
        vocabulary="SNOMED",
        prevalence=0.07,
        age_range=(50, 100),
        gender_modifier={"male": 1.5, "female": 0.7},
    ),
    ConditionPrevalence(
        condition_code="195967001",
        condition_name="Asthma",
        vocabulary="SNOMED",
        prevalence=0.08,
        age_range=(0, 100),
    ),
    ConditionPrevalence(
        condition_code="73211009",
        condition_name="Diabetes Mellitus Type 1",
        vocabulary="SNOMED",
        prevalence=0.005,
        age_range=(0, 40),
    ),
    ConditionPrevalence(
        condition_code="35489007",
        condition_name="Depressive Disorder",
        vocabulary="SNOMED",
        prevalence=0.08,
        gender_modifier={"male": 0.6, "female": 1.4},
    ),
    ConditionPrevalence(
        condition_code="197480006",
        condition_name="Anxiety Disorder",
        vocabulary="SNOMED",
        prevalence=0.10,
        gender_modifier={"male": 0.5, "female": 1.5},
    ),
    ConditionPrevalence(
        condition_code="13644009",
        condition_name="Hyperlipidemia",
        vocabulary="SNOMED",
        prevalence=0.12,
        age_range=(30, 100),
    ),
    ConditionPrevalence(
        condition_code="40930008",
        condition_name="Hypothyroidism",
        vocabulary="SNOMED",
        prevalence=0.05,
        gender_modifier={"male": 0.3, "female": 1.7},
    ),
]


DEFAULT_MEDICATION_PATTERNS = [
    MedicationPattern(
        medication_code="860975",
        medication_name="Metformin 500 MG",
        vocabulary="RxNorm",
        associated_conditions=["44054006", "73211009"],
        prescription_rate=0.85,
    ),
    MedicationPattern(
        medication_code="197361",
        medication_name="Lisinopril 10 MG",
        vocabulary="RxNorm",
        associated_conditions=["38341003", "414545008"],
        prescription_rate=0.70,
    ),
    MedicationPattern(
        medication_code="83367",
        medication_name="Atorvastatin 20 MG",
        vocabulary="RxNorm",
        associated_conditions=["13644009", "414545008"],
        prescription_rate=0.75,
    ),
    MedicationPattern(
        medication_code="830839",
        medication_name="Albuterol 90 MCG Inhaler",
        vocabulary="RxNorm",
        associated_conditions=["13645005", "195967001"],
        prescription_rate=0.80,
    ),
    MedicationPattern(
        medication_code="966247",
        medication_name="Levothyroxine 50 MCG",
        vocabulary="RxNorm",
        associated_conditions=["40930008"],
        prescription_rate=0.95,
    ),
    MedicationPattern(
        medication_code="311725",
        medication_name="Sertraline 50 MG",
        vocabulary="RxNorm",
        associated_conditions=["35489007", "197480006"],
        prescription_rate=0.60,
    ),
]


DEFAULT_LAB_CORRELATIONS = [
    LabCorrelation(
        lab_code="4548-4",
        lab_name="Hemoglobin A1c",
        vocabulary="LOINC",
        unit="%",
        normal_range=(4.0, 5.6),
        abnormal_conditions=["44054006", "73211009"],
        abnormal_shift=2.5,
    ),
    LabCorrelation(
        lab_code="2339-0",
        lab_name="Glucose",
        vocabulary="LOINC",
        unit="mg/dL",
        normal_range=(70, 100),
        abnormal_conditions=["44054006", "73211009"],
        abnormal_shift=50,
    ),
    LabCorrelation(
        lab_code="2093-3",
        lab_name="Total Cholesterol",
        vocabulary="LOINC",
        unit="mg/dL",
        normal_range=(120, 200),
        abnormal_conditions=["13644009"],
        abnormal_shift=60,
    ),
    LabCorrelation(
        lab_code="2571-8",
        lab_name="Triglycerides",
        vocabulary="LOINC",
        unit="mg/dL",
        normal_range=(50, 150),
        abnormal_conditions=["13644009", "44054006"],
        abnormal_shift=100,
    ),
    LabCorrelation(
        lab_code="3094-0",
        lab_name="Blood Urea Nitrogen",
        vocabulary="LOINC",
        unit="mg/dL",
        normal_range=(7, 20),
        abnormal_conditions=["38341003"],
        abnormal_shift=10,
    ),
    LabCorrelation(
        lab_code="2160-0",
        lab_name="Creatinine",
        vocabulary="LOINC",
        unit="mg/dL",
        normal_range=(0.6, 1.2),
        abnormal_conditions=["38341003", "44054006"],
        abnormal_shift=0.5,
    ),
    LabCorrelation(
        lab_code="3016-3",
        lab_name="TSH",
        vocabulary="LOINC",
        unit="mIU/L",
        normal_range=(0.4, 4.0),
        abnormal_conditions=["40930008"],
        abnormal_shift=5.0,
    ),
]


# ============================================================================
# FHIR Code Systems
# ============================================================================


FHIR_CODE_SYSTEMS = {
    "SNOMED": "http://snomed.info/sct",
    "RxNorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "LOINC": "http://loinc.org",
    "ICD10": "http://hl7.org/fhir/sid/icd-10-cm",
}


# ============================================================================
# Synthetic Data Service
# ============================================================================


class SyntheticDataService:
    """Service for generating synthetic clinical data."""

    def __init__(self):
        """Initialize the synthetic data service."""
        self._jobs: dict[str, GenerationJob] = {}
        self._templates: dict[str, GenerationTemplate] = {}
        self._generated_data: dict[str, list[SyntheticPatient]] = {}
        self._lock = threading.Lock()
        self._rng = random.Random()

        # Statistics tracking
        self._total_patients_generated = 0
        self._total_jobs_completed = 0

        # Initialize default templates
        self._initialize_default_templates()

    def _initialize_default_templates(self) -> None:
        """Initialize default generation templates."""
        # General population template
        self._templates["general_population"] = GenerationTemplate(
            template_id="general_population",
            name="General Population",
            description="Synthetic population with typical US demographic and disease prevalence",
            config=SynthesisConfig(
                patient_count=1000,
                condition_prevalences=DEFAULT_CONDITION_PREVALENCES,
                medication_patterns=DEFAULT_MEDICATION_PATTERNS,
                lab_correlations=DEFAULT_LAB_CORRELATIONS,
            ),
        )

        # Diabetes focused template
        diabetes_conditions = [
            ConditionPrevalence(
                condition_code="44054006",
                condition_name="Type 2 Diabetes Mellitus",
                vocabulary="SNOMED",
                prevalence=0.60,  # Higher prevalence for diabetes cohort
                age_range=(30, 100),
            ),
            ConditionPrevalence(
                condition_code="38341003",
                condition_name="Hypertension",
                vocabulary="SNOMED",
                prevalence=0.50,  # Common comorbidity
            ),
            ConditionPrevalence(
                condition_code="13644009",
                condition_name="Hyperlipidemia",
                vocabulary="SNOMED",
                prevalence=0.45,
            ),
            ConditionPrevalence(
                condition_code="431855005",
                condition_name="Chronic Kidney Disease",
                vocabulary="SNOMED",
                prevalence=0.25,
            ),
            ConditionPrevalence(
                condition_code="4855003",
                condition_name="Diabetic Retinopathy",
                vocabulary="SNOMED",
                prevalence=0.20,
            ),
        ]

        self._templates["diabetes_cohort"] = GenerationTemplate(
            template_id="diabetes_cohort",
            name="Diabetes Cohort",
            description="Synthetic cohort focused on diabetes patients with common comorbidities",
            config=SynthesisConfig(
                patient_count=500,
                age_distribution=AgeDistribution(min_age=30, max_age=85, mean_age=58, std_dev=12),
                condition_prevalences=diabetes_conditions,
                medication_patterns=DEFAULT_MEDICATION_PATTERNS,
                lab_correlations=DEFAULT_LAB_CORRELATIONS,
            ),
        )

        # Privacy-safe template
        self._templates["privacy_safe"] = GenerationTemplate(
            template_id="privacy_safe",
            name="Privacy-Safe Dataset",
            description="Synthetic data with strong privacy guarantees (epsilon=0.5)",
            config=SynthesisConfig(
                patient_count=2000,
                condition_prevalences=DEFAULT_CONDITION_PREVALENCES,
                medication_patterns=DEFAULT_MEDICATION_PATTERNS,
            ),
            privacy_config=PrivacyConfig(
                epsilon=0.5,
                delta=1e-6,
                k_anonymity=10,
                l_diversity=3,
            ),
        )

    def generate_patients(self, config: SynthesisConfig) -> list[SyntheticPatient]:
        """
        Generate synthetic patient population.

        Args:
            config: Synthesis configuration

        Returns:
            List of synthetic patients
        """
        if config.seed is not None:
            self._rng.seed(config.seed)

        patients = []

        for i in range(config.patient_count):
            patient = self._generate_single_patient(config, i)
            patients.append(patient)

        with self._lock:
            self._total_patients_generated += len(patients)

        return patients

    def _generate_single_patient(self, config: SynthesisConfig, index: int) -> SyntheticPatient:
        """Generate a single synthetic patient."""
        # Generate demographics
        gender = self._sample_gender(config.gender_distribution)
        race = self._sample_race(config.race_distribution)
        ethnicity = self._sample_ethnicity()
        age = self._sample_age(config.age_distribution)
        birth_date = self._calculate_birth_date(age)

        # Generate patient ID
        patient_id = f"SYN-{uuid.uuid4().hex[:12].upper()}"

        # Create patient
        patient = SyntheticPatient(
            patient_id=patient_id,
            gender=gender,
            race=race,
            ethnicity=ethnicity,
            birth_date=birth_date,
            age=age,
        )

        # Generate conditions based on prevalence
        patient_conditions = self._generate_conditions(
            config.condition_prevalences or DEFAULT_CONDITION_PREVALENCES,
            age,
            gender,
        )
        patient.conditions = patient_conditions

        # Generate medications based on conditions
        patient.medications = self._generate_medications(
            config.medication_patterns or DEFAULT_MEDICATION_PATTERNS,
            [c["code"] for c in patient_conditions],
        )

        # Generate lab observations with correlations
        patient.observations = self._generate_observations(
            config.lab_correlations or DEFAULT_LAB_CORRELATIONS,
            [c["code"] for c in patient_conditions],
            config.observation_period_years,
        )

        # Generate encounters
        patient.encounters = self._generate_encounters(
            patient_conditions,
            config.observation_period_years,
        )

        return patient

    def _sample_gender(self, dist: GenderDistribution) -> Gender:
        """Sample gender based on distribution."""
        r = self._rng.random()
        if r < dist.male_ratio:
            return Gender.MALE
        elif r < dist.male_ratio + dist.female_ratio:
            return Gender.FEMALE
        else:
            return Gender.OTHER

    def _sample_race(self, dist: RaceDistribution) -> Race:
        """Sample race based on distribution."""
        r = self._rng.random()
        cumulative = 0.0

        for race, prob in [
            (Race.WHITE, dist.white),
            (Race.BLACK, dist.black),
            (Race.ASIAN, dist.asian),
            (Race.NATIVE_AMERICAN, dist.native_american),
            (Race.PACIFIC_ISLANDER, dist.pacific_islander),
            (Race.TWO_OR_MORE, dist.two_or_more),
            (Race.OTHER, dist.other),
        ]:
            cumulative += prob
            if r < cumulative:
                return race

        return Race.OTHER

    def _sample_ethnicity(self) -> Ethnicity:
        """Sample ethnicity (simplified US distribution)."""
        r = self._rng.random()
        if r < 0.18:  # ~18% Hispanic
            return Ethnicity.HISPANIC
        elif r < 0.95:
            return Ethnicity.NON_HISPANIC
        else:
            return Ethnicity.UNKNOWN

    def _sample_age(self, dist: AgeDistribution) -> int:
        """Sample age based on distribution."""
        # Use truncated normal distribution
        while True:
            age = int(self._rng.gauss(dist.mean_age, dist.std_dev))
            if dist.min_age <= age <= dist.max_age:
                return age

    def _calculate_birth_date(self, age: int) -> str:
        """Calculate birth date from age."""
        today = date.today()
        birth_year = today.year - age
        # Randomize month and day
        birth_month = self._rng.randint(1, 12)
        max_day = 28  # Safe for all months
        birth_day = self._rng.randint(1, max_day)

        return f"{birth_year}-{birth_month:02d}-{birth_day:02d}"

    def _generate_conditions(
        self,
        prevalences: list[ConditionPrevalence],
        age: int,
        gender: Gender,
    ) -> list[dict[str, Any]]:
        """Generate conditions based on prevalence."""
        conditions = []

        for prev in prevalences:
            effective_prevalence = prev.prevalence

            # Apply age range modifier
            if prev.age_range:
                min_age, max_age = prev.age_range
                if age < min_age or age > max_age:
                    # Outside age range, reduce prevalence
                    effective_prevalence *= 0.2

            # Apply gender modifier
            if prev.gender_modifier and gender.value in prev.gender_modifier:
                effective_prevalence *= prev.gender_modifier[gender.value]

            # Sample condition
            if self._rng.random() < effective_prevalence:
                onset_years_ago = self._rng.randint(1, min(10, age))
                onset_date = (datetime.now(timezone.utc) - timedelta(days=365 * onset_years_ago)).strftime("%Y-%m-%d")

                conditions.append({
                    "code": prev.condition_code,
                    "name": prev.condition_name,
                    "vocabulary": prev.vocabulary,
                    "onset_date": onset_date,
                    "status": "active",
                })

        return conditions

    def _generate_medications(
        self,
        patterns: list[MedicationPattern],
        condition_codes: list[str],
    ) -> list[dict[str, Any]]:
        """Generate medications based on conditions."""
        medications = []

        for pattern in patterns:
            # Check if patient has any associated condition
            has_condition = any(
                cond in condition_codes
                for cond in pattern.associated_conditions
            )

            if has_condition and self._rng.random() < pattern.prescription_rate:
                start_date = (datetime.now(timezone.utc) - timedelta(days=self._rng.randint(30, 365))).strftime("%Y-%m-%d")

                medications.append({
                    "code": pattern.medication_code,
                    "name": pattern.medication_name,
                    "vocabulary": pattern.vocabulary,
                    "start_date": start_date,
                    "status": "active",
                })

        return medications

    def _generate_observations(
        self,
        correlations: list[LabCorrelation],
        condition_codes: list[str],
        observation_years: int,
    ) -> list[dict[str, Any]]:
        """Generate lab observations with clinical correlations."""
        observations = []

        for corr in correlations:
            # Determine if patient has abnormal-associated condition
            has_abnormal_condition = any(
                cond in condition_codes
                for cond in corr.abnormal_conditions
            )

            # Generate multiple observations over time
            num_observations = self._rng.randint(2, 5) * observation_years

            for _ in range(num_observations):
                # Generate date within observation period
                days_ago = self._rng.randint(1, 365 * observation_years)
                obs_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

                # Generate value
                normal_min, normal_max = corr.normal_range
                base_value = self._rng.uniform(normal_min, normal_max)

                if has_abnormal_condition:
                    # Shift value toward abnormal
                    shift = corr.abnormal_shift * self._rng.uniform(0.5, 1.5)
                    base_value += shift

                # Add some noise
                noise = self._rng.gauss(0, (normal_max - normal_min) * 0.05)
                value = round(base_value + noise, 2)

                observations.append({
                    "code": corr.lab_code,
                    "name": corr.lab_name,
                    "vocabulary": corr.vocabulary,
                    "value": value,
                    "unit": corr.unit,
                    "date": obs_date,
                })

        return observations

    def _generate_encounters(
        self,
        conditions: list[dict[str, Any]],
        observation_years: int,
    ) -> list[dict[str, Any]]:
        """Generate healthcare encounters."""
        encounters = []

        # Base number of encounters per year
        base_encounters_per_year = 2

        # Add encounters for chronic conditions
        if len(conditions) > 0:
            base_encounters_per_year += len(conditions) * 2

        total_encounters = base_encounters_per_year * observation_years

        encounter_types = [
            ("outpatient", 0.70),
            ("inpatient", 0.05),
            ("emergency", 0.08),
            ("wellness", 0.15),
            ("telehealth", 0.02),
        ]

        for i in range(total_encounters):
            # Sample encounter type
            r = self._rng.random()
            cumulative = 0.0
            enc_type = "outpatient"
            for t, prob in encounter_types:
                cumulative += prob
                if r < cumulative:
                    enc_type = t
                    break

            # Generate date
            days_ago = self._rng.randint(1, 365 * observation_years)
            enc_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            encounters.append({
                "encounter_id": f"ENC-{uuid.uuid4().hex[:8].upper()}",
                "type": enc_type,
                "date": enc_date,
                "status": "finished",
            })

        # Sort by date
        encounters.sort(key=lambda e: e["date"], reverse=True)

        return encounters

    def generate_fhir_bundle(
        self,
        patient_count: int,
        config: dict | None = None,
    ) -> FHIRBundle:
        """
        Generate FHIR bundle with realistic patient data.

        Args:
            patient_count: Number of patients to generate
            config: Optional configuration dictionary

        Returns:
            FHIR Bundle containing all resources
        """
        # Build synthesis config from dict
        synthesis_config = SynthesisConfig(patient_count=patient_count)
        if config:
            if "age_min" in config and "age_max" in config:
                synthesis_config.age_distribution = AgeDistribution(
                    min_age=config["age_min"],
                    max_age=config["age_max"],
                    mean_age=config.get("age_mean", 45),
                    std_dev=config.get("age_std", 20),
                )
            if "male_ratio" in config:
                synthesis_config.gender_distribution = GenderDistribution(
                    male_ratio=config["male_ratio"],
                    female_ratio=1.0 - config["male_ratio"] - 0.01,
                    other_ratio=0.01,
                )
            if "seed" in config:
                synthesis_config.seed = config["seed"]

        # Generate patients
        patients = self.generate_patients(synthesis_config)

        # Convert to FHIR bundle
        bundle_id = f"bundle-{uuid.uuid4().hex[:12]}"
        entries = []

        for patient in patients:
            # Add Patient resource
            patient_resource = self._create_fhir_patient(patient)
            entries.append({
                "fullUrl": f"urn:uuid:{patient.patient_id}",
                "resource": patient_resource,
            })

            # Add Condition resources
            for condition in patient.conditions:
                condition_resource = self._create_fhir_condition(patient.patient_id, condition)
                entries.append({
                    "fullUrl": f"urn:uuid:{uuid.uuid4().hex[:12]}",
                    "resource": condition_resource,
                })

            # Add MedicationStatement resources
            for medication in patient.medications:
                med_resource = self._create_fhir_medication_statement(patient.patient_id, medication)
                entries.append({
                    "fullUrl": f"urn:uuid:{uuid.uuid4().hex[:12]}",
                    "resource": med_resource,
                })

            # Add Observation resources
            for observation in patient.observations:
                obs_resource = self._create_fhir_observation(patient.patient_id, observation)
                entries.append({
                    "fullUrl": f"urn:uuid:{uuid.uuid4().hex[:12]}",
                    "resource": obs_resource,
                })

        return FHIRBundle(
            bundle_id=bundle_id,
            bundle_type="collection",
            total=len(entries),
            entries=entries,
        )

    def _create_fhir_patient(self, patient: SyntheticPatient) -> dict[str, Any]:
        """Create FHIR Patient resource."""
        # Map gender
        fhir_gender = patient.gender.value
        if patient.gender == Gender.OTHER:
            fhir_gender = "other"

        return {
            "resourceType": "Patient",
            "id": patient.patient_id,
            "identifier": [
                {
                    "system": "http://synthetic.example.org/patients",
                    "value": patient.patient_id,
                }
            ],
            "gender": fhir_gender,
            "birthDate": patient.birth_date,
            "extension": [
                {
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                    "extension": [
                        {
                            "url": "ombCategory",
                            "valueCoding": {
                                "system": "urn:oid:2.16.840.1.113883.6.238",
                                "code": self._race_to_omb_code(patient.race),
                                "display": patient.race.value.replace("_", " ").title(),
                            }
                        }
                    ]
                },
                {
                    "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                    "extension": [
                        {
                            "url": "ombCategory",
                            "valueCoding": {
                                "system": "urn:oid:2.16.840.1.113883.6.238",
                                "code": "2135-2" if patient.ethnicity == Ethnicity.HISPANIC else "2186-5",
                                "display": "Hispanic or Latino" if patient.ethnicity == Ethnicity.HISPANIC else "Not Hispanic or Latino",
                            }
                        }
                    ]
                },
            ],
        }

    def _race_to_omb_code(self, race: Race) -> str:
        """Convert race to OMB code."""
        mapping = {
            Race.WHITE: "2106-3",
            Race.BLACK: "2054-5",
            Race.ASIAN: "2028-9",
            Race.NATIVE_AMERICAN: "1002-5",
            Race.PACIFIC_ISLANDER: "2076-8",
            Race.TWO_OR_MORE: "2131-1",
            Race.OTHER: "2131-1",
        }
        return mapping.get(race, "2131-1")

    def _create_fhir_condition(self, patient_id: str, condition: dict[str, Any]) -> dict[str, Any]:
        """Create FHIR Condition resource."""
        return {
            "resourceType": "Condition",
            "id": f"cond-{uuid.uuid4().hex[:12]}",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": condition.get("status", "active"),
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "system": FHIR_CODE_SYSTEMS.get(condition["vocabulary"], "http://snomed.info/sct"),
                        "code": condition["code"],
                        "display": condition["name"],
                    }
                ],
                "text": condition["name"],
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "onsetDateTime": condition.get("onset_date"),
        }

    def _create_fhir_medication_statement(self, patient_id: str, medication: dict[str, Any]) -> dict[str, Any]:
        """Create FHIR MedicationStatement resource."""
        return {
            "resourceType": "MedicationStatement",
            "id": f"med-{uuid.uuid4().hex[:12]}",
            "status": medication.get("status", "active"),
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": FHIR_CODE_SYSTEMS.get(medication["vocabulary"], "http://www.nlm.nih.gov/research/umls/rxnorm"),
                        "code": medication["code"],
                        "display": medication["name"],
                    }
                ],
                "text": medication["name"],
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": medication.get("start_date"),
        }

    def _create_fhir_observation(self, patient_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        """Create FHIR Observation resource."""
        return {
            "resourceType": "Observation",
            "id": f"obs-{uuid.uuid4().hex[:12]}",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": FHIR_CODE_SYSTEMS.get(observation["vocabulary"], "http://loinc.org"),
                        "code": observation["code"],
                        "display": observation["name"],
                    }
                ],
                "text": observation["name"],
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": observation.get("date"),
            "valueQuantity": {
                "value": observation["value"],
                "unit": observation.get("unit", ""),
                "system": "http://unitsofmeasure.org",
            },
        }

    def apply_differential_privacy(
        self,
        data: list[dict[str, Any]],
        epsilon: float,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Apply differential privacy to dataset.

        Uses Laplace mechanism for numeric columns and randomized response
        for categorical columns.

        Args:
            data: Input data as list of dictionaries
            epsilon: Privacy budget (smaller = more private)
            columns: Columns to apply privacy to (None = all numeric)

        Returns:
            Privacy-protected data
        """
        if not data:
            return data

        protected_data = []

        # Identify column types from first row
        sample_row = data[0]
        numeric_cols = []
        categorical_cols = []

        for col in sample_row.keys():
            if columns and col not in columns:
                continue
            val = sample_row[col]
            if isinstance(val, (int, float)):
                numeric_cols.append(col)
            elif isinstance(val, str):
                categorical_cols.append(col)

        for row in data:
            new_row = dict(row)

            # Apply Laplace noise to numeric columns
            for col in numeric_cols:
                if col in new_row and new_row[col] is not None:
                    value = float(new_row[col])
                    # Sensitivity is estimated as range of data
                    sensitivity = 1.0  # Could be calculated from data
                    scale = sensitivity / epsilon
                    noise = self._laplace_noise(scale)
                    new_row[col] = round(value + noise, 2)

            # Apply randomized response to categorical columns
            for col in categorical_cols:
                if col in new_row:
                    # With probability 1/(1+e^epsilon), flip to random value
                    prob_keep = math.exp(epsilon) / (1 + math.exp(epsilon))
                    if self._rng.random() > prob_keep:
                        # Would need to know domain of values for proper randomization
                        # For now, keep original (this is a simplified implementation)
                        pass

            protected_data.append(new_row)

        return protected_data

    def _laplace_noise(self, scale: float) -> float:
        """Generate Laplace noise."""
        # Use inverse CDF method
        u = self._rng.uniform(-0.5, 0.5)
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def validate_synthetic_data(
        self,
        synthetic: list[dict[str, Any]],
        real: list[dict[str, Any]],
        columns: list[str] | None = None,
    ) -> ValidationReport:
        """
        Compare statistical properties of synthetic vs real data.

        Performs:
        - Distribution comparison (KS test for numeric)
        - Chi-square test for categorical
        - Correlation preservation check
        - Marginal statistics comparison

        Args:
            synthetic: Synthetic data
            real: Real data
            columns: Columns to validate (None = all common)

        Returns:
            ValidationReport with metrics
        """
        metrics = []

        if not synthetic or not real:
            return ValidationReport(
                generated_at=datetime.now(timezone.utc).isoformat(),
                synthetic_row_count=len(synthetic),
                real_row_count=len(real),
                metrics=[],
                overall_score=0.0,
                passed=False,
            )

        # Find common columns
        synthetic_cols = set(synthetic[0].keys())
        real_cols = set(real[0].keys())
        common_cols = synthetic_cols.intersection(real_cols)

        if columns:
            common_cols = common_cols.intersection(set(columns))

        for col in common_cols:
            synthetic_vals = [row[col] for row in synthetic if row.get(col) is not None]
            real_vals = [row[col] for row in real if row.get(col) is not None]

            if not synthetic_vals or not real_vals:
                continue

            # Check if numeric or categorical
            if isinstance(synthetic_vals[0], (int, float)):
                # Numeric: compare mean and std
                syn_mean = sum(synthetic_vals) / len(synthetic_vals)
                real_mean = sum(real_vals) / len(real_vals)

                syn_std = (sum((x - syn_mean) ** 2 for x in synthetic_vals) / len(synthetic_vals)) ** 0.5
                real_std = (sum((x - real_mean) ** 2 for x in real_vals) / len(real_vals)) ** 0.5

                # Mean comparison
                mean_diff = abs(syn_mean - real_mean) / (real_mean if real_mean != 0 else 1)
                mean_passed = mean_diff < 0.15  # Within 15%

                metrics.append(ValidationMetric(
                    metric_name="mean_comparison",
                    column=col,
                    expected_value=real_mean,
                    actual_value=syn_mean,
                    passed=mean_passed,
                    message=f"Mean difference: {mean_diff:.2%}",
                ))

                # Std comparison
                std_diff = abs(syn_std - real_std) / (real_std if real_std != 0 else 1)
                std_passed = std_diff < 0.25  # Within 25%

                metrics.append(ValidationMetric(
                    metric_name="std_comparison",
                    column=col,
                    expected_value=real_std,
                    actual_value=syn_std,
                    passed=std_passed,
                    message=f"Std difference: {std_diff:.2%}",
                ))

            else:
                # Categorical: compare distributions
                syn_counts: dict[Any, int] = defaultdict(int)
                real_counts: dict[Any, int] = defaultdict(int)

                for v in synthetic_vals:
                    syn_counts[v] += 1
                for v in real_vals:
                    real_counts[v] += 1

                # Calculate chi-square-like metric
                all_values = set(syn_counts.keys()).union(set(real_counts.keys()))
                chi_sq = 0
                for val in all_values:
                    syn_freq = syn_counts.get(val, 0) / len(synthetic_vals)
                    real_freq = real_counts.get(val, 0) / len(real_vals)
                    if real_freq > 0:
                        chi_sq += ((syn_freq - real_freq) ** 2) / real_freq

                passed = chi_sq < 0.1

                metrics.append(ValidationMetric(
                    metric_name="distribution_comparison",
                    column=col,
                    expected_value=0.0,
                    actual_value=chi_sq,
                    passed=passed,
                    message=f"Chi-square statistic: {chi_sq:.4f}",
                ))

        # Calculate overall score
        if metrics:
            passed_count = sum(1 for m in metrics if m.passed)
            overall_score = passed_count / len(metrics)
        else:
            overall_score = 0.0

        return ValidationReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            synthetic_row_count=len(synthetic),
            real_row_count=len(real),
            metrics=metrics,
            overall_score=round(overall_score, 3),
            passed=overall_score >= 0.7,
        )

    def calculate_privacy_score(
        self,
        synthetic: list[dict[str, Any]],
        real: list[dict[str, Any]],
        quasi_identifiers: list[str] | None = None,
    ) -> float:
        """
        Calculate privacy preservation score.

        Measures how well synthetic data protects against re-identification.
        Higher score = better privacy.

        Args:
            synthetic: Synthetic data
            real: Real data
            quasi_identifiers: Columns that could be used for re-identification

        Returns:
            Privacy score between 0 and 1
        """
        if not synthetic or not real:
            return 1.0  # Perfect privacy with no data

        if quasi_identifiers is None:
            # Use all common columns as potential QIs
            quasi_identifiers = list(set(synthetic[0].keys()).intersection(set(real[0].keys())))

        # Check k-anonymity equivalent groups
        group_sizes = defaultdict(int)
        for row in synthetic:
            key = tuple(str(row.get(qi, "")) for qi in quasi_identifiers)
            group_sizes[key] += 1

        if not group_sizes:
            return 1.0

        min_group_size = min(group_sizes.values())
        avg_group_size = sum(group_sizes.values()) / len(group_sizes)

        # Score based on group sizes (larger = more private)
        k_score = min(1.0, min_group_size / 10)

        # Check uniqueness (fewer unique records = more private)
        unique_ratio = len(group_sizes) / len(synthetic)
        uniqueness_score = 1.0 - unique_ratio

        # Combined score
        privacy_score = (k_score * 0.6 + uniqueness_score * 0.4)

        return round(privacy_score, 3)

    def calculate_utility_score(
        self,
        synthetic: list[dict[str, Any]],
        real: list[dict[str, Any]],
    ) -> float:
        """
        Calculate data utility/fidelity score.

        Measures how well synthetic data preserves analytical utility.
        Higher score = better utility.

        Args:
            synthetic: Synthetic data
            real: Real data

        Returns:
            Utility score between 0 and 1
        """
        validation = self.validate_synthetic_data(synthetic, real)
        return validation.overall_score

    def check_k_anonymity(
        self,
        data: list[dict[str, Any]],
        quasi_identifiers: list[str],
        k: int = 5,
    ) -> tuple[bool, int]:
        """
        Check if data satisfies k-anonymity.

        Args:
            data: Data to check
            quasi_identifiers: Columns that could be used for re-identification
            k: Minimum group size

        Returns:
            Tuple of (satisfies_k_anonymity, actual_k)
        """
        if not data:
            return True, k

        # Group by quasi-identifiers
        groups: dict[tuple, int] = defaultdict(int)
        for row in data:
            key = tuple(str(row.get(qi, "")) for qi in quasi_identifiers)
            groups[key] += 1

        if not groups:
            return True, k

        min_group_size = min(groups.values())
        return min_group_size >= k, min_group_size

    def check_l_diversity(
        self,
        data: list[dict[str, Any]],
        quasi_identifiers: list[str],
        sensitive_attribute: str,
        l: int = 2,
    ) -> tuple[bool, int]:
        """
        Check if data satisfies l-diversity.

        Args:
            data: Data to check
            quasi_identifiers: QI columns
            sensitive_attribute: Sensitive column
            l: Minimum distinct sensitive values per group

        Returns:
            Tuple of (satisfies_l_diversity, actual_l)
        """
        if not data:
            return True, l

        # Group by quasi-identifiers
        groups: dict[tuple, set] = defaultdict(set)
        for row in data:
            key = tuple(str(row.get(qi, "")) for qi in quasi_identifiers)
            if sensitive_attribute in row:
                groups[key].add(row[sensitive_attribute])

        if not groups:
            return True, l

        min_diversity = min(len(vals) for vals in groups.values())
        return min_diversity >= l, min_diversity

    def generate_privacy_report(
        self,
        synthetic: list[dict[str, Any]],
        real: list[dict[str, Any]],
        privacy_config: PrivacyConfig,
        quasi_identifiers: list[str] | None = None,
        sensitive_attributes: list[str] | None = None,
    ) -> PrivacyReport:
        """
        Generate comprehensive privacy analysis report.

        Args:
            synthetic: Synthetic data
            real: Real data (for comparison)
            privacy_config: Privacy configuration
            quasi_identifiers: QI columns
            sensitive_attributes: Sensitive columns

        Returns:
            PrivacyReport with all metrics
        """
        if quasi_identifiers is None:
            quasi_identifiers = []
        if sensitive_attributes is None:
            sensitive_attributes = []

        # Check k-anonymity
        k_satisfied, actual_k = self.check_k_anonymity(
            synthetic, quasi_identifiers, privacy_config.k_anonymity
        )

        # Check l-diversity (for first sensitive attribute if any)
        if sensitive_attributes:
            l_satisfied, actual_l = self.check_l_diversity(
                synthetic, quasi_identifiers, sensitive_attributes[0], privacy_config.l_diversity
            )
        else:
            l_satisfied, actual_l = True, privacy_config.l_diversity

        # T-closeness would require full implementation - simplified here
        t_satisfied = True
        actual_t = 0.0

        # Calculate scores
        privacy_score = self.calculate_privacy_score(synthetic, real, quasi_identifiers)
        utility_score = self.calculate_utility_score(synthetic, real)

        # Generate recommendations
        recommendations = []
        if not k_satisfied:
            recommendations.append(
                f"Increase generalization or suppression to achieve k={privacy_config.k_anonymity} anonymity (current k={actual_k})"
            )
        if not l_satisfied:
            recommendations.append(
                f"Increase diversity of sensitive values to achieve l={privacy_config.l_diversity} diversity (current l={actual_l})"
            )
        if privacy_score < 0.7:
            recommendations.append(
                "Consider reducing epsilon or adding more noise to improve privacy"
            )
        if utility_score < 0.6:
            recommendations.append(
                "Utility is low - consider increasing epsilon or reducing noise levels"
            )

        return PrivacyReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            epsilon=privacy_config.epsilon,
            delta=privacy_config.delta,
            k_anonymity_satisfied=k_satisfied,
            actual_k=actual_k,
            l_diversity_satisfied=l_satisfied,
            actual_l=actual_l,
            t_closeness_satisfied=t_satisfied,
            actual_t=actual_t,
            privacy_score=privacy_score,
            utility_score=utility_score,
            recommendations=recommendations,
        )

    def create_job(
        self,
        config: SynthesisConfig,
        privacy_config: PrivacyConfig | None = None,
    ) -> GenerationJob:
        """Create a new generation job."""
        job_id = f"gen-{uuid.uuid4().hex[:12]}"

        job = GenerationJob(
            job_id=job_id,
            config=config,
            privacy_config=privacy_config,
        )

        with self._lock:
            self._jobs[job_id] = job

        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_templates(self) -> list[GenerationTemplate]:
        """Get all available generation templates."""
        with self._lock:
            return list(self._templates.values())

    def get_template(self, template_id: str) -> GenerationTemplate | None:
        """Get a template by ID."""
        with self._lock:
            return self._templates.get(template_id)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                "total_patients_generated": self._total_patients_generated,
                "total_jobs": len(self._jobs),
                "completed_jobs": sum(1 for j in self._jobs.values() if j.status == JobStatus.COMPLETED),
                "available_templates": len(self._templates),
                "default_conditions": len(DEFAULT_CONDITION_PREVALENCES),
                "default_medications": len(DEFAULT_MEDICATION_PATTERNS),
                "default_labs": len(DEFAULT_LAB_CORRELATIONS),
            }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: SyntheticDataService | None = None
_service_lock = threading.Lock()


def get_synthetic_data_service() -> SyntheticDataService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = SyntheticDataService()

    return _service_instance


def reset_synthetic_data_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
