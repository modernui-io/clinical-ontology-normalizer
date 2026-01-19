"use client";

import { useState, useMemo, use } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Calculator,
  ArrowLeft,
  Heart,
  Activity,
  Stethoscope,
  Droplets,
  Scale,
  FlaskConical,
  Star,
  StarOff,
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  BookOpen,
  Gauge,
  RotateCcw,
} from "lucide-react";

// Types
interface InputDefinition {
  type: string;
  title?: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  default?: any;
  enum?: string[];
  pattern?: string;
}

interface CalculatorDetail {
  id: string;
  name: string;
  short_name: string;
  category: string;
  description: string;
  inputs: Record<string, InputDefinition>;
  required: string[];
}

interface CalculationResult {
  calculator_id: string;
  calculator_name: string;
  score: number;
  score_unit: string;
  risk_level: string;
  interpretation: string;
  recommendations: string[];
  components: Record<string, any>;
  references: string[];
  formula_used: string;
  warnings: string[];
}

// Calculator definitions with input schemas (matching backend)
const calculatorDefinitions: Record<string, CalculatorDetail> = {
  bmi: {
    id: "bmi",
    name: "Body Mass Index (BMI)",
    short_name: "BMI",
    category: "general",
    description: "Calculate body mass index for obesity classification",
    inputs: {
      weight_kg: { type: "number", title: "Weight", description: "Weight in kilograms", minimum: 1, maximum: 500 },
      height_cm: { type: "number", title: "Height", description: "Height in centimeters", minimum: 50, maximum: 300 },
    },
    required: ["weight_kg", "height_cm"],
  },
  bsa: {
    id: "bsa",
    name: "Body Surface Area (BSA)",
    short_name: "BSA",
    category: "general",
    description: "Calculate body surface area using Du Bois formula",
    inputs: {
      weight_kg: { type: "number", title: "Weight", description: "Weight in kilograms", minimum: 1, maximum: 500 },
      height_cm: { type: "number", title: "Height", description: "Height in centimeters", minimum: 50, maximum: 300 },
    },
    required: ["weight_kg", "height_cm"],
  },
  egfr_ckdepi: {
    id: "egfr_ckdepi",
    name: "CKD-EPI eGFR (2021)",
    short_name: "eGFR",
    category: "renal",
    description: "Estimated glomerular filtration rate using race-free CKD-EPI 2021 equation",
    inputs: {
      creatinine: { type: "number", title: "Serum Creatinine", description: "mg/dL", minimum: 0.1, maximum: 30 },
      age: { type: "number", title: "Age", description: "Years", minimum: 18, maximum: 120 },
      sex: { type: "string", title: "Sex", enum: ["male", "female"] },
    },
    required: ["creatinine", "age", "sex"],
  },
  cockcroft_gault: {
    id: "cockcroft_gault",
    name: "Creatinine Clearance (Cockcroft-Gault)",
    short_name: "CrCl",
    category: "renal",
    description: "Creatinine clearance for medication dosing",
    inputs: {
      creatinine: { type: "number", title: "Serum Creatinine", description: "mg/dL", minimum: 0.1, maximum: 30 },
      age: { type: "number", title: "Age", description: "Years", minimum: 18, maximum: 120 },
      weight_kg: { type: "number", title: "Weight", description: "kg", minimum: 1, maximum: 500 },
      sex: { type: "string", title: "Sex", enum: ["male", "female"] },
    },
    required: ["creatinine", "age", "weight_kg", "sex"],
  },
  cha2ds2_vasc: {
    id: "cha2ds2_vasc",
    name: "CHA2DS2-VASc Score",
    short_name: "CHA2DS2-VASc",
    category: "cardiovascular",
    description: "Stroke risk in atrial fibrillation",
    inputs: {
      age: { type: "number", title: "Age", description: "Years", minimum: 18, maximum: 120 },
      sex: { type: "string", title: "Sex", enum: ["male", "female"] },
      chf: { type: "boolean", title: "Congestive Heart Failure", default: false },
      hypertension: { type: "boolean", title: "Hypertension", default: false },
      diabetes: { type: "boolean", title: "Diabetes Mellitus", default: false },
      stroke_tia: { type: "boolean", title: "Prior Stroke/TIA/Thromboembolism", default: false },
      vascular_disease: { type: "boolean", title: "Vascular Disease (MI, PAD, aortic plaque)", default: false },
    },
    required: ["age", "sex"],
  },
  has_bled: {
    id: "has_bled",
    name: "HAS-BLED Score",
    short_name: "HAS-BLED",
    category: "cardiovascular",
    description: "Bleeding risk on anticoagulation",
    inputs: {
      hypertension: { type: "boolean", title: "Hypertension (SBP >160 mmHg)", default: false },
      renal_disease: { type: "boolean", title: "Renal Disease (Dialysis, Cr >2.6)", default: false },
      liver_disease: { type: "boolean", title: "Liver Disease", default: false },
      stroke_history: { type: "boolean", title: "Prior Stroke", default: false },
      bleeding_history: { type: "boolean", title: "Prior Major Bleeding", default: false },
      labile_inr: { type: "boolean", title: "Labile INR (<60% TTR)", default: false },
      age_over_65: { type: "boolean", title: "Age >65 years", default: false },
      antiplatelet_nsaid: { type: "boolean", title: "Antiplatelet or NSAID Use", default: false },
      alcohol_use: { type: "boolean", title: "Alcohol Use (>=8 drinks/week)", default: false },
    },
    required: [],
  },
  heart: {
    id: "heart",
    name: "HEART Score",
    short_name: "HEART",
    category: "cardiovascular",
    description: "Major adverse cardiac event risk for chest pain patients",
    inputs: {
      age: { type: "number", title: "Age", description: "Years", minimum: 18, maximum: 120 },
      history: { type: "string", title: "History", enum: ["highly_suspicious", "moderately_suspicious", "slightly_suspicious"] },
      ecg: { type: "string", title: "ECG Findings", enum: ["significant_st_depression", "nonspecific_repolarization", "normal"] },
      troponin: { type: "string", title: "Troponin", enum: ["greater_than_3x", "1_to_3x", "normal"] },
      risk_factors: { type: "number", title: "Number of Risk Factors", description: "HTN, DM, smoking, family hx, obesity, hyperlipidemia", minimum: 0, maximum: 7 },
    },
    required: ["age", "history", "ecg", "troponin", "risk_factors"],
  },
  meld: {
    id: "meld",
    name: "MELD/MELD-Na Score",
    short_name: "MELD",
    category: "hepatic",
    description: "Liver disease severity for transplant prioritization",
    inputs: {
      creatinine: { type: "number", title: "Serum Creatinine", description: "mg/dL", minimum: 0.1, maximum: 15 },
      bilirubin: { type: "number", title: "Total Bilirubin", description: "mg/dL", minimum: 0.1, maximum: 50 },
      inr: { type: "number", title: "INR", minimum: 0.5, maximum: 15 },
      sodium: { type: "number", title: "Serum Sodium (optional)", description: "mEq/L for MELD-Na", minimum: 100, maximum: 160 },
      on_dialysis: { type: "boolean", title: "On Dialysis (sets Cr to 4)", default: false },
    },
    required: ["creatinine", "bilirubin", "inr"],
  },
  child_pugh: {
    id: "child_pugh",
    name: "Child-Pugh Score",
    short_name: "Child-Pugh",
    category: "hepatic",
    description: "Cirrhosis severity classification",
    inputs: {
      bilirubin: { type: "number", title: "Total Bilirubin", description: "mg/dL", minimum: 0.1, maximum: 50 },
      albumin: { type: "number", title: "Serum Albumin", description: "g/dL", minimum: 1, maximum: 6 },
      inr: { type: "number", title: "INR", minimum: 0.5, maximum: 10 },
      ascites: { type: "string", title: "Ascites", enum: ["none", "mild", "moderate_severe"] },
      encephalopathy: { type: "string", title: "Encephalopathy", enum: ["none", "grade_1_2", "grade_3_4"] },
    },
    required: ["bilirubin", "albumin", "inr", "ascites", "encephalopathy"],
  },
  fib4: {
    id: "fib4",
    name: "FIB-4 Score",
    short_name: "FIB-4",
    category: "hepatic",
    description: "Liver fibrosis risk assessment",
    inputs: {
      age: { type: "number", title: "Age", description: "Years", minimum: 18, maximum: 120 },
      ast: { type: "number", title: "AST", description: "U/L", minimum: 1, maximum: 2000 },
      alt: { type: "number", title: "ALT", description: "U/L", minimum: 1, maximum: 2000 },
      platelets: { type: "number", title: "Platelet Count", description: "10^9/L", minimum: 1, maximum: 1000 },
    },
    required: ["age", "ast", "alt", "platelets"],
  },
  qsofa: {
    id: "qsofa",
    name: "qSOFA Score",
    short_name: "qSOFA",
    category: "critical_care",
    description: "Quick sepsis screening",
    inputs: {
      respiratory_rate: { type: "number", title: "Respiratory Rate", description: "/min", minimum: 0, maximum: 80 },
      systolic_bp: { type: "number", title: "Systolic BP", description: "mmHg", minimum: 0, maximum: 300 },
      altered_mental_status: { type: "boolean", title: "Altered Mental Status (GCS <15)", default: false },
    },
    required: ["respiratory_rate", "systolic_bp"],
  },
  wells_pe: {
    id: "wells_pe",
    name: "Wells Score for PE",
    short_name: "Wells PE",
    category: "critical_care",
    description: "Pulmonary embolism probability",
    inputs: {
      clinical_dvt: { type: "boolean", title: "Clinical Signs of DVT", default: false },
      pe_most_likely: { type: "boolean", title: "PE Most Likely Diagnosis", default: false },
      heart_rate_over_100: { type: "boolean", title: "Heart Rate >100 bpm", default: false },
      immobilization_surgery: { type: "boolean", title: "Immobilization or Surgery (past 4 weeks)", default: false },
      previous_pe_dvt: { type: "boolean", title: "Previous PE or DVT", default: false },
      hemoptysis: { type: "boolean", title: "Hemoptysis", default: false },
      malignancy: { type: "boolean", title: "Malignancy (treatment within 6 months)", default: false },
    },
    required: [],
  },
  wells_dvt: {
    id: "wells_dvt",
    name: "Wells Score for DVT",
    short_name: "Wells DVT",
    category: "critical_care",
    description: "Deep vein thrombosis probability",
    inputs: {
      active_cancer: { type: "boolean", title: "Active Cancer", default: false },
      paralysis_immobilization: { type: "boolean", title: "Paralysis or Immobilization", default: false },
      bedridden_surgery: { type: "boolean", title: "Bedridden >3 days or Surgery <12 weeks", default: false },
      localized_tenderness: { type: "boolean", title: "Localized Tenderness Along Deep Veins", default: false },
      entire_leg_swollen: { type: "boolean", title: "Entire Leg Swollen", default: false },
      calf_swelling_3cm: { type: "boolean", title: "Calf Swelling >3cm vs Other Leg", default: false },
      pitting_edema: { type: "boolean", title: "Pitting Edema (Symptomatic Leg)", default: false },
      collateral_veins: { type: "boolean", title: "Collateral Superficial Veins", default: false },
      previous_dvt: { type: "boolean", title: "Previous DVT", default: false },
      alternative_diagnosis_likely: { type: "boolean", title: "Alternative Diagnosis at Least as Likely (-2)", default: false },
    },
    required: [],
  },
  corrected_calcium: {
    id: "corrected_calcium",
    name: "Corrected Calcium",
    short_name: "Corr Ca",
    category: "laboratory",
    description: "Albumin-corrected calcium level",
    inputs: {
      calcium: { type: "number", title: "Total Calcium", description: "mg/dL", minimum: 4, maximum: 20 },
      albumin: { type: "number", title: "Serum Albumin", description: "g/dL", minimum: 0.5, maximum: 6 },
    },
    required: ["calcium", "albumin"],
  },
  anion_gap: {
    id: "anion_gap",
    name: "Anion Gap",
    short_name: "AG",
    category: "laboratory",
    description: "Serum anion gap calculation",
    inputs: {
      sodium: { type: "number", title: "Sodium", description: "mEq/L", minimum: 100, maximum: 180 },
      chloride: { type: "number", title: "Chloride", description: "mEq/L", minimum: 70, maximum: 130 },
      bicarbonate: { type: "number", title: "Bicarbonate", description: "mEq/L", minimum: 5, maximum: 50 },
      albumin: { type: "number", title: "Albumin (optional)", description: "g/dL for correction", minimum: 0.5, maximum: 6 },
    },
    required: ["sodium", "chloride", "bicarbonate"],
  },
  ascvd: {
    id: "ascvd",
    name: "ASCVD 10-Year Risk",
    short_name: "ASCVD",
    category: "cardiovascular",
    description: "10-year atherosclerotic cardiovascular disease risk using Pooled Cohort Equations",
    inputs: {
      age: { type: "number", title: "Age", description: "Years (40-79)", minimum: 40, maximum: 79 },
      sex: { type: "string", title: "Sex", enum: ["male", "female"] },
      race: { type: "string", title: "Race", enum: ["white", "african_american", "other"] },
      total_cholesterol: { type: "number", title: "Total Cholesterol", description: "mg/dL", minimum: 130, maximum: 320 },
      hdl_cholesterol: { type: "number", title: "HDL Cholesterol", description: "mg/dL", minimum: 20, maximum: 100 },
      systolic_bp: { type: "number", title: "Systolic BP", description: "mmHg", minimum: 90, maximum: 200 },
      bp_treated: { type: "boolean", title: "On BP Medication", default: false },
      diabetes: { type: "boolean", title: "Has Diabetes", default: false },
      smoker: { type: "boolean", title: "Current Smoker", default: false },
    },
    required: ["age", "sex", "race", "total_cholesterol", "hdl_cholesterol", "systolic_bp"],
  },
  uacr: {
    id: "uacr",
    name: "UACR Interpretation",
    short_name: "UACR",
    category: "renal",
    description: "Urine albumin-to-creatinine ratio interpretation",
    inputs: {
      uacr: { type: "number", title: "UACR", description: "mg/g", minimum: 0, maximum: 10000 },
    },
    required: ["uacr"],
  },
  sofa: {
    id: "sofa",
    name: "SOFA Score",
    short_name: "SOFA",
    category: "critical_care",
    description: "Sequential organ failure assessment",
    inputs: {
      pao2_fio2: { type: "number", title: "PaO2/FiO2 Ratio", minimum: 0, maximum: 700 },
      on_ventilator: { type: "boolean", title: "On Mechanical Ventilation", default: false },
      platelets: { type: "number", title: "Platelets", description: "10^3/uL", minimum: 0, maximum: 1000 },
      bilirubin: { type: "number", title: "Bilirubin", description: "mg/dL", minimum: 0, maximum: 50 },
      map: { type: "number", title: "Mean Arterial Pressure", description: "mmHg", minimum: 0, maximum: 300 },
      vasopressor: { type: "string", title: "Vasopressor Use", enum: ["none", "dopamine_low", "dobutamine", "dopamine_high", "epi_low", "norepi_low", "high_dose"] },
      gcs: { type: "number", title: "Glasgow Coma Scale", minimum: 3, maximum: 15 },
      creatinine: { type: "number", title: "Creatinine", description: "mg/dL", minimum: 0, maximum: 20 },
      urine_output: { type: "number", title: "24h Urine Output (optional)", description: "mL", minimum: 0, maximum: 10000 },
    },
    required: ["pao2_fio2", "platelets", "bilirubin", "map", "gcs", "creatinine"],
  },
};

