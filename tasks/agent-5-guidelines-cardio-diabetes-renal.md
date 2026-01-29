# Agent 5: Clinical Guidelines - Cardiology/Diabetes/Renal

## Objective
Add ~100 clinical guideline sections from major cardiology, diabetes, and nephrology societies.

## Target File
`backend/fixtures/clinical_guidelines.json`

## Prerequisites
1. Read the existing guideline infrastructure:
   - `backend/fixtures/clinical_guidelines.json` - Current guideline sections
   - `backend/app/services/guideline_rag_service.py` - RAG service
   - `backend/app/api/guidelines.py` - API endpoints

2. Understand the JSON structure for each guideline section

## Guideline Section Format

```json
{
  "section_id": "acc-aha-hf-2022-gdmt",
  "guideline": "2022 ACC/AHA/HFSA Guideline for the Management of Heart Failure",
  "section_title": "Guideline-Directed Medical Therapy (GDMT)",
  "recommendation_text": "In patients with HFrEF, the use of an ACE inhibitor (or ARB if ACE inhibitor not tolerated), a beta-blocker (bisoprolol, carvedilol, or sustained-release metoprolol succinate), and an MRA is recommended to reduce morbidity and mortality (Class I, Level A). In patients with symptomatic HFrEF, an ARNI is recommended in place of an ACE inhibitor or ARB to further reduce morbidity and mortality (Class I, Level A). In patients with HFrEF and NYHA class II-IV symptoms, an SGLT2 inhibitor is recommended to reduce hospitalizations and cardiovascular mortality (Class I, Level A).",
  "evidence_grade": "A",
  "recommendation_level": "Strong",
  "applies_to_conditions": [
    "heart failure",
    "HFrEF",
    "reduced ejection fraction",
    "systolic heart failure",
    "CHF"
  ],
  "applies_to_medications": [
    "ACE inhibitor",
    "ARB",
    "lisinopril",
    "losartan",
    "beta blocker",
    "metoprolol",
    "carvedilol",
    "bisoprolol",
    "MRA",
    "spironolactone",
    "eplerenone",
    "ARNI",
    "sacubitril-valsartan",
    "entresto",
    "SGLT2 inhibitor",
    "dapagliflozin",
    "empagliflozin"
  ],
  "applies_to_measurements": [
    "ejection fraction",
    "EF",
    "LVEF",
    "BNP",
    "NT-proBNP"
  ],
  "keywords": [
    "GDMT",
    "guideline directed medical therapy",
    "quad therapy",
    "pillars of heart failure",
    "HFrEF treatment"
  ]
}
```

## Evidence Grade Key
- **A** = High-quality evidence from multiple RCTs or meta-analyses
- **B-R** = Moderate evidence from 1+ RCT
- **B-NR** = Moderate evidence from well-designed non-randomized studies
- **C-LD** = Limited data
- **C-EO** = Expert opinion

## Recommendation Level Key
- **Strong (Class I)** = Benefit >>> Risk, IS recommended
- **Moderate (Class IIa)** = Benefit >> Risk, IS REASONABLE
- **Weak (Class IIb)** = Benefit ≥ Risk, MAY BE CONSIDERED
- **No Benefit (Class III)** = No benefit OR Harm, NOT recommended

---

## ACC/AHA CARDIOLOGY GUIDELINES

### 2022 Heart Failure Guideline
Add sections for:
1. HFrEF GDMT (quad therapy pillars)
2. HFpEF management
3. HFmrEF management
4. Diuretic therapy
5. Device therapy (ICD, CRT)
6. Advanced HF therapies (LVAD, transplant)
7. Hospitalized HF management
8. Comorbidity management (AF, CAD, diabetes)
9. Palliative care in HF
10. Stage A/B prevention

### 2017 Hypertension Guideline
Add sections for:
11. BP targets (<130/80 for most)
12. Lifestyle modifications
13. Initial drug therapy
14. Resistant hypertension
15. Secondary hypertension
16. Hypertensive crisis
17. Special populations (CKD, diabetes, elderly)
18. BP measurement technique
19. Home BP monitoring
20. Masked and white coat hypertension

### 2023 Atrial Fibrillation Guideline
Add sections for:
21. Stroke risk assessment (CHA2DS2-VASc)
22. Anticoagulation selection (DOAC vs warfarin)
23. Bleeding risk assessment (HAS-BLED)
24. Rate control targets
25. Rhythm control strategies
26. Catheter ablation indications
27. AF and heart failure
28. Perioperative AF management
29. AF screening
30. Lifestyle factors

