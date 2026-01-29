# Agent 4: Specialty Calculators (Neuro/Peds/OB/Oncology)

## Objective
Add ~80 specialty clinical calculators covering neurology, pediatrics, obstetrics, and oncology.

## Target File
`backend/app/services/calculator_definitions.py`

## Prerequisites
1. Read the existing calculator infrastructure:
   - `backend/app/services/calculator_definitions.py` - Data structures and existing calculators
   - `backend/app/services/clinical_calculators.py` - Calculator service
   - `backend/tests/test_clinical_calculators.py` - Test patterns

## Calculator Categories

This agent covers four specialty areas:
- **Neurological** - Stroke, head injury, mental status
- **Pediatric** - Growth, developmental, pediatric-specific
- **Obstetric** - Pregnancy, labor, fetal assessment
- **Oncology** - Performance status, staging, prognosis

---

## NEUROLOGY CALCULATORS

### Tier 1 - Stroke & Neurological Emergency
1. **NIH Stroke Scale (NIHSS)** - Stroke severity (15 items)
2. **Glasgow Coma Scale (GCS)** - Consciousness level
3. **ABCD2 Score** - TIA stroke risk
4. **Hunt & Hess Scale** - SAH grading
5. **Fisher Grade** - SAH CT grading
6. **Modified Fisher Scale** - SAH vasospasm risk
7. **World Federation of Neurological Surgeons (WFNS) Grade** - SAH
8. **ICH Score** - Intracerebral hemorrhage mortality
9. **FUNC Score** - ICH functional outcome
10. **DRAGON Score** - Stroke outcome after tPA

### Tier 2 - Head Injury
11. **Canadian CT Head Rule**
12. **New Orleans Criteria** - Minor head injury
13. **NEXUS II Head CT Decision Instrument**
14. **PECARN Pediatric Head Injury** - CT decision in children
15. **CHALICE Rule** - Pediatric head injury
16. **CATCH Rule** - Canadian CT head rule for children
17. **Scandinavian Guidelines** - Head injury

### Tier 3 - Stroke Decisions
18. **THRIVE Score** - Thrombectomy outcome
19. **SPAN-100 Index** - tPA futility
20. **HAT Score** - Hemorrhagic transformation risk
21. **SEDAN Score** - Symptomatic ICH after tPA
22. **iScore** - Ischemic stroke mortality
23. **ASTRAL Score** - Stroke outcome
24. **PLAN Score** - Post-stroke mortality

### Tier 4 - Other Neurological
25. **Ottawa SAH Rule** - SAH screening
26. **Hemphill ICH Score**
27. **FOUR Score** - Full Outline of Unresponsiveness
28. **Simplified Motor Score**
29. **Reaction Level Scale (RLS85)**
30. **Rankin Scale (mRS)** - Stroke disability
31. **Barthel Index** - ADL function
32. **EDSS** - MS disability (simplified)

---

## PEDIATRIC CALCULATORS

### Tier 1 - Neonatal Assessment
33. **APGAR Score** - (verify/expand existing)
34. **Ballard Score** - Gestational age assessment
35. **New Ballard Score**
36. **Palme Score** - Jaundice risk
37. **Bhutani Nomogram** - Bilirubin risk zones
38. **SNAPPE-II** - Neonatal mortality

### Tier 2 - Pediatric Emergency
39. **Pediatric GCS** - Modified for children
40. **Yale Observation Scale** - Febrile infants
41. **Rochester Criteria** - Febrile infant low risk
42. **Philadelphia Criteria** - Febrile infant
43. **Boston Criteria** - Febrile infant
44. **Step-by-Step Approach** - Febrile infant
45. **Pediatric Appendicitis Score (PAS)**
46. **Alvarado Score** - (Pediatric application)

### Tier 3 - Growth & Development
47. **WHO Z-Scores** - Weight/height for age
48. **CDC Growth Percentiles**
49. **Mid-Parental Height**
50. **Target Height Range**
51. **Bone Age Assessment** - (interpretation guide)
52. **Tanner Staging** - Pubertal development

