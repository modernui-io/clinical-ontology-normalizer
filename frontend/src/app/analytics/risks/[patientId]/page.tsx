"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  AlertTriangle,
  Activity,
  TrendingUp,
  TrendingDown,
  ArrowLeft,
  Heart,
  Stethoscope,
  RefreshCw,
  Download,
  Settings,
  Bell,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Clock,
  Gauge,
  Brain,
  Target,
  Info,
  Minus,
  Thermometer,
  Droplets,
  Wind,
  HeartPulse,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface RiskScore {
  risk_type: string;
  score: number;
  score_raw: number | null;
  tier: string;
  percentile: number | null;
  confidence: number;
  calculated_at: string;
}

interface RiskFactor {
  name: string;
  value: string | number | boolean;
  contribution: number;
  direction: string;
  explanation: string | null;
}

interface RiskHistoryEntry {
  timestamp: string;
  score: number;
  tier: string;
}

interface PatientRiskDetail {
  patient_id: string;
  patient_name: string;
  age: number;
  gender: string;
  mrn: string;
  department: string;
  admission_date: string;
  attending_physician: string;

  readmission_risk: RiskScore | null;
  deterioration_risk: RiskScore | null;
  mortality_risk: RiskScore | null;

  overall_tier: string;
  overall_score: number;

  risk_factors: RiskFactor[];
  recommendations: string[];

  readmission_history: RiskHistoryEntry[];
  deterioration_history: RiskHistoryEntry[];
  mortality_history: RiskHistoryEntry[];

  vital_signs: {
    heart_rate: number;
    blood_pressure: string;
    respiratory_rate: number;
    temperature: number;
    oxygen_saturation: number;
    recorded_at: string;
  };

  alert_thresholds: {
    readmission: number;
    deterioration: number;
    mortality: number;
  };
}

