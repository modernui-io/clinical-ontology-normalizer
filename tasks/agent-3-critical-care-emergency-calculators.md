# Agent 3: Critical Care & Emergency Medicine Calculators

## Objective
Add ~70 critical care and emergency medicine clinical calculators to the existing data-driven calculator system.

## Target File
`backend/app/services/calculator_definitions.py`

## Prerequisites
1. Read the existing calculator infrastructure:
   - `backend/app/services/calculator_definitions.py` - Data structures and existing calculators
   - `backend/app/services/clinical_calculators.py` - Calculator service
   - `backend/tests/test_clinical_calculators.py` - Test patterns

2. Understand the data structures:
   - `CalculatorDefinition` - Main definition class
   - `ScoringCriterion` - Boolean yes/no criteria
   - `ThresholdCriterion` - Numeric range-based scoring
   - `ThresholdInterpretation` - Score interpretation bands

## Calculator Format Example

```python
CALCULATOR_SOFA = CalculatorDefinition(
    id="sofa",
    name="Sequential Organ Failure Assessment (SOFA) Score",
    short_name="SOFA",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CRITICAL_CARE,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Predicts ICU mortality based on degree of organ dysfunction across 6 organ systems.",
    references=[
        "Vincent JL, et al. Intensive Care Med. 1996;22(7):707-710. PMID: 8844239",
        "Ferreira FL, et al. JAMA. 2001;286(14):1754-1758. PMID: 11594901",
    ],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="respiration",
            display_name="Respiration (PaO2/FiO2)",
            levels=[
                ("pf_less_100", 4, "PaO2/FiO2 <100 with respiratory support"),
                ("pf_100_199", 3, "PaO2/FiO2 100-199 with respiratory support"),
                ("pf_200_299", 2, "PaO2/FiO2 200-299"),
                ("pf_300_399", 1, "PaO2/FiO2 300-399"),
                ("pf_400_plus", 0, "PaO2/FiO2 ≥400"),
            ],
            description="Respiratory function based on PaO2/FiO2 ratio",
        ),
        MultiLevelCriterion(
            name="coagulation",
            display_name="Coagulation (Platelets)",
            levels=[
                ("plt_less_20", 4, "Platelets <20 ×10³/µL"),
                ("plt_20_49", 3, "Platelets 20-49 ×10³/µL"),
                ("plt_50_99", 2, "Platelets 50-99 ×10³/µL"),
                ("plt_100_149", 1, "Platelets 100-149 ×10³/µL"),
                ("plt_150_plus", 0, "Platelets ≥150 ×10³/µL"),
            ],
            description="Coagulation function based on platelet count",
        ),
        MultiLevelCriterion(
            name="liver",
            display_name="Liver (Bilirubin)",
            levels=[
                ("bili_12_plus", 4, "Bilirubin ≥12 mg/dL"),
                ("bili_6_11", 3, "Bilirubin 6.0-11.9 mg/dL"),
                ("bili_2_5", 2, "Bilirubin 2.0-5.9 mg/dL"),
                ("bili_1_1", 1, "Bilirubin 1.2-1.9 mg/dL"),
                ("bili_normal", 0, "Bilirubin <1.2 mg/dL"),
            ],
            description="Hepatic function based on bilirubin",
        ),
        MultiLevelCriterion(
            name="cardiovascular",
            display_name="Cardiovascular (MAP/Vasopressors)",
            levels=[
                ("high_vasopressors", 4, "Dopamine >15 or Epi >0.1 or Norepi >0.1"),
                ("mod_vasopressors", 3, "Dopamine >5 or Epi ≤0.1 or Norepi ≤0.1"),
                ("low_vasopressors", 2, "Dopamine ≤5 or any dobutamine"),
                ("map_less_70", 1, "MAP <70 mmHg"),
                ("no_hypotension", 0, "MAP ≥70 mmHg, no vasopressors"),
            ],
            description="Cardiovascular function based on MAP and vasopressor requirements",
        ),
        MultiLevelCriterion(
            name="cns",
            display_name="CNS (Glasgow Coma Scale)",
            levels=[
                ("gcs_less_6", 4, "GCS <6"),
                ("gcs_6_9", 3, "GCS 6-9"),
                ("gcs_10_12", 2, "GCS 10-12"),
                ("gcs_13_14", 1, "GCS 13-14"),
                ("gcs_15", 0, "GCS 15"),
            ],
            description="Central nervous system function based on GCS",
        ),
        MultiLevelCriterion(
            name="renal",
            display_name="Renal (Creatinine/Urine Output)",
            levels=[
                ("cr_5_plus", 4, "Creatinine ≥5.0 mg/dL or UOP <200 mL/day"),
                ("cr_3_4", 3, "Creatinine 3.5-4.9 mg/dL or UOP <500 mL/day"),
                ("cr_2_3", 2, "Creatinine 2.0-3.4 mg/dL"),
                ("cr_1_2", 1, "Creatinine 1.2-1.9 mg/dL"),
                ("cr_normal", 0, "Creatinine <1.2 mg/dL"),
            ],
            description="Renal function based on creatinine or urine output",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0,
            max_score=2,
            risk_level=RiskLevel.LOW,
            interpretation="Minimal organ dysfunction (mortality <10%)",
            recommendations=[
                "Continue current management",
                "Monitor for clinical deterioration",
            ],
        ),
        ThresholdInterpretation(
            min_score=2,
            max_score=6,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="Mild organ dysfunction (mortality ~15-20%)",
            recommendations=[
                "ICU level monitoring",
                "Assess for source of dysfunction",
            ],
        ),
        ThresholdInterpretation(
            min_score=6,
            max_score=10,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate organ dysfunction (mortality ~40-50%)",
            recommendations=[
                "Aggressive ICU management",
                "Consider goals of care discussion",
            ],
        ),
        ThresholdInterpretation(
            min_score=10,
            max_score=15,
            risk_level=RiskLevel.HIGH,
            interpretation="Severe organ dysfunction (mortality ~80%)",
            recommendations=[
                "Maximum supportive care",
                "Goals of care discussion recommended",
            ],
        ),
        ThresholdInterpretation(
            min_score=15,
            max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Very severe organ dysfunction (mortality >90%)",
            recommendations=[
                "Mortality extremely high",
                "Urgent goals of care discussion",
                "Comfort-focused care consideration",
            ],
        ),
    ],
    specialties=["critical care", "emergency medicine", "internal medicine"],
    notes=[
        "Serial SOFA scores (Delta SOFA) may be more useful than single measurements",
        "An increase of 2+ points indicates sepsis per Sepsis-3 criteria",
    ],
)
```