const categoryIcons: Record<string, React.ReactNode> = {
  cardiovascular: <Heart className="h-5 w-5" />,
  renal: <Droplets className="h-5 w-5" />,
  hepatic: <Activity className="h-5 w-5" />,
  critical_care: <Gauge className="h-5 w-5" />,
  general: <Scale className="h-5 w-5" />,
  laboratory: <FlaskConical className="h-5 w-5" />,
};

const categoryColors: Record<string, string> = {
  cardiovascular: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  renal: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  hepatic: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  critical_care: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  general: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  laboratory: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
};

const riskLevelStyles: Record<string, { bg: string; icon: React.ReactNode; label: string }> = {
  low: { bg: "bg-green-500", icon: <CheckCircle className="h-5 w-5" />, label: "Low Risk" },
  low_moderate: { bg: "bg-green-400", icon: <CheckCircle className="h-5 w-5" />, label: "Low-Moderate Risk" },
  moderate: { bg: "bg-amber-500", icon: <Info className="h-5 w-5" />, label: "Moderate Risk" },
  moderate_high: { bg: "bg-orange-500", icon: <AlertTriangle className="h-5 w-5" />, label: "Moderate-High Risk" },
  high: { bg: "bg-red-500", icon: <AlertCircle className="h-5 w-5" />, label: "High Risk" },
  very_high: { bg: "bg-red-700", icon: <AlertCircle className="h-5 w-5" />, label: "Very High Risk" },
};