### 2021 Chest Pain Guideline
Add sections for:
31. Initial evaluation algorithm
32. High-sensitivity troponin interpretation
33. Low-risk chest pain pathways
34. Stress testing indications
35. CCTA indications
36. Observation unit protocols
37. Risk stratification scores
38. Disposition decision making

### 2021 Coronary Revascularization Guideline
Add sections for:
39. CABG vs PCI decision making
40. SYNTAX score usage
41. Left main disease
42. Multivessel CAD
43. Stable angina revascularization
44. DAPT duration
45. Antiplatelet selection
46. Complete revascularization

### 2018/2019 Lipid Management Guideline
Add sections for:
47. ASCVD risk assessment
48. Statin intensity selection
49. Primary prevention
50. Secondary prevention
51. LDL-C targets
52. Non-statin therapies (ezetimibe, PCSK9i)
53. Statin intolerance
54. Monitoring on therapy
55. Familial hypercholesterolemia

---

## ADA DIABETES GUIDELINES (Expand existing)

### Standards of Care 2024 - Diagnosis
Add sections for:
56. Diagnostic criteria (A1C, FPG, OGTT)
57. Prediabetes identification
58. Type 1 vs Type 2 differentiation
59. LADA recognition
60. Screening recommendations

### Glycemic Management
61. A1C targets by population
62. CGM indications and targets
63. Time in range goals
64. Hypoglycemia prevention
65. Sick day management

### Pharmacotherapy (expand existing)
66. Metformin as first-line
67. Second agent selection algorithm
68. GLP-1 RA benefits
69. SGLT2i benefits (CV, renal)
70. Insulin initiation
71. Insulin intensification
72. Injectable combination therapy

### Cardiovascular Risk
73. BP targets in diabetes
74. Lipid management in diabetes
75. Antiplatelet therapy
76. Comprehensive CV risk reduction

### Complications
77. Retinopathy screening
78. Nephropathy screening and management
79. Neuropathy screening
80. Foot care

---

## KDIGO NEPHROLOGY GUIDELINES

### CKD 2024 Guideline
Add sections for:
81. CKD definition and staging
82. GFR estimation (CKD-EPI 2021)
83. Albuminuria assessment
84. Progression risk assessment
85. BP targets in CKD
86. ACEi/ARB use in CKD
87. SGLT2i in CKD
88. Anemia management
89. MBD (mineral bone disease)
90. Bicarbonate supplementation

### AKI 2012 Guideline
Add sections for:
91. AKI definition (KDIGO criteria)
92. AKI staging
93. Prevention strategies
94. Contrast-induced AKI
95. Drug dosing in AKI
96. RRT initiation

### Diabetes in CKD 2022
Add sections for:
97. A1C targets with CKD
98. Metformin dosing in CKD
99. GLP-1 RA in diabetic CKD
100. SGLT2i for diabetic kidney disease
101. Finerenone indications

---

## Implementation Notes

1. **Use official guideline text** - Paraphrase or quote key recommendations
2. **Include evidence grades** - From original guideline
3. **Cross-reference conditions** - Link related conditions
4. **Medication mapping** - Include both generic and brand names
5. **Keyword optimization** - Think about clinical search queries

## Validation

After adding guidelines, test the RAG service:

```python
from app.services.guideline_rag_service import get_guideline_rag_service

service = get_guideline_rag_service()
service.load()

# Test search
results = service.search(
    "SGLT2 inhibitor heart failure",
    patient_conditions=["heart failure", "diabetes"],
)
assert len(results) > 0
assert any("SGLT2" in r.section.recommendation_text for r in results)
```

## Completion Checklist
- [ ] All ACC/AHA Heart Failure sections added
- [ ] All ACC/AHA Hypertension sections added
- [ ] All ACC/AHA Atrial Fibrillation sections added
- [ ] All ACC/AHA Chest Pain sections added
- [ ] All ACC/AHA Revascularization sections added
- [ ] All ACC/AHA Lipid sections added
- [ ] All ADA Diabetes sections added
- [ ] All KDIGO CKD sections added
- [ ] All KDIGO AKI sections added
- [ ] All KDIGO Diabetes/CKD sections added
- [ ] JSON validates correctly
- [ ] RAG service loads without error
- [ ] Search queries return expected results
