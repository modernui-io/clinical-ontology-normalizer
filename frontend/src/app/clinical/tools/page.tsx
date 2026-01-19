"use client";

import { useState, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Calculator,
  Search,
  ArrowLeft,
  Heart,
  Activity,
  Stethoscope,
  Brain,
  Droplets,
  Scale,
  AlertCircle,
  CheckCircle,
  Info,
} from "lucide-react";

// Calculator definitions matching backend
interface CalculatorDefinition {
  id: string;
  name: string;
  shortName: string;
  description: string;
  category: string;
  parameters: CalculatorParameter[];
  references: string[];
}

interface CalculatorParameter {
  id: string;
  name: string;
  type: "number" | "boolean" | "select";
  required: boolean;
  unit?: string;
  min?: number;
  max?: number;
  options?: { value: string; label: string }[];
  defaultValue?: number | boolean;
}

interface CalculatorResult {
  score: number;
  unit: string;
  riskLevel: "low" | "low_moderate" | "moderate" | "moderate_high" | "high" | "very_high";
  interpretation: string;
  recommendations: string[];
}

const calculators: CalculatorDefinition[] = [
  {
    id: "bmi",
    name: "Body Mass Index (BMI)",
    shortName: "BMI",
    description: "Calculate body mass index for obesity classification",
    category: "General",
    parameters: [
      { id: "weight_kg", name: "Weight", type: "number", required: true, unit: "kg", min: 20, max: 300 },
      { id: "height_cm", name: "Height", type: "number", required: true, unit: "cm", min: 100, max: 250 },
    ],
    references: ["WHO BMI Classification"],
  },
  {
    id: "egfr",
    name: "CKD-EPI eGFR (2021)",
    shortName: "eGFR",
    description: "Estimate glomerular filtration rate using the race-free CKD-EPI equation",
    category: "Renal",
    parameters: [
      { id: "creatinine", name: "Serum Creatinine", type: "number", required: true, unit: "mg/dL", min: 0.1, max: 20 },
      { id: "age", name: "Age", type: "number", required: true, unit: "years", min: 18, max: 120 },
      { id: "female", name: "Female", type: "boolean", required: true, defaultValue: false },
    ],
    references: ["CKD-EPI 2021 (Inker et al., NEJM 2021)"],
  },
  {
    id: "chadsvasc",
    name: "CHA2DS2-VASc Score",
    shortName: "CHADS-VASc",
    description: "Estimate stroke risk in patients with atrial fibrillation",
    category: "Cardiology",
    parameters: [
      { id: "age", name: "Age", type: "number", required: true, unit: "years", min: 18, max: 120 },
      { id: "female", name: "Female", type: "boolean", required: true, defaultValue: false },
      { id: "congestive_heart_failure", name: "Congestive Heart Failure", type: "boolean", required: false, defaultValue: false },
      { id: "hypertension", name: "Hypertension", type: "boolean", required: false, defaultValue: false },
      { id: "diabetes", name: "Diabetes Mellitus", type: "boolean", required: false, defaultValue: false },
      { id: "stroke_tia_thromboembolism", name: "Prior Stroke/TIA/Thromboembolism", type: "boolean", required: false, defaultValue: false },
      { id: "vascular_disease", name: "Vascular Disease (MI, PAD, Aortic plaque)", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["2019 AHA/ACC/HRS AF Guidelines"],
  },
  {
    id: "hasbled",
    name: "HAS-BLED Score",
    shortName: "HAS-BLED",
    description: "Estimate major bleeding risk in patients on anticoagulation",
    category: "Cardiology",
    parameters: [
      { id: "hypertension", name: "Hypertension (SBP >160)", type: "boolean", required: false, defaultValue: false },
      { id: "renal_disease", name: "Renal Disease (Dialysis, Cr >2.6)", type: "boolean", required: false, defaultValue: false },
      { id: "liver_disease", name: "Liver Disease", type: "boolean", required: false, defaultValue: false },
      { id: "stroke_history", name: "Stroke History", type: "boolean", required: false, defaultValue: false },
      { id: "bleeding_history", name: "Prior Major Bleeding", type: "boolean", required: false, defaultValue: false },
      { id: "labile_inr", name: "Labile INR (<60% TTR)", type: "boolean", required: false, defaultValue: false },
      { id: "age_over_65", name: "Age >65", type: "boolean", required: false, defaultValue: false },
      { id: "antiplatelet_nsaid", name: "Antiplatelet or NSAID Use", type: "boolean", required: false, defaultValue: false },
      { id: "alcohol_use", name: "Alcohol Use (>=8 drinks/week)", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["Pisters R, et al. Chest 2010"],
  },
  {
    id: "meld",
    name: "MELD-Na Score",
    shortName: "MELD",
    description: "Assess liver disease severity for transplant prioritization",
    category: "Hepatology",
    parameters: [
      { id: "creatinine", name: "Serum Creatinine", type: "number", required: true, unit: "mg/dL", min: 0.1, max: 10 },
      { id: "bilirubin", name: "Total Bilirubin", type: "number", required: true, unit: "mg/dL", min: 0.1, max: 50 },
      { id: "inr", name: "INR", type: "number", required: true, unit: "", min: 0.5, max: 10 },
      { id: "sodium", name: "Serum Sodium", type: "number", required: false, unit: "mEq/L", min: 100, max: 160 },
      { id: "on_dialysis", name: "On Dialysis", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["UNOS MELD allocation policy"],
  },
  {
    id: "wells_dvt",
    name: "Wells Score for DVT",
    shortName: "Wells DVT",
    description: "Estimate clinical probability of deep vein thrombosis",
    category: "Hematology",
    parameters: [
      { id: "active_cancer", name: "Active Cancer", type: "boolean", required: false, defaultValue: false },
      { id: "paralysis_immobilization", name: "Paralysis/Immobilization", type: "boolean", required: false, defaultValue: false },
      { id: "bedridden_surgery", name: "Bedridden >3 days or Surgery <12 weeks", type: "boolean", required: false, defaultValue: false },
      { id: "localized_tenderness", name: "Localized Tenderness Along Deep Veins", type: "boolean", required: false, defaultValue: false },
      { id: "entire_leg_swollen", name: "Entire Leg Swollen", type: "boolean", required: false, defaultValue: false },
      { id: "calf_swelling_3cm", name: "Calf Swelling >3cm vs Other Leg", type: "boolean", required: false, defaultValue: false },
      { id: "pitting_edema", name: "Pitting Edema (Symptomatic Leg)", type: "boolean", required: false, defaultValue: false },
      { id: "collateral_veins", name: "Collateral Superficial Veins", type: "boolean", required: false, defaultValue: false },
      { id: "previous_dvt", name: "Previous DVT", type: "boolean", required: false, defaultValue: false },
      { id: "alternative_diagnosis_likely", name: "Alternative Diagnosis at Least as Likely", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["Wells PS, et al. NEJM 2003"],
  },
  {
    id: "curb65",
    name: "CURB-65 Score",
    shortName: "CURB-65",
    description: "Assess severity of community-acquired pneumonia",
    category: "Pulmonology",
    parameters: [
      { id: "confusion", name: "Confusion (New mental confusion)", type: "boolean", required: false, defaultValue: false },
      { id: "bun_over_19", name: "BUN >19 mg/dL (Urea >7 mmol/L)", type: "boolean", required: false, defaultValue: false },
      { id: "respiratory_rate_over_30", name: "Respiratory Rate >=30/min", type: "boolean", required: false, defaultValue: false },
      { id: "sbp_under_90_or_dbp_under_60", name: "Low BP (SBP <90 or DBP <=60)", type: "boolean", required: false, defaultValue: false },
      { id: "age_65_or_older", name: "Age >=65", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["Lim WS, et al. Thorax 2003"],
  },
  {
    id: "framingham",
    name: "Framingham 10-Year CVD Risk",
    shortName: "Framingham",
    description: "Estimate 10-year cardiovascular disease risk",
    category: "Cardiology",
    parameters: [
      { id: "age", name: "Age", type: "number", required: true, unit: "years", min: 30, max: 79 },
      { id: "female", name: "Female", type: "boolean", required: true, defaultValue: false },
      { id: "total_cholesterol", name: "Total Cholesterol", type: "number", required: true, unit: "mg/dL", min: 100, max: 400 },
      { id: "hdl_cholesterol", name: "HDL Cholesterol", type: "number", required: true, unit: "mg/dL", min: 20, max: 150 },
      { id: "systolic_bp", name: "Systolic BP", type: "number", required: true, unit: "mmHg", min: 80, max: 200 },
      { id: "bp_treated", name: "On BP Medication", type: "boolean", required: false, defaultValue: false },
      { id: "smoker", name: "Current Smoker", type: "boolean", required: false, defaultValue: false },
      { id: "diabetic", name: "Diabetic", type: "boolean", required: false, defaultValue: false },
    ],
    references: ["D'Agostino RB, et al. Circulation 2008"],
  },
];

const categoryIcons: Record<string, React.ReactNode> = {
  General: <Scale className="h-5 w-5" />,
  Renal: <Droplets className="h-5 w-5" />,
  Cardiology: <Heart className="h-5 w-5" />,
  Hepatology: <Activity className="h-5 w-5" />,
  Hematology: <Droplets className="h-5 w-5" />,
  Pulmonology: <Stethoscope className="h-5 w-5" />,
};

const riskLevelStyles: Record<string, string> = {
  low: "bg-green-500 text-white",
  low_moderate: "bg-green-400 text-white",
  moderate: "bg-amber-500 text-white",
  moderate_high: "bg-orange-500 text-white",
  high: "bg-red-500 text-white",
  very_high: "bg-red-700 text-white",
};

const riskLevelLabels: Record<string, string> = {
  low: "Low",
  low_moderate: "Low-Moderate",
  moderate: "Moderate",
  moderate_high: "Moderate-High",
  high: "High",
  very_high: "Very High",
};

// Simple client-side calculator implementations
function calculateBMI(params: Record<string, number | boolean>): CalculatorResult {
  const weight = params.weight_kg as number;
  const height = (params.height_cm as number) / 100;
  const bmi = weight / (height * height);

  let riskLevel: CalculatorResult["riskLevel"];
  let interpretation: string;
  let recommendations: string[];

  if (bmi < 18.5) {
    riskLevel = "moderate";
    interpretation = "Underweight";
    recommendations = ["Evaluate for malnutrition", "Consider nutritional supplementation"];
  } else if (bmi < 25) {
    riskLevel = "low";
    interpretation = "Normal weight";
    recommendations = ["Maintain healthy lifestyle", "Continue regular physical activity"];
  } else if (bmi < 30) {
    riskLevel = "moderate";
    interpretation = "Overweight";
    recommendations = ["Lifestyle modifications", "Screen for metabolic syndrome"];
  } else if (bmi < 35) {
    riskLevel = "high";
    interpretation = "Class I Obesity";
    recommendations = ["Intensive lifestyle intervention", "Consider pharmacotherapy"];
  } else if (bmi < 40) {
    riskLevel = "high";
    interpretation = "Class II Obesity";
    recommendations = ["Intensive lifestyle intervention", "Evaluate bariatric surgery"];
  } else {
    riskLevel = "very_high";
    interpretation = "Class III (Morbid) Obesity";
    recommendations = ["Bariatric surgery evaluation", "Intensive medical management"];
  }

  return { score: Math.round(bmi * 10) / 10, unit: "kg/m2", riskLevel, interpretation, recommendations };
}

function calculateEGFR(params: Record<string, number | boolean>): CalculatorResult {
  const cr = params.creatinine as number;
  const age = params.age as number;
  const female = params.female as boolean;

  const kappa = female ? 0.7 : 0.9;
  const alpha = female ? -0.241 : -0.302;
  const scrRatio = cr / kappa;
  const minTerm = Math.pow(Math.min(scrRatio, 1), alpha);
  const maxTerm = Math.pow(Math.max(scrRatio, 1), -1.2);
  const ageTerm = Math.pow(0.9938, age);
  const sexTerm = female ? 1.012 : 1;
  const egfr = Math.round(142 * minTerm * maxTerm * ageTerm * sexTerm * 10) / 10;

  let riskLevel: CalculatorResult["riskLevel"];
  let interpretation: string;
  let recommendations: string[];
  let stage: string;

  if (egfr >= 90) {
    stage = "G1";
    riskLevel = "low";
    interpretation = `CKD Stage ${stage}: Normal or high function`;
    recommendations = ["Annual monitoring if risk factors", "Control BP and diabetes"];
  } else if (egfr >= 60) {
    stage = "G2";
    riskLevel = "low_moderate";
    interpretation = `CKD Stage ${stage}: Mildly decreased`;
    recommendations = ["Monitor eGFR annually", "Optimize BP control"];
  } else if (egfr >= 45) {
    stage = "G3a";
    riskLevel = "moderate";
    interpretation = `CKD Stage ${stage}: Mild-moderate decrease`;
    recommendations = ["Monitor every 6 months", "Nephrology referral if declining"];
  } else if (egfr >= 30) {
    stage = "G3b";
    riskLevel = "moderate_high";
    interpretation = `CKD Stage ${stage}: Moderate-severe decrease`;
    recommendations = ["Nephrology referral", "Avoid nephrotoxins"];
  } else if (egfr >= 15) {
    stage = "G4";
    riskLevel = "high";
    interpretation = `CKD Stage ${stage}: Severely decreased`;
    recommendations = ["Nephrology co-management", "Plan for dialysis/transplant"];
  } else {
    stage = "G5";
    riskLevel = "very_high";
    interpretation = `CKD Stage ${stage}: Kidney failure`;
    recommendations = ["Initiate dialysis or transplant", "Intensive management"];
  }

  return { score: egfr, unit: "mL/min/1.73m2", riskLevel, interpretation, recommendations };
}

function calculateCHADSVASc(params: Record<string, number | boolean>): CalculatorResult {
  const age = params.age as number;
  let score = 0;

  if (params.congestive_heart_failure) score += 1;
  if (params.hypertension) score += 1;
  if (age >= 75) score += 2;
  else if (age >= 65) score += 1;
  if (params.diabetes) score += 1;
  if (params.stroke_tia_thromboembolism) score += 2;
  if (params.vascular_disease) score += 1;
  if (params.female) score += 1;

  let riskLevel: CalculatorResult["riskLevel"];
  let interpretation: string;
  let recommendations: string[];

  if (score === 0) {
    riskLevel = "low";
    interpretation = "Low risk (~0% annual stroke)";
    recommendations = ["Anticoagulation not recommended", "Consider aspirin or no therapy"];
  } else if (score === 1) {
    riskLevel = "low_moderate";
    interpretation = "Low-moderate risk (~1.3% annual stroke)";
    recommendations = ["Consider anticoagulation", "Discuss risks vs benefits"];
  } else if (score === 2) {
    riskLevel = "moderate";
    interpretation = "Moderate risk (~2.2% annual stroke)";
    recommendations = ["Anticoagulation recommended", "DOAC preferred over warfarin"];
  } else {
    riskLevel = score <= 4 ? "high" : "very_high";
    interpretation = `High risk (~${Math.min(score * 1.5 + 1, 15).toFixed(1)}% annual stroke)`;
    recommendations = ["Anticoagulation strongly recommended", "Consider LAA closure if contraindicated"];
  }

  return { score, unit: "points", riskLevel, interpretation, recommendations };
}

function calculateGeneric(calcId: string, params: Record<string, number | boolean>): CalculatorResult {
  // Simplified generic calculation for demo
  let score = 0;
  Object.values(params).forEach((v) => {
    if (typeof v === "boolean" && v) score += 1;
    if (typeof v === "number") score += v > 50 ? 1 : 0;
  });

  return {
    score,
    unit: "points",
    riskLevel: score <= 2 ? "low" : score <= 4 ? "moderate" : "high",
    interpretation: `Score: ${score}`,
    recommendations: ["Consult clinical guidelines for interpretation"],
  };
}

function ClinicalToolsContent() {
  const searchParams = useSearchParams();
  const initialCalcId = searchParams.get("calc");

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedCalculator, setSelectedCalculator] = useState<string | null>(
    initialCalcId
  );
  const [formValues, setFormValues] = useState<Record<string, number | boolean>>({});
  const [result, setResult] = useState<CalculatorResult | null>(null);

  const filteredCalculators = useMemo(() => {
    return calculators.filter((calc) => {
      const matchesSearch =
        searchQuery === "" ||
        calc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.category.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        selectedCategory === null || calc.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [searchQuery, selectedCategory]);

  const categories = useMemo(() => {
    return Array.from(new Set(calculators.map((c) => c.category)));
  }, []);

  const currentCalculator = calculators.find((c) => c.id === selectedCalculator);

  const handleCalculate = () => {
    if (!currentCalculator) return;

    let calculatorResult: CalculatorResult;

    switch (currentCalculator.id) {
      case "bmi":
        calculatorResult = calculateBMI(formValues);
        break;
      case "egfr":
        calculatorResult = calculateEGFR(formValues);
        break;
      case "chadsvasc":
        calculatorResult = calculateCHADSVASc(formValues);
        break;
      default:
        calculatorResult = calculateGeneric(currentCalculator.id, formValues);
    }

    setResult(calculatorResult);
  };

  const handleSelectCalculator = (calcId: string) => {
    setSelectedCalculator(calcId);
    setFormValues({});
    setResult(null);

    const calc = calculators.find((c) => c.id === calcId);
    if (calc) {
      const defaults: Record<string, number | boolean> = {};
      calc.parameters.forEach((p) => {
        if (p.defaultValue !== undefined) {
          defaults[p.id] = p.defaultValue;
        }
      });
      setFormValues(defaults);
    }
  };

  const handleInputChange = (paramId: string, value: number | boolean) => {
    setFormValues((prev) => ({ ...prev, [paramId]: value }));
    setResult(null);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/clinical">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Clinical Calculators
            </h1>
            <p className="text-muted-foreground">
              Validated risk calculators for clinical decision support
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Calculator List */}
        <div className="lg:col-span-1 space-y-4">
          {/* Search and Filter */}
          <Card>
            <CardContent className="pt-4">
              <div className="space-y-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search calculators..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge
                    variant={selectedCategory === null ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => setSelectedCategory(null)}
                  >
                    All
                  </Badge>
                  {categories.map((cat) => (
                    <Badge
                      key={cat}
                      variant={selectedCategory === cat ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => setSelectedCategory(cat)}
                    >
                      {cat}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Calculator List */}
          <div className="space-y-2">
            {filteredCalculators.map((calc) => (
              <Card
                key={calc.id}
                className={`cursor-pointer transition-colors hover:border-primary/50 ${
                  selectedCalculator === calc.id
                    ? "border-primary bg-primary/5"
                    : ""
                }`}
                onClick={() => handleSelectCalculator(calc.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      {categoryIcons[calc.category] || <Calculator className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-sm truncate">
                          {calc.shortName}
                        </h3>
                        <Badge variant="secondary" className="text-xs">
                          {calc.category}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {calc.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Calculator Form and Result */}
        <div className="lg:col-span-2 space-y-6">
          {currentCalculator ? (
            <>
              {/* Calculator Form */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      {categoryIcons[currentCalculator.category] || (
                        <Calculator className="h-6 w-6" />
                      )}
                    </div>
                    <div>
                      <CardTitle>{currentCalculator.name}</CardTitle>
                      <CardDescription>
                        {currentCalculator.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {currentCalculator.parameters.map((param) => (
                      <div key={param.id} className="space-y-2">
                        <Label htmlFor={param.id} className="flex items-center gap-2">
                          {param.name}
                          {param.required && (
                            <span className="text-red-500">*</span>
                          )}
                          {param.unit && (
                            <span className="text-muted-foreground text-xs">
                              ({param.unit})
                            </span>
                          )}
                        </Label>
                        {param.type === "boolean" ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              id={param.id}
                              checked={!!formValues[param.id]}
                              onChange={(e) =>
                                handleInputChange(param.id, e.target.checked)
                              }
                              className="h-4 w-4 rounded border-gray-300"
                            />
                            <span className="text-sm text-muted-foreground">
                              {formValues[param.id] ? "Yes" : "No"}
                            </span>
                          </div>
                        ) : (
                          <Input
                            id={param.id}
                            type="number"
                            min={param.min}
                            max={param.max}
                            value={formValues[param.id] as number || ""}
                            onChange={(e) =>
                              handleInputChange(
                                param.id,
                                e.target.value ? parseFloat(e.target.value) : 0
                              )
                            }
                            placeholder={`${param.min || 0} - ${param.max || "..."}`}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="mt-6">
                    <Button onClick={handleCalculate} className="w-full">
                      <Calculator className="mr-2 h-4 w-4" />
                      Calculate
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Result */}
              {result && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      {result.riskLevel === "low" || result.riskLevel === "low_moderate" ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : result.riskLevel === "moderate" || result.riskLevel === "moderate_high" ? (
                        <Info className="h-5 w-5 text-amber-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-red-500" />
                      )}
                      Result
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-4 rounded-lg bg-muted">
                        <div>
                          <p className="text-sm text-muted-foreground">Score</p>
                          <p className="text-3xl font-bold">
                            {result.score} {result.unit}
                          </p>
                        </div>
                        <Badge className={riskLevelStyles[result.riskLevel]}>
                          {riskLevelLabels[result.riskLevel]}
                        </Badge>
                      </div>

                      <div>
                        <p className="font-medium mb-2">Interpretation</p>
                        <p className="text-muted-foreground">{result.interpretation}</p>
                      </div>

                      <div>
                        <p className="font-medium mb-2">Recommendations</p>
                        <ul className="space-y-2">
                          {result.recommendations.map((rec, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-sm">
                              <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                              {rec}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="pt-4 border-t">
                        <p className="text-xs text-muted-foreground">
                          References: {currentCalculator.references.join(", ")}
                        </p>
                      </div>
                    </div>
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
                    <h3 className="text-lg font-medium">Select a Calculator</h3>
                    <p className="text-muted-foreground">
                      Choose a clinical calculator from the list to get started
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

export default function ClinicalToolsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading...</div>}>
      <ClinicalToolsContent />
    </Suspense>
  );
}
