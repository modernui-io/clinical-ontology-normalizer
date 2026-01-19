"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  Download,
  Eye,
  Globe2,
  Key,
  Layers,
  Lock,
  MoreVertical,
  Network,
  Play,
  Plus,
  RefreshCw,
  Server,
  Settings,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  X,
  XCircle,
  Zap,
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
  PieChart,
  Pie,
} from "recharts";

// Types
interface Federation {
  federation_id: string;
  name: string;
  description: string | null;
  status: "initializing" | "active" | "training" | "paused" | "completed" | "archived";
  model_type: string;
  aggregation_protocol: string;
  privacy_mechanism: string;
  min_participants: number;
  max_participants: number;
  current_participants: number;
  current_round: number;
  total_rounds: number;
  total_samples: number;
  privacy_budget_epsilon: number;
  privacy_budget_spent: number;
  created_at: string;
  updated_at: string;
  coordinator_id: string | null;
}

interface Participant {
  participant_id: string;
  federation_id: string;
  org_id: string;
  org_name: string;
  org_type: string;
  location: string | null;
  role: "coordinator" | "participant";
  status: string;
  joined_at: string;
  last_update_at: string | null;
  rounds_participated: number;
  total_samples: number;
  contribution_score: number;
}

interface TrainingRound {
  round_id: string;
  federation_id: string;
  round_number: number;
  status: "waiting" | "in_progress" | "aggregating" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  participating_orgs: string[];
  updates_received: number;
  updates_expected: number;
  global_loss: number | null;
  global_metrics: { auc?: number; accuracy?: number };
  privacy_budget_used: number;
}

interface TrainingMetrics {
  federation_id: string;
  current_round: number;
  total_rounds: number;
  global_loss_history: number[];
  global_auc_history: number[];
  global_accuracy_history: number[];
  participants_per_round: number[];
  samples_per_round: number[];
  privacy_budget_spent: number;
  privacy_budget_total: number;
  convergence_rate: number | null;
  estimated_rounds_remaining: number | null;
}

interface GlobalModel {
  model_id: string;
  federation_id: string;
  version: number;
  model_type: string;
  architecture: Record<string, unknown>;
  feature_names: string[];
  training_samples: number;
  performance_metrics: {
    auc?: number;
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1?: number;
  };
  created_at: string;
  updated_at: string;
}

// Mock Data
const mockFederations: Federation[] = [
  {
    federation_id: "fed-demo-12345",
    name: "Multi-Hospital Readmission Study",
    description: "Collaborative study to predict 30-day readmission risk across multiple healthcare systems",
    status: "active",
    model_type: "readmission_prediction",
    aggregation_protocol: "fed_avg",
    privacy_mechanism: "gradient_clipping",
    min_participants: 3,
    max_participants: 100,
    current_participants: 5,
    current_round: 3,
    total_rounds: 10,
    total_samples: 75000,
    privacy_budget_epsilon: 1.0,
    privacy_budget_spent: 0.3,
    created_at: "2026-01-15T10:00:00Z",
    updated_at: "2026-01-19T08:00:00Z",
    coordinator_id: "org-metro-1234",
  },
  {
    federation_id: "fed-mortality-67890",
    name: "ICU Mortality Risk Consortium",
    description: "Multi-center study for in-hospital mortality prediction using federated learning",
    status: "training",
    model_type: "mortality_risk",
    aggregation_protocol: "fed_prox",
    privacy_mechanism: "local_dp",
    min_participants: 4,
    max_participants: 50,
    current_participants: 8,
    current_round: 7,
    total_rounds: 15,
    total_samples: 120000,
    privacy_budget_epsilon: 0.5,
    privacy_budget_spent: 0.35,
    created_at: "2026-01-10T14:00:00Z",
    updated_at: "2026-01-19T09:30:00Z",
    coordinator_id: "org-academic-5678",
  },
  {
    federation_id: "fed-phenotype-11111",
    name: "Diabetes Phenotyping Network",
    description: "Federated phenotyping model for diabetes risk stratification",
    status: "completed",
    model_type: "phenotyping",
    aggregation_protocol: "secure_aggregation",
    privacy_mechanism: "central_dp",
    min_participants: 5,
    max_participants: 30,
    current_participants: 12,
    current_round: 20,
    total_rounds: 20,
    total_samples: 250000,
    privacy_budget_epsilon: 0.8,
    privacy_budget_spent: 0.75,
    created_at: "2025-12-01T08:00:00Z",
    updated_at: "2026-01-10T16:00:00Z",
    coordinator_id: "org-research-9012",
  },
];

