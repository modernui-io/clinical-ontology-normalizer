"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BarChart3,
  Brain,
  Calendar,
  CheckCircle2,
  Clock,
  Database,
  Download,
  FileText,
  Filter,
  GitBranch,
  Layers,
  Loader2,
  MoreVertical,
  Play,
  RefreshCw,
  Settings,
  Target,
  TrendingDown,
  TrendingUp,
  Upload,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
} from "recharts";

// ---------------------------------------------------------------------------
// Types - frontend display types
// ---------------------------------------------------------------------------

interface ModelVersion {
  version: string;
  createdAt: string;
  status: "active" | "archived" | "training" | "failed";
  metrics: {
    aucRoc: number;
    aucPr: number;
    precision: number;
    recall: number;
    f1Score: number;
    brierScore: number;
  };
  trainingSize: number;
  features: number;
}

interface Model {
  id: string;
  name: string;
  type: string;
  description: string;
  currentVersion: string;
  versions: ModelVersion[];
  lastTrained: string;
  nextScheduledTraining: string | null;
  status: "healthy" | "degraded" | "critical" | "training";
  driftScore: number;
  predictionsLast24h: number;
  avgLatencyMs: number;
  riskTier: string;
  owner: string;
  governanceStatus: string;
}

interface DriftDataPoint {
  date: string;
  psi: number;
  threshold: number;
}

interface PerformanceHistory {
  date: string;
  aucRoc: number;
  precision: number;
  recall: number;
}

interface TrainingRun {
  id: string;
  modelId: string;
  version: string;
  status: "completed" | "running" | "failed" | "queued";
  startedAt: string;
  completedAt: string | null;
  duration: string | null;
  triggeredBy: "scheduled" | "manual" | "drift_alert";
  metrics: {
    aucRoc: number;
    aucPr: number;
  } | null;
}

// ---------------------------------------------------------------------------
// Types - backend API response shapes
// ---------------------------------------------------------------------------

interface GovernedModelAPI {
  id: string;
  name: string;
  version: string;
  description: string;
  model_type: string;
  risk_tier: string;
  status: string;
  owner: string;
  team: string;
  training_data_hash: string;
  performance_metrics: Record<string, unknown>;
  fairness_metrics: Record<string, unknown>;
  validation_date: string | null;
  approved_by: string | null;
  approval_date: string | null;
  deployment_date: string | null;
  monitoring_config: Record<string, unknown>;
  review_frequency_days: number;
  next_review_date: string | null;
  created_at: string;
  updated_at: string;
}

interface GovernedModelListResponseAPI {
  total: number;
  models: GovernedModelAPI[];
}

interface ModelGovernanceMetricsAPI {
  total_models: number;
  by_tier: Record<string, number>;
  by_status: Record<string, number>;
  pending_approvals: number;
  overdue_reviews: number;
  active_alerts: number;
  avg_time_to_approval_days: number;
  models_in_production: number;
  deprecated_count: number;
}

interface MonitoringAlertAPI {
  id: string;
  model_id: string;
  alert_type: string;
  severity: string;
  message: string;
  detected_at: string;
  acknowledged: boolean;
  resolved_at: string | null;
}

interface AlertListResponseAPI {
  total: number;
  alerts: MonitoringAlertAPI[];
}

interface ModelHistoryResponseAPI {
  model_id: string;
  model_name: string;
  validations: unknown[];
  alerts: MonitoringAlertAPI[];
  approval_requests: unknown[];
}

// ---------------------------------------------------------------------------
// Backend -> Frontend mapping helpers
// ---------------------------------------------------------------------------