// Client-side calculation functions (simplified versions)
function calculateClientSide(calculatorId: string, inputs: Record<string, any>): CalculationResult | null {
  // This would normally call the backend API
  // For demo purposes, implementing a few calculators client-side

  switch (calculatorId) {
    case "bmi": {
      const weight = inputs.weight_kg;
      const height = inputs.height_cm / 100;
      const bmi = weight / (height * height);
      let risk_level = "low";
      let interpretation = "Normal Weight";
      let recommendations = ["Maintain healthy lifestyle"];

      if (bmi < 18.5) {
        risk_level = "moderate";
        interpretation = "Underweight";
        recommendations = ["Nutritional assessment recommended", "Consider dietary counseling"];
      } else if (bmi >= 25 && bmi < 30) {
        risk_level = "moderate";
        interpretation = "Overweight";
        recommendations = ["Lifestyle modifications", "Screen for metabolic syndrome"];
      } else if (bmi >= 30 && bmi < 35) {
        risk_level = "high";
        interpretation = "Obese Class I";
        recommendations = ["Intensive lifestyle intervention", "Consider pharmacotherapy"];
      } else if (bmi >= 35) {
        risk_level = "very_high";
        interpretation = bmi >= 40 ? "Obese Class III (Morbid Obesity)" : "Obese Class II";
        recommendations = ["Bariatric surgery evaluation", "Intensive medical management"];
      }

      return {
        calculator_id: "bmi",
        calculator_name: "Body Mass Index (BMI)",
        score: Math.round(bmi * 10) / 10,
        score_unit: "kg/m2",
        risk_level,
        interpretation,
        recommendations,
        components: { weight_kg: weight, height_cm: inputs.height_cm },
        references: ["WHO BMI Classification"],
        formula_used: "BMI = weight(kg) / height(m)^2",
        warnings: [],
      };
    }

    case "egfr_ckdepi": {
      const cr = inputs.creatinine;
      const age = inputs.age;
      const female = inputs.sex === "female";

      const kappa = female ? 0.7 : 0.9;
      const alpha = female ? -0.241 : -0.302;
      const scrRatio = cr / kappa;
      const minTerm = Math.pow(Math.min(scrRatio, 1), alpha);
      const maxTerm = Math.pow(Math.max(scrRatio, 1), -1.2);
      const ageTerm = Math.pow(0.9938, age);
      const sexTerm = female ? 1.012 : 1;
      const egfr = Math.round(142 * minTerm * maxTerm * ageTerm * sexTerm * 10) / 10;

      let risk_level = "low";
      let interpretation = "CKD Stage G1: Normal or high function";
      let recommendations = ["Annual monitoring if risk factors", "Control BP and diabetes"];

      if (egfr < 15) {
        risk_level = "very_high";
        interpretation = "CKD Stage G5: Kidney failure";
        recommendations = ["Initiate dialysis or transplant evaluation", "Intensive nephrology management"];
      } else if (egfr < 30) {
        risk_level = "high";
        interpretation = "CKD Stage G4: Severely decreased";
        recommendations = ["Nephrology co-management essential", "Plan for dialysis or transplant"];
      } else if (egfr < 45) {
        risk_level = "moderate_high";
        interpretation = "CKD Stage G3b: Moderate-severe decrease";
        recommendations = ["Nephrology referral recommended", "Strict avoidance of nephrotoxins"];
      } else if (egfr < 60) {
        risk_level = "moderate";
        interpretation = "CKD Stage G3a: Mild-moderate decrease";
        recommendations = ["Monitor eGFR every 6 months", "Screen for CKD complications"];
      } else if (egfr < 90) {
        risk_level = "low_moderate";
        interpretation = "CKD Stage G2: Mildly decreased";
        recommendations = ["Monitor eGFR annually", "Optimize blood pressure control"];
      }

      return {
        calculator_id: "egfr_ckdepi",
        calculator_name: "CKD-EPI eGFR (2021)",
        score: egfr,
        score_unit: "mL/min/1.73m2",
        risk_level,
        interpretation,
        recommendations,
        components: { creatinine: cr, age, sex: inputs.sex },
        references: ["Inker LA, et al. NEJM 2021"],
        formula_used: "eGFR = 142 x min(Scr/k,1)^a x max(Scr/k,1)^-1.2 x 0.9938^Age x (1.012 if female)",
        warnings: [],
      };
    }

    case "cha2ds2_vasc": {
      let score = 0;
      const components: Record<string, number> = {};

      if (inputs.chf) { score += 1; components["CHF"] = 1; }
      if (inputs.hypertension) { score += 1; components["Hypertension"] = 1; }
      if (inputs.age >= 75) { score += 2; components["Age >=75"] = 2; }
      else if (inputs.age >= 65) { score += 1; components["Age 65-74"] = 1; }
      if (inputs.diabetes) { score += 1; components["Diabetes"] = 1; }
      if (inputs.stroke_tia) { score += 2; components["Stroke/TIA"] = 2; }
      if (inputs.vascular_disease) { score += 1; components["Vascular disease"] = 1; }
      if (inputs.sex === "female") { score += 1; components["Female sex"] = 1; }

      const strokeRates: Record<number, number> = {0: 0, 1: 1.3, 2: 2.2, 3: 3.2, 4: 4.0, 5: 6.7, 6: 9.8, 7: 9.6, 8: 12.5, 9: 15.2};
      const strokeRate = strokeRates[Math.min(score, 9)] || 15.2;

      let risk_level = score === 0 ? "low" : score === 1 ? "low_moderate" : score === 2 ? "moderate" : score <= 4 ? "high" : "very_high";

      return {
        calculator_id: "cha2ds2_vasc",
        calculator_name: "CHA2DS2-VASc Score",
        score,
        score_unit: "points",
        risk_level,
        interpretation: `Annual stroke rate ~${strokeRate}%`,
        recommendations: score === 0
          ? ["Anticoagulation generally not recommended", "May consider no therapy"]
          : score === 1
          ? ["Consider oral anticoagulation", "Shared decision-making based on bleeding risk"]
          : ["Oral anticoagulation recommended", "DOAC preferred over warfarin"],
        components,
        references: ["2019 AHA/ACC/HRS AF Guidelines"],
        formula_used: "C(HF)+H(ypertension)+A2(ge>=75)+D(iabetes)+S2(troke)+V(ascular)+A(ge 65-74)+Sc(female)",
        warnings: [],
      };
    }

    default:
      return null;
  }
}