## Priority Calculators to Implement

### Tier 1 - Sepsis & Critical Illness (implement first)
1. **SOFA Score** - Organ failure assessment
2. **qSOFA Score** - Quick sepsis screening
3. **SIRS Criteria** - Systemic inflammatory response
4. **Sepsis-3 Criteria** - Current sepsis definition
5. **APACHE II** - ICU mortality prediction
6. **APACHE IV** - Updated APACHE
7. **SAPS II** - Simplified Acute Physiology Score
8. **SAPS III** - Updated SAPS
9. **NEWS Score** - National Early Warning Score
10. **NEWS2 Score** - Updated NEWS with SpO2 scale

### Tier 2 - Respiratory & Pulmonary
11. **CURB-65** - Pneumonia severity
12. **CRB-65** - Community assessment (no urea)
13. **PSI/PORT Score** - Pneumonia Severity Index
14. **SMART-COP** - ICU admission for pneumonia
15. **A-a Gradient** - Alveolar-arterial gradient
16. **PaO2/FiO2 Ratio** - Oxygenation index
17. **Oxygenation Index (OI)** - Pediatric/ARDS
18. **ARDS Berlin Criteria** - ARDS classification
19. **Murray Lung Injury Score** - ARDS severity
20. **ROX Index** - HFNC failure prediction

### Tier 3 - GI Bleeding
21. **Glasgow-Blatchford Score** - GI bleed need for intervention
22. **Rockall Score** - GI bleed mortality (pre/post-endoscopy)
23. **AIMS65 Score** - Upper GI bleed mortality
24. **Oakland Score** - Lower GI bleed
25. **Forrest Classification** - Ulcer bleeding
26. **Child-Pugh Score** - (cross-reference hepatic)
27. **MELD Score** - (cross-reference hepatic)

### Tier 4 - Pancreatitis
28. **BISAP Score** - Acute pancreatitis mortality
29. **Ranson's Criteria** - Pancreatitis severity (admission)
30. **Ranson's Criteria** - Pancreatitis severity (48h)
31. **Glasgow-Imrie Criteria** - Pancreatitis severity
32. **CTSI Score** - CT Severity Index
33. **Modified CTSI** - Balthazar score
34. **APACHE II for Pancreatitis** - (subset)
35. **Harmless Acute Pancreatitis Score (HAPS)**