/** Map backend governance status to the frontend display status. */
function mapGovernanceStatusToDisplayStatus(
  status: string,
  activeAlerts: MonitoringAlertAPI[],
): Model["status"] {
  // If the model is still in development/validation, treat as training
  if (status === "development" || status === "validation") return "training";
  // If deprecated or retired, treat as critical
  if (status === "deprecated" || status === "retired") return "critical";

  // For deployed/monitoring/approved models, check alert severity
  const modelHasCriticalAlert = activeAlerts.some(
    (a) => a.severity === "critical" || a.severity === "high",
  );
  const modelHasMediumAlert = activeAlerts.some(
    (a) => a.severity === "medium",
  );

  if (modelHasCriticalAlert) return "critical";
  if (modelHasMediumAlert) return "degraded";
  return "healthy";
}

/** Extract a numeric metric from performance_metrics dict, with fallback. */
function pm(metrics: Record<string, unknown>, key: string, fallback = 0): number {
  const val = metrics[key];
  return typeof val === "number" ? val : fallback;
}

/** Map a single backend GovernedModel to the frontend Model shape. */
function mapGovernedModelToModel(
  gm: GovernedModelAPI,
  alerts: MonitoringAlertAPI[],
): Model {
  const modelAlerts = alerts.filter((a) => a.model_id === gm.id && !a.resolved_at);
  const perf = gm.performance_metrics ?? {};

  // Build a single version entry from the backend model's current state
  const currentVersion: ModelVersion = {
    version: gm.version,
    createdAt: gm.created_at,
    status: gm.status === "development" || gm.status === "validation" ? "training" : "active",
    metrics: {
      aucRoc: pm(perf, "auc_roc") || pm(perf, "aucRoc") || pm(perf, "auc"),
      aucPr: pm(perf, "auc_pr") || pm(perf, "aucPr"),
      precision: pm(perf, "precision"),
      recall: pm(perf, "recall"),
      f1Score: pm(perf, "f1_score") || pm(perf, "f1Score") || pm(perf, "f1"),
      brierScore: pm(perf, "brier_score") || pm(perf, "brierScore"),
    },
    trainingSize: pm(perf, "training_size") || pm(perf, "trainingSize"),
    features: pm(perf, "features") || pm(perf, "feature_count"),
  };

  return {
    id: gm.id,
    name: gm.name,
    type: gm.model_type,
    description: gm.description,
    currentVersion: gm.version,
    versions: [currentVersion],
    lastTrained: gm.updated_at,
    nextScheduledTraining: gm.next_review_date,
    status: mapGovernanceStatusToDisplayStatus(gm.status, modelAlerts),
    driftScore: pm(perf, "drift_score") || pm(perf, "driftScore"),
    predictionsLast24h: pm(perf, "predictions_last_24h") || pm(perf, "predictionsLast24h"),
    avgLatencyMs: pm(perf, "avg_latency_ms") || pm(perf, "avgLatencyMs"),
    riskTier: gm.risk_tier,
    owner: gm.owner,
    governanceStatus: gm.status,
  };
}

// ---------------------------------------------------------------------------
// Static chart data (not available from backend governance endpoints)
// ---------------------------------------------------------------------------

const staticDriftData: DriftDataPoint[] = [
  { date: "Jan 1", psi: 0.012, threshold: 0.1 },
  { date: "Jan 3", psi: 0.015, threshold: 0.1 },
  { date: "Jan 5", psi: 0.018, threshold: 0.1 },
  { date: "Jan 7", psi: 0.022, threshold: 0.1 },
  { date: "Jan 9", psi: 0.019, threshold: 0.1 },
  { date: "Jan 11", psi: 0.025, threshold: 0.1 },
  { date: "Jan 13", psi: 0.031, threshold: 0.1 },
  { date: "Jan 15", psi: 0.028, threshold: 0.1 },
  { date: "Jan 17", psi: 0.035, threshold: 0.1 },
  { date: "Jan 19", psi: 0.023, threshold: 0.1 },
];

