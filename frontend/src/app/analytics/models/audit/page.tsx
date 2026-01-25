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
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Search,
  Clock,
  User,
  Brain,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Activity,
  FileText,
  BarChart3,
  Eye,
  Filter,
  Calendar,
  Target,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
} from "recharts";

// ============================================================================
// Types
// ============================================================================

interface PredictionAuditEntry {
  id: string;
  timestamp: string;
  modelId: string;
  modelName: string;
  modelVersion: string;
  patientId: string;
  patientName?: string;
  userId: string;
  userName: string;
  prediction: number;
  riskTier: "low" | "medium" | "high" | "critical";
  outcome?: "correct" | "incorrect" | "pending";
  latencyMs: number;
  featureCount: number;
  topFeatures: string[];
  requestSource: string;
  clinicalAction?: string;
}

interface ModelPerformanceMetrics {
  date: string;
  predictions: number;
  avgLatency: number;
  accuracy: number;
  auc: number;
}

interface PredictionDistribution {
  tier: string;
  count: number;
  percentage: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockAuditEntries: PredictionAuditEntry[] = [
  { id: "1", timestamp: "2024-02-15T14:32:15Z", modelId: "m1", modelName: "30-Day Readmission", modelVersion: "2.3.1", patientId: "P12345", patientName: "John Smith", userId: "u1", userName: "Dr. Williams", prediction: 0.72, riskTier: "high", outcome: "correct", latencyMs: 145, featureCount: 45, topFeatures: ["charlson_score", "prior_admits", "age"], requestSource: "EHR Integration", clinicalAction: "Care plan created" },
  { id: "2", timestamp: "2024-02-15T14:28:42Z", modelId: "m1", modelName: "30-Day Readmission", modelVersion: "2.3.1", patientId: "P12346", patientName: "Mary Johnson", userId: "u2", userName: "Dr. Chen", prediction: 0.35, riskTier: "medium", outcome: "correct", latencyMs: 132, featureCount: 45, topFeatures: ["los_days", "medication_count", "age"], requestSource: "API", clinicalAction: undefined },
  { id: "3", timestamp: "2024-02-15T14:25:18Z", modelId: "m2", modelName: "Mortality Risk", modelVersion: "1.8.0", patientId: "P12347", patientName: "Robert Williams", userId: "u1", userName: "Dr. Williams", prediction: 0.85, riskTier: "critical", outcome: "pending", latencyMs: 178, featureCount: 52, topFeatures: ["cci_score", "icu_days", "ventilator"], requestSource: "Dashboard", clinicalAction: "Palliative consult ordered" },
  { id: "4", timestamp: "2024-02-15T14:22:05Z", modelId: "m1", modelName: "30-Day Readmission", modelVersion: "2.3.1", patientId: "P12348", patientName: "Patricia Brown", userId: "u3", userName: "Nurse Davis", prediction: 0.18, riskTier: "low", outcome: "correct", latencyMs: 128, featureCount: 45, topFeatures: ["age", "bmi", "hemoglobin"], requestSource: "EHR Integration", clinicalAction: undefined },
  { id: "5", timestamp: "2024-02-15T14:18:33Z", modelId: "m3", modelName: "Sepsis Early Warning", modelVersion: "3.1.2", patientId: "P12349", patientName: "James Davis", userId: "u4", userName: "Dr. Martinez", prediction: 0.67, riskTier: "high", outcome: "incorrect", latencyMs: 92, featureCount: 38, topFeatures: ["temp", "wbc", "heart_rate"], requestSource: "Real-time Monitor", clinicalAction: "Blood cultures ordered" },
  { id: "6", timestamp: "2024-02-15T14:15:22Z", modelId: "m1", modelName: "30-Day Readmission", modelVersion: "2.3.1", patientId: "P12350", patientName: "Linda Miller", userId: "u2", userName: "Dr. Chen", prediction: 0.52, riskTier: "high", outcome: "pending", latencyMs: 138, featureCount: 45, topFeatures: ["prior_admits", "ed_visits", "cci_score"], requestSource: "API", clinicalAction: "Follow-up scheduled" },
  { id: "7", timestamp: "2024-02-15T14:10:45Z", modelId: "m2", modelName: "Mortality Risk", modelVersion: "1.8.0", patientId: "P12351", patientName: "Michael Wilson", userId: "u1", userName: "Dr. Williams", prediction: 0.28, riskTier: "low", outcome: "correct", latencyMs: 165, featureCount: 52, topFeatures: ["age", "albumin", "functional_status"], requestSource: "Dashboard", clinicalAction: undefined },
  { id: "8", timestamp: "2024-02-15T14:05:12Z", modelId: "m1", modelName: "30-Day Readmission", modelVersion: "2.3.1", patientId: "P12352", patientName: "Barbara Taylor", userId: "u3", userName: "Nurse Davis", prediction: 0.78, riskTier: "critical", outcome: "correct", latencyMs: 142, featureCount: 45, topFeatures: ["chf_hx", "dialysis", "prior_admits"], requestSource: "EHR Integration", clinicalAction: "Case management referral" },
];

const mockPerformanceMetrics: ModelPerformanceMetrics[] = [
  { date: "2024-02-09", predictions: 245, avgLatency: 142, accuracy: 0.82, auc: 0.847 },
  { date: "2024-02-10", predictions: 312, avgLatency: 138, accuracy: 0.84, auc: 0.852 },
  { date: "2024-02-11", predictions: 198, avgLatency: 145, accuracy: 0.81, auc: 0.845 },
  { date: "2024-02-12", predictions: 287, avgLatency: 135, accuracy: 0.85, auc: 0.858 },
  { date: "2024-02-13", predictions: 356, avgLatency: 148, accuracy: 0.83, auc: 0.849 },
  { date: "2024-02-14", predictions: 423, avgLatency: 141, accuracy: 0.86, auc: 0.862 },
  { date: "2024-02-15", predictions: 178, avgLatency: 139, accuracy: 0.84, auc: 0.855 },
];

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

const getOutcomeIcon = (outcome?: string) => {
  switch (outcome) {
    case "correct":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "incorrect":
      return <XCircle className="h-4 w-4 text-red-600" />;
    case "pending":
    default:
      return <Clock className="h-4 w-4 text-gray-500" />;
  }
};

const formatTimestamp = (timestamp: string) => {
  const date = new Date(timestamp);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

// ============================================================================
// Main Component
// ============================================================================

export default function PredictionAuditPage() {
  const [activeTab, setActiveTab] = useState("audit");
  const [searchQuery, setSearchQuery] = useState("");
  const [modelFilter, setModelFilter] = useState<string>("all");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");
  const [auditEntries] = useState<PredictionAuditEntry[]>(mockAuditEntries);
  const [performanceMetrics] = useState<ModelPerformanceMetrics[]>(mockPerformanceMetrics);

  // Get unique models
  const models = useMemo(() => {
    const unique = new Set(auditEntries.map(e => e.modelName));
    return ["all", ...Array.from(unique)];
  }, [auditEntries]);

  // Filter entries
  const filteredEntries = useMemo(() => {
    return auditEntries.filter(e => {
      const matchesSearch = searchQuery === "" ||
        e.patientName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.patientId.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.userName.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesModel = modelFilter === "all" || e.modelName === modelFilter;
      const matchesOutcome = outcomeFilter === "all" || e.outcome === outcomeFilter;
      return matchesSearch && matchesModel && matchesOutcome;
    });
  }, [auditEntries, searchQuery, modelFilter, outcomeFilter]);

  // Summary stats
  const stats = useMemo(() => {
    const total = auditEntries.length;
    const correct = auditEntries.filter(e => e.outcome === "correct").length;
    const incorrect = auditEntries.filter(e => e.outcome === "incorrect").length;
    const pending = auditEntries.filter(e => e.outcome === "pending").length;
    const avgLatency = auditEntries.reduce((sum, e) => sum + e.latencyMs, 0) / total;
    const withAction = auditEntries.filter(e => e.clinicalAction).length;

    const distribution: PredictionDistribution[] = [
      { tier: "critical", count: auditEntries.filter(e => e.riskTier === "critical").length, percentage: 0 },
      { tier: "high", count: auditEntries.filter(e => e.riskTier === "high").length, percentage: 0 },
      { tier: "medium", count: auditEntries.filter(e => e.riskTier === "medium").length, percentage: 0 },
      { tier: "low", count: auditEntries.filter(e => e.riskTier === "low").length, percentage: 0 },
    ];
    distribution.forEach(d => d.percentage = (d.count / total) * 100);

    return { total, correct, incorrect, pending, avgLatency, withAction, distribution };
  }, [auditEntries]);

  const latestMetrics = performanceMetrics[performanceMetrics.length - 1];

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
            <h1 className="text-2xl font-bold tracking-tight">Prediction Audit Trail</h1>
            <p className="text-muted-foreground">
              Track and monitor all ML model predictions
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

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Predictions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <div className="text-xs text-muted-foreground">Last 24 hours</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Correct
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.correct}</div>
            <div className="text-xs text-muted-foreground">
              {((stats.correct / (stats.correct + stats.incorrect)) * 100).toFixed(1)}% accuracy
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-600" />
              Incorrect
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.incorrect}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-500">{stats.pending}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avgLatency.toFixed(0)}ms</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Clinical Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.withAction}</div>
            <div className="text-xs text-muted-foreground">
              {((stats.withAction / stats.total) * 100).toFixed(0)}% actioned
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
          <TabsTrigger value="performance">Performance Trends</TabsTrigger>
          <TabsTrigger value="distribution">Prediction Distribution</TabsTrigger>
        </TabsList>

