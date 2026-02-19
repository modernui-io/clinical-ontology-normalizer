export const DEMO_DRUG_ALERTS = [
  {
    alert_type: "drug_interaction",
    severity: "high",
    drug1: "Metformin",
    drug2: "IV Contrast Dye",
    description: "Risk of lactic acidosis. Hold metformin 48h before and after contrast administration.",
  },
  {
    alert_type: "drug_interaction",
    severity: "moderate",
    drug1: "Warfarin",
    drug2: "Aspirin",
    description: "Increased bleeding risk. Monitor INR closely if co-administered.",
  },
  {
    alert_type: "duplicate_therapy",
    severity: "low",
    drug1: "Albuterol HFA",
    drug2: "Levalbuterol",
    description: "Duplicate short-acting beta-agonist therapy detected.",
  },
  {
    alert_type: "renal_dosing",
    severity: "high",
    drug1: "Metformin",
    drug2: null,
    description: "Patient pat-004 has GFR 22 mL/min. Metformin contraindicated with GFR < 30.",
  },
];

export const DEMO_HCC_GAPS = [
  {
    patient_id: "pat-001",
    patient_name: "John Smith",
    current_code: "E11.9",
    current_description: "Type 2 diabetes mellitus without complications",
    suggested_code: "E11.65",
    suggested_description: "Type 2 diabetes mellitus with hyperglycemia",
    rationale: "A1c 8.2% indicates hyperglycemia. Specificity upgrade increases RAF score.",
    raf_impact: "+0.318",
  },
  {
    patient_id: "pat-003",
    patient_name: "Mary Johnson",
    current_code: "I50.9",
    current_description: "Heart failure, unspecified",
    suggested_code: "I50.22",
    suggested_description: "Chronic systolic heart failure",
    rationale: "EF 35% documents systolic dysfunction. Code should reflect chronicity and type.",
    raf_impact: "+0.368",
  },
  {
    patient_id: "pat-004",
    patient_name: "Robert Williams",
    current_code: "N18.4",
    current_description: "CKD Stage 4",
    suggested_code: "N18.4 + D63.1",
    suggested_description: "CKD Stage 4 with anemia of chronic disease",
    rationale: "Hgb 9.8 with EPO therapy. Anemia complication not captured.",
    raf_impact: "+0.234",
  },
];

export const DEMO_DOCUMENTATION_ISSUES = [
  {
    patient_id: "pat-001",
    patient_name: "John Smith",
    issue_type: "Missing Specificity",
    description: "Diabetes documented without complication specificity despite A1c 8.2%",
    severity: "moderate",
  },
  {
    patient_id: "pat-003",
    patient_name: "Mary Johnson",
    issue_type: "Incomplete Documentation",
    description: "Heart failure NYHA class not documented despite EF 35%",
    severity: "high",
  },
  {
    patient_id: "pat-005",
    patient_name: "Sarah Chen",
    issue_type: "Missing Laterality",
    description: "Asthma severity and persistence level not specified in latest note",
    severity: "low",
  },
];

export const DEMO_QUALITY_GAPS = [
  {
    patient_id: "pat-001",
    patient_name: "John Smith",
    measure: "Diabetes: A1c Control",
    target: "A1c < 7.0%",
    current: "A1c 8.2%",
    gap: "Above target by 1.2%",
    recommendation: "Consider medication intensification or endocrinology referral",
  },
  {
    patient_id: "pat-001",
    patient_name: "John Smith",
    measure: "Hypertension: BP Control",
    target: "BP < 130/80 mmHg",
    current: "BP 142/88 mmHg",
    gap: "Above target",
    recommendation: "Titrate lisinopril or add second agent",
  },
  {
    patient_id: "pat-003",
    patient_name: "Mary Johnson",
    measure: "Heart Failure: Beta-blocker Therapy",
    target: "Target dose metoprolol 200mg",
    current: "Metoprolol 50mg",
    gap: "Sub-therapeutic dose",
    recommendation: "Titrate metoprolol to target dose if tolerated",
  },
];