### Tier 4 - Pediatric Critical Care
53. **PEWS** - Pediatric Early Warning Score
54. **PRISM III** - Pediatric ICU mortality
55. **PIM2/PIM3** - Pediatric Index of Mortality
56. **PELOD-2** - Pediatric organ dysfunction
57. **Pediatric SOFA**
58. **Pediatric Trauma Score**

### Tier 5 - Respiratory & Asthma
59. **Pediatric Respiratory Assessment Measure (PRAM)**
60. **Pulmonary Index Score** - Asthma severity
61. **Westley Croup Score**
62. **Modified Tal Score** - Bronchiolitis
63. **Wang Bronchiolitis Score**

---

## OBSTETRIC CALCULATORS

### Tier 1 - Pregnancy Dating & Growth
64. **Estimated Due Date (EDD)** - Naegele's rule
65. **Gestational Age Calculator**
66. **Fetal Weight Estimation** - Hadlock formula
67. **Amniotic Fluid Index (AFI)** - Interpretation
68. **Biophysical Profile (BPP)** - Scoring

### Tier 2 - Labor & Delivery
69. **Bishop Score** - (verify/expand existing)
70. **Modified Bishop Score**
71. **Simplified Bishop Score**
72. **Friedman Curve** - Labor progression
73. **VBAC Calculator** - Vaginal birth after C-section
74. **MFMU VBAC Calculator**

### Tier 3 - Risk Assessment
75. **Edinburgh Postnatal Depression Scale (EPDS)**
76. **PHQ-9 in Pregnancy**
77. **Preeclampsia Risk** - NICE/ACOG criteria
78. **PIERS Model** - Preeclampsia outcomes
79. **fullPIERS**
80. **miniPIERS**
81. **sFlt-1/PlGF Ratio** - Preeclampsia
82. **Preterm Birth Risk** - Fetal fibronectin interpretation

### Tier 4 - Fetal Assessment
83. **Nonstress Test (NST)** - Interpretation guide
84. **Contraction Stress Test (CST)** - Interpretation
85. **Umbilical Artery Doppler** - Interpretation
86. **Middle Cerebral Artery Doppler** - Anemia prediction
87. **Ductus Venosus Doppler** - Interpretation

---

## ONCOLOGY CALCULATORS

### Tier 1 - Performance Status
88. **ECOG Performance Status**
89. **Karnofsky Performance Status (KPS)**
90. **Lansky Play-Performance Scale** - Pediatric
91. **Palliative Performance Scale (PPS)**
92. **Palliative Prognostic Index (PPI)**
93. **Palliative Prognostic Score (PaP)**

### Tier 2 - Prognostic Indices
94. **International Prognostic Index (IPI)** - NHL
95. **Revised IPI (R-IPI)**
96. **FLIPI** - Follicular lymphoma
97. **MIPI** - Mantle cell lymphoma
98. **International Staging System (ISS)** - Myeloma
99. **Revised ISS (R-ISS)** - Myeloma
100. **CLL-IPI** - Chronic lymphocytic leukemia

### Tier 3 - Solid Tumor Staging Helpers
101. **TNM Stage Grouping** - (conceptual helper)
102. **Gleason Score** - Prostate cancer
103. **AJCC Staging** - (stage grouping logic)
104. **Nottingham Grade** - Breast cancer
105. **Fuhrman Grade** - Renal cell carcinoma
106. **BCLC Staging** - Hepatocellular carcinoma

### Tier 4 - Treatment & Toxicity
107. **Febrile Neutropenia Risk (MASCC)**
108. **CISNE Score** - Febrile neutropenia
109. **Khorana Score** - VTE risk in cancer
110. **CAT Score** - Cancer-associated thrombosis
111. **Body Surface Area (BSA)** - Chemotherapy dosing
112. **Calvert Formula** - Carboplatin dosing
113. **Cockcroft-Gault** - (for chemo dosing context)

---

## Implementation Example - NIHSS