        <TabsContent value="audit" className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search patients, users..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={modelFilter} onValueChange={setModelFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Model" />
              </SelectTrigger>
              <SelectContent>
                {models.map(m => (
                  <SelectItem key={m} value={m}>
                    {m === "all" ? "All Models" : m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={outcomeFilter} onValueChange={setOutcomeFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Outcome" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Outcomes</SelectItem>
                <SelectItem value="correct">Correct</SelectItem>
                <SelectItem value="incorrect">Incorrect</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Audit Table */}
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-center">Prediction</TableHead>
                    <TableHead className="text-center">Outcome</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Top Features</TableHead>
                    <TableHead className="text-right">Latency</TableHead>
                    <TableHead>Action Taken</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEntries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTimestamp(entry.timestamp)}
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{entry.patientName}</div>
                          <div className="text-xs text-muted-foreground">{entry.patientId}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="text-sm">{entry.modelName}</div>
                          <div className="text-xs text-muted-foreground">v{entry.modelVersion}</div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex flex-col items-center gap-1">
                          <span className="font-mono font-bold">{(entry.prediction * 100).toFixed(0)}%</span>
                          <Badge className={getTierColor(entry.riskTier)}>{entry.riskTier}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        {getOutcomeIcon(entry.outcome)}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">{entry.userName}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {entry.topFeatures.slice(0, 2).map(f => (
                            <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {entry.latencyMs}ms
                      </TableCell>
                      <TableCell>
                        {entry.clinicalAction ? (
                          <span className="text-sm text-green-600">{entry.clinicalAction}</span>
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance" className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Predictions Over Time */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Predictions Volume
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={performanceMetrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Area type="monotone" dataKey="predictions" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Latency Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Latency Trend
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={performanceMetrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} domain={[100, 160]} />
                      <Tooltip formatter={(value) => [`${value}ms`, "Latency"]} />
                      <Line type="monotone" dataKey="avgLatency" stroke="#f59e0b" strokeWidth={2} dot={{ fill: "#f59e0b" }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Accuracy Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5" />
                  Accuracy Trend
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={performanceMetrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} domain={[0.7, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                      <Tooltip formatter={(value) => [`${((value as number) * 100).toFixed(1)}%`, "Accuracy"]} />
                      <Line type="monotone" dataKey="accuracy" stroke="#22c55e" strokeWidth={2} dot={{ fill: "#22c55e" }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* AUC Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  AUC-ROC Trend
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={performanceMetrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} domain={[0.8, 0.9]} tickFormatter={(v) => v.toFixed(2)} />
                      <Tooltip formatter={(value) => [(value as number).toFixed(3), "AUC"]} />
                      <Line type="monotone" dataKey="auc" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: "#8b5cf6" }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="distribution" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Prediction Risk Distribution</CardTitle>
              <CardDescription>Distribution of predictions by risk tier</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.distribution} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" tickFormatter={(v) => `${v}%`} />
                    <YAxis type="category" dataKey="tier" tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(value) => [`${(value as number).toFixed(1)}%`, "Percentage"]} />
                    <Bar dataKey="percentage">
                      {stats.distribution.map((entry, index) => {
                        const colors: Record<string, string> = {
                          critical: "#dc2626",
                          high: "#ef4444",
                          medium: "#f59e0b",
                          low: "#22c55e",
                        };
                        return <Cell key={index} fill={colors[entry.tier] || "#6b7280"} />;
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
