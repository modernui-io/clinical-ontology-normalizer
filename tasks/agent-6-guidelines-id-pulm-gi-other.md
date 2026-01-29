# Agent 6: Clinical Guidelines - ID/Pulmonary/GI/Other Specialties

## Objective
Add ~100 clinical guideline sections from infectious disease, pulmonary, GI, and other specialty societies.

## Target File
`backend/fixtures/clinical_guidelines.json`

## Prerequisites
1. Read the existing guideline infrastructure:
   - `backend/fixtures/clinical_guidelines.json` - Current guideline sections
   - `backend/app/services/guideline_rag_service.py` - RAG service
   - `backend/app/api/guidelines.py` - API endpoints

2. Understand the JSON structure (see Agent 5 task file for format)

---

## IDSA INFECTIOUS DISEASE GUIDELINES

### Community-Acquired Pneumonia (2019)
Add sections for:
1. Outpatient CAP treatment (no comorbidities)
2. Outpatient CAP treatment (with comorbidities)
3. Inpatient non-ICU CAP treatment
4. Severe CAP / ICU treatment
5. MRSA coverage indications
6. Pseudomonas coverage indications
7. Atypical coverage
8. Duration of therapy
9. Procalcitonin-guided therapy
10. CURB-65 / PSI usage

### Hospital-Acquired/Ventilator-Associated Pneumonia (2016)
Add sections for:
11. HAP empiric therapy
12. VAP empiric therapy
13. MDR pathogen risk factors
14. De-escalation strategies
15. Duration of therapy
16. Aerosolized antibiotics

### Urinary Tract Infections (2010)
Add sections for:
17. Uncomplicated cystitis treatment
18. Uncomplicated pyelonephritis
19. Complicated UTI treatment
20. Catheter-associated UTI
21. Asymptomatic bacteriuria (when to treat)
22. Recurrent UTI prevention

### Skin and Soft Tissue Infections (2014)
Add sections for:
23. Impetigo treatment
24. Purulent cellulitis (abscess)
25. Non-purulent cellulitis
26. Necrotizing fasciitis
27. MRSA SSTI treatment
28. Diabetic foot infections

### Sepsis Management
Add sections for:
29. Surviving Sepsis Campaign 2021 - Hour-1 bundle
30. Fluid resuscitation targets
31. Vasopressor selection
32. Antibiotic timing
33. Source control
34. Lactate clearance monitoring
35. Corticosteroids in septic shock

### Other ID Guidelines
Add sections for:
36. Clostridioides difficile infection treatment
37. Endocarditis prophylaxis
38. Infective endocarditis treatment
39. Osteomyelitis management
40. Intra-abdominal infections

---

## GOLD COPD GUIDELINES (2024)

Add sections for:
41. COPD diagnosis (spirometry criteria)
42. GOLD ABCD assessment
43. Inhaler selection algorithm
44. Triple therapy indications
45. Systemic corticosteroids for exacerbations
46. Antibiotic use in exacerbations
47. Oxygen therapy indications
48. NIV in acute exacerbation
49. Smoking cessation
50. Pulmonary rehabilitation
51. Vaccination recommendations

---

## GINA ASTHMA GUIDELINES (2024)

Add sections for:
52. Asthma diagnosis criteria
53. Asthma severity classification
54. Asthma control assessment
55. Step-up/step-down therapy
56. ICS-formoterol as reliever (MART)
57. Biologic therapy indications
58. Acute asthma management
59. Asthma in pregnancy
60. Exercise-induced bronchoconstriction
61. Severe asthma definition

---

## ACG GI GUIDELINES

### Upper GI Bleeding (2021)
Add sections for:
62. Risk stratification (Glasgow-Blatchford)
63. Resuscitation targets
64. PPI therapy timing
65. Endoscopy timing
66. Transfusion thresholds
67. Post-endoscopy management
68. Helicobacter pylori testing

### Lower GI Bleeding (2023)
Add sections for:
69. Risk stratification (Oakland Score)
70. Colonoscopy timing
71. CT angiography indications
72. Hemodynamic management

### Cirrhosis (2021)
Add sections for:
73. Ascites management
74. SBP prophylaxis
75. Hepatic encephalopathy treatment
76. Variceal bleeding prophylaxis
77. HCC surveillance
78. Liver transplant evaluation
79. TIPS indications

### IBD - Crohn's Disease
Add sections for:
80. Induction therapy options
81. Maintenance therapy
82. Biologic selection
83. Steroid-sparing strategies
84. Perianal disease management
85. Postoperative prophylaxis