const staticPerformanceHistory: PerformanceHistory[] = [
  { date: "Dec 1", aucRoc: 0.832, precision: 0.74, recall: 0.69 },
  { date: "Dec 8", aucRoc: 0.835, precision: 0.75, recall: 0.70 },
  { date: "Dec 15", aucRoc: 0.841, precision: 0.76, recall: 0.71 },
  { date: "Dec 22", aucRoc: 0.839, precision: 0.75, recall: 0.70 },
  { date: "Dec 29", aucRoc: 0.843, precision: 0.77, recall: 0.71 },
  { date: "Jan 5", aucRoc: 0.845, precision: 0.77, recall: 0.72 },
  { date: "Jan 12", aucRoc: 0.847, precision: 0.78, recall: 0.72 },
  { date: "Jan 19", aucRoc: 0.847, precision: 0.78, recall: 0.72 },
];

// Training runs are static placeholders - the backend model-governance API
// does not expose a training-runs endpoint. Wire to a real endpoint when available.
const staticTrainingRuns: TrainingRun[] = [];

// Helper Components
function StatusBadge({ status }: { status: Model["status"] }) {
  const config = {
    healthy: { color: "bg-green-100 text-green-800", icon: CheckCircle2 },
    degraded: { color: "bg-yellow-100 text-yellow-800", icon: AlertTriangle },
    critical: { color: "bg-red-100 text-red-800", icon: XCircle },
    training: { color: "bg-blue-100 text-blue-800", icon: RefreshCw },
  };

  const { color, icon: Icon } = config[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`h-3 w-3 ${status === "training" ? "animate-spin" : ""}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function TrainingStatusBadge({ status }: { status: TrainingRun["status"] }) {
  const config = {
    completed: { color: "bg-green-100 text-green-800", icon: CheckCircle2 },
    running: { color: "bg-blue-100 text-blue-800", icon: RefreshCw },
    failed: { color: "bg-red-100 text-red-800", icon: XCircle },
    queued: { color: "bg-gray-100 text-gray-800", icon: Clock },
  };

  const { color, icon: Icon } = config[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function MetricCard({
  label,
  value,
  change,
  format = "percent",
}: {
  label: string;
  value: number;
  change?: number;
  format?: "percent" | "number" | "ms";
}) {
  const formatValue = () => {
    switch (format) {
      case "percent":
        return `${(value * 100).toFixed(1)}%`;
      case "ms":
        return `${value}ms`;
      default:
        return value.toLocaleString();
    }
  };

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="text-sm text-gray-500 mb-1">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold">{formatValue()}</span>
        {change !== undefined && (
          <span
            className={`flex items-center text-xs ${
              change >= 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            {change >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {Math.abs(change * 100).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

function CalibrationPlot({ modelId }: { modelId: string }) {
  // Mock calibration data - shows predicted vs actual probabilities
  const calibrationData = [
    { predicted: 0.1, actual: 0.08, perfect: 0.1 },
    { predicted: 0.2, actual: 0.18, perfect: 0.2 },
    { predicted: 0.3, actual: 0.28, perfect: 0.3 },
    { predicted: 0.4, actual: 0.42, perfect: 0.4 },
    { predicted: 0.5, actual: 0.48, perfect: 0.5 },
    { predicted: 0.6, actual: 0.62, perfect: 0.6 },
    { predicted: 0.7, actual: 0.68, perfect: 0.7 },
    { predicted: 0.8, actual: 0.82, perfect: 0.8 },
    { predicted: 0.9, actual: 0.88, perfect: 0.9 },
  ];

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={calibrationData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="predicted"
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 10 }}
          />
          <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value) => [`${((value as number ?? 0) * 100).toFixed(1)}%`]}
            labelFormatter={(label) => `Predicted: ${((label as number ?? 0) * 100).toFixed(0)}%`}
          />
          <Line
            type="linear"
            dataKey="perfect"
            stroke="#d1d5db"
            strokeDasharray="5 5"
            dot={false}
            name="Perfect Calibration"
          />
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Actual"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function FeatureImportanceChart() {
  const features = [
    { name: "Length of Stay", importance: 0.18 },
    { name: "Prior Admissions", importance: 0.15 },
    { name: "Charlson Index", importance: 0.12 },
    { name: "Age", importance: 0.10 },
    { name: "ED Visits (6mo)", importance: 0.09 },
    { name: "Medication Count", importance: 0.08 },
    { name: "Lab Abnormalities", importance: 0.07 },
    { name: "Discharge Disposition", importance: 0.06 },
  ];

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={features} layout="vertical" margin={{ top: 5, right: 10, left: 80, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
          <XAxis type="number" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={75} />
          <Tooltip formatter={(value) => [`${((value as number ?? 0) * 100).toFixed(1)}%`, "Importance"]} />
          <Bar dataKey="importance" fill="#3b82f6" radius={[0, 4, 4, 0]}>
            {features.map((_, index) => (
              <Cell key={`cell-${index}`} fill={index < 3 ? "#3b82f6" : "#93c5fd"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ModelsPage() {
  // -----------------------------------------------------------------------
  // State: API data
  // -----------------------------------------------------------------------
  const [models, setModels] = useState<Model[]>([]);
  const [metrics, setMetrics] = useState<ModelGovernanceMetricsAPI | null>(null);
  const [alerts, setAlerts] = useState<MonitoringAlertAPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // -----------------------------------------------------------------------
  // State: UI
  // -----------------------------------------------------------------------
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "performance" | "drift" | "training">("overview");
  const [searchQuery, setSearchQuery] = useState("");

  // -----------------------------------------------------------------------
  // Data fetching
  // -----------------------------------------------------------------------
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelsRes, metricsRes, alertsRes] = await Promise.all([
        fetch("/api/model-governance/models"),
        fetch("/api/model-governance/metrics"),
        fetch("/api/model-governance/alerts"),
      ]);

      if (!modelsRes.ok) throw new Error(`Failed to fetch models: ${modelsRes.status} ${modelsRes.statusText}`);
      if (!metricsRes.ok) throw new Error(`Failed to fetch metrics: ${metricsRes.status} ${metricsRes.statusText}`);
      if (!alertsRes.ok) throw new Error(`Failed to fetch alerts: ${alertsRes.status} ${alertsRes.statusText}`);

      const modelsData: GovernedModelListResponseAPI = await modelsRes.json();
      const metricsData: ModelGovernanceMetricsAPI = await metricsRes.json();
      const alertsData: AlertListResponseAPI = await alertsRes.json();

      setAlerts(alertsData.alerts);
      setMetrics(metricsData);

      const mapped = modelsData.models.map((gm) => mapGovernedModelToModel(gm, alertsData.alerts));
      setModels(mapped);

      // Auto-select first model if nothing selected yet
      if (mapped.length > 0) {
        setSelectedModel((prev) => {
          // Keep current selection if it still exists in the new data
          if (prev && mapped.some((m) => m.id === prev.id)) {
            return mapped.find((m) => m.id === prev.id) ?? mapped[0];
          }
          return mapped[0];
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // -----------------------------------------------------------------------
  // Derived summary stats (from live data or metrics endpoint)
  // -----------------------------------------------------------------------
  const totalModels = metrics?.total_models ?? models.length;
  const healthyModels = models.filter((m) => m.status === "healthy").length;
  const modelsWithDrift = models.filter((m) => m.driftScore > 0.05).length;
  const totalPredictions = models.reduce((sum, m) => sum + m.predictionsLast24h, 0);
  const avgLatency = models.length > 0 ? models.reduce((sum, m) => sum + m.avgLatencyMs, 0) / models.length : 0;

  // Filtered model list for search
  const filteredModels = searchQuery
    ? models.filter(
        (m) =>
          m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          m.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
          m.id.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : models;

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
          <p className="text-sm text-gray-500">Loading model governance data...</p>
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Error state
  // -----------------------------------------------------------------------
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg border border-red-200 p-8 max-w-md text-center">
          <XCircle className="h-10 w-10 text-red-500 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Models</h2>
          <p className="text-sm text-gray-600 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Link href="/analytics" className="hover:text-blue-600">
                Analytics
              </Link>
              <span>/</span>
              <span>Model Management</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">ML Model Management</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
              title="Refresh data"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <button className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
              <Upload className="h-4 w-4" />
              Import Model
            </button>
            <button className="flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Play className="h-4 w-4" />
              Train New Model
            </button>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="px-6 py-4">
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Brain className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{totalModels}</div>
                <div className="text-sm text-gray-500">Total Models</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{metrics?.models_in_production ?? healthyModels}</div>
                <div className="text-sm text-gray-500">In Production</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{metrics?.active_alerts ?? modelsWithDrift}</div>
                <div className="text-sm text-gray-500">Active Alerts</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Activity className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{metrics?.pending_approvals ?? 0}</div>
                <div className="text-sm text-gray-500">Pending Approvals</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Clock className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{metrics?.overdue_reviews ?? 0}</div>
                <div className="text-sm text-gray-500">Overdue Reviews</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-6 pb-6">
        <div className="grid grid-cols-3 gap-6">
          {/* Model List */}
          <div className="col-span-1 bg-white rounded-lg border">
            <div className="p-4 border-b">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">Models</h2>
                <button className="p-1 hover:bg-gray-100 rounded">
                  <Filter className="h-4 w-4 text-gray-500" />
                </button>
              </div>
              <input
                type="text"
                placeholder="Search models..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="divide-y max-h-[600px] overflow-y-auto">
              {filteredModels.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-500">
                  {models.length === 0 ? "No models registered yet." : "No models match your search."}
                </div>
              ) : (
                filteredModels.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => setSelectedModel(model)}
                    className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${
                      selectedModel?.id === model.id ? "bg-blue-50 border-l-2 border-l-blue-600" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="font-medium text-gray-900">{model.name}</div>
                        <div className="text-xs text-gray-500">v{model.currentVersion}</div>
                      </div>
                      <StatusBadge status={model.status} />
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      {model.versions[0]?.metrics.aucRoc > 0 && (
                        <span className="flex items-center gap-1">
                          <Target className="h-3 w-3" />
                          AUC: {(model.versions[0].metrics.aucRoc * 100).toFixed(1)}%
                        </span>
                      )}
                      {model.predictionsLast24h > 0 && (
                        <span className="flex items-center gap-1">
                          <Activity className="h-3 w-3" />
                          {model.predictionsLast24h.toLocaleString()}/day
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{model.riskTier.replace(/_/g, " ")}</span>
                    </div>
                    {model.driftScore > 0.05 && (
                      <div className="mt-2 flex items-center gap-1 text-xs text-yellow-600">
                        <AlertTriangle className="h-3 w-3" />
                        Drift: {(model.driftScore * 100).toFixed(1)}%
                      </div>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Model Details */}
          <div className="col-span-2">
            {selectedModel ? (
              <div className="bg-white rounded-lg border">
                {/* Model Header */}
                <div className="p-4 border-b">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-3">
                        <h2 className="text-xl font-semibold">{selectedModel.name}</h2>
                        <StatusBadge status={selectedModel.status} />
                      </div>
                      <p className="text-sm text-gray-500 mt-1">{selectedModel.description}</p>
                      <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                        <span className="flex items-center gap-1">
                          <GitBranch className="h-4 w-4" />
                          v{selectedModel.currentVersion}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-4 w-4" />
                          Last trained:{" "}
                          {new Date(selectedModel.lastTrained).toLocaleDateString()}
                        </span>
                        {selectedModel.nextScheduledTraining && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-4 w-4" />
                            Next:{" "}
                            {new Date(selectedModel.nextScheduledTraining).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="p-2 hover:bg-gray-100 rounded-lg">
                        <Settings className="h-4 w-4 text-gray-500" />
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg">
                        <Download className="h-4 w-4 text-gray-500" />
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg">
                        <MoreVertical className="h-4 w-4 text-gray-500" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Tabs */}
                <div className="border-b">
                  <div className="flex">
                    {(["overview", "performance", "drift", "training"] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                          activeTab === tab
                            ? "border-blue-600 text-blue-600"
                            : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                      >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tab Content */}
                <div className="p-4">
                  {activeTab === "overview" && (
                    <div className="space-y-6">
                      {/* Key Metrics */}
                      <div className="grid grid-cols-4 gap-4">
                        <MetricCard
                          label="AUC-ROC"
                          value={selectedModel.versions[0].metrics.aucRoc}
                          change={0.006}
                        />
                        <MetricCard
                          label="Precision"
                          value={selectedModel.versions[0].metrics.precision}
                          change={0.02}
                        />
                        <MetricCard
                          label="Recall"
                          value={selectedModel.versions[0].metrics.recall}
                          change={0.01}
                        />
                        <MetricCard
                          label="Brier Score"
                          value={selectedModel.versions[0].metrics.brierScore}
                          change={-0.006}
                        />
                      </div>

                      {/* Charts Row */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Calibration Plot</h3>
                          <CalibrationPlot modelId={selectedModel.id} />
                        </div>
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Top Feature Importance</h3>
                          <FeatureImportanceChart />
                        </div>
                      </div>

                      {/* Model Info */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Model Details</h3>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-500">Model Type</span>
                              <span>{selectedModel.type}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Training Size</span>
                              <span>{selectedModel.versions[0].trainingSize.toLocaleString()} samples</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Features</span>
                              <span>{selectedModel.versions[0].features}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Avg Latency</span>
                              <span>{selectedModel.avgLatencyMs}ms</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Predictions (24h)</span>
                              <span>{selectedModel.predictionsLast24h.toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                        <div className="border rounded-lg p-4">
                          <div className="flex items-center justify-between mb-3">
                            <h3 className="font-medium">Version History</h3>
                            <button
                              onClick={() => setShowVersionHistory(!showVersionHistory)}
                              className="text-sm text-blue-600 hover:underline"
                            >
                              {showVersionHistory ? "Hide" : "Show All"}
                            </button>
                          </div>
                          <div className="space-y-2">
                            {selectedModel.versions
                              .slice(0, showVersionHistory ? undefined : 2)
                              .map((version) => (
                                <div
                                  key={version.version}
                                  className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm"
                                >
                                  <div className="flex items-center gap-2">
                                    <Layers className="h-4 w-4 text-gray-400" />
                                    <span>v{version.version}</span>
                                    {version.status === "active" && (
                                      <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                                        Active
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-gray-500">
                                    {new Date(version.createdAt).toLocaleDateString()}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "performance" && (
                    <div className="space-y-6">
                      {/* Performance Over Time */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Performance Trend</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={staticPerformanceHistory}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                              <YAxis
                                domain={[0.6, 1]}
                                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                                tick={{ fontSize: 11 }}
                              />
                              <Tooltip
                                formatter={(value) => [`${((value as number ?? 0) * 100).toFixed(1)}%`]}
                              />
                              <Line
                                type="monotone"
                                dataKey="aucRoc"
                                stroke="#3b82f6"
                                strokeWidth={2}
                                dot={{ r: 3 }}
                                name="AUC-ROC"
                              />
                              <Line
                                type="monotone"
                                dataKey="precision"
                                stroke="#10b981"
                                strokeWidth={2}
                                dot={{ r: 3 }}
                                name="Precision"
                              />
                              <Line
                                type="monotone"
                                dataKey="recall"
                                stroke="#f59e0b"
                                strokeWidth={2}
                                dot={{ r: 3 }}
                                name="Recall"
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* Detailed Metrics */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="border rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-500 mb-2">
                            Discrimination Metrics
                          </h4>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm">AUC-ROC</span>
                              <span className="font-medium">
                                {(selectedModel.versions[0].metrics.aucRoc * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-600 h-2 rounded-full"
                                style={{
                                  width: `${selectedModel.versions[0].metrics.aucRoc * 100}%`,
                                }}
                              />
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm">AUC-PR</span>
                              <span className="font-medium">
                                {(selectedModel.versions[0].metrics.aucPr * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-green-600 h-2 rounded-full"
                                style={{
                                  width: `${selectedModel.versions[0].metrics.aucPr * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="border rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-500 mb-2">
                            Classification Metrics
                          </h4>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm">Precision</span>
                              <span className="font-medium">
                                {(selectedModel.versions[0].metrics.precision * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm">Recall</span>
                              <span className="font-medium">
                                {(selectedModel.versions[0].metrics.recall * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm">F1 Score</span>
                              <span className="font-medium">
                                {(selectedModel.versions[0].metrics.f1Score * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="border rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-500 mb-2">
                            Calibration Metrics
                          </h4>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm">Brier Score</span>
                              <span className="font-medium">
                                {selectedModel.versions[0].metrics.brierScore.toFixed(3)}
                              </span>
                            </div>
                            <div className="text-xs text-gray-500 mt-2">
                              Lower is better. Perfect calibration = 0
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "drift" && (
                    <div className="space-y-6">
                      {/* Drift Alert */}
                      {selectedModel.driftScore > 0.05 && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                            <div>
                              <h4 className="font-medium text-yellow-800">Data Drift Detected</h4>
                              <p className="text-sm text-yellow-700 mt-1">
                                Population Stability Index (PSI) of{" "}
                                {(selectedModel.driftScore * 100).toFixed(1)}% exceeds threshold.
                                Consider retraining the model.
                              </p>
                              <button className="mt-2 px-3 py-1.5 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700">
                                Schedule Retrain
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Drift Chart */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Population Stability Index (PSI) Trend</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={staticDriftData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                              <YAxis
                                domain={[0, 0.15]}
                                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                                tick={{ fontSize: 11 }}
                              />
                              <Tooltip
                                formatter={(value) => [`${((value as number ?? 0) * 100).toFixed(1)}%`]}
                              />
                              <ReferenceLine
                                y={0.1}
                                stroke="#ef4444"
                                strokeDasharray="5 5"
                                label={{ value: "Threshold", fill: "#ef4444", fontSize: 10 }}
                              />
                              <Area
                                type="monotone"
                                dataKey="psi"
                                stroke="#3b82f6"
                                fill="#93c5fd"
                                fillOpacity={0.3}
                                name="PSI"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* Feature Drift Table */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Feature Drift Analysis</h3>
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b">
                              <th className="text-left py-2 font-medium">Feature</th>
                              <th className="text-right py-2 font-medium">PSI</th>
                              <th className="text-right py-2 font-medium">Status</th>
                              <th className="text-right py-2 font-medium">Trend</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[
                              { name: "Age Distribution", psi: 0.015, status: "stable", trend: "flat" },
                              { name: "Length of Stay", psi: 0.042, status: "monitoring", trend: "up" },
                              { name: "Comorbidity Count", psi: 0.028, status: "stable", trend: "flat" },
                              { name: "Lab Values", psi: 0.065, status: "warning", trend: "up" },
                              { name: "Medication Count", psi: 0.021, status: "stable", trend: "down" },
                            ].map((feature) => (
                              <tr key={feature.name} className="border-b">
                                <td className="py-2">{feature.name}</td>
                                <td className="text-right py-2">
                                  {(feature.psi * 100).toFixed(1)}%
                                </td>
                                <td className="text-right py-2">
                                  <span
                                    className={`px-2 py-0.5 rounded text-xs ${
                                      feature.status === "stable"
                                        ? "bg-green-100 text-green-700"
                                        : feature.status === "monitoring"
                                        ? "bg-blue-100 text-blue-700"
                                        : "bg-yellow-100 text-yellow-700"
                                    }`}
                                  >
                                    {feature.status}
                                  </span>
                                </td>
                                <td className="text-right py-2">
                                  {feature.trend === "up" ? (
                                    <ArrowUp className="h-4 w-4 text-red-500 inline" />
                                  ) : feature.trend === "down" ? (
                                    <ArrowDown className="h-4 w-4 text-green-500 inline" />
                                  ) : (
                                    <span className="text-gray-400">-</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {activeTab === "training" && (
                    <div className="space-y-6">
                      {/* Training Actions */}
                      <div className="flex items-center gap-4">
                        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                          <Play className="h-4 w-4" />
                          Start Training
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50">
                          <Calendar className="h-4 w-4" />
                          Schedule Training
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50">
                          <Database className="h-4 w-4" />
                          Configure Data
                        </button>
                      </div>

                      {/* Training Runs */}
                      <div className="border rounded-lg">
                        <div className="p-4 border-b">
                          <h3 className="font-medium">Training History</h3>
                        </div>
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="text-left px-4 py-3 font-medium">Version</th>
                              <th className="text-left px-4 py-3 font-medium">Status</th>
                              <th className="text-left px-4 py-3 font-medium">Started</th>
                              <th className="text-left px-4 py-3 font-medium">Duration</th>
                              <th className="text-left px-4 py-3 font-medium">Trigger</th>
                              <th className="text-right px-4 py-3 font-medium">AUC-ROC</th>
                              <th className="text-right px-4 py-3 font-medium">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {staticTrainingRuns
                              .filter((run) => run.modelId === selectedModel.id)
                              .map((run) => (
                                <tr key={run.id} className="hover:bg-gray-50">
                                  <td className="px-4 py-3">v{run.version}</td>
                                  <td className="px-4 py-3">
                                    <TrainingStatusBadge status={run.status} />
                                  </td>
                                  <td className="px-4 py-3 text-gray-500">
                                    {new Date(run.startedAt).toLocaleString()}
                                  </td>
                                  <td className="px-4 py-3 text-gray-500">
                                    {run.duration || "-"}
                                  </td>
                                  <td className="px-4 py-3">
                                    <span
                                      className={`px-2 py-0.5 rounded text-xs ${
                                        run.triggeredBy === "scheduled"
                                          ? "bg-gray-100 text-gray-700"
                                          : run.triggeredBy === "manual"
                                          ? "bg-blue-100 text-blue-700"
                                          : "bg-yellow-100 text-yellow-700"
                                      }`}
                                    >
                                      {run.triggeredBy.replace("_", " ")}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    {run.metrics
                                      ? `${(run.metrics.aucRoc * 100).toFixed(1)}%`
                                      : "-"}
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    <button className="p-1 hover:bg-gray-100 rounded">
                                      <FileText className="h-4 w-4 text-gray-500" />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Training Configuration */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Training Configuration</h3>
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Training Data Range
                            </label>
                            <select className="w-full px-3 py-2 border rounded-lg text-sm">
                              <option>Last 12 months</option>
                              <option>Last 6 months</option>
                              <option>Last 3 months</option>
                              <option>Custom range</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Validation Split
                            </label>
                            <select className="w-full px-3 py-2 border rounded-lg text-sm">
                              <option>20% holdout</option>
                              <option>5-fold cross-validation</option>
                              <option>10-fold cross-validation</option>
                              <option>Time-based split</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Auto-retrain Trigger
                            </label>
                            <select className="w-full px-3 py-2 border rounded-lg text-sm">
                              <option>Monthly</option>
                              <option>Quarterly</option>
                              <option>On drift detection</option>
                              <option>Manual only</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Drift Threshold (PSI)
                            </label>
                            <input
                              type="number"
                              defaultValue="0.1"
                              step="0.01"
                              className="w-full px-3 py-2 border rounded-lg text-sm"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border p-12 text-center">
                <Brain className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900">Select a Model</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Choose a model from the list to view its details
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