```python
CALCULATOR_NIHSS = CalculatorDefinition(
    id="nihss",
    name="NIH Stroke Scale",
    short_name="NIHSS",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.NEUROLOGICAL,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Quantifies stroke severity. Score 0-42 based on 15 items assessing various neurological deficits.",
    references=[
        "Brott T, et al. Stroke. 1989;20(7):864-870. PMID: 2749846",
        "Lyden P, et al. Stroke. 1994;25(11):2220-2226. PMID: 7974549",
    ],
    multi_level_criteria=[
        MultiLevelCriterion(
            name="loc",
            display_name="1a. Level of Consciousness",
            levels=[
                ("loc_3", 3, "Unresponsive"),
                ("loc_2", 2, "Responds only to painful stimuli"),
                ("loc_1", 1, "Not alert, but arousable"),
                ("loc_0", 0, "Alert and responsive"),
            ],
        ),
        MultiLevelCriterion(
            name="loc_questions",
            display_name="1b. LOC Questions (month, age)",
            levels=[
                ("locq_2", 2, "Answers neither correctly"),
                ("locq_1", 1, "Answers one correctly"),
                ("locq_0", 0, "Answers both correctly"),
            ],
        ),
        MultiLevelCriterion(
            name="loc_commands",
            display_name="1c. LOC Commands (open/close eyes, grip/release)",
            levels=[
                ("locc_2", 2, "Performs neither correctly"),
                ("locc_1", 1, "Performs one correctly"),
                ("locc_0", 0, "Performs both correctly"),
            ],
        ),
        # ... continue for all 15 items
        MultiLevelCriterion(
            name="best_gaze",
            display_name="2. Best Gaze",
            levels=[
                ("gaze_2", 2, "Forced deviation or total paresis"),
                ("gaze_1", 1, "Partial gaze palsy"),
                ("gaze_0", 0, "Normal"),
            ],
        ),
        # Items 3-11 follow similar pattern...
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=0,
            max_score=5,
            risk_level=RiskLevel.LOW,
            interpretation="Minor stroke",
            recommendations=["Consider tPA if within window", "Stroke unit admission"],
        ),
        ThresholdInterpretation(
            min_score=5,
            max_score=15,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate stroke",
            recommendations=["tPA candidate if within window", "Consider thrombectomy evaluation"],
        ),
        ThresholdInterpretation(
            min_score=15,
            max_score=25,
            risk_level=RiskLevel.HIGH,
            interpretation="Moderate to severe stroke",
            recommendations=["Urgent reperfusion evaluation", "Thrombectomy consideration if LVO"],
        ),
        ThresholdInterpretation(
            min_score=25,
            max_score=None,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="Severe stroke",
            recommendations=["High mortality risk", "Discuss goals of care"],
        ),
    ],
    specialties=["neurology", "emergency medicine", "critical care"],
)
```

## Testing Pattern

```python
def test_nihss_moderate_stroke():
    """Test NIHSS for moderate stroke."""
    result = calculator_service.calculate(
        "nihss",
        {
            "loc_loc_0": True,
            "loc_questions_locq_1": True,  # 1 point
            "loc_commands_locc_0": True,
            "best_gaze_gaze_1": True,      # 1 point
            "visual_visual_1": True,        # 1 point
            "facial_palsy_facial_2": True,  # 2 points
            "motor_arm_left_arm_3": True,   # 3 points
            # ... etc
        },
    )
    assert 5 <= result.score <= 15
    assert result.risk_level == RiskLevel.MODERATE


def test_apgar_score():
    """Test APGAR scoring."""
    result = calculator_service.calculate(
        "apgar",
        {
            "appearance_pink": True,         # 2 points
            "pulse_above_100": True,         # 2 points
            "grimace_cry": True,             # 2 points
            "activity_active": True,         # 2 points
            "respiration_good_cry": True,    # 2 points
        },
    )
    assert result.score == 10
    assert result.risk_level == RiskLevel.LOW
```

## Completion Checklist
- [ ] All Neurology Tier 1-4 calculators implemented
- [ ] All Pediatric Tier 1-5 calculators implemented
- [ ] All Obstetric Tier 1-4 calculators implemented
- [ ] All Oncology Tier 1-4 calculators implemented
- [ ] Tests written for each calculator
- [ ] All calculators registered in CALCULATORS dict
- [ ] Code passes `ruff check` and `pytest`
