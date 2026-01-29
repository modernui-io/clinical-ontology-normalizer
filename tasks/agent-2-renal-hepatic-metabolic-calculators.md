# Agent 2: Renal/Hepatic/Metabolic Calculators

## Objective
Add ~60 renal, hepatic, and metabolic clinical calculators to the existing data-driven calculator system.

## Target File
`backend/app/services/calculator_definitions.py`

## Prerequisites
1. Read the existing calculator infrastructure:
   - `backend/app/services/calculator_definitions.py` - Data structures and existing calculators
   - `backend/app/services/clinical_calculators.py` - Calculator service
   - `backend/tests/test_clinical_calculators.py` - Test patterns

2. Understand the data structures:
   - `CalculatorDefinition` - Main definition class
   - `FormulaDefinition` - For equation-based calculators (most in this category)
   - `FormulaParameter` - Input parameters for formulas
   - `ThresholdInterpretation` - Score interpretation bands

## Calculator Format Example (Equation-Based)

```python
CALCULATOR_CKD_EPI_2021 = CalculatorDefinition(
    id="ckd_epi_2021",
    name="CKD-EPI Creatinine Equation (2021)",
    short_name="CKD-EPI 2021",
    calc_type=CalculatorType.EQUATION,
    category=CalculatorCategory.RENAL,
    output_type=OutputType.DECIMAL,
    score_unit="mL/min/1.73m²",
    description="Estimates glomerular filtration rate (GFR) using the 2021 CKD-EPI equation without race coefficient.",
    references=[
        "Inker LA, et al. NEJM. 2021;385(19):1737-1749. PMID: 34554658",
    ],
    formula=FormulaDefinition(
        expression="141 * min(creatinine/kappa, 1)**alpha * max(creatinine/kappa, 1)**-1.209 * 0.9938**age * sex_factor",
        parameters=[
            FormulaParameter(
                name="creatinine",
                display_name="Serum Creatinine",
                unit="mg/dL",
                min_value=0.1,
                max_value=20.0,
                description="Serum creatinine level",
            ),
            FormulaParameter(
                name="age",
                display_name="Age",
                unit="years",
                min_value=18,
                max_value=120,
                description="Patient age in years",
            ),
            FormulaParameter(
                name="sex",
                display_name="Sex",
                unit="",
                description="Patient biological sex (male/female)",
                options=["male", "female"],
            ),
        ],
        constants={
            "kappa_female": 0.7,
            "kappa_male": 0.9,
            "alpha_female": -0.241,
            "alpha_male": -0.302,
            "sex_factor_female": 1.012,
            "sex_factor_male": 1.0,
        },
    ),
    interpretations=[
        ThresholdInterpretation(
            min_score=90,
            max_score=None,
            risk_level=RiskLevel.LOW,
            interpretation="CKD Stage 1: Normal or high GFR",
            recommendations=[
                "Monitor annually if risk factors present",
                "Assess for albuminuria",
            ],
        ),
        ThresholdInterpretation(
            min_score=60,
            max_score=90,
            risk_level=RiskLevel.LOW_MODERATE,
            interpretation="CKD Stage 2: Mildly decreased GFR",
            recommendations=[
                "Monitor GFR and albuminuria annually",
                "Control blood pressure and glucose",
                "Avoid nephrotoxins",
            ],
        ),
        ThresholdInterpretation(
            min_score=45,
            max_score=60,
            risk_level=RiskLevel.MODERATE,
            interpretation="CKD Stage 3a: Mildly to moderately decreased GFR",
            recommendations=[
                "Referral to nephrology if progressive",
                "Monitor every 6 months",
                "Adjust renally-cleared medications",
            ],
        ),
        ThresholdInterpretation(
            min_score=30,
            max_score=45,
            risk_level=RiskLevel.MODERATE_HIGH,
            interpretation="CKD Stage 3b: Moderately to severely decreased GFR",
            recommendations=[
                "Nephrology referral recommended",
                "Monitor every 3-6 months",
                "Prepare for possible RRT",
            ],
        ),
        ThresholdInterpretation(
            min_score=15,
            max_score=30,
            risk_level=RiskLevel.HIGH,
            interpretation="CKD Stage 4: Severely decreased GFR",
            recommendations=[
                "Nephrology co-management required",
                "Discuss RRT options (dialysis, transplant)",
                "Monitor monthly",
            ],
        ),
        ThresholdInterpretation(
            min_score=0,
            max_score=15,
            risk_level=RiskLevel.VERY_HIGH,
            interpretation="CKD Stage 5: Kidney failure",
            recommendations=[
                "Initiate dialysis planning",
                "Transplant evaluation if candidate",
                "Urgent nephrology involvement",
            ],
        ),
    ],
    specialties=["nephrology", "internal medicine", "primary care"],
)
```

## Priority Calculators to Implement

### Tier 1 - Renal Function (implement first)
1. **CKD-EPI 2021** - Current standard eGFR (race-free)
2. **CKD-EPI 2009** - Legacy eGFR (for comparison)
3. **MDRD GFR** - Older eGFR equation
4. **Cockcroft-Gault CrCl** - Creatinine clearance (drug dosing)
5. **Schwartz Formula** - Pediatric eGFR
6. **Cystatin C-based eGFR** - Alternative GFR marker
7. **CKD-EPI Cystatin C** - Combined equation
8. **FENa** - Fractional excretion of sodium
9. **FEUrea** - Fractional excretion of urea
10. **TTKG** - Transtubular potassium gradient