### IBD - Ulcerative Colitis
Add sections for:
86. Mild-moderate UC treatment
87. Moderate-severe UC treatment
88. Acute severe UC management
89. Maintenance therapy
90. Colectomy indications

### H. pylori (2017)
Add sections for:
91. Testing indications
92. First-line treatment regimens
93. Treatment failure management
94. Bismuth quadruple therapy
95. Post-treatment confirmation

---

## AASLD HEPATOLOGY GUIDELINES

### Hepatitis B (2018)
Add sections for:
96. HBV screening recommendations
97. Treatment indications
98. Antiviral selection
99. Monitoring on treatment
100. HCC surveillance in HBV

### Hepatitis C (2023)
Add sections for:
101. HCV screening recommendations
102. DAA regimen selection
103. Treatment duration
104. SVR confirmation
105. Retreatment after failure

### Hepatocellular Carcinoma (2023)
Add sections for:
106. HCC surveillance protocols
107. BCLC staging
108. Locoregional therapy selection
109. Systemic therapy options
110. Transplant criteria (Milan)

---

## ENDOCRINE SOCIETY GUIDELINES

### Diabetes Technology
Add sections for:
111. CGM indications
112. Insulin pump indications
113. Automated insulin delivery
114. CGM in type 2 diabetes

### Thyroid
Add sections for:
115. Hypothyroidism treatment
116. Thyroid nodule evaluation
117. Hyperthyroidism treatment
118. Thyroid in pregnancy

### Osteoporosis
Add sections for:
119. Screening recommendations
120. Treatment thresholds
121. Bisphosphonate selection
122. Duration of therapy
123. Drug holiday considerations

---

## ASH ANTICOAGULATION GUIDELINES (2020)

Add sections for:
124. VTE treatment duration
125. Extended anticoagulation criteria
126. DOACs vs warfarin selection
127. Cancer-associated VTE
128. Perioperative anticoagulation
129. Anticoagulation reversal
130. Atrial fibrillation anticoagulation

---

## Implementation Example

```json
{
  "section_id": "idsa-cap-2019-outpatient-healthy",
  "guideline": "IDSA/ATS Community-Acquired Pneumonia Guideline (2019)",
  "section_title": "Outpatient Treatment - Healthy Adults",
  "recommendation_text": "For outpatient treatment of CAP in adults without comorbidities or risk factors for resistant pathogens, monotherapy with amoxicillin (1g TID) OR doxycycline (100mg BID) OR a macrolide (azithromycin or clarithromycin) is recommended. Macrolide monotherapy should only be used in areas with pneumococcal macrolide resistance <25%.",
  "evidence_grade": "Strong",
  "recommendation_level": "Strong",
  "applies_to_conditions": [
    "pneumonia",
    "community-acquired pneumonia",
    "CAP",
    "lower respiratory tract infection",
    "LRTI"
  ],
  "applies_to_medications": [
    "amoxicillin",
    "doxycycline",
    "azithromycin",
    "clarithromycin",
    "macrolide"
  ],
  "applies_to_measurements": [
    "chest x-ray",
    "procalcitonin",
    "temperature",
    "respiratory rate",
    "oxygen saturation"
  ],
  "keywords": [
    "outpatient pneumonia",
    "CAP treatment",
    "empiric antibiotics",
    "healthy adult pneumonia"
  ]
}
```

## Validation

After adding guidelines, test the RAG service:

```python
from app.services.guideline_rag_service import get_guideline_rag_service

service = get_guideline_rag_service()
service.load()

# Test infection search
results = service.search(
    "pneumonia antibiotic treatment",
    patient_conditions=["pneumonia"],
)
assert len(results) > 0

# Test GI search
results = service.search(
    "cirrhosis ascites",
    patient_conditions=["cirrhosis"],
)
assert len(results) > 0
```

## Completion Checklist
- [ ] All IDSA CAP sections added
- [ ] All IDSA HAP/VAP sections added
- [ ] All IDSA UTI sections added
- [ ] All IDSA SSTI sections added
- [ ] All Sepsis management sections added
- [ ] All Other ID sections added
- [ ] All GOLD COPD sections added
- [ ] All GINA Asthma sections added
- [ ] All ACG Upper GI sections added
- [ ] All ACG Lower GI sections added
- [ ] All ACG Cirrhosis sections added
- [ ] All ACG IBD sections added
- [ ] All ACG H. pylori sections added
- [ ] All AASLD Hepatitis sections added
- [ ] All AASLD HCC sections added
- [ ] All Endocrine Society sections added
- [ ] All ASH Anticoagulation sections added
- [ ] JSON validates correctly
- [ ] RAG service loads without error
- [ ] Search queries return expected results