export default function CalculatorPage({ params }: { params: Promise<{ calculatorId: string }> }) {
  const { calculatorId } = use(params);
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isCalculating, setIsCalculating] = useState(false);

  const calculator = calculatorDefinitions[calculatorId];

  // Initialize form values with defaults
  useMemo(() => {
    if (calculator) {
      const defaults: Record<string, any> = {};
      Object.entries(calculator.inputs).forEach(([key, def]) => {
        if (def.default !== undefined) {
          defaults[key] = def.default;
        } else if (def.type === "boolean") {
          defaults[key] = false;
        }
      });
      setFormValues(defaults);
    }
  }, [calculatorId]);

  const handleInputChange = (key: string, value: any) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setResult(null);
  };

  const validateInputs = (): boolean => {
    const newErrors: Record<string, string> = {};

    for (const key of calculator.required) {
      const value = formValues[key];
      const def = calculator.inputs[key];

      if (value === undefined || value === null || value === "") {
        newErrors[key] = "This field is required";
        continue;
      }

      if (def.type === "number") {
        const numVal = Number(value);
        if (isNaN(numVal)) {
          newErrors[key] = "Must be a valid number";
        } else if (def.minimum !== undefined && numVal < def.minimum) {
          newErrors[key] = `Minimum value is ${def.minimum}`;
        } else if (def.maximum !== undefined && numVal > def.maximum) {
          newErrors[key] = `Maximum value is ${def.maximum}`;
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleCalculate = async () => {
    if (!validateInputs()) return;

    setIsCalculating(true);

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 300));

    const calculationResult = calculateClientSide(calculatorId, formValues);
    if (calculationResult) {
      setResult(calculationResult);
    } else {
      // Fallback for unimplemented calculators
      setResult({
        calculator_id: calculatorId,
        calculator_name: calculator.name,
        score: 0,
        score_unit: "points",
        risk_level: "moderate",
        interpretation: "Calculator not yet implemented client-side. Please use the API.",
        recommendations: ["Connect to backend API for full functionality"],
        components: formValues,
        references: [],
        formula_used: "",
        warnings: ["Client-side calculation not available for this calculator"],
      });
    }

    setIsCalculating(false);
  };

  const handleReset = () => {
    const defaults: Record<string, any> = {};
    Object.entries(calculator.inputs).forEach(([key, def]) => {
      if (def.default !== undefined) {
        defaults[key] = def.default;
      } else if (def.type === "boolean") {
        defaults[key] = false;
      }
    });
    setFormValues(defaults);
    setResult(null);
    setErrors({});
  };

  if (!calculator) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="py-12">
            <div className="text-center space-y-4">
              <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground" />
              <h2 className="text-xl font-semibold">Calculator Not Found</h2>
              <p className="text-muted-foreground">
                The calculator "{calculatorId}" does not exist.
              </p>
              <Link href="/clinical/calculators">
                <Button>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Calculators
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const riskStyle = result ? riskLevelStyles[result.risk_level] || riskLevelStyles.moderate : null;
  const riskProgress = result
    ? { low: 16, low_moderate: 33, moderate: 50, moderate_high: 66, high: 83, very_high: 100 }[result.risk_level] || 50
    : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/clinical/calculators">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${categoryColors[calculator.category]}`}>
              {categoryIcons[calculator.category] || <Calculator className="h-6 w-6" />}
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">{calculator.name}</h1>
              <p className="text-sm text-muted-foreground capitalize">
                {calculator.category.replace("_", " ")}
              </p>
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsFavorite(!isFavorite)}
        >
          {isFavorite ? (
            <>
              <Star className="mr-2 h-4 w-4 text-amber-500 fill-amber-500" />
              Favorited
            </>
          ) : (
            <>
              <StarOff className="mr-2 h-4 w-4" />
              Add to Favorites
            </>
          )}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Form */}
        <Card>
          <CardHeader>
            <CardTitle>Input Parameters</CardTitle>
            <CardDescription>{calculator.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(calculator.inputs).map(([key, def]) => (
              <div key={key} className="space-y-2">
                <Label htmlFor={key} className="flex items-center gap-2">
                  {def.title || key}
                  {calculator.required.includes(key) && (
                    <span className="text-red-500">*</span>
                  )}
                  {def.description && (
                    <span className="text-xs text-muted-foreground">
                      ({def.description})
                    </span>
                  )}
                </Label>

                {def.type === "boolean" ? (
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id={key}
                      checked={!!formValues[key]}
                      onCheckedChange={(checked) => handleInputChange(key, checked)}
                    />
                    <span className="text-sm text-muted-foreground">
                      {formValues[key] ? "Yes" : "No"}
                    </span>
                  </div>
                ) : def.enum ? (
                  <Select
                    value={formValues[key] || ""}
                    onValueChange={(value) => handleInputChange(key, value)}
                  >
                    <SelectTrigger id={key}>
                      <SelectValue placeholder="Select..." />
                    </SelectTrigger>
                    <SelectContent>
                      {def.enum.map((opt) => (
                        <SelectItem key={opt} value={opt}>
                          {opt.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    id={key}
                    type="number"
                    min={def.minimum}
                    max={def.maximum}
                    step={def.type === "number" ? "any" : 1}
                    value={formValues[key] ?? ""}
                    onChange={(e) => handleInputChange(key, e.target.value ? Number(e.target.value) : "")}
                    placeholder={def.minimum !== undefined && def.maximum !== undefined
                      ? `${def.minimum} - ${def.maximum}`
                      : "Enter value"}
                    className={errors[key] ? "border-red-500" : ""}
                  />
                )}

                {errors[key] && (
                  <p className="text-xs text-red-500">{errors[key]}</p>
                )}
              </div>
            ))}
          </CardContent>
          <CardFooter className="flex gap-2">
            <Button onClick={handleCalculate} className="flex-1" disabled={isCalculating}>
              <Calculator className="mr-2 h-4 w-4" />
              {isCalculating ? "Calculating..." : "Calculate"}
            </Button>
            <Button variant="outline" onClick={handleReset}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
          </CardFooter>
        </Card>

        {/* Result Display */}
        <div className="space-y-6">
          {result ? (
            <>
              {/* Score Card */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2">
                    {riskStyle?.icon}
                    Result
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-lg bg-muted">
                    <div>
                      <p className="text-sm text-muted-foreground">Score</p>
                      <p className="text-4xl font-bold">
                        {result.score}
                        <span className="text-lg font-normal text-muted-foreground ml-2">
                          {result.score_unit}
                        </span>
                      </p>
                    </div>
                    <Badge className={`${riskStyle?.bg} text-white px-3 py-1 text-sm`}>
                      {riskStyle?.label}
                    </Badge>
                  </div>

                  {/* Risk Gauge */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Low</span>
                      <span>High</span>
                    </div>
                    <Progress value={riskProgress} className="h-3" />
                  </div>
                </CardContent>
              </Card>

              {/* Interpretation */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Interpretation</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{result.interpretation}</p>
                </CardContent>
              </Card>

              {/* Recommendations */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {result.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm">
                        <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              {/* Warnings */}
              {result.warnings.length > 0 && (
                <Card className="border-amber-200 dark:border-amber-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2 text-amber-600">
                      <AlertTriangle className="h-4 w-4" />
                      Warnings
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1">
                      {result.warnings.map((warning, idx) => (
                        <li key={idx} className="text-sm text-amber-600">{warning}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* References */}
              {result.references.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      References
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1">
                      {result.references.map((ref, idx) => (
                        <li key={idx} className="text-sm text-muted-foreground">{ref}</li>
                      ))}
                    </ul>
                    {result.formula_used && (
                      <div className="mt-4 pt-4 border-t">
                        <p className="text-xs text-muted-foreground">
                          <strong>Formula:</strong> {result.formula_used}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center space-y-4">
                  <div className="flex justify-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <Calculator className="h-8 w-8 text-muted-foreground" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium">Enter Values to Calculate</h3>
                    <p className="text-muted-foreground">
                      Fill in the required fields and click Calculate
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