const mockParticipants: Participant[] = [
  {
    participant_id: "part-001",
    federation_id: "fed-demo-12345",
    org_id: "org-metro-1234",
    org_name: "Metro General Hospital",
    org_type: "hospital",
    location: "Northeast",
    role: "coordinator",
    status: "active",
    joined_at: "2026-01-15T10:00:00Z",
    last_update_at: "2026-01-19T08:00:00Z",
    rounds_participated: 3,
    total_samples: 18000,
    contribution_score: 0.92,
  },
  {
    participant_id: "part-002",
    federation_id: "fed-demo-12345",
    org_id: "org-univ-5678",
    org_name: "University Medical Center",
    org_type: "hospital",
    location: "Southeast",
    role: "participant",
    status: "active",
    joined_at: "2026-01-15T11:30:00Z",
    last_update_at: "2026-01-19T07:45:00Z",
    rounds_participated: 3,
    total_samples: 22000,
    contribution_score: 0.88,
  },
  {
    participant_id: "part-003",
    federation_id: "fed-demo-12345",
    org_id: "org-regional-9012",
    org_name: "Regional Health System",
    org_type: "hospital",
    location: "Midwest",
    role: "participant",
    status: "active",
    joined_at: "2026-01-15T14:00:00Z",
    last_update_at: "2026-01-19T08:15:00Z",
    rounds_participated: 3,
    total_samples: 15000,
    contribution_score: 0.85,
  },
  {
    participant_id: "part-004",
    federation_id: "fed-demo-12345",
    org_id: "org-community-3456",
    org_name: "Community Hospital Network",
    org_type: "hospital",
    location: "Southwest",
    role: "participant",
    status: "active",
    joined_at: "2026-01-16T09:00:00Z",
    last_update_at: "2026-01-19T07:30:00Z",
    rounds_participated: 2,
    total_samples: 12000,
    contribution_score: 0.78,
  },
  {
    participant_id: "part-005",
    federation_id: "fed-demo-12345",
    org_id: "org-academic-7890",
    org_name: "Academic Medical Center",
    org_type: "hospital",
    location: "West Coast",
    role: "participant",
    status: "active",
    joined_at: "2026-01-17T10:30:00Z",
    last_update_at: "2026-01-19T08:30:00Z",
    rounds_participated: 2,
    total_samples: 8000,
    contribution_score: 0.82,
  },
];

const mockRounds: TrainingRound[] = [
  {
    round_id: "round-1-demo",
    federation_id: "fed-demo-12345",
    round_number: 1,
    status: "completed",
    started_at: "2026-01-16T10:00:00Z",
    completed_at: "2026-01-16T10:45:00Z",
    participating_orgs: ["org-metro-1234", "org-univ-5678", "org-regional-9012"],
    updates_received: 3,
    updates_expected: 3,
    global_loss: 0.45,
    global_metrics: { auc: 0.72, accuracy: 0.68 },
    privacy_budget_used: 0.1,
  },
  {
    round_id: "round-2-demo",
    federation_id: "fed-demo-12345",
    round_number: 2,
    status: "completed",
    started_at: "2026-01-17T10:00:00Z",
    completed_at: "2026-01-17T10:50:00Z",
    participating_orgs: ["org-metro-1234", "org-univ-5678", "org-regional-9012", "org-community-3456"],
    updates_received: 4,
    updates_expected: 4,
    global_loss: 0.38,
    global_metrics: { auc: 0.76, accuracy: 0.72 },
    privacy_budget_used: 0.1,
  },
  {
    round_id: "round-3-demo",
    federation_id: "fed-demo-12345",
    round_number: 3,
    status: "completed",
    started_at: "2026-01-18T10:00:00Z",
    completed_at: "2026-01-18T10:55:00Z",
    participating_orgs: ["org-metro-1234", "org-univ-5678", "org-regional-9012", "org-community-3456", "org-academic-7890"],
    updates_received: 5,
    updates_expected: 5,
    global_loss: 0.32,
    global_metrics: { auc: 0.78, accuracy: 0.74 },
    privacy_budget_used: 0.1,
  },
];

const mockMetrics: TrainingMetrics = {
  federation_id: "fed-demo-12345",
  current_round: 3,
  total_rounds: 10,
  global_loss_history: [0.45, 0.38, 0.32],
  global_auc_history: [0.72, 0.76, 0.78],
  global_accuracy_history: [0.68, 0.72, 0.74],
  participants_per_round: [3, 4, 5],
  samples_per_round: [55000, 67000, 75000],
  privacy_budget_spent: 0.3,
  privacy_budget_total: 1.0,
  convergence_rate: -0.065,
  estimated_rounds_remaining: 5,
};

