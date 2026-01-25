"use client";

import { useState, useMemo } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Brain,
  Search,
  Download,
  RefreshCw,
  Info,
  Target,
  Sparkles,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  User,
  Filter,
  Lightbulb,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
} from "recharts";

// ============================================================================
// Types
// ============================================================================

interface ShapFeature {
  name: string;
  displayName: string;
  shapValue: number;
  featureValue: number | string;
  featureValueNormalized: number;
  importance: number;
  direction: "positive" | "negative" | "neutral";
  category: string;
}

interface ModelPrediction {
  patientId: string;
  patientName: string;
  prediction: number;
  baseValue: number;
  outputValue: number;
  riskTier: "low" | "medium" | "high" | "critical";
  features: ShapFeature[];
  timestamp: string;
}

interface FeatureImportance {
  name: string;
  displayName: string;
  importance: number;
  meanAbsShap: number;
  stdShap: number;
}

interface ModelInfo {
  id: string;
  name: string;
  version: string;
  type: string;
  targetVariable: string;
  trainedAt: string;
  auc: number;
  accuracy: number;
  featureCount: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockModel: ModelInfo = {
  id: "model-001",
  name: "30-Day Readmission Risk",
  version: "2.3.1",
  type: "XGBoost",
  targetVariable: "readmission_30d",
  trainedAt: "2024-02-10",
  auc: 0.847,
  accuracy: 0.792,
  featureCount: 45,
};

const mockFeatureImportance: FeatureImportance[] = [
  { name: "age", displayName: "Age", importance: 0.142, meanAbsShap: 0.089, stdShap: 0.045 },
  { name: "charlson_score", displayName: "Charlson Comorbidity Index", importance: 0.128, meanAbsShap: 0.078, stdShap: 0.042 },
  { name: "prior_admits_12m", displayName: "Prior Admissions (12 mo)", importance: 0.115, meanAbsShap: 0.071, stdShap: 0.038 },
  { name: "los_days", displayName: "Length of Stay (days)", importance: 0.098, meanAbsShap: 0.062, stdShap: 0.035 },
  { name: "ed_visits_6m", displayName: "ED Visits (6 mo)", importance: 0.087, meanAbsShap: 0.054, stdShap: 0.032 },
  { name: "medication_count", displayName: "Medication Count", importance: 0.076, meanAbsShap: 0.048, stdShap: 0.028 },
  { name: "creatinine_last", displayName: "Last Creatinine", importance: 0.068, meanAbsShap: 0.043, stdShap: 0.025 },
  { name: "hemoglobin_last", displayName: "Last Hemoglobin", importance: 0.061, meanAbsShap: 0.039, stdShap: 0.022 },
  { name: "has_diabetes", displayName: "Diabetes", importance: 0.054, meanAbsShap: 0.035, stdShap: 0.019 },
  { name: "has_chf", displayName: "Heart Failure", importance: 0.051, meanAbsShap: 0.033, stdShap: 0.018 },
  { name: "bmi", displayName: "BMI", importance: 0.042, meanAbsShap: 0.027, stdShap: 0.015 },
  { name: "discharge_disposition", displayName: "Discharge Disposition", importance: 0.038, meanAbsShap: 0.024, stdShap: 0.014 },
];

const mockPrediction: ModelPrediction = {
  patientId: "P12345",
  patientName: "John Smith",
  prediction: 0.72,
  baseValue: 0.35,
  outputValue: 0.72,
  riskTier: "high",
  timestamp: "2024-02-15T10:30:00Z",
  features: [
    { name: "charlson_score", displayName: "Charlson Comorbidity Index", shapValue: 0.12, featureValue: 5, featureValueNormalized: 0.8, importance: 0.128, direction: "positive", category: "Clinical" },
    { name: "prior_admits_12m", displayName: "Prior Admissions (12 mo)", shapValue: 0.09, featureValue: 3, featureValueNormalized: 0.75, importance: 0.115, direction: "positive", category: "Utilization" },
    { name: "age", displayName: "Age", shapValue: 0.07, featureValue: 74, featureValueNormalized: 0.82, importance: 0.142, direction: "positive", category: "Demographics" },
    { name: "ed_visits_6m", displayName: "ED Visits (6 mo)", shapValue: 0.05, featureValue: 2, featureValueNormalized: 0.5, importance: 0.087, direction: "positive", category: "Utilization" },
    { name: "creatinine_last", displayName: "Last Creatinine", shapValue: 0.04, featureValue: 1.8, featureValueNormalized: 0.65, importance: 0.068, direction: "positive", category: "Labs" },
    { name: "los_days", displayName: "Length of Stay", shapValue: 0.03, featureValue: 7, featureValueNormalized: 0.58, importance: 0.098, direction: "positive", category: "Encounter" },
    { name: "has_diabetes", displayName: "Diabetes", shapValue: 0.02, featureValue: "Yes", featureValueNormalized: 1, importance: 0.054, direction: "positive", category: "Clinical" },
    { name: "hemoglobin_last", displayName: "Last Hemoglobin", shapValue: -0.03, featureValue: 11.2, featureValueNormalized: 0.45, importance: 0.061, direction: "negative", category: "Labs" },
    { name: "bmi", displayName: "BMI", shapValue: -0.02, featureValue: 26.5, featureValueNormalized: 0.52, importance: 0.042, direction: "negative", category: "Vitals" },
    { name: "medication_count", displayName: "Medication Count", shapValue: 0.01, featureValue: 8, featureValueNormalized: 0.6, importance: 0.076, direction: "positive", category: "Medications" },
  ],
};

const mockSummaryPlotData = mockFeatureImportance.map((f, i) => ({
  name: f.displayName,
  importance: f.meanAbsShap,
  samples: Array.from({ length: 50 }, (_, j) => ({
    shap: (Math.random() - 0.5) * f.meanAbsShap * 4,
    value: Math.random(),
  })),
}));

// ============================================================================
// Helper Functions
// ============================================================================

const getTierColor = (tier: string) => {
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

const getDirectionColor = (direction: string) => {
  switch (direction) {
    case "positive":
      return "#ef4444"; // red - increases risk
    case "negative":
      return "#22c55e"; // green - decreases risk
    default:
      return "#6b7280";
  }
};

const formatShapValue = (value: number) => {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
};

// ============================================================================
// Waterfall Chart Component
// ============================================================================

function WaterfallChart({ prediction }: { prediction: ModelPrediction }) {
  // Build waterfall data
  const sortedFeatures = [...prediction.features].sort((a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue));

  let cumulative = prediction.baseValue;
  const waterfallData = [
    { name: "Base", value: prediction.baseValue, fill: "#6b7280", start: 0, end: prediction.baseValue },
    ...sortedFeatures.map((f) => {
      const start = cumulative;
      cumulative += f.shapValue;
      return {
        name: f.displayName.length > 15 ? f.displayName.slice(0, 15) + "..." : f.displayName,
        value: f.shapValue,
        fill: getDirectionColor(f.direction),
        start,
        end: cumulative,
        fullName: f.displayName,
        featureValue: f.featureValue,
      };
    }),
    { name: "Output", value: prediction.outputValue, fill: "#3b82f6", start: 0, end: prediction.outputValue },
  ];

  return (
    <div className="h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={waterfallData}
          layout="vertical"
          margin={{ top: 20, right: 30, left: 120, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
          <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value, name, props) => {
              const item = props.payload;
              if (item.fullName) {
                return [`SHAP: ${formatShapValue(value as number)} | Value: ${item.featureValue}`, item.fullName];
              }
              return [`${((value as number) * 100).toFixed(1)}%`, name];
            }}
          />
          <Bar dataKey="end" stackId="a" fill="transparent" />
          <Bar dataKey="value" stackId="b">
            {waterfallData.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ============================================================================
// Force Plot Component (simplified version)
// ============================================================================

function ForcePlot({ prediction }: { prediction: ModelPrediction }) {
  const sortedFeatures = [...prediction.features].sort((a, b) => b.shapValue - a.shapValue);
  const positiveFeatures = sortedFeatures.filter(f => f.shapValue > 0);
  const negativeFeatures = sortedFeatures.filter(f => f.shapValue < 0);

  const totalPositive = positiveFeatures.reduce((sum, f) => sum + f.shapValue, 0);
  const totalNegative = Math.abs(negativeFeatures.reduce((sum, f) => sum + f.shapValue, 0));
  const total = totalPositive + totalNegative;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded" />
          <span>Increases Risk</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-500 rounded" />
          <span>Decreases Risk</span>
        </div>
      </div>

      <div className="relative h-16 flex items-center">
        {/* Positive forces (left side pushing right) */}
        <div
          className="h-full bg-red-500 flex items-center justify-end px-2"
          style={{ width: `${(totalPositive / total) * 100}%` }}
        >
          <span className="text-white text-xs font-medium">+{(totalPositive * 100).toFixed(1)}%</span>
        </div>

        {/* Negative forces (right side pushing left) */}
        <div
          className="h-full bg-green-500 flex items-center justify-start px-2"
          style={{ width: `${(totalNegative / total) * 100}%` }}
        >
          <span className="text-white text-xs font-medium">-{(totalNegative * 100).toFixed(1)}%</span>
        </div>

        {/* Output marker */}
        <div
          className="absolute top-0 bottom-0 w-1 bg-blue-600"
          style={{ left: `${(totalPositive / total) * 100}%` }}
        >
          <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-blue-600 text-white px-2 py-1 rounded text-xs font-bold whitespace-nowrap">
            {(prediction.outputValue * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h5 className="font-medium text-red-600 mb-2 flex items-center gap-1">
            <TrendingUp className="h-4 w-4" />
            Risk Factors
          </h5>
          {positiveFeatures.slice(0, 5).map((f) => (
            <div key={f.name} className="flex justify-between text-sm py-1 border-b last:border-0">
              <span className="text-muted-foreground">{f.displayName}</span>
              <span className="font-mono text-red-600">{formatShapValue(f.shapValue)}</span>
            </div>
          ))}
        </div>
        <div>
          <h5 className="font-medium text-green-600 mb-2 flex items-center gap-1">
            <TrendingDown className="h-4 w-4" />
            Protective Factors
          </h5>
          {negativeFeatures.slice(0, 5).map((f) => (
            <div key={f.name} className="flex justify-between text-sm py-1 border-b last:border-0">
              <span className="text-muted-foreground">{f.displayName}</span>
              <span className="font-mono text-green-600">{formatShapValue(f.shapValue)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ModelExplainabilityPage() {
  const [activeTab, setActiveTab] = useState("individual");
  const [selectedModel] = useState<ModelInfo>(mockModel);
  const [prediction] = useState<ModelPrediction>(mockPrediction);
  const [featureImportance] = useState<FeatureImportance[]>(mockFeatureImportance);
  const [searchQuery, setSearchQuery] = useState("");
  const [patientId, setPatientId] = useState(mockPrediction.patientId);

  // Filter features by search
  const filteredFeatures = useMemo(() => {
    if (!searchQuery) return prediction.features;
    return prediction.features.filter(f =>
      f.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.category.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [prediction.features, searchQuery]);

  // Feature importance chart data
  const importanceChartData = featureImportance.slice(0, 12).map(f => ({
    name: f.displayName.length > 20 ? f.displayName.slice(0, 20) + "..." : f.displayName,
    importance: f.meanAbsShap,
    fullName: f.displayName,
  }));

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/models">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Models
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Model Explainability</h1>
            <p className="text-muted-foreground">
              SHAP-based prediction explanations and feature importance
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Model Info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                {selectedModel.name}
              </CardTitle>
              <CardDescription>
                {selectedModel.type} v{selectedModel.version} - Target: {selectedModel.targetVariable}
              </CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{(selectedModel.auc * 100).toFixed(1)}%</div>
                <div className="text-xs text-muted-foreground">AUC-ROC</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{(selectedModel.accuracy * 100).toFixed(1)}%</div>
                <div className="text-xs text-muted-foreground">Accuracy</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{selectedModel.featureCount}</div>
                <div className="text-xs text-muted-foreground">Features</div>
              </div>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="individual">Individual Explanation</TabsTrigger>
          <TabsTrigger value="global">Global Feature Importance</TabsTrigger>
          <TabsTrigger value="features">Feature Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="individual" className="space-y-6">
          {/* Patient Search */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Patient Prediction
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <div className="flex-1 max-w-sm">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Enter patient ID..."
                      value={patientId}
                      onChange={(e) => setPatientId(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                </div>
                <Button>
                  <Target className="mr-2 h-4 w-4" />
                  Explain Prediction
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Prediction Summary */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Patient</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-bold">{prediction.patientName}</div>
                <div className="text-sm text-muted-foreground">{prediction.patientId}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Risk Score</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{(prediction.prediction * 100).toFixed(1)}%</div>
                <Badge className={getTierColor(prediction.riskTier)}>{prediction.riskTier}</Badge>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Base Rate</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{(prediction.baseValue * 100).toFixed(1)}%</div>
                <div className="text-sm text-muted-foreground">Population average</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Net SHAP Effect</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">
                  +{((prediction.outputValue - prediction.baseValue) * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-muted-foreground">Above baseline</div>
              </CardContent>
            </Card>
          </div>

          {/* Waterfall Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                SHAP Waterfall Plot
              </CardTitle>
              <CardDescription>
                How each feature contributes to the prediction from base value to output
              </CardDescription>
            </CardHeader>
            <CardContent>
              <WaterfallChart prediction={prediction} />
            </CardContent>
          </Card>

          {/* Force Plot */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Force Plot
              </CardTitle>
              <CardDescription>
                Visualizing positive and negative feature contributions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ForcePlot prediction={prediction} />
            </CardContent>
          </Card>

          {/* Feature Details Table */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Feature Contributions</CardTitle>
                <div className="relative w-64">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search features..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Feature</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Value</TableHead>
                    <TableHead className="text-right">SHAP Value</TableHead>
                    <TableHead>Contribution</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredFeatures.sort((a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue)).map((f) => (
                    <TableRow key={f.name}>
                      <TableCell className="font-medium">{f.displayName}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{f.category}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">{f.featureValue}</TableCell>
                      <TableCell className="text-right">
                        <span className={`font-mono ${f.direction === "positive" ? "text-red-600" : "text-green-600"}`}>
                          {formatShapValue(f.shapValue)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress
                            value={Math.abs(f.shapValue) / 0.15 * 100}
                            className={`h-2 w-24 ${f.direction === "positive" ? "[&>div]:bg-red-500" : "[&>div]:bg-green-500"}`}
                          />
                          {f.direction === "positive" ? (
                            <ArrowUp className="h-4 w-4 text-red-500" />
                          ) : (
                            <ArrowDown className="h-4 w-4 text-green-500" />
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="global" className="space-y-6">
          {/* Global Feature Importance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                Mean |SHAP| Feature Importance
              </CardTitle>
              <CardDescription>
                Average absolute SHAP value for each feature across all predictions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[500px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={importanceChartData}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 150, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                    <XAxis type="number" tickFormatter={(v) => v.toFixed(3)} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} />
                    <Tooltip
                      formatter={(value, name, props) => [
                        `Mean |SHAP|: ${(value as number).toFixed(4)}`,
                        props.payload.fullName,
                      ]}
                    />
                    <Bar dataKey="importance" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Feature Importance Table */}
          <Card>
            <CardHeader>
              <CardTitle>Feature Importance Details</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Feature</TableHead>
                    <TableHead className="text-right">Mean |SHAP|</TableHead>
                    <TableHead className="text-right">Std Dev</TableHead>
                    <TableHead className="text-right">Importance %</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {featureImportance.map((f, i) => (
                    <TableRow key={f.name}>
                      <TableCell className="font-mono">{i + 1}</TableCell>
                      <TableCell className="font-medium">{f.displayName}</TableCell>
                      <TableCell className="text-right font-mono">{f.meanAbsShap.toFixed(4)}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">{f.stdShap.toFixed(4)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={f.importance * 100 / 0.15} className="h-2 w-16" />
                          <span className="w-12 text-right">{(f.importance * 100).toFixed(1)}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="features" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5" />
                Feature Analysis Insights
              </CardTitle>
              <CardDescription>
                Key insights about how features affect predictions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="p-4 rounded-lg border bg-red-50 dark:bg-red-950">
                  <h4 className="font-medium text-red-700 dark:text-red-300 mb-2 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Top Risk Increasing Factors
                  </h4>
                  <ul className="space-y-2 text-sm">
                    <li>High Charlson Comorbidity Index strongly predicts readmission</li>
                    <li>Multiple prior admissions indicate chronic disease burden</li>
                    <li>Extended length of stay correlates with severity</li>
                    <li>Elevated creatinine suggests kidney dysfunction</li>
                  </ul>
                </div>
                <div className="p-4 rounded-lg border bg-green-50 dark:bg-green-950">
                  <h4 className="font-medium text-green-700 dark:text-green-300 mb-2 flex items-center gap-2">
                    <TrendingDown className="h-4 w-4" />
                    Top Risk Decreasing Factors
                  </h4>
                  <ul className="space-y-2 text-sm">
                    <li>Healthy hemoglobin levels indicate better overall health</li>
                    <li>Normal BMI range associated with lower readmission</li>
                    <li>Discharge to home with support reduces risk</li>
                    <li>Younger age generally protective</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Feature Categories</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
                {["Clinical", "Utilization", "Demographics", "Labs", "Medications"].map((cat) => {
                  const catFeatures = prediction.features.filter(f => f.category === cat);
                  const avgImpact = catFeatures.length > 0
                    ? catFeatures.reduce((sum, f) => sum + f.shapValue, 0) / catFeatures.length
                    : 0;
                  return (
                    <Card key={cat}>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{cat}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold">
                          {catFeatures.length}
                        </div>
                        <div className="text-xs text-muted-foreground">features</div>
                        <div className={`text-sm mt-2 ${avgImpact >= 0 ? "text-red-600" : "text-green-600"}`}>
                          Avg: {formatShapValue(avgImpact)}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
