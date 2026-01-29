# Agent 1: Cardiovascular Calculators

## Objective
Add ~80 cardiovascular clinical calculators to the existing data-driven calculator system.

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
   - `MultiLevelCriterion` - 0/1/2 point severity levels
   - `ThresholdCriterion` - Numeric range-based scoring
   - `FormulaDefinition` - For equation-based calculators
   - `ThresholdInterpretation` - Score interpretation bands

## Calculator Format Example

```python
CALCULATOR_WELLS_DVT = CalculatorDefinition(
    id="wells_dvt",
    name="Wells' Criteria for DVT",
    short_name="Wells DVT",
    calc_type=CalculatorType.CRITERIA,
    category=CalculatorCategory.CARDIOVASCULAR,
    output_type=OutputType.INTEGER,
    score_unit="points",
    description="Calculates probability of deep vein thrombosis (DVT) based on clinical criteria.",
    references=[
        "Wells PS, et al. Lancet. 1997;350(9094):1795-1798. PMID: 9428249",
        "Wells PS, et al. NEJM. 2003;349(13):1227-1235. PMID: 14507948",
    ],
    criteria=[
        ScoringCriterion(
            name="active_cancer",
            display_name="Active cancer",
            points=1,
            description="Treatment ongoing, within 6 months, or palliative",
        ),
        ScoringCriterion(
            name="paralysis_paresis",
            display_name="Paralysis, paresis, or recent plaster immobilization",
            points=1,
            description="Of the lower extremities",
        ),
        ScoringCriterion(
            name="bedridden_surgery",
            display_name="Recently bedridden >3 days or major surgery within 12 weeks",
            points=1,
            description="Requiring general or regional anesthesia",
        ),
        ScoringCriterion(
            name="localized_tenderness",
            display_name="Localized tenderness along deep venous system",
            points=1,
            description="Along the distribution of the deep venous system",
        ),
        ScoringCriterion(
            name="entire_leg_swollen",
            display_name="Entire leg swollen",
            points=1,
            description="Compared to asymptomatic leg",
        ),
        ScoringCriterion(
            name="calf_swelling",
            display_name="Calf swelling >3 cm compared to asymptomatic leg",
            points=1,
            description="Measured 10 cm below tibial tuberosity",
        ),
        ScoringCriterion(
            name="pitting_edema",
            display_name="Pitting edema confined to symptomatic leg",
            points=1,
            description="Greater in the symptomatic leg",
        ),
        ScoringCriterion(
            name="collateral_veins",
            display_name="Collateral superficial veins (non-varicose)",
            points=1,
            description="Non-varicose superficial veins",
        ),
        ScoringCriterion(
            name="previous_dvt",
            display_name="Previously documented DVT",
            points=1,
            description="History of objectively diagnosed DVT",
        ),
        ScoringCriterion(
            name="alternative_diagnosis",
            display_name="Alternative diagnosis at least as likely as DVT",
            points=-2,
            description="Subtract 2 points if alternative diagnosis present",
        ),
    ],
    interpretations=[
        ThresholdInterpretation(
            min_score=-2,
            max_score=1,
            risk_level=RiskLevel.LOW,
            interpretation="Low probability of DVT (3% prevalence)",
            recommendations=[
                "Consider D-dimer testing",
                "If D-dimer negative, DVT unlikely - no further testing needed",
                "If D-dimer positive, perform ultrasound",
            ],
        ),
        ThresholdInterpretation(
            min_score=1,
            max_score=3,
            risk_level=RiskLevel.MODERATE,
            interpretation="Moderate probability of DVT (17% prevalence)",
            recommendations=[
                "Perform D-dimer testing",
                "If D-dimer negative, DVT unlikely",
                "If D-dimer positive, perform compression ultrasound",
            ],
        ),
        ThresholdInterpretation(
            min_score=3,
            max_score=None,
            risk_level=RiskLevel.HIGH,
            interpretation="High probability of DVT (75% prevalence)",
            recommendations=[
                "Perform compression ultrasound",
                "D-dimer not recommended as standalone test",
                "Consider empiric anticoagulation while awaiting imaging",
            ],
        ),
    ],
    specialties=["emergency medicine", "internal medicine", "hematology"],
)
```

## Priority Calculators to Implement

