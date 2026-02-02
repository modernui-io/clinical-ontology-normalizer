"use client";

import { useState, use, useEffect } from "react";
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
import {
  Calculator,
  ArrowLeft,
  Heart,
  Activity,
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
  RefreshCw,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface CriterionLevel {
  suffix: string;
  points: number;
  display: string;
}

interface ThresholdLevel {
  operator: string;
  value: number | [number, number];
  points: number;
  display: string;
}

interface Criterion {
  name: string;
  display_name: string;
  type: "boolean" | "multi_level" | "threshold";
  points?: number;
  levels?: CriterionLevel[];
  thresholds?: ThresholdLevel[];
  unit?: string;
  description?: string;
}

interface Interpretation {
  min_score: number;
  max_score: number | null;
  risk_level: string;
  interpretation: string;
  recommendations: string[];
}

interface DataDrivenCalculatorDetail {
  id: string;
  name: string;
  short_name: string;
  category: string;
  calc_type: string;
  description: string;
  score_unit: string;
  criteria: Criterion[];
  has_age_scoring: boolean;
  interpretations: Interpretation[];
  references: string[];
  notes: string[];
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
  warnings: string[];
}

// Legacy calculator detail type (for fallback/hardcoded calculators)
interface LegacyInputDefinition {
  type: string;
  title?: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  default?: any;
  enum?: string[];
}

interface LegacyCalculatorDetail {
  id: string;
  name: string;
  short_name: string;
  category: string;
  description: string;
  inputs: Record<string, LegacyInputDefinition>;
  required: string[];
}

// =============================================================================
// Fallback Legacy Calculator Definitions (for non-data-driven calculators)
// =============================================================================

const legacyCalculatorDefinitions: Record<string, LegacyCalculatorDetail> = {
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
};

// =============================================================================
// UI Constants
// =============================================================================

const categoryIcons: Record<string, React.ReactNode> = {
  cardiovascular: <Heart className="h-5 w-5" />,
  renal: <Droplets className="h-5 w-5" />,
  hepatic: <Activity className="h-5 w-5" />,
  critical_care: <Gauge className="h-5 w-5" />,
  general: <Scale className="h-5 w-5" />,
  laboratory: <FlaskConical className="h-5 w-5" />,
  pulmonary: <Activity className="h-5 w-5" />,
  neurological: <Activity className="h-5 w-5" />,
  infectious: <Activity className="h-5 w-5" />,
  emergency: <AlertCircle className="h-5 w-5" />,
};

const categoryColors: Record<string, string> = {
  cardiovascular: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  renal: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  hepatic: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  critical_care: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  general: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  laboratory: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
  pulmonary: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  neurological: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
  infectious: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  emergency: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
};

const riskLevelStyles: Record<string, { bg: string; icon: React.ReactNode; label: string }> = {
  low: { bg: "bg-green-500", icon: <CheckCircle className="h-5 w-5" />, label: "Low Risk" },
  low_moderate: { bg: "bg-green-400", icon: <CheckCircle className="h-5 w-5" />, label: "Low-Moderate Risk" },
  moderate: { bg: "bg-amber-500", icon: <Info className="h-5 w-5" />, label: "Moderate Risk" },
  moderate_high: { bg: "bg-orange-500", icon: <AlertTriangle className="h-5 w-5" />, label: "Moderate-High Risk" },
  high: { bg: "bg-red-500", icon: <AlertCircle className="h-5 w-5" />, label: "High Risk" },
  very_high: { bg: "bg-red-700", icon: <AlertCircle className="h-5 w-5" />, label: "Very High Risk" },
};

// =============================================================================
// API Functions
// =============================================================================

async function fetchDataDrivenCalculator(calculatorId: string): Promise<DataDrivenCalculatorDetail | null> {
  try {
    const response = await fetch(`/api/calculators/definitions/${calculatorId}`);
    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Failed to fetch calculator: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching data-driven calculator:", error);
    return null;
  }
}

async function fetchClinicalCalculator(calculatorId: string): Promise<LegacyCalculatorDetail | null> {
  try {
    const response = await fetch(`/api/calculators/clinical/${calculatorId}`);
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching clinical calculator:", error);
    return null;
  }
}

async function executeDataDrivenCalculation(
  calculatorId: string,
  values: Record<string, boolean | number>,
  age?: number
): Promise<CalculationResult> {
  const response = await fetch(`/api/calculators/definitions/${calculatorId}/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values, age }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Calculation failed");
  }
  return response.json();
}

async function executeClinicalCalculation(
  calculatorId: string,
  inputs: Record<string, any>
): Promise<CalculationResult> {
  const response = await fetch(`/api/calculators/clinical/${calculatorId}/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Calculation failed");
  }
  return response.json();
}

// =============================================================================
// Component: Data-Driven Calculator Form
// =============================================================================

function DataDrivenCalculatorForm({
  calculator,
  onCalculate,
  isCalculating,
}: {
  calculator: DataDrivenCalculatorDetail;
  onCalculate: (values: Record<string, boolean | number>, age?: number) => void;
  isCalculating: boolean;
}) {
  const [formValues, setFormValues] = useState<Record<string, boolean | number | string>>({});
  const [age, setAge] = useState<number | "">("");

  // Initialize form values
  useEffect(() => {
    const defaults: Record<string, boolean | number | string> = {};
    for (const criterion of calculator.criteria) {
      if (criterion.type === "boolean") {
        defaults[criterion.name] = false;
      } else if (criterion.type === "multi_level" && criterion.levels) {
        defaults[criterion.name] = "";
      } else if (criterion.type === "threshold") {
        defaults[criterion.name] = "";
      }
    }
    setFormValues(defaults);
    setAge("");
  }, [calculator.id, calculator.criteria]);

  const handleChange = (name: string, value: boolean | number | string) => {
    setFormValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    // Convert form values to API format
    const values: Record<string, boolean | number> = {};
    for (const criterion of calculator.criteria) {
      const val = formValues[criterion.name];
      if (criterion.type === "boolean") {
        values[criterion.name] = val === true;
      } else if (criterion.type === "multi_level") {
        // For multi-level, we need to set the selected level as true
        if (criterion.levels && typeof val === "string" && val) {
          for (const level of criterion.levels) {
            values[`${criterion.name}_${level.suffix}`] = level.suffix === val;
          }
        }
      } else if (criterion.type === "threshold" && typeof val === "number") {
        values[criterion.name] = val;
      }
    }
    onCalculate(values, age !== "" ? age : undefined);
  };

  const handleReset = () => {
    const defaults: Record<string, boolean | number | string> = {};
    for (const criterion of calculator.criteria) {
      if (criterion.type === "boolean") {
        defaults[criterion.name] = false;
      } else {
        defaults[criterion.name] = "";
      }
    }
    setFormValues(defaults);
    setAge("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Parameters</CardTitle>
        <CardDescription>{calculator.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Age input if calculator uses age scoring */}
        {calculator.has_age_scoring && (
          <div className="space-y-2">
            <Label htmlFor="age" className="flex items-center gap-2">
              Age <span className="text-red-500">*</span>
              <span className="text-xs text-muted-foreground">(years)</span>
            </Label>
            <Input
              id="age"
              type="number"
              min={0}
              max={150}
              value={age}
              onChange={(e) => setAge(e.target.value ? Number(e.target.value) : "")}
              placeholder="Enter age"
            />
          </div>
        )}

        {/* Criteria inputs */}
        {calculator.criteria.map((criterion) => {
          const thresholdValue = formValues[criterion.name];
          return (
          <div key={criterion.name} className="space-y-2">
            <Label className="flex items-center gap-2">
              {criterion.display_name}
              {criterion.type === "boolean" && criterion.points && (
                <Badge variant="secondary" className="text-xs">
                  {criterion.points} pt{criterion.points !== 1 ? "s" : ""}
                </Badge>
              )}
            </Label>
            {criterion.description && (
              <p className="text-xs text-muted-foreground">{criterion.description}</p>
            )}

            {criterion.type === "boolean" ? (
              <div className="flex items-center gap-2">
                <Checkbox
                  id={criterion.name}
                  checked={formValues[criterion.name] === true}
                  onCheckedChange={(checked) => handleChange(criterion.name, checked === true)}
                />
                <span className="text-sm text-muted-foreground">
                  {formValues[criterion.name] ? "Yes" : "No"}
                </span>
              </div>
            ) : criterion.type === "multi_level" && criterion.levels ? (
              <Select
                value={String(formValues[criterion.name] || "")}
                onValueChange={(value) => handleChange(criterion.name, value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                  {criterion.levels.map((level) => (
                    <SelectItem key={level.suffix} value={level.suffix}>
                      {level.display} ({level.points} pt{level.points !== 1 ? "s" : ""})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : criterion.type === "threshold" ? (
              <Input
                type="number"
                value={
                  typeof thresholdValue === "number" || typeof thresholdValue === "string"
                    ? thresholdValue
                    : ""
                }
                onChange={(e) =>
                  handleChange(criterion.name, e.target.value ? Number(e.target.value) : "")
                }
                placeholder={criterion.unit ? `Enter value (${criterion.unit})` : "Enter value"}
              />
            ) : null}
          </div>
          );
        })}
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button onClick={handleSubmit} className="flex-1" disabled={isCalculating}>
          <Calculator className="mr-2 h-4 w-4" />
          {isCalculating ? "Calculating..." : "Calculate"}
        </Button>
        <Button variant="outline" onClick={handleReset}>
          <RotateCcw className="mr-2 h-4 w-4" />
          Reset
        </Button>
      </CardFooter>
    </Card>
  );
}

// =============================================================================
// Component: Legacy Calculator Form
// =============================================================================

function LegacyCalculatorForm({
  calculator,
  onCalculate,
  isCalculating,
}: {
  calculator: LegacyCalculatorDetail;
  onCalculate: (inputs: Record<string, any>) => void;
  isCalculating: boolean;
}) {
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Initialize form values with defaults
  useEffect(() => {
    const defaults: Record<string, any> = {};
    Object.entries(calculator.inputs).forEach(([key, def]) => {
      if (def.default !== undefined) {
        defaults[key] = def.default;
      } else if (def.type === "boolean") {
        defaults[key] = false;
      }
    });
    setFormValues(defaults);
    setErrors({});
  }, [calculator.id, calculator.inputs]);

  const handleInputChange = (key: string, value: string | number | boolean) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
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

  const handleSubmit = () => {
    if (validateInputs()) {
      onCalculate(formValues);
    }
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
    setErrors({});
  };

  return (
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
              {calculator.required.includes(key) && <span className="text-red-500">*</span>}
              {def.description && (
                <span className="text-xs text-muted-foreground">({def.description})</span>
              )}
            </Label>

            {def.type === "boolean" ? (
              <div className="flex items-center gap-2">
                <Checkbox
                  id={key}
                  checked={!!formValues[key]}
                  onCheckedChange={(checked) => handleInputChange(key, checked === true)}
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
                step="any"
                value={formValues[key] ?? ""}
                onChange={(e) =>
                  handleInputChange(key, e.target.value ? Number(e.target.value) : "")
                }
                placeholder={
                  def.minimum !== undefined && def.maximum !== undefined
                    ? `${def.minimum} - ${def.maximum}`
                    : "Enter value"
                }
                className={errors[key] ? "border-red-500" : ""}
              />
            )}

            {errors[key] && <p className="text-xs text-red-500">{errors[key]}</p>}
          </div>
        ))}
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button onClick={handleSubmit} className="flex-1" disabled={isCalculating}>
          <Calculator className="mr-2 h-4 w-4" />
          {isCalculating ? "Calculating..." : "Calculate"}
        </Button>
        <Button variant="outline" onClick={handleReset}>
          <RotateCcw className="mr-2 h-4 w-4" />
          Reset
        </Button>
      </CardFooter>
    </Card>
  );
}

// =============================================================================
// Component: Result Display
// =============================================================================

function ResultDisplay({ result }: { result: CalculationResult }) {
  const riskStyle = riskLevelStyles[result.risk_level] || riskLevelStyles.moderate;
  const riskProgress =
    { low: 16, low_moderate: 33, moderate: 50, moderate_high: 66, high: 83, very_high: 100 }[
      result.risk_level
    ] || 50;

  return (
    <div className="space-y-6">
      {/* Score Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            {riskStyle.icon}
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
            <Badge className={`${riskStyle.bg} text-white px-3 py-1 text-sm`}>
              {riskStyle.label}
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
      {result.recommendations.length > 0 && (
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
      )}

      {/* Warnings */}
      {result.warnings && result.warnings.length > 0 && (
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
                <li key={idx} className="text-sm text-amber-600">
                  {warning}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* References */}
      {result.references && result.references.length > 0 && (
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
                <li key={idx} className="text-sm text-muted-foreground">
                  {ref}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Components breakdown */}
      {result.components && Object.keys(result.components).length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Score Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {Object.entries(result.components).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export default function CalculatorPage({
  params,
}: {
  params: Promise<{ calculatorId: string }>;
}) {
  const { calculatorId } = use(params);

  const [isLoading, setIsLoading] = useState(true);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);

  // Calculator data - could be data-driven or legacy
  const [dataDrivenCalc, setDataDrivenCalc] = useState<DataDrivenCalculatorDetail | null>(null);
  const [legacyCalc, setLegacyCalc] = useState<LegacyCalculatorDetail | null>(null);
  const [result, setResult] = useState<CalculationResult | null>(null);

  // Fetch calculator definition on mount
  useEffect(() => {
    const loadCalculator = async () => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      setDataDrivenCalc(null);
      setLegacyCalc(null);

      // Try data-driven API first
      const ddCalc = await fetchDataDrivenCalculator(calculatorId);
      if (ddCalc) {
        setDataDrivenCalc(ddCalc);
        setIsLoading(false);
        return;
      }

      // Try clinical calculator API
      const clinicalCalc = await fetchClinicalCalculator(calculatorId);
      if (clinicalCalc) {
        setLegacyCalc(clinicalCalc);
        setIsLoading(false);
        return;
      }

      // Fall back to hardcoded definitions
      const hardcoded = legacyCalculatorDefinitions[calculatorId];
      if (hardcoded) {
        setLegacyCalc(hardcoded);
        setIsLoading(false);
        return;
      }

      // Not found
      setError(`Calculator "${calculatorId}" not found`);
      setIsLoading(false);
    };

    loadCalculator();
  }, [calculatorId]);

  const handleDataDrivenCalculate = async (
    values: Record<string, boolean | number>,
    age?: number
  ) => {
    setIsCalculating(true);
    setError(null);
    try {
      const calcResult = await executeDataDrivenCalculation(calculatorId, values, age);
      setResult(calcResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setIsCalculating(false);
    }
  };

  const handleLegacyCalculate = async (inputs: Record<string, any>) => {
    setIsCalculating(true);
    setError(null);
    try {
      const calcResult = await executeClinicalCalculation(calculatorId, inputs);
      setResult(calcResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setIsCalculating(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="py-12">
            <div className="text-center space-y-4">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">Loading calculator...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Not found state
  if (!dataDrivenCalc && !legacyCalc) {
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

  // Get display info from whichever calculator is loaded
  const displayInfo = dataDrivenCalc
    ? {
        name: dataDrivenCalc.name,
        short_name: dataDrivenCalc.short_name,
        category: dataDrivenCalc.category,
      }
    : {
        name: legacyCalc!.name,
        short_name: legacyCalc!.short_name,
        category: legacyCalc!.category,
      };

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
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-lg ${
                categoryColors[displayInfo.category] || categoryColors.general
              }`}
            >
              {categoryIcons[displayInfo.category] || <Calculator className="h-6 w-6" />}
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">{displayInfo.name}</h1>
              <p className="text-sm text-muted-foreground capitalize">
                {displayInfo.category.replace("_", " ")}
              </p>
            </div>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setIsFavorite(!isFavorite)}>
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

      {/* Error Alert */}
      {error && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
          <CardContent className="py-3">
            <p className="text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Form */}
        {dataDrivenCalc ? (
          <DataDrivenCalculatorForm
            calculator={dataDrivenCalc}
            onCalculate={handleDataDrivenCalculate}
            isCalculating={isCalculating}
          />
        ) : legacyCalc ? (
          <LegacyCalculatorForm
            calculator={legacyCalc}
            onCalculate={handleLegacyCalculate}
            isCalculating={isCalculating}
          />
        ) : null}

        {/* Result Display */}
        <div>
          {result ? (
            <ResultDisplay result={result} />
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