const mockGlobalModel: GlobalModel = {
  model_id: "model-demo-001",
  federation_id: "fed-demo-12345",
  version: 3,
  model_type: "readmission_prediction",
  architecture: { type: "feedforward_nn", layers: [8, 16, 8, 1] },
  feature_names: [
    "age",
    "length_of_stay",
    "comorbidity_count",
    "prior_admissions",
    "ed_visits_6mo",
    "medication_count",
    "hemoglobin",
    "creatinine",
  ],
  training_samples: 75000,
  performance_metrics: {
    auc: 0.78,
    accuracy: 0.74,
    precision: 0.71,
    recall: 0.68,
    f1: 0.695,
  },
  created_at: "2026-01-16T10:00:00Z",
  updated_at: "2026-01-18T10:55:00Z",
};

// Helper Components
function StatusBadge({ status }: { status: Federation["status"] }) {
  const config = {
    initializing: { color: "bg-gray-100 text-gray-800", icon: Clock },
    active: { color: "bg-green-100 text-green-800", icon: CheckCircle2 },
    training: { color: "bg-blue-100 text-blue-800", icon: RefreshCw },
    paused: { color: "bg-yellow-100 text-yellow-800", icon: AlertTriangle },
    completed: { color: "bg-purple-100 text-purple-800", icon: Target },
    archived: { color: "bg-gray-100 text-gray-600", icon: Database },
  };

  const { color, icon: Icon } = config[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`h-3 w-3 ${status === "training" ? "animate-spin" : ""}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function RoundStatusBadge({ status }: { status: TrainingRound["status"] }) {
  const config = {
    waiting: { color: "bg-gray-100 text-gray-800", icon: Clock },
    in_progress: { color: "bg-blue-100 text-blue-800", icon: RefreshCw },
    aggregating: { color: "bg-purple-100 text-purple-800", icon: Layers },
    completed: { color: "bg-green-100 text-green-800", icon: CheckCircle2 },
    failed: { color: "bg-red-100 text-red-800", icon: XCircle },
  };

  const { color, icon: Icon } = config[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon className={`h-3 w-3 ${status === "in_progress" || status === "aggregating" ? "animate-spin" : ""}`} />
      {status.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
    </span>
  );
}

function PrivacyMechanismBadge({ mechanism }: { mechanism: string }) {
  const config: Record<string, { color: string; label: string }> = {
    none: { color: "bg-gray-100 text-gray-700", label: "No Privacy" },
    gradient_clipping: { color: "bg-blue-100 text-blue-700", label: "Gradient Clipping" },
    local_dp: { color: "bg-green-100 text-green-700", label: "Local DP" },
    central_dp: { color: "bg-purple-100 text-purple-700", label: "Central DP" },
  };

  const { color, label } = config[mechanism] || config.none;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      <Shield className="h-3 w-3" />
      {label}
    </span>
  );
}

function AggregationBadge({ protocol }: { protocol: string }) {
  const config: Record<string, { color: string; label: string }> = {
    fed_avg: { color: "bg-indigo-100 text-indigo-700", label: "FedAvg" },
    fed_prox: { color: "bg-cyan-100 text-cyan-700", label: "FedProx" },
    secure_aggregation: { color: "bg-emerald-100 text-emerald-700", label: "Secure Agg" },
  };

  const { color, label } = config[protocol] || { color: "bg-gray-100 text-gray-700", label: protocol };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      <Network className="h-3 w-3" />
      {label}
    </span>
  );
}

function ProgressRing({ value, max, size = 80, strokeWidth = 8 }: { value: number; max: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const percent = Math.min(value / max, 1);
  const offset = circumference - percent * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-semibold">{Math.round(percent * 100)}%</span>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  format = "percent",
  icon: Icon,
  trend,
}: {
  label: string;
  value: number;
  format?: "percent" | "number" | "decimal";
  icon?: React.ComponentType<{ className?: string }>;
  trend?: number;
}) {
  const formatValue = () => {
    switch (format) {
      case "percent":
        return `${(value * 100).toFixed(1)}%`;
      case "decimal":
        return value.toFixed(3);
      default:
        return value.toLocaleString();
    }
  };

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-500">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-gray-400" />}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold">{formatValue()}</span>
        {trend !== undefined && (
          <span className={`flex items-center text-xs ${trend >= 0 ? "text-green-600" : "text-red-600"}`}>
            <TrendingUp className={`h-3 w-3 ${trend < 0 ? "rotate-180" : ""}`} />
            {Math.abs(trend * 100).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

// Create Federation Modal Component
function CreateFederationModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    model_type: "readmission_prediction",
    aggregation_protocol: "fed_avg",
    privacy_mechanism: "gradient_clipping",
    min_participants: 3,
    rounds_total: 10,
    privacy_budget_epsilon: 1.0,
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b flex items-center justify-between">
          <h2 className="text-xl font-semibold">Create New Federation</h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Federation Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Multi-Hospital Readmission Study"
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe the purpose and goals of this federation..."
              rows={3}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Type</label>
              <select
                value={formData.model_type}
                onChange={(e) => setFormData({ ...formData, model_type: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="readmission_prediction">Readmission Prediction</option>
                <option value="mortality_risk">Mortality Risk</option>
                <option value="length_of_stay">Length of Stay</option>
                <option value="phenotyping">Phenotyping</option>
                <option value="treatment_response">Treatment Response</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Aggregation Protocol</label>
              <select
                value={formData.aggregation_protocol}
                onChange={(e) => setFormData({ ...formData, aggregation_protocol: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="fed_avg">FedAvg (Federated Averaging)</option>
                <option value="fed_prox">FedProx (with Proximal Term)</option>
                <option value="secure_aggregation">Secure Aggregation</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Privacy Mechanism</label>
              <select
                value={formData.privacy_mechanism}
                onChange={(e) => setFormData({ ...formData, privacy_mechanism: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="gradient_clipping">Gradient Clipping</option>
                <option value="local_dp">Local Differential Privacy</option>
                <option value="central_dp">Central Differential Privacy</option>
                <option value="none">No Privacy (Testing Only)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Privacy Budget (Epsilon)</label>
              <input
                type="number"
                value={formData.privacy_budget_epsilon}
                onChange={(e) => setFormData({ ...formData, privacy_budget_epsilon: parseFloat(e.target.value) })}
                step="0.1"
                min="0.1"
                max="10"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Minimum Participants</label>
              <input
                type="number"
                value={formData.min_participants}
                onChange={(e) => setFormData({ ...formData, min_participants: parseInt(e.target.value) })}
                min="2"
                max="50"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Training Rounds</label>
              <input
                type="number"
                value={formData.rounds_total}
                onChange={(e) => setFormData({ ...formData, rounds_total: parseInt(e.target.value) })}
                min="1"
                max="100"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <h4 className="font-medium text-blue-800">Privacy Guarantee</h4>
                <p className="text-sm text-blue-700 mt-1">
                  With epsilon = {formData.privacy_budget_epsilon} and {formData.privacy_mechanism.replace("_", " ")},
                  your federation provides ({formData.privacy_budget_epsilon}, 10^-5)-differential privacy
                  guarantees for participating organizations.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 border-t flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              // In real app, would call API
              onClose();
            }}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Create Federation
          </button>
        </div>
      </div>
    </div>
  );
}

// Main Page Component
export default function FederatedLearningPage() {
  const [federations, setFederations] = useState<Federation[]>(mockFederations);
  const [selectedFederation, setSelectedFederation] = useState<Federation | null>(mockFederations[0]);
  const [participants, setParticipants] = useState<Participant[]>(mockParticipants);
  const [rounds, setRounds] = useState<TrainingRound[]>(mockRounds);
  const [metrics, setMetrics] = useState<TrainingMetrics>(mockMetrics);
  const [globalModel, setGlobalModel] = useState<GlobalModel>(mockGlobalModel);
  const [activeTab, setActiveTab] = useState<"overview" | "participants" | "training" | "model">("overview");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  // Simulate training round
  const handleSimulateRound = async () => {
    if (!selectedFederation || isSimulating) return;

    setIsSimulating(true);

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Update mock data to show new round
    const newRoundNumber = selectedFederation.current_round + 1;
    const newLoss = metrics.global_loss_history[metrics.global_loss_history.length - 1] * 0.9;
    const newAuc = Math.min(0.95, metrics.global_auc_history[metrics.global_auc_history.length - 1] + 0.02);
    const newAccuracy = Math.min(0.92, metrics.global_accuracy_history[metrics.global_accuracy_history.length - 1] + 0.015);

    const newRound: TrainingRound = {
      round_id: `round-${newRoundNumber}-demo`,
      federation_id: selectedFederation.federation_id,
      round_number: newRoundNumber,
      status: "completed",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      participating_orgs: participants.map((p) => p.org_id),
      updates_received: participants.length,
      updates_expected: participants.length,
      global_loss: newLoss,
      global_metrics: { auc: newAuc, accuracy: newAccuracy },
      privacy_budget_used: 0.1,
    };

    setRounds([...rounds, newRound]);
    setMetrics({
      ...metrics,
      current_round: newRoundNumber,
      global_loss_history: [...metrics.global_loss_history, newLoss],
      global_auc_history: [...metrics.global_auc_history, newAuc],
      global_accuracy_history: [...metrics.global_accuracy_history, newAccuracy],
      participants_per_round: [...metrics.participants_per_round, participants.length],
      privacy_budget_spent: metrics.privacy_budget_spent + 0.1,
    });
    setSelectedFederation({
      ...selectedFederation,
      current_round: newRoundNumber,
      privacy_budget_spent: selectedFederation.privacy_budget_spent + 0.1,
    });
    setGlobalModel({
      ...globalModel,
      version: globalModel.version + 1,
      performance_metrics: {
        ...globalModel.performance_metrics,
        auc: newAuc,
        accuracy: newAccuracy,
      },
      updated_at: new Date().toISOString(),
    });

    setIsSimulating(false);
  };

  // Chart data
  const trainingProgressData = metrics.global_loss_history.map((loss, i) => ({
    round: `Round ${i + 1}`,
    loss: loss,
    auc: metrics.global_auc_history[i],
    accuracy: metrics.global_accuracy_history[i],
  }));

  const participationData = metrics.participants_per_round.map((count, i) => ({
    round: `R${i + 1}`,
    participants: count,
    samples: metrics.samples_per_round[i] / 1000,
  }));

  const contributionData = participants.map((p) => ({
    name: p.org_name.split(" ")[0],
    samples: p.total_samples,
    score: p.contribution_score * 100,
  }));

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
              <span>Federated Learning</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Federated Learning</h1>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">
              <Eye className="h-4 w-4" />
              View Documentation
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              Create Federation
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
                <Globe2 className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">{federations.length}</div>
                <div className="text-sm text-gray-500">Federations</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Building2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">
                  {federations.reduce((sum, f) => sum + f.current_participants, 0)}
                </div>
                <div className="text-sm text-gray-500">Total Participants</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Database className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">
                  {(federations.reduce((sum, f) => sum + f.total_samples, 0) / 1000).toFixed(0)}K
                </div>
                <div className="text-sm text-gray-500">Total Samples</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Activity className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">
                  {federations.filter((f) => f.status === "training" || f.status === "active").length}
                </div>
                <div className="text-sm text-gray-500">Active Training</div>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <Shield className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <div className="text-2xl font-semibold">100%</div>
                <div className="text-sm text-gray-500">Privacy Compliant</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-6 pb-6">
        <div className="grid grid-cols-3 gap-6">
          {/* Federation List */}
          <div className="col-span-1 bg-white rounded-lg border">
            <div className="p-4 border-b">
              <h2 className="font-semibold">Federations</h2>
            </div>
            <div className="divide-y max-h-[600px] overflow-y-auto">
              {federations.map((federation) => (
                <button
                  key={federation.federation_id}
                  onClick={() => setSelectedFederation(federation)}
                  className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${
                    selectedFederation?.federation_id === federation.federation_id
                      ? "bg-blue-50 border-l-2 border-l-blue-600"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">{federation.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {federation.model_type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                      </div>
                    </div>
                    <StatusBadge status={federation.status} />
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {federation.current_participants} orgs
                    </span>
                    <span className="flex items-center gap-1">
                      <Layers className="h-3 w-3" />
                      Round {federation.current_round}/{federation.total_rounds}
                    </span>
                  </div>
                  <div className="mt-2">
                    <div className="w-full bg-gray-100 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all"
                        style={{ width: `${(federation.current_round / federation.total_rounds) * 100}%` }}
                      />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Federation Details */}
          <div className="col-span-2">
            {selectedFederation ? (
              <div className="bg-white rounded-lg border">
                {/* Federation Header */}
                <div className="p-4 border-b">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-3">
                        <h2 className="text-xl font-semibold">{selectedFederation.name}</h2>
                        <StatusBadge status={selectedFederation.status} />
                      </div>
                      <p className="text-sm text-gray-500 mt-1">{selectedFederation.description}</p>
                      <div className="flex items-center gap-4 mt-3">
                        <AggregationBadge protocol={selectedFederation.aggregation_protocol} />
                        <PrivacyMechanismBadge mechanism={selectedFederation.privacy_mechanism} />
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleSimulateRound}
                        disabled={isSimulating || selectedFederation.current_round >= selectedFederation.total_rounds}
                        className="flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSimulating ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                        {isSimulating ? "Training..." : "Simulate Round"}
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg">
                        <Settings className="h-4 w-4 text-gray-500" />
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
                    {(["overview", "participants", "training", "model"] as const).map((tab) => (
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
                      {/* Progress Overview */}
                      <div className="grid grid-cols-4 gap-4">
                        <div className="bg-gray-50 rounded-lg p-4 flex items-center gap-4">
                          <ProgressRing
                            value={selectedFederation.current_round}
                            max={selectedFederation.total_rounds}
                          />
                          <div>
                            <div className="text-sm text-gray-500">Training Progress</div>
                            <div className="font-semibold">
                              Round {selectedFederation.current_round} of {selectedFederation.total_rounds}
                            </div>
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-4 flex items-center gap-4">
                          <ProgressRing
                            value={selectedFederation.privacy_budget_spent}
                            max={selectedFederation.privacy_budget_epsilon}
                          />
                          <div>
                            <div className="text-sm text-gray-500">Privacy Budget</div>
                            <div className="font-semibold">
                              {selectedFederation.privacy_budget_spent.toFixed(2)} / {selectedFederation.privacy_budget_epsilon}
                            </div>
                          </div>
                        </div>
                        <MetricCard
                          label="Current AUC"
                          value={globalModel.performance_metrics.auc || 0}
                          icon={Target}
                          trend={0.02}
                        />
                        <MetricCard
                          label="Current Accuracy"
                          value={globalModel.performance_metrics.accuracy || 0}
                          icon={Activity}
                          trend={0.015}
                        />
                      </div>

                      {/* Training Progress Chart */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Training Progress</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trainingProgressData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis dataKey="round" tick={{ fontSize: 11 }} />
                              <YAxis
                                yAxisId="left"
                                domain={[0, 1]}
                                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                                tick={{ fontSize: 11 }}
                              />
                              <YAxis
                                yAxisId="right"
                                orientation="right"
                                domain={[0, 1]}
                                tickFormatter={(v) => v.toFixed(2)}
                                tick={{ fontSize: 11 }}
                              />
                              <Tooltip
                                formatter={(value, name) => [
                                  name === "loss"
                                    ? (value as number).toFixed(3)
                                    : `${((value as number) * 100).toFixed(1)}%`,
                                  (name ?? "").toString().toUpperCase(),
                                ]}
                              />
                              <Line
                                yAxisId="right"
                                type="monotone"
                                dataKey="loss"
                                stroke="#ef4444"
                                strokeWidth={2}
                                dot={{ r: 4 }}
                                name="Loss"
                              />
                              <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="auc"
                                stroke="#3b82f6"
                                strokeWidth={2}
                                dot={{ r: 4 }}
                                name="AUC"
                              />
                              <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="accuracy"
                                stroke="#10b981"
                                strokeWidth={2}
                                dot={{ r: 4 }}
                                name="Accuracy"
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* Federation Details */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Configuration</h3>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-500">Model Type</span>
                              <span>{selectedFederation.model_type.replace("_", " ")}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Aggregation</span>
                              <span>{selectedFederation.aggregation_protocol.replace("_", " ")}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Privacy</span>
                              <span>{selectedFederation.privacy_mechanism.replace("_", " ")}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Min Participants</span>
                              <span>{selectedFederation.min_participants}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Total Samples</span>
                              <span>{selectedFederation.total_samples.toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Participation by Round</h3>
                          <div className="h-40">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={participationData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                <XAxis dataKey="round" tick={{ fontSize: 10 }} />
                                <YAxis yAxisId="left" tick={{ fontSize: 10 }} />
                                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} />
                                <Tooltip />
                                <Bar yAxisId="left" dataKey="participants" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Participants" />
                                <Bar yAxisId="right" dataKey="samples" fill="#10b981" radius={[4, 4, 0, 0]} name="Samples (K)" />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "participants" && (
                    <div className="space-y-6">
                      {/* Participant Stats */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Users className="h-5 w-5 text-blue-600" />
                            <span className="font-medium">Total Participants</span>
                          </div>
                          <div className="text-3xl font-semibold">{participants.length}</div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Database className="h-5 w-5 text-green-600" />
                            <span className="font-medium">Total Samples</span>
                          </div>
                          <div className="text-3xl font-semibold">
                            {participants.reduce((sum, p) => sum + p.total_samples, 0).toLocaleString()}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="h-5 w-5 text-purple-600" />
                            <span className="font-medium">Avg Contribution</span>
                          </div>
                          <div className="text-3xl font-semibold">
                            {(
                              (participants.reduce((sum, p) => sum + p.contribution_score, 0) / participants.length) *
                              100
                            ).toFixed(1)}
                            %
                          </div>
                        </div>
                      </div>

                      {/* Contribution Chart */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Contribution by Organization</h3>
                        <div className="h-48">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={contributionData} layout="vertical">
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                              <XAxis type="number" tick={{ fontSize: 10 }} />
                              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
                              <Tooltip />
                              <Bar dataKey="samples" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Samples">
                                {contributionData.map((_, index) => (
                                  <Cell
                                    key={`cell-${index}`}
                                    fill={index === 0 ? "#3b82f6" : "#93c5fd"}
                                  />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* Participant Table */}
                      <div className="border rounded-lg">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="text-left px-4 py-3 font-medium">Organization</th>
                              <th className="text-left px-4 py-3 font-medium">Role</th>
                              <th className="text-left px-4 py-3 font-medium">Location</th>
                              <th className="text-right px-4 py-3 font-medium">Samples</th>
                              <th className="text-right px-4 py-3 font-medium">Rounds</th>
                              <th className="text-right px-4 py-3 font-medium">Score</th>
                              <th className="text-right px-4 py-3 font-medium">Last Update</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {participants.map((participant) => (
                              <tr key={participant.participant_id} className="hover:bg-gray-50">
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-2">
                                    <Building2 className="h-4 w-4 text-gray-400" />
                                    <span className="font-medium">{participant.org_name}</span>
                                  </div>
                                </td>
                                <td className="px-4 py-3">
                                  <span
                                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                                      participant.role === "coordinator"
                                        ? "bg-purple-100 text-purple-700"
                                        : "bg-gray-100 text-gray-700"
                                    }`}
                                  >
                                    {participant.role}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-gray-500">{participant.location || "-"}</td>
                                <td className="px-4 py-3 text-right">{participant.total_samples.toLocaleString()}</td>
                                <td className="px-4 py-3 text-right">{participant.rounds_participated}</td>
                                <td className="px-4 py-3 text-right">
                                  <span
                                    className={`font-medium ${
                                      participant.contribution_score >= 0.9
                                        ? "text-green-600"
                                        : participant.contribution_score >= 0.8
                                        ? "text-blue-600"
                                        : "text-gray-600"
                                    }`}
                                  >
                                    {(participant.contribution_score * 100).toFixed(0)}%
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-right text-gray-500">
                                  {participant.last_update_at
                                    ? new Date(participant.last_update_at).toLocaleString()
                                    : "-"}
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
                      {/* Training Stats */}
                      <div className="grid grid-cols-4 gap-4">
                        <MetricCard
                          label="Current Round"
                          value={metrics.current_round}
                          format="number"
                          icon={Layers}
                        />
                        <MetricCard
                          label="Latest Loss"
                          value={metrics.global_loss_history[metrics.global_loss_history.length - 1] || 0}
                          format="decimal"
                          icon={Activity}
                        />
                        <MetricCard
                          label="Convergence Rate"
                          value={Math.abs(metrics.convergence_rate || 0)}
                          format="decimal"
                          icon={TrendingUp}
                        />
                        <MetricCard
                          label="Est. Rounds Left"
                          value={metrics.estimated_rounds_remaining || 0}
                          format="number"
                          icon={Clock}
                        />
                      </div>

                      {/* Training Rounds Table */}
                      <div className="border rounded-lg">
                        <div className="p-4 border-b flex items-center justify-between">
                          <h3 className="font-medium">Training History</h3>
                          <button
                            onClick={handleSimulateRound}
                            disabled={isSimulating || selectedFederation.current_round >= selectedFederation.total_rounds}
                            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                          >
                            {isSimulating ? (
                              <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                            Run Next Round
                          </button>
                        </div>
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="text-left px-4 py-3 font-medium">Round</th>
                              <th className="text-left px-4 py-3 font-medium">Status</th>
                              <th className="text-left px-4 py-3 font-medium">Started</th>
                              <th className="text-right px-4 py-3 font-medium">Participants</th>
                              <th className="text-right px-4 py-3 font-medium">Loss</th>
                              <th className="text-right px-4 py-3 font-medium">AUC</th>
                              <th className="text-right px-4 py-3 font-medium">Privacy Used</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {rounds.map((round) => (
                              <tr key={round.round_id} className="hover:bg-gray-50">
                                <td className="px-4 py-3 font-medium">Round {round.round_number}</td>
                                <td className="px-4 py-3">
                                  <RoundStatusBadge status={round.status} />
                                </td>
                                <td className="px-4 py-3 text-gray-500">
                                  {round.started_at ? new Date(round.started_at).toLocaleString() : "-"}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {round.updates_received}/{round.updates_expected}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {round.global_loss?.toFixed(4) || "-"}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {round.global_metrics.auc
                                    ? `${(round.global_metrics.auc * 100).toFixed(1)}%`
                                    : "-"}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {round.privacy_budget_used.toFixed(2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Loss Convergence Chart */}
                      <div className="border rounded-lg p-4">
                        <h3 className="font-medium mb-4">Loss Convergence</h3>
                        <div className="h-48">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart
                              data={trainingProgressData}
                              margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis dataKey="round" tick={{ fontSize: 11 }} />
                              <YAxis
                                domain={[0, "dataMax + 0.1"]}
                                tickFormatter={(v) => v.toFixed(2)}
                                tick={{ fontSize: 11 }}
                              />
                              <Tooltip formatter={(value) => [(value as number).toFixed(4), "Loss"]} />
                              <Area
                                type="monotone"
                                dataKey="loss"
                                stroke="#ef4444"
                                fill="#fecaca"
                                fillOpacity={0.3}
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "model" && (
                    <div className="space-y-6">
                      {/* Model Info */}
                      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <Sparkles className="h-5 w-5 text-blue-600" />
                              <h3 className="text-lg font-semibold">Global Model v{globalModel.version}</h3>
                            </div>
                            <p className="text-sm text-gray-600">
                              {globalModel.model_type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())} model
                              trained on {globalModel.training_samples.toLocaleString()} samples
                            </p>
                            <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                              <span>Updated: {new Date(globalModel.updated_at).toLocaleString()}</span>
                            </div>
                          </div>
                          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                            <Download className="h-4 w-4" />
                            Download Model
                          </button>
                        </div>
                      </div>

                      {/* Performance Metrics */}
                      <div className="grid grid-cols-5 gap-4">
                        <MetricCard
                          label="AUC-ROC"
                          value={globalModel.performance_metrics.auc || 0}
                          icon={Target}
                        />
                        <MetricCard
                          label="Accuracy"
                          value={globalModel.performance_metrics.accuracy || 0}
                          icon={Activity}
                        />
                        <MetricCard
                          label="Precision"
                          value={globalModel.performance_metrics.precision || 0}
                          icon={Zap}
                        />
                        <MetricCard
                          label="Recall"
                          value={globalModel.performance_metrics.recall || 0}
                          icon={Eye}
                        />
                        <MetricCard
                          label="F1 Score"
                          value={globalModel.performance_metrics.f1 || 0}
                          icon={BarChart3}
                        />
                      </div>

                      {/* Model Details */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Architecture</h3>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-500">Type</span>
                              <span>{(globalModel.architecture as { type?: string }).type || "Unknown"}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Layers</span>
                              <span>{((globalModel.architecture as { layers?: number[] }).layers || []).join(" -> ")}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Training Samples</span>
                              <span>{globalModel.training_samples.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Model Version</span>
                              <span>v{globalModel.version}</span>
                            </div>
                          </div>
                        </div>
                        <div className="border rounded-lg p-4">
                          <h3 className="font-medium mb-3">Features ({globalModel.feature_names.length})</h3>
                          <div className="flex flex-wrap gap-2">
                            {globalModel.feature_names.map((feature) => (
                              <span
                                key={feature}
                                className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                              >
                                {feature}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Privacy Guarantees */}
                      <div className="border rounded-lg p-4">
                        <div className="flex items-start gap-3">
                          <Shield className="h-5 w-5 text-green-600 mt-0.5" />
                          <div>
                            <h3 className="font-medium text-green-800">Privacy Guarantees</h3>
                            <p className="text-sm text-green-700 mt-1">
                              This model was trained with {selectedFederation.privacy_mechanism.replace("_", " ")} and
                              provides ({selectedFederation.privacy_budget_epsilon}, 10^-5)-differential privacy
                              guarantees. Privacy budget spent: {selectedFederation.privacy_budget_spent.toFixed(2)} /{" "}
                              {selectedFederation.privacy_budget_epsilon}
                            </p>
                            <div className="mt-3 w-full bg-green-100 rounded-full h-2">
                              <div
                                className="bg-green-600 h-2 rounded-full transition-all"
                                style={{
                                  width: `${
                                    (selectedFederation.privacy_budget_spent / selectedFederation.privacy_budget_epsilon) *
                                    100
                                  }%`,
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border p-12 text-center">
                <Globe2 className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900">Select a Federation</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Choose a federation from the list to view its details
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create Federation Modal */}
      <CreateFederationModal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} />
    </div>
  );
}