### Tier 5 - Trauma & Burns
36. **Revised Trauma Score (RTS)**
37. **Injury Severity Score (ISS)**
38. **Trauma and Injury Severity Score (TRISS)**
39. **Glasgow Coma Scale** - (verify existing or create)
40. **Pediatric Glasgow Coma Scale**
41. **NEXUS Criteria** - C-spine clearance
42. **Canadian C-Spine Rule**
43. **Parkland Formula** - Burn fluid resuscitation
44. **Modified Brooke Formula** - Burn fluids
45. **TBSA Calculator** - Rule of 9s / Lund-Browder

### Tier 6 - Early Warning & Screening
46. **MEWS** - Modified Early Warning Score
47. **PEWS** - Pediatric Early Warning Score
48. **REMS** - Rapid Emergency Medicine Score
49. **ViEWS** - VitalPAC Early Warning Score
50. **CART Score** - Cardiac Arrest Risk Triage
51. **LODS Score** - Logistic Organ Dysfunction
52. **MODS Score** - Multiple Organ Dysfunction
53. **Marshall Score** - Organ failure in pancreatitis

### Tier 7 - Resuscitation & Arrest
54. **ROSC Probability** - Cardiac arrest
55. **GO-FAR Score** - In-hospital arrest survival
56. **Prognosis After Resuscitation (PAR) Score**
57. **CASPRI Score** - Survival after IHCA
58. **Good Outcome Following Attempted Resuscitation (GO-FAR)**
59. **OHCA Score** - Out-of-hospital cardiac arrest

### Tier 8 - Miscellaneous Critical Care
60. **RIFLE Criteria** - AKI staging
61. **AKIN Criteria** - AKI staging
62. **KDIGO AKI Staging**
63. **HAS-BLED** - (cross-reference cardiovascular)
64. **DIC Score (ISTH)**
65. **HIT (4Ts) Score** - Heparin-induced thrombocytopenia
66. **Padua VTE Risk** - Medical patients
67. **Caprini VTE Risk** - Surgical patients
68. **Wells DVT/PE** - (cross-reference cardiovascular)
69. **Simplified PESI**
70. **PESI Score**

## Implementation Notes

1. **Multi-organ scores** - SOFA, APACHE need multiple multi-level criteria
2. **Serial scoring** - Note where delta scores are meaningful
3. **Age adjustments** - APACHE includes age points
4. **Validation cohorts** - Note original validation populations
5. **Local adaptations** - Some scores have regional versions (NEWS vs MEWS)

## Testing Pattern

```python
def test_sofa_score_septic_shock():
    """Test SOFA score in severe sepsis."""
    result = calculator_service.calculate(
        "sofa",
        {
            "respiration_pf_100_199": True,  # 3 points
            "coagulation_plt_50_99": True,   # 2 points
            "liver_bili_2_5": True,          # 2 points
            "cardiovascular_mod_vasopressors": True,  # 3 points
            "cns_gcs_13_14": True,           # 1 point
            "renal_cr_2_3": True,            # 2 points
        },
    )
    assert result.score == 13
    assert result.risk_level == RiskLevel.HIGH


def test_qsofa_sepsis_screening():
    """Test qSOFA quick sepsis screen."""
    result = calculator_service.calculate(
        "qsofa",
        {
            "respiratory_rate_22_plus": True,
            "altered_mental_status": True,
            "systolic_bp_100_or_less": False,
        },
    )
    assert result.score == 2
    assert "sepsis" in result.interpretation.lower()
```

## Completion Checklist
- [ ] All Tier 1 sepsis calculators implemented
- [ ] All Tier 2 respiratory calculators implemented
- [ ] All Tier 3 GI bleeding calculators implemented
- [ ] All Tier 4 pancreatitis calculators implemented
- [ ] All Tier 5 trauma calculators implemented
- [ ] All Tier 6 early warning calculators implemented
- [ ] All Tier 7 resuscitation calculators implemented
- [ ] All Tier 8 miscellaneous calculators implemented
- [ ] Tests written for each calculator
- [ ] All calculators registered in CALCULATORS dict
- [ ] Code passes `ruff check` and `pytest`