### Tier 2 - Hepatic Function
11. **MELD Score** - Original Model for End-stage Liver Disease
12. **MELD-Na** - MELD with sodium
13. **MELD 3.0** - Latest MELD version (2022)
14. **Child-Pugh Score** - Cirrhosis severity
15. **FIB-4 Index** - Liver fibrosis
16. **NAFLD Fibrosis Score** - NASH fibrosis
17. **AST to Platelet Ratio (APRI)** - Fibrosis marker
18. **Discriminant Function (Maddrey)** - Alcoholic hepatitis
19. **Lille Model** - Alcoholic hepatitis response
20. **GAHS Score** - Glasgow Alcoholic Hepatitis Score

### Tier 3 - Electrolytes & Acid-Base
21. **Anion Gap** - With and without albumin correction
22. **Delta Gap** - Mixed acid-base disorders
23. **Osmolal Gap** - Toxic alcohol screening
24. **Serum Osmolality** - Calculated
25. **Corrected Sodium (for hyperglycemia)**
26. **Corrected Calcium (for albumin)**
27. **Winter's Formula** - Expected pCO2 in metabolic acidosis
28. **Bicarbonate Deficit**
29. **Sodium Correction Rate**
30. **Free Water Deficit**

### Tier 4 - Fluid/Dosing Calculations
31. **Maintenance Fluids (Holliday-Segar)** - Pediatric/adult
32. **Ideal Body Weight**
33. **Adjusted Body Weight**
34. **Body Surface Area (BSA)** - Du Bois formula
35. **Body Surface Area (Mosteller)**
36. **LBW (Lean Body Weight)**
37. **IV Fluid Rate Calculator**
38. **Creatinine Clearance (24h urine)**
39. **Protein-Creatinine Ratio to 24h conversion**
40. **Albumin-Creatinine Ratio interpretation**

### Tier 5 - Metabolic & Endocrine
41. **BMI Calculator** - (verify existing)
42. **BMI Classification (WHO/Asian)**
43. **Basal Metabolic Rate (Harris-Benedict)**
44. **Basal Metabolic Rate (Mifflin-St Jeor)**
45. **Total Energy Expenditure**
46. **HOMA-IR** - Insulin resistance
47. **HOMA-B** - Beta cell function
48. **Insulin Sensitivity Index**
49. **Thyroid Hormone Conversion (T4 to T3)**
50. **Free Thyroxine Index (FTI)**

### Tier 6 - Additional Renal/Hepatic
51. **UKELD Score** - UK liver transplant
52. **King's College Criteria** - Acute liver failure
53. **CLIF-C ACLF Score** - Acute-on-chronic liver failure
54. **AIMS65 for GI Bleed** - (cross-reference with GI)
55. **Rockall Score** - (cross-reference with GI)
56. **AKI Staging (KDIGO)**
57. **RIFLE Criteria** - AKI staging
58. **AKIN Criteria** - AKI staging
59. **Urinary Indices Panel** - Combined FENa/FEUrea
60. **Creatinine Kinetics** - AKI vs CKD

## Implementation Notes

1. **Equations need custom handlers** - For FormulaDefinition, you may need to add formula evaluation logic in `clinical_calculators.py`
2. **Unit conversions** - Support both mg/dL and µmol/L for creatinine, etc.
3. **Age/sex adjustments** - Many renal formulas vary by sex
4. **Validation ranges** - Add sensible min/max for inputs
5. **Reference original papers** - Use PMID numbers

## Formula Evaluation

For equation-based calculators, the service uses eval or custom functions. Complex formulas may need helper functions:

```python
def calculate_ckd_epi_2021(creatinine: float, age: int, sex: str) -> float:
    """Calculate eGFR using CKD-EPI 2021 equation."""
    if sex.lower() == "female":
        kappa = 0.7
        alpha = -0.241
        sex_factor = 1.012
    else:
        kappa = 0.9
        alpha = -0.302
        sex_factor = 1.0

    cr_ratio = creatinine / kappa
    term1 = min(cr_ratio, 1) ** alpha
    term2 = max(cr_ratio, 1) ** -1.209
    age_factor = 0.9938 ** age

    return 142 * term1 * term2 * age_factor * sex_factor
```

## Testing Pattern

```python
def test_ckd_epi_2021_normal():
    """Test CKD-EPI 2021 with normal GFR."""
    result = calculator_service.calculate(
        "ckd_epi_2021",
        {
            "creatinine": 0.9,
            "age": 45,
            "sex": "male",
        },
    )
    # Expected ~95 mL/min/1.73m²
    assert 90 <= result.score <= 100
    assert result.risk_level == RiskLevel.LOW

def test_meld_na_score():
    """Test MELD-Na calculation."""
    result = calculator_service.calculate(
        "meld_na",
        {
            "bilirubin": 2.0,
            "creatinine": 1.5,
            "inr": 1.8,
            "sodium": 130,
            "dialysis": False,
        },
    )
    assert 15 <= result.score <= 25
```

## Completion Checklist
- [ ] All Tier 1 renal calculators implemented
- [ ] All Tier 2 hepatic calculators implemented
- [ ] All Tier 3 electrolyte calculators implemented
- [ ] All Tier 4 fluid/dosing calculators implemented
- [ ] All Tier 5 metabolic calculators implemented
- [ ] All Tier 6 additional calculators implemented
- [ ] Formula handlers added to clinical_calculators.py
- [ ] Tests written for each calculator
- [ ] All calculators registered in CALCULATORS dict
- [ ] Code passes `ruff check` and `pytest`