interface SHAPValue {
  feature: string;
  value: number;
  contribution: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const getMockPatientDetail = (patientId: string): PatientRiskDetail => {
  // Generate consistent mock data based on patient ID
  const seed = patientId.charCodeAt(patientId.length - 1) || 0;
  const baseScore = 0.3 + (seed % 5) * 0.15;

  return {
    patient_id: patientId,
    patient_name: "John Smith",
    age: 72,
    gender: "Male",
    mrn: "MRN-" + patientId,
    department: "Cardiology",
    admission_date: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    attending_physician: "Dr. Sarah Johnson",

    readmission_risk: {
      risk_type: "readmission",
      score: Math.min(0.95, baseScore + 0.2),
      score_raw: 15,
      tier: baseScore > 0.5 ? "critical" : "high",
      percentile: 85,
      confidence: 0.82,
      calculated_at: new Date(Date.now() - 30 * 60000).toISOString(),
    },
    deterioration_risk: {
      risk_type: "deterioration",
      score: Math.min(0.95, baseScore),
      score_raw: 7,
      tier: baseScore > 0.5 ? "high" : "medium",
      percentile: 72,
      confidence: 0.78,
      calculated_at: new Date(Date.now() - 30 * 60000).toISOString(),
    },
    mortality_risk: {
      risk_type: "mortality",
      score: Math.min(0.95, baseScore - 0.1),
      score_raw: 10,
      tier: "medium",
      percentile: 65,
      confidence: 0.75,
      calculated_at: new Date(Date.now() - 30 * 60000).toISOString(),
    },

    overall_tier: baseScore > 0.5 ? "critical" : "high",
    overall_score: Math.min(0.95, baseScore + 0.2),

    risk_factors: [
      {
        name: "Length of Stay",
        value: 8,
        contribution: 0.18,
        direction: "increases",
        explanation: "Extended hospital stay of 8 days increases readmission risk",
      },
      {
        name: "Comorbidity Count",
        value: 5,
        contribution: 0.15,
        direction: "increases",
        explanation: "Multiple comorbidities (CHF, DM, CKD, HTN, COPD)",
      },
      {
        name: "ED Visits (6mo)",
        value: 3,
        contribution: 0.12,
        direction: "increases",
        explanation: "3 ED visits in past 6 months indicates instability",
      },
      {
        name: "Age",
        value: 72,
        contribution: 0.08,
        direction: "increases",
        explanation: "Advanced age associated with higher risk",
      },
      {
        name: "Medication Count",
        value: 12,
        contribution: 0.06,
        direction: "increases",
        explanation: "Polypharmacy with 12+ medications",
      },
      {
        name: "Prior Admissions",
        value: 2,
        contribution: 0.05,
        direction: "increases",
        explanation: "2 prior admissions in past 12 months",
      },
    ],

    recommendations: [
      "Schedule follow-up appointment within 7 days of discharge",
      "Enroll in transitional care management program",
      "Perform medication reconciliation before discharge",
      "Consider home health services for post-discharge monitoring",
      "Review polypharmacy - opportunity to deprescribe",
      "Ensure patient has 24-hour contact number for questions",
    ],

    readmission_history: Array.from({ length: 14 }, (_, i) => ({
      timestamp: new Date(Date.now() - (13 - i) * 24 * 60 * 60 * 1000).toISOString(),
      score: Math.max(0.3, Math.min(0.9, baseScore + 0.2 + Math.sin(i / 3) * 0.1)),
      tier: "high",
    })),

    deterioration_history: Array.from({ length: 14 }, (_, i) => ({
      timestamp: new Date(Date.now() - (13 - i) * 24 * 60 * 60 * 1000).toISOString(),
      score: Math.max(0.2, Math.min(0.8, baseScore + Math.cos(i / 2) * 0.15)),
      tier: "medium",
    })),

    mortality_history: Array.from({ length: 14 }, (_, i) => ({
      timestamp: new Date(Date.now() - (13 - i) * 24 * 60 * 60 * 1000).toISOString(),
      score: Math.max(0.15, Math.min(0.7, baseScore - 0.1 + Math.sin(i / 4) * 0.08)),
      tier: "medium",
    })),

    vital_signs: {
      heart_rate: 88,
      blood_pressure: "142/88",
      respiratory_rate: 18,
      temperature: 37.2,
      oxygen_saturation: 94,
      recorded_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    },

    alert_thresholds: {
      readmission: 0.6,
      deterioration: 0.5,
      mortality: 0.5,
    },
  };
};

const getMockSHAPValues = (riskType: string): SHAPValue[] => {
  const values: Record<string, SHAPValue[]> = {
    readmission: [
      { feature: "length_of_stay", value: 8, contribution: 0.18 },
      { feature: "comorbidity_count", value: 5, contribution: 0.15 },
      { feature: "ed_visits_6mo", value: 3, contribution: 0.12 },
      { feature: "age", value: 72, contribution: 0.08 },
      { feature: "medication_count", value: 12, contribution: 0.06 },
      { feature: "prior_admissions", value: 2, contribution: 0.05 },
      { feature: "discharge_disposition", value: 1, contribution: -0.03 },
      { feature: "hemoglobin", value: 11.2, contribution: -0.02 },
    ],
    deterioration: [
      { feature: "oxygen_saturation", value: 94, contribution: 0.12 },
      { feature: "respiratory_rate", value: 18, contribution: 0.08 },
      { feature: "heart_rate", value: 88, contribution: 0.05 },
      { feature: "systolic_bp", value: 142, contribution: 0.04 },
      { feature: "temperature", value: 37.2, contribution: -0.02 },
      { feature: "consciousness", value: 0, contribution: -0.05 },
    ],
    mortality: [
      { feature: "charlson_score", value: 5, contribution: 0.15 },
      { feature: "age", value: 72, contribution: 0.10 },
      { feature: "icu_admission", value: 0, contribution: -0.08 },
      { feature: "mechanical_ventilation", value: 0, contribution: -0.12 },
      { feature: "creatinine", value: 1.4, contribution: 0.05 },
      { feature: "albumin", value: 3.2, contribution: -0.03 },
    ],
  };
  return values[riskType] || [];
};

// ============================================================================
// Helper Functions
// ============================================================================

const getTierColor = (tier: string): string => {
  switch (tier) {
    case "critical":
      return "bg-red-600 text-white";
    case "high":
      return "bg-red-500 text-white";
    case "medium":
      return "bg-amber-500 text-white";
    case "low":
      return "bg-green-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
};

const getScoreColor = (score: number): string => {
  if (score >= 0.7) return "text-red-600 dark:text-red-400";
  if (score >= 0.5) return "text-orange-600 dark:text-orange-400";
  if (score >= 0.3) return "text-amber-600 dark:text-amber-400";
  return "text-green-600 dark:text-green-400";
};

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const formatTime = (dateString: string): string => {
  return new Date(dateString).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
};

// ============================================================================
// Risk Gauge Component
// ============================================================================

function RiskGauge({
  score,
  label,
  rawScore,
  confidence,
  size = "large"
}: {
  score: number;
  label: string;
  rawScore?: number | null;
  confidence?: number;
  size?: "large" | "medium" | "small";
}) {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - score * circumference;

  const getColor = (s: number) => {
    if (s >= 0.7) return "#dc2626";
    if (s >= 0.5) return "#ea580c";
    if (s >= 0.3) return "#d97706";
    return "#16a34a";
  };

  const sizeClasses = {
    large: "w-36 h-36",
    medium: "w-28 h-28",
    small: "w-20 h-20",
  };

  return (
    <div className="flex flex-col items-center">
      <div className={`relative ${sizeClasses[size]}`}>
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="currentColor"
            className="text-gray-200 dark:text-gray-700"
            strokeWidth={size === "large" ? "8" : "6"}
          />
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke={getColor(score)}
            strokeWidth={size === "large" ? "8" : "6"}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: "stroke-dashoffset 0.5s ease-in-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={`font-bold ${size === "large" ? "text-3xl" : size === "medium" ? "text-2xl" : "text-lg"}`}
            style={{ color: getColor(score) }}
          >
            {Math.round(score * 100)}%
          </span>
          {rawScore !== undefined && rawScore !== null && size === "large" && (
            <span className="text-xs text-muted-foreground">
              Raw: {rawScore}
            </span>
          )}
        </div>
      </div>
      <span className={`mt-2 font-medium ${size === "small" ? "text-xs" : "text-sm"}`}>
        {label}
      </span>
      {confidence !== undefined && size !== "small" && (
        <span className="text-xs text-muted-foreground">
          {(confidence * 100).toFixed(0)}% confidence
        </span>
      )}
    </div>
  );
}

// ============================================================================
// SHAP Waterfall Chart Component
// ============================================================================

function SHAPWaterfallChart({ values, baseValue = 0.5 }: { values: SHAPValue[]; baseValue?: number }) {
  const sortedValues = [...values].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  const maxContribution = Math.max(...values.map((v) => Math.abs(v.contribution)));
  const scale = 100 / (maxContribution * 2);

  let cumulative = baseValue;

  return (
    <div className="space-y-2">
      {/* Base value */}
      <div className="flex items-center gap-2 text-sm">
        <span className="w-32 text-right text-muted-foreground">Base value</span>
        <div className="flex-1 h-6 relative">
          <div
            className="absolute h-full bg-gray-200 dark:bg-gray-700 rounded"
            style={{
              left: "50%",
              width: `${baseValue * scale}%`,
              transform: "translateX(-100%)"
            }}
          />
        </div>
        <span className="w-16 text-right font-mono">{(baseValue * 100).toFixed(0)}%</span>
      </div>

      {/* Feature contributions */}
      {sortedValues.slice(0, 8).map((item, index) => {
        const isPositive = item.contribution > 0;
        const width = Math.abs(item.contribution) * scale;
        cumulative += item.contribution;

        return (
          <div key={item.feature} className="flex items-center gap-2 text-sm">
            <span className="w-32 text-right truncate" title={item.feature}>
              {item.feature.replace(/_/g, " ")}
            </span>
            <div className="flex-1 h-6 relative">
              <div
                className={`absolute h-full rounded ${isPositive ? "bg-red-400" : "bg-green-400"}`}
                style={{
                  left: isPositive ? "50%" : `${50 - width}%`,
                  width: `${width}%`,
                }}
              />
              {/* Cumulative line */}
              <div
                className="absolute h-full w-0.5 bg-gray-800 dark:bg-gray-200"
                style={{ left: `${50 + (cumulative - 0.5) * scale}%` }}
              />
            </div>
            <span className={`w-16 text-right font-mono ${isPositive ? "text-red-600" : "text-green-600"}`}>
              {isPositive ? "+" : ""}{(item.contribution * 100).toFixed(1)}%
            </span>
          </div>
        );
      })}

      {/* Final prediction */}
      <div className="flex items-center gap-2 text-sm font-medium border-t pt-2">
        <span className="w-32 text-right">Prediction</span>
        <div className="flex-1 h-6 relative">
          <div
            className="absolute h-full bg-blue-500 rounded"
            style={{
              left: "0%",
              width: `${cumulative * 100}%`,
            }}
          />
        </div>
        <span className="w-16 text-right font-mono text-blue-600">
          {(cumulative * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

// ============================================================================
// Risk History Chart Component
// ============================================================================

function RiskHistoryChart({
  data,
  color = "#3b82f6",
  threshold
}: {
  data: RiskHistoryEntry[];
  color?: string;
  threshold?: number;
}) {
  const height = 120;
  const width = 400;
  const padding = { top: 10, right: 10, bottom: 30, left: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const scores = data.map((d) => d.score);
  const min = 0;
  const max = 1;
  const stepX = chartWidth / (data.length - 1);

  const points = data
    .map((d, i) => {
      const x = padding.left + i * stepX;
      const y = padding.top + chartHeight - ((d.score - min) / (max - min)) * chartHeight;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {/* Y-axis labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((val) => {
        const y = padding.top + chartHeight - ((val - min) / (max - min)) * chartHeight;
        return (
          <g key={val}>
            <line
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              strokeDasharray="2,2"
            />
            <text
              x={padding.left - 5}
              y={y}
              textAnchor="end"
              alignmentBaseline="middle"
              className="text-xs fill-muted-foreground"
            >
              {(val * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}

      {/* Threshold line */}
      {threshold && (
        <line
          x1={padding.left}
          y1={padding.top + chartHeight - ((threshold - min) / (max - min)) * chartHeight}
          x2={width - padding.right}
          y2={padding.top + chartHeight - ((threshold - min) / (max - min)) * chartHeight}
          stroke="#ef4444"
          strokeWidth="2"
          strokeDasharray="4,4"
        />
      )}

      {/* Data line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Data points */}
      {data.map((d, i) => {
        const x = padding.left + i * stepX;
        const y = padding.top + chartHeight - ((d.score - min) / (max - min)) * chartHeight;
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r="4"
            fill={color}
            className="hover:r-6 cursor-pointer"
          />
        );
      })}

      {/* X-axis labels */}
      {data.filter((_, i) => i % 3 === 0).map((d, i) => {
        const x = padding.left + i * 3 * stepX;
        return (
          <text
            key={i}
            x={x}
            y={height - 5}
            textAnchor="middle"
            className="text-xs fill-muted-foreground"
          >
            {new Date(d.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </text>
        );
      })}
    </svg>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function PatientRiskDetailPage() {
  const params = useParams();
  const patientId = params.patientId as string;

  const [patient, setPatient] = useState<PatientRiskDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedRiskType, setSelectedRiskType] = useState("readmission");
  const [shapValues, setShapValues] = useState<SHAPValue[]>([]);

  // Alert threshold settings
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [thresholds, setThresholds] = useState({
    readmission: 60,
    deterioration: 50,
    mortality: 50,
  });

  useEffect(() => {
    // Simulate API call
    setIsLoading(true);
    setTimeout(() => {
      const data = getMockPatientDetail(patientId);
      setPatient(data);
      setThresholds({
        readmission: data.alert_thresholds.readmission * 100,
        deterioration: data.alert_thresholds.deterioration * 100,
        mortality: data.alert_thresholds.mortality * 100,
      });
      setShapValues(getMockSHAPValues(selectedRiskType));
      setIsLoading(false);
    }, 500);
  }, [patientId]);

  useEffect(() => {
    setShapValues(getMockSHAPValues(selectedRiskType));
  }, [selectedRiskType]);

  if (isLoading || !patient) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const getCurrentRisk = () => {
    switch (selectedRiskType) {
      case "readmission":
        return patient.readmission_risk;
      case "deterioration":
        return patient.deterioration_risk;
      case "mortality":
        return patient.mortality_risk;
      default:
        return null;
    }
  };

  const getCurrentHistory = () => {
    switch (selectedRiskType) {
      case "readmission":
        return patient.readmission_history;
      case "deterioration":
        return patient.deterioration_history;
      case "mortality":
        return patient.mortality_history;
      default:
        return [];
    }
  };

  const getRiskColor = (type: string) => {
    switch (type) {
      case "readmission":
        return "#3b82f6";
      case "deterioration":
        return "#f59e0b";
      case "mortality":
        return "#ef4444";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/risks">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{patient.patient_name}</h1>
              <Badge className={getTierColor(patient.overall_tier)}>
                {patient.overall_tier} risk
              </Badge>
            </div>
            <p className="text-muted-foreground">
              {patient.patient_id} | {patient.age}yo {patient.gender} | {patient.department}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Bell className="mr-2 h-4 w-4" />
            Configure Alerts
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Patient Info and Risk Gauges */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Patient Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5" />
              Patient Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between">
              <span className="text-muted-foreground">MRN</span>
              <span className="font-medium">{patient.mrn}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Admission Date</span>
              <span className="font-medium">{formatDate(patient.admission_date)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Attending</span>
              <span className="font-medium">{patient.attending_physician}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Length of Stay</span>
              <span className="font-medium">
                {Math.ceil((Date.now() - new Date(patient.admission_date).getTime()) / (24 * 60 * 60 * 1000))} days
              </span>
            </div>
            <div className="border-t pt-3 mt-3">
              <div className="text-sm font-medium mb-2">Latest Vitals</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex items-center gap-1">
                  <HeartPulse className="h-3 w-3 text-red-500" />
                  <span>{patient.vital_signs.heart_rate} bpm</span>
                </div>
                <div className="flex items-center gap-1">
                  <Activity className="h-3 w-3 text-blue-500" />
                  <span>{patient.vital_signs.blood_pressure}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Wind className="h-3 w-3 text-cyan-500" />
                  <span>{patient.vital_signs.respiratory_rate}/min</span>
                </div>
                <div className="flex items-center gap-1">
                  <Thermometer className="h-3 w-3 text-orange-500" />
                  <span>{patient.vital_signs.temperature}C</span>
                </div>
                <div className="flex items-center gap-1 col-span-2">
                  <Droplets className="h-3 w-3 text-blue-500" />
                  <span>SpO2: {patient.vital_signs.oxygen_saturation}%</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Recorded {formatTime(patient.vital_signs.recorded_at)}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Risk Gauges */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5" />
              Risk Scores
            </CardTitle>
            <CardDescription>
              Last calculated {formatTime(patient.readmission_risk?.calculated_at || "")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex justify-around items-center">
              {patient.readmission_risk && (
                <RiskGauge
                  score={patient.readmission_risk.score}
                  label="Readmission"
                  rawScore={patient.readmission_risk.score_raw}
                  confidence={patient.readmission_risk.confidence}
                />
              )}
              {patient.deterioration_risk && (
                <RiskGauge
                  score={patient.deterioration_risk.score}
                  label="Deterioration"
                  rawScore={patient.deterioration_risk.score_raw}
                  confidence={patient.deterioration_risk.confidence}
                />
              )}
              {patient.mortality_risk && (
                <RiskGauge
                  score={patient.mortality_risk.score}
                  label="Mortality"
                  rawScore={patient.mortality_risk.score_raw}
                  confidence={patient.mortality_risk.confidence}
                />
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Explainability and Factors */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* SHAP Explainability */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5" />
                  Risk Explanation
                </CardTitle>
                <CardDescription>
                  Feature contributions to prediction (SHAP values)
                </CardDescription>
              </div>
              <Tabs value={selectedRiskType} onValueChange={setSelectedRiskType}>
                <TabsList className="grid grid-cols-3 w-auto">
                  <TabsTrigger value="readmission" className="text-xs">Readmit</TabsTrigger>
                  <TabsTrigger value="deterioration" className="text-xs">Deteri</TabsTrigger>
                  <TabsTrigger value="mortality" className="text-xs">Mortality</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            <SHAPWaterfallChart values={shapValues} baseValue={0.3} />
          </CardContent>
        </Card>

        {/* Contributing Factors */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Contributing Factors
            </CardTitle>
            <CardDescription>
              Key factors influencing risk scores
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {patient.risk_factors.map((factor, index) => (
                <div key={index} className="flex items-start gap-3 p-2 rounded-lg hover:bg-muted/50">
                  <div className={`mt-1 ${factor.direction === "increases" ? "text-red-500" : "text-green-500"}`}>
                    {factor.direction === "increases" ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{factor.name}</span>
                      <Badge variant="outline">{String(factor.value)}</Badge>
                    </div>
                    {factor.explanation && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {factor.explanation}
                      </p>
                    )}
                  </div>
                  <div className={`text-sm font-mono ${factor.contribution > 0 ? "text-red-600" : "text-green-600"}`}>
                    {factor.contribution > 0 ? "+" : ""}{(factor.contribution * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Risk History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Risk History
          </CardTitle>
          <CardDescription>
            Risk score trends over time
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={selectedRiskType} onValueChange={setSelectedRiskType}>
            <TabsList className="mb-4">
              <TabsTrigger value="readmission">Readmission Risk</TabsTrigger>
              <TabsTrigger value="deterioration">Deterioration Risk</TabsTrigger>
              <TabsTrigger value="mortality">Mortality Risk</TabsTrigger>
            </TabsList>
            <TabsContent value={selectedRiskType}>
              <RiskHistoryChart
                data={getCurrentHistory()}
                color={getRiskColor(selectedRiskType)}
                threshold={thresholds[selectedRiskType as keyof typeof thresholds] / 100}
              />
              <div className="flex items-center justify-center gap-6 mt-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-0.5 rounded" style={{ backgroundColor: getRiskColor(selectedRiskType) }} />
                  <span>Risk Score</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-0.5 rounded bg-red-500" style={{ borderStyle: "dashed" }} />
                  <span>Alert Threshold ({thresholds[selectedRiskType as keyof typeof thresholds]}%)</span>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Recommendations and Alert Settings */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              Recommendations
            </CardTitle>
            <CardDescription>
              Actions to mitigate identified risks
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {patient.recommendations.map((rec, index) => (
                <li key={index} className="flex items-start gap-2">
                  <CheckCircle className="h-4 w-4 mt-0.5 text-green-500 shrink-0" />
                  <span className="text-sm">{rec}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Alert Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Alert Configuration
            </CardTitle>
            <CardDescription>
              Set thresholds for risk alerts
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Switch
                  id="alerts-enabled"
                  checked={alertsEnabled}
                  onCheckedChange={setAlertsEnabled}
                />
                <Label htmlFor="alerts-enabled">Enable alerts for this patient</Label>
              </div>
            </div>

            {alertsEnabled && (
              <div className="space-y-4 pt-2">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Readmission Risk Threshold</Label>
                    <span className="text-sm font-medium">{thresholds.readmission}%</span>
                  </div>
                  <Input
                    type="range"
                    min="20"
                    max="90"
                    value={thresholds.readmission}
                    onChange={(e) => setThresholds({ ...thresholds, readmission: parseInt(e.target.value) })}
                    className="w-full"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Deterioration Risk Threshold</Label>
                    <span className="text-sm font-medium">{thresholds.deterioration}%</span>
                  </div>
                  <Input
                    type="range"
                    min="20"
                    max="90"
                    value={thresholds.deterioration}
                    onChange={(e) => setThresholds({ ...thresholds, deterioration: parseInt(e.target.value) })}
                    className="w-full"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Mortality Risk Threshold</Label>
                    <span className="text-sm font-medium">{thresholds.mortality}%</span>
                  </div>
                  <Input
                    type="range"
                    min="20"
                    max="90"
                    value={thresholds.mortality}
                    onChange={(e) => setThresholds({ ...thresholds, mortality: parseInt(e.target.value) })}
                    className="w-full"
                  />
                </div>

                <Button className="w-full" variant="outline">
                  <Settings className="mr-2 h-4 w-4" />
                  Save Alert Settings
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