### Tier 1 - Most Common (implement first)
1. **Wells DVT Score** - DVT probability
2. **Wells PE Score** - Pulmonary embolism probability
3. **Geneva Score (Revised)** - PE probability
4. **TIMI Risk Score STEMI** - STEMI mortality
5. **TIMI Risk Score NSTEMI/UA** - ACS risk
6. **GRACE Score** - ACS mortality
7. **HAS-BLED Score** - Bleeding risk on anticoagulation
8. **Framingham Risk Score** - 10-year CVD risk
9. **ASCVD Risk Calculator** - (verify existing is complete)
10. **CHA2DS2-VASc** - (verify existing is complete)

### Tier 2 - Important
11. **Caprini VTE Risk Score** - Surgical VTE risk
12. **Padua Prediction Score** - Medical VTE risk
13. **IMPROVE VTE Risk Score** - Hospitalized medical patients
14. **CRUSADE Bleeding Score** - ACS bleeding risk
15. **ATRIA Bleeding Risk Score** - AF anticoagulation bleeding
16. **HEMORR2HAGES Score** - AF bleeding risk
17. **Revised Cardiac Risk Index (RCRI)** - Perioperative cardiac risk
18. **Duke Treadmill Score** - Exercise stress test
19. **MAGGIC Heart Failure Score** - HF mortality
20. **Seattle Heart Failure Model** - HF survival

### Tier 3 - Specialized
21. **DASH Score** - VTE recurrence after stopping anticoagulation
22. **HERDOO2 Rule** - VTE recurrence in women
23. **Vienna Prediction Model** - VTE recurrence
24. **EuroSCORE II** - Cardiac surgery mortality
25. **STS Risk Score concepts** - Cardiac surgery risk
26. **SYNTAX Score** - PCI vs CABG decision
27. **PRECISE-DAPT Score** - Bleeding risk with DAPT
28. **DAPT Score** - Duration of dual antiplatelet
29. **ORBIT Bleeding Score** - AF anticoagulation
30. **ABC Bleeding Score** - AF anticoagulation

### Tier 4 - Additional
31. **Canadian Syncope Risk Score**
32. **San Francisco Syncope Rule**
33. **OESIL Score** - Syncope risk
34. **EGSYS Score** - Cardiac syncope
35. **Martin Algorithm** - Syncope
36. **Boston Syncope Criteria**
37. **Sgarbossa Criteria** - STEMI with LBBB
38. **Modified Sgarbossa Criteria**
39. **PERC Rule** - PE exclusion
40. **Years Algorithm** - PE diagnosis

### Tier 5 - Comprehensive Coverage
41. **Aortic Dissection Detection Risk Score**
42. **HEART Pathway** - (verify existing)
43. **EDACS Score** - ED chest pain
44. **ADAPT Protocol**
45. **Vancouver Chest Pain Rule**
46. **Marburg Heart Score**
47. **Interchest Score**
48. **SPESI Score** - Simplified PE severity
49. **PESI Score** - PE severity
50. **Bova Score** - PE risk stratification

## Implementation Notes

1. **Use original publications** - Reference PMID numbers, not MDCalc
2. **Include evidence grades** - Note if criteria are validated vs derived
3. **Add specialty tags** - For filtering in UI
4. **Test each calculator** - Add tests in `tests/test_clinical_calculators.py`
5. **Register in CALCULATORS dict** - Add to the main registry at bottom of file

## Testing Pattern

```python
def test_wells_dvt_low_risk():
    """Test Wells DVT with low risk scenario."""
    result = calculator_service.calculate(
        "wells_dvt",
        {
            "active_cancer": False,
            "paralysis_paresis": False,
            "bedridden_surgery": False,
            "localized_tenderness": False,
            "entire_leg_swollen": False,
            "calf_swelling": False,
            "pitting_edema": False,
            "collateral_veins": False,
            "previous_dvt": False,
            "alternative_diagnosis": True,  # -2 points
        },
    )
    assert result.score == -2
    assert result.risk_level == RiskLevel.LOW
```

## Completion Checklist
- [ ] All Tier 1 calculators implemented
- [ ] All Tier 2 calculators implemented
- [ ] All Tier 3 calculators implemented
- [ ] All Tier 4 calculators implemented
- [ ] All Tier 5 calculators implemented
- [ ] Tests written for each calculator
- [ ] All calculators registered in CALCULATORS dict
- [ ] Code passes `ruff check` and `pytest`
