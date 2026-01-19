"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Target,
  Activity,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  Download,
  ChevronDown,
  ChevronUp,
  Search,
  Filter,
  Star,
  Users,
  BarChart3,
  Shield,
  Database,
  FileCheck,
  AlertTriangle,
  Gauge,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  XCircle,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

// Quality Measures Types (existing)
interface QualityMeasure {
  id: string;
  name: string;
  category: string;
  measureType: "hedis" | "cqm" | "mips";
  description: string;
  performanceRate: number;
  benchmark50th: number;
  benchmark90th: number;
  starRating: number;
  eligiblePopulation: number;
  numeratorCount: number;
  denominatorCount: number;
  excludedCount: number;
  totalGaps: number;
  criticalGaps: number;
  previousRate: number | null;
  trend: "up" | "down" | "stable";
}

interface PatientGap {
  id: string;
  patientId: string;
  patientName: string;
  measureId: string;
  measureName: string;
  category: string;
  missingElement: string;
  dueDate: string;
  priority: "critical" | "high" | "medium" | "low";
  daysOverdue: number;
  recommendation: string;
}

interface CategoryPerformance {
  category: string;
  measureCount: number;
  avgPerformance: number;
  meetsBenchmark: number;
  totalGaps: number;
}

// DQD Types (new)
interface DQDSummary {
  overall_score: number;
  executed_at: string;
  execution_time_ms: number;
  completeness_score: number;
  conformance_score: number;
  plausibility_score: number;
  total_checks: number;
  checks_passed: number;
  checks_failed: number;
  checks_warning: number;
  checks_error: number;
  total_issues: number;
  critical_issues: number;
  high_issues: number;
  medium_issues: number;
  low_issues: number;
  category_summaries: DQDCategorySummary[];
  table_summaries: DQDTableSummary[];
}

interface DQDCategorySummary {
  category: string;
  score: number;
  checks_total: number;
  checks_passed: number;
  checks_failed: number;
  checks_warning: number;
  critical_issues: number;
  high_issues: number;
  previous_score: number | null;
  score_change: number | null;
}

interface DQDTableSummary {
  table: string;
  record_count: number;
  score: number;
  completeness_score: number;
  conformance_score: number;
  plausibility_score: number;
  issues_count: number;
  critical_issues: number;
}

interface DQDCheckResult {
  check_id: string;
  check_name: string;
  category: string;
  subcategory: string;
  table: string;
  field: string | null;
  status: "passed" | "failed" | "warning" | "error" | "not_applicable";
  severity: "critical" | "high" | "medium" | "low";
  score: number;
  records_total: number;
  records_passed: number;
  records_failed: number;
  percent_passed: number;
  threshold_value: number;
  message: string;
  failed_examples: Record<string, unknown>[];
  execution_time_ms: number;
  executed_at: string;
}

interface DQDIssue {
  issue_id: string;
  check_id: string;
  table: string;
  field: string | null;
  record_id: string | null;
  severity: "critical" | "high" | "medium" | "low";
  category: string;
  description: string;
  current_value: string | null;
  expected_value: string | null;
  recommendation: string;
  detected_at: string;
  resolved: boolean;
}

interface DQDHistoryEntry {
  run_id: string;
  timestamp: string;
  overall_score: number;
  completeness_score: number;
  conformance_score: number;
  plausibility_score: number;
  total_checks: number;
  checks_passed: number;
  total_issues: number;
}

// ============================================================================
// Mock Data for Quality Measures (existing)
// ============================================================================

const mockMeasures: QualityMeasure[] = [
  {
    id: "HEDIS-CDC-HBA1C",
    name: "Diabetes: HbA1c Control (<8%)",
    category: "Diabetes",
    measureType: "hedis",
    description: "Percentage of patients 18-75 with diabetes whose HbA1c was <8%",
    performanceRate: 0.72,
    benchmark50th: 0.65,
    benchmark90th: 0.78,
    starRating: 4,
    eligiblePopulation: 1250,
    numeratorCount: 900,
    denominatorCount: 1250,
    excludedCount: 45,
    totalGaps: 350,
    criticalGaps: 28,
    previousRate: 0.68,
    trend: "up",
  },
  {
    id: "HEDIS-CDC-EYE",
    name: "Diabetes: Eye Exam",
    category: "Diabetes",
    measureType: "hedis",
    description: "Percentage of patients with diabetes who had a retinal eye exam",
    performanceRate: 0.58,
    benchmark50th: 0.58,
    benchmark90th: 0.72,
    starRating: 3,
    eligiblePopulation: 1250,
    numeratorCount: 725,
    denominatorCount: 1250,
    excludedCount: 30,
    totalGaps: 525,
    criticalGaps: 42,
    previousRate: 0.55,
    trend: "up",
  },
  {
    id: "HEDIS-SPC",
    name: "Statin Therapy for Cardiovascular Disease",
    category: "Cardiovascular",
    measureType: "hedis",
    description: "Patients with ASCVD who were prescribed statin therapy",
    performanceRate: 0.85,
    benchmark50th: 0.80,
    benchmark90th: 0.90,
    starRating: 4,
    eligiblePopulation: 890,
    numeratorCount: 756,
    denominatorCount: 890,
    excludedCount: 25,
    totalGaps: 134,
    criticalGaps: 15,
    previousRate: 0.82,
    trend: "up",
  },
  {
    id: "HEDIS-CBP",
    name: "Controlling High Blood Pressure",
    category: "Cardiovascular",
    measureType: "hedis",
    description: "Patients with hypertension whose BP was <140/90",
    performanceRate: 0.62,
    benchmark50th: 0.65,
    benchmark90th: 0.78,
    starRating: 2,
    eligiblePopulation: 2100,
    numeratorCount: 1302,
    denominatorCount: 2100,
    excludedCount: 85,
    totalGaps: 798,
    criticalGaps: 120,
    previousRate: 0.64,
    trend: "down",
  },
  {
    id: "HEDIS-BCS",
    name: "Breast Cancer Screening",
    category: "Preventive",
    measureType: "hedis",
    description: "Women 50-74 who had a mammogram in the past 2 years",
    performanceRate: 0.75,
    benchmark50th: 0.72,
    benchmark90th: 0.82,
    starRating: 4,
    eligiblePopulation: 1580,
    numeratorCount: 1185,
    denominatorCount: 1580,
    excludedCount: 62,
    totalGaps: 395,
    criticalGaps: 48,
    previousRate: 0.73,
    trend: "up",
  },
  {
    id: "HEDIS-COL",
    name: "Colorectal Cancer Screening",
    category: "Preventive",
    measureType: "hedis",
    description: "Adults 50-75 who had appropriate colorectal cancer screening",
    performanceRate: 0.68,
    benchmark50th: 0.68,
    benchmark90th: 0.80,
    starRating: 3,
    eligiblePopulation: 3200,
    numeratorCount: 2176,
    denominatorCount: 3200,
    excludedCount: 145,
    totalGaps: 1024,
    criticalGaps: 85,
    previousRate: 0.66,
    trend: "up",
  },
  {
    id: "HEDIS-AMM-ACUTE",
    name: "Antidepressant Medication Management - Acute",
    category: "Behavioral Health",
    measureType: "hedis",
    description: "Patients with depression who remained on antidepressant for 84 days",
    performanceRate: 0.55,
    benchmark50th: 0.58,
    benchmark90th: 0.72,
    starRating: 2,
    eligiblePopulation: 450,
    numeratorCount: 248,
    denominatorCount: 450,
    excludedCount: 18,
    totalGaps: 202,
    criticalGaps: 35,
    previousRate: 0.52,
    trend: "up",
  },
  {
    id: "CQM-IMM-2",
    name: "Adult Immunization: Influenza",
    category: "Preventive",
    measureType: "cqm",
    description: "Adults 18+ who received influenza vaccine during flu season",
    performanceRate: 0.48,
    benchmark50th: 0.48,
    benchmark90th: 0.60,
    starRating: 3,
    eligiblePopulation: 5200,
    numeratorCount: 2496,
    denominatorCount: 5200,
    excludedCount: 210,
    totalGaps: 2704,
    criticalGaps: 180,
    previousRate: 0.45,
    trend: "up",
  },
];

const mockPatientGaps: PatientGap[] = [
  {
    id: "gap-1",
    patientId: "P001",
    patientName: "John Smith",
    measureId: "HEDIS-CDC-HBA1C",
    measureName: "Diabetes: HbA1c Control",
    category: "Diabetes",
    missingElement: "HbA1c test overdue by 45 days",
    dueDate: "2025-11-15",
    priority: "critical",
    daysOverdue: 45,
    recommendation: "Order HbA1c test. Target <8% for most patients.",
  },
  {
    id: "gap-2",
    patientId: "P003",
    patientName: "Mary Johnson",
    measureId: "HEDIS-CDC-EYE",
    measureName: "Diabetes: Eye Exam",
    category: "Diabetes",
    missingElement: "Annual dilated eye exam not documented",
    dueDate: "2025-12-31",
    priority: "high",
    daysOverdue: 0,
    recommendation: "Schedule dilated eye exam with ophthalmologist.",
  },
  {
    id: "gap-3",
    patientId: "P008",
    patientName: "Robert Williams",
    measureId: "HEDIS-CBP",
    measureName: "Controlling High Blood Pressure",
    category: "Cardiovascular",
    missingElement: "Last BP reading 148/94 (target: <140/90)",
    dueDate: "2025-12-31",
    priority: "high",
    daysOverdue: 0,
    recommendation: "Medication adjustment recommended. Schedule follow-up.",
  },
  {
    id: "gap-4",
    patientId: "P012",
    patientName: "Lisa Brown",
    measureId: "HEDIS-BCS",
    measureName: "Breast Cancer Screening",
    category: "Preventive",
    missingElement: "Mammogram due (last: 2023-06-15)",
    dueDate: "2025-06-15",
    priority: "medium",
    daysOverdue: 0,
    recommendation: "Schedule screening mammogram.",
  },
  {
    id: "gap-5",
    patientId: "P015",
    patientName: "David Garcia",
    measureId: "HEDIS-COL",
    measureName: "Colorectal Cancer Screening",
    category: "Preventive",
    missingElement: "No colonoscopy or FIT in record",
    dueDate: "2025-12-31",
    priority: "high",
    daysOverdue: 0,
    recommendation: "Discuss screening options: colonoscopy or annual FIT.",
  },
  {
    id: "gap-6",
    patientId: "P018",
    patientName: "Sarah Miller",
    measureId: "HEDIS-AMM-ACUTE",
    measureName: "Antidepressant Medication Management",
    category: "Behavioral Health",
    missingElement: "Antidepressant discontinued after 42 days",
    dueDate: "2025-12-31",
    priority: "critical",
    daysOverdue: 0,
    recommendation: "Contact patient. Acute phase requires 84 days of treatment.",
  },
];

// ============================================================================
// Helper Functions
// ============================================================================

const getCategoryPerformance = (measures: QualityMeasure[]): CategoryPerformance[] => {
  const categories = new Map<string, QualityMeasure[]>();
  measures.forEach((m) => {
    const list = categories.get(m.category) || [];
    list.push(m);
    categories.set(m.category, list);
  });

  return Array.from(categories.entries()).map(([category, list]) => ({
    category,
    measureCount: list.length,
    avgPerformance: list.reduce((sum, m) => sum + m.performanceRate, 0) / list.length,
    meetsBenchmark: list.filter((m) => m.performanceRate >= m.benchmark50th).length,
    totalGaps: list.reduce((sum, m) => sum + m.totalGaps, 0),
  }));
};

const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case "critical":
      return "bg-red-600 text-white";
    case "high":
      return "bg-red-500 text-white";
    case "medium":
      return "bg-amber-500 text-white";
    case "low":
      return "bg-blue-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
};

const getMeasureTypeColor = (type: string): string => {
  switch (type) {
    case "hedis":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "cqm":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "mips":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getStarDisplay = (rating: number) => {
  return Array.from({ length: 5 }, (_, i) => (
    <Star
      key={i}
      className={`h-4 w-4 ${
        i < rating
          ? "fill-amber-400 text-amber-400"
          : "fill-gray-200 text-gray-200 dark:fill-gray-700 dark:text-gray-700"
      }`}
    />
  ));
};

const getScoreColor = (score: number): string => {
  if (score >= 90) return "text-green-600 dark:text-green-400";
  if (score >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
};

const getScoreBgColor = (score: number): string => {
  if (score >= 90) return "bg-green-500";
  if (score >= 75) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
};

const getStatusBadge = (status: string) => {
  switch (status) {
    case "passed":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Passed</Badge>;
    case "failed":
      return <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">Failed</Badge>;
    case "warning":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Warning</Badge>;
    case "error":
      return <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">Error</Badge>;
    default:
      return <Badge variant="outline">N/A</Badge>;
  }
};

const getSeverityBadge = (severity: string) => {
  switch (severity) {
    case "critical":
      return <Badge className="bg-red-600 text-white">Critical</Badge>;
    case "high":
      return <Badge className="bg-red-500 text-white">High</Badge>;
    case "medium":
      return <Badge className="bg-amber-500 text-white">Medium</Badge>;
    case "low":
      return <Badge className="bg-blue-500 text-white">Low</Badge>;
    default:
      return <Badge variant="outline">{severity}</Badge>;
  }
};

const getCategoryIcon = (category: string) => {
  switch (category) {
    case "completeness":
      return <FileCheck className="h-5 w-5" />;
    case "conformance":
      return <Shield className="h-5 w-5" />;
    case "plausibility":
      return <Gauge className="h-5 w-5" />;
    default:
      return <Database className="h-5 w-5" />;
  }
};

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

async function fetchDQDSummary(): Promise<DQDSummary> {
  const response = await fetch(`${API_BASE}/quality/dqd/summary`);
  if (!response.ok) throw new Error("Failed to fetch DQD summary");
  return response.json();
}

async function fetchDQDChecks(category?: string): Promise<{ checks: DQDCheckResult[] }> {
  const url = category
    ? `${API_BASE}/quality/dqd/checks/${category}`
    : `${API_BASE}/quality/dqd/checks`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch DQD checks");
  return response.json();
}

async function fetchDQDHistory(limit: number = 30): Promise<{ entries: DQDHistoryEntry[] }> {
  const response = await fetch(`${API_BASE}/quality/dqd/history?limit=${limit}`);
  if (!response.ok) throw new Error("Failed to fetch DQD history");
  return response.json();
}

async function fetchDQDIssues(severity?: string): Promise<{ issues: DQDIssue[] }> {
  const url = severity
    ? `${API_BASE}/quality/dqd/issues?severity=${severity}`
    : `${API_BASE}/quality/dqd/issues`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch DQD issues");
  return response.json();
}

async function runDQDChecks(): Promise<{ summary: DQDSummary }> {
  const response = await fetch(`${API_BASE}/quality/dqd/run`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to run DQD checks");
  return response.json();
}

// ============================================================================
// Gauge Component for Overall Score
// ============================================================================

function ScoreGauge({ score, size = "large" }: { score: number; size?: "large" | "small" }) {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;
  const isLarge = size === "large";

  return (
    <div className={`relative ${isLarge ? "w-48 h-48" : "w-24 h-24"}`}>
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
        {/* Background circle */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          className="text-gray-200 dark:text-gray-700"
          strokeWidth={isLarge ? "8" : "6"}
        />
        {/* Progress circle */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          className={getScoreColor(score)}
          strokeWidth={isLarge ? "8" : "6"}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 0.5s ease-in-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-bold ${getScoreColor(score)} ${isLarge ? "text-4xl" : "text-xl"}`}>
          {score.toFixed(1)}
        </span>
        {isLarge && <span className="text-sm text-muted-foreground">Overall Score</span>}
      </div>
    </div>
  );
}

// ============================================================================
// Trend Sparkline Component
// ============================================================================

function TrendSparkline({ data, height = 40 }: { data: number[]; height?: number }) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 100;
  const stepX = width / (data.length - 1);

  const points = data
    .map((v, i) => `${i * stepX},${height - ((v - min) / range) * (height - 4) - 2}`)
    .join(" ");

  return (
    <svg width={width} height={height} className="text-emerald-500">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function QualityDashboardPage() {
  // Quality Measures State
  const [measures] = useState<QualityMeasure[]>(mockMeasures);
  const [patientGaps] = useState<PatientGap[]>(mockPatientGaps);
  const [measureSearchQuery, setMeasureSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [expandedMeasure, setExpandedMeasure] = useState<string | null>(null);

  // DQD State
  const [dqdSummary, setDqdSummary] = useState<DQDSummary | null>(null);
  const [dqdChecks, setDqdChecks] = useState<DQDCheckResult[]>([]);
  const [dqdHistory, setDqdHistory] = useState<DQDHistoryEntry[]>([]);
  const [dqdIssues, setDqdIssues] = useState<DQDIssue[]>([]);
  const [dqdLoading, setDqdLoading] = useState(true);
  const [dqdError, setDqdError] = useState<string | null>(null);
  const [dqdCheckFilter, setDqdCheckFilter] = useState<string>("all");
  const [dqdSeverityFilter, setDqdSeverityFilter] = useState<string>("all");
  const [isRunningChecks, setIsRunningChecks] = useState(false);

  // Derived state
  const categories = ["all", ...new Set(measures.map((m) => m.category))];
  const categoryPerformance = getCategoryPerformance(measures);

  const filteredMeasures = measures.filter((m) => {
    const matchesSearch =
      measureSearchQuery === "" ||
      m.name.toLowerCase().includes(measureSearchQuery.toLowerCase()) ||
      m.id.toLowerCase().includes(measureSearchQuery.toLowerCase());
    const matchesCategory =
      categoryFilter === "all" || m.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const filteredGaps = patientGaps.filter((g) => {
    const matchesCategory =
      categoryFilter === "all" || g.category === categoryFilter;
    return matchesCategory;
  });

  const totalGaps = measures.reduce((sum, m) => sum + m.totalGaps, 0);
  const criticalGaps = measures.reduce((sum, m) => sum + m.criticalGaps, 0);
  const avgPerformance =
    measures.reduce((sum, m) => sum + m.performanceRate, 0) / measures.length;
  const meetsBenchmark = measures.filter(
    (m) => m.performanceRate >= m.benchmark50th
  ).length;

  // DQD Data Fetching
  const loadDqdData = useCallback(async () => {
    setDqdLoading(true);
    setDqdError(null);
    try {
      const [summaryRes, checksRes, historyRes, issuesRes] = await Promise.all([
        fetchDQDSummary(),
        fetchDQDChecks(),
        fetchDQDHistory(),
        fetchDQDIssues(),
      ]);
      setDqdSummary(summaryRes);
      setDqdChecks(checksRes.checks);
      setDqdHistory(historyRes.entries);
      setDqdIssues(issuesRes.issues);
    } catch (err) {
      setDqdError(err instanceof Error ? err.message : "Failed to load DQD data");
    } finally {
      setDqdLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDqdData();
  }, [loadDqdData]);

  const handleRunChecks = async () => {
    setIsRunningChecks(true);
    try {
      await runDQDChecks();
      await loadDqdData();
    } catch (err) {
      setDqdError(err instanceof Error ? err.message : "Failed to run checks");
    } finally {
      setIsRunningChecks(false);
    }
  };

  const handleExportDQD = () => {
    if (!dqdSummary || !dqdChecks) return;

    const exportData = {
      summary: dqdSummary,
      checks: dqdChecks,
      issues: dqdIssues,
      exportedAt: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dqd-report-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filter DQD checks
  const filteredDqdChecks = dqdChecks.filter((c) => {
    if (dqdCheckFilter !== "all" && c.category !== dqdCheckFilter) return false;
    if (dqdSeverityFilter !== "all" && c.severity !== dqdSeverityFilter) return false;
    return true;
  });

  // Filter DQD issues
  const filteredDqdIssues = dqdIssues.filter((i) => {
    if (dqdCheckFilter !== "all" && i.category !== dqdCheckFilter) return false;
    if (dqdSeverityFilter !== "all" && i.severity !== dqdSeverityFilter) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Quality Dashboard</h1>
          <p className="text-muted-foreground">
            Data quality validation and clinical quality measures
          </p>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="dqd" className="space-y-6">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="dqd" className="gap-2">
            <Database className="h-4 w-4" />
            Data Quality (DQD)
          </TabsTrigger>
          <TabsTrigger value="measures" className="gap-2">
            <Target className="h-4 w-4" />
            Quality Measures
          </TabsTrigger>
        </TabsList>

        {/* ================================================================
            DQD TAB
            ================================================================ */}
        <TabsContent value="dqd" className="space-y-6">
          {dqdError && (
            <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
              <CardContent className="flex items-center gap-3 py-4">
                <AlertCircle className="h-5 w-5 text-red-600" />
                <span className="text-red-700 dark:text-red-300">{dqdError}</span>
                <Button variant="outline" size="sm" onClick={loadDqdData} className="ml-auto">
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {/* DQD Header with Actions */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">OHDSI Data Quality Dashboard</h2>
              <p className="text-sm text-muted-foreground">
                Validating Completeness, Conformance, and Plausibility of OMOP CDM data
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRunChecks}
                disabled={isRunningChecks || dqdLoading}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${isRunningChecks ? "animate-spin" : ""}`} />
                Run Checks
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportDQD} disabled={!dqdSummary}>
                <Download className="mr-2 h-4 w-4" />
                Export Report
              </Button>
            </div>
          </div>

          {dqdLoading && !dqdSummary ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : dqdSummary && (
            <>
              {/* Overall Score Card */}
              <div className="grid gap-6 lg:grid-cols-3">
                <Card className="lg:row-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Gauge className="h-5 w-5" />
                      Overall Quality Score
                    </CardTitle>
                    <CardDescription>
                      Aggregate score across all quality dimensions
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col items-center gap-4">
                    <ScoreGauge score={dqdSummary.overall_score} />
                    <div className="grid grid-cols-3 gap-4 w-full text-center">
                      <div>
                        <div className={`text-xl font-bold ${getScoreColor(dqdSummary.completeness_score)}`}>
                          {dqdSummary.completeness_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-muted-foreground">Completeness</div>
                      </div>
                      <div>
                        <div className={`text-xl font-bold ${getScoreColor(dqdSummary.conformance_score)}`}>
                          {dqdSummary.conformance_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-muted-foreground">Conformance</div>
                      </div>
                      <div>
                        <div className={`text-xl font-bold ${getScoreColor(dqdSummary.plausibility_score)}`}>
                          {dqdSummary.plausibility_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-muted-foreground">Plausibility</div>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Last updated: {new Date(dqdSummary.executed_at).toLocaleString()}
                    </div>
                  </CardContent>
                </Card>

                {/* Summary Stats */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Checks Executed</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">{dqdSummary.total_checks}</div>
                    <div className="flex items-center gap-4 mt-2 text-sm">
                      <span className="flex items-center gap-1 text-green-600">
                        <CheckCircle className="h-4 w-4" />
                        {dqdSummary.checks_passed} passed
                      </span>
                      <span className="flex items-center gap-1 text-red-600">
                        <XCircle className="h-4 w-4" />
                        {dqdSummary.checks_failed} failed
                      </span>
                    </div>
                    <Progress
                      value={(dqdSummary.checks_passed / dqdSummary.total_checks) * 100}
                      className="mt-3 h-2"
                    />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Issues Found</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">{dqdSummary.total_issues}</div>
                    <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
                      <div className="text-center">
                        <div className="font-bold text-red-600">{dqdSummary.critical_issues}</div>
                        <div className="text-muted-foreground">Critical</div>
                      </div>
                      <div className="text-center">
                        <div className="font-bold text-red-500">{dqdSummary.high_issues}</div>
                        <div className="text-muted-foreground">High</div>
                      </div>
                      <div className="text-center">
                        <div className="font-bold text-amber-500">{dqdSummary.medium_issues}</div>
                        <div className="text-muted-foreground">Medium</div>
                      </div>
                      <div className="text-center">
                        <div className="font-bold text-blue-500">{dqdSummary.low_issues}</div>
                        <div className="text-muted-foreground">Low</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Category Breakdown */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5" />
                      Quality by Category
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 sm:grid-cols-3">
                      {dqdSummary.category_summaries.map((cat) => (
                        <div key={cat.category} className="rounded-lg border p-4">
                          <div className="flex items-center gap-2 mb-2">
                            {getCategoryIcon(cat.category)}
                            <span className="font-medium capitalize">{cat.category}</span>
                          </div>
                          <div className={`text-3xl font-bold ${getScoreColor(cat.score)}`}>
                            {cat.score.toFixed(1)}%
                          </div>
                          <Progress
                            value={cat.score}
                            className="mt-2 h-2"
                          />
                          <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                            <span>{cat.checks_passed}/{cat.checks_total} passed</span>
                            <span>{cat.critical_issues + cat.high_issues} issues</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Trend Chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Quality Score Trend
                  </CardTitle>
                  <CardDescription>
                    Overall quality score over the past 30 days
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {dqdHistory.length > 0 ? (
                    <div className="space-y-4">
                      {/* Simple trend visualization */}
                      <div className="flex items-end gap-1 h-32">
                        {dqdHistory.slice(-30).map((entry, i) => (
                          <div
                            key={entry.run_id}
                            className="flex-1 rounded-t transition-all hover:opacity-80"
                            style={{
                              height: `${(entry.overall_score / 100) * 100}%`,
                              backgroundColor: entry.overall_score >= 80
                                ? "rgb(34, 197, 94)"
                                : entry.overall_score >= 60
                                ? "rgb(245, 158, 11)"
                                : "rgb(239, 68, 68)",
                            }}
                            title={`${new Date(entry.timestamp).toLocaleDateString()}: ${entry.overall_score.toFixed(1)}%`}
                          />
                        ))}
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{new Date(dqdHistory[dqdHistory.length - 1]?.timestamp).toLocaleDateString()}</span>
                        <span>{new Date(dqdHistory[0]?.timestamp).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed bg-muted/30">
                      <p className="text-sm text-muted-foreground">No historical data available</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Table Quality */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Quality by OMOP Table
                  </CardTitle>
                  <CardDescription>
                    Quality scores for each OMOP CDM table
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Table</TableHead>
                        <TableHead className="text-right">Records</TableHead>
                        <TableHead className="text-right">Overall</TableHead>
                        <TableHead className="text-right">Completeness</TableHead>
                        <TableHead className="text-right">Conformance</TableHead>
                        <TableHead className="text-right">Plausibility</TableHead>
                        <TableHead className="text-right">Issues</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dqdSummary.table_summaries.map((table) => (
                        <TableRow key={table.table}>
                          <TableCell className="font-medium">{table.table}</TableCell>
                          <TableCell className="text-right">{table.record_count.toLocaleString()}</TableCell>
                          <TableCell className={`text-right font-bold ${getScoreColor(table.score)}`}>
                            {table.score.toFixed(1)}%
                          </TableCell>
                          <TableCell className={`text-right ${getScoreColor(table.completeness_score)}`}>
                            {table.completeness_score.toFixed(1)}%
                          </TableCell>
                          <TableCell className={`text-right ${getScoreColor(table.conformance_score)}`}>
                            {table.conformance_score.toFixed(1)}%
                          </TableCell>
                          <TableCell className={`text-right ${getScoreColor(table.plausibility_score)}`}>
                            {table.plausibility_score.toFixed(1)}%
                          </TableCell>
                          <TableCell className="text-right">
                            {table.critical_issues > 0 && (
                              <Badge className="bg-red-600 text-white mr-1">{table.critical_issues}</Badge>
                            )}
                            {table.issues_count - table.critical_issues > 0 && (
                              <Badge variant="outline">{table.issues_count - table.critical_issues}</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Check Results and Issues */}
              <div className="grid gap-6 lg:grid-cols-2">
                {/* Check Results */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Check Results</CardTitle>
                        <CardDescription>Individual quality check results</CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Select value={dqdCheckFilter} onValueChange={setDqdCheckFilter}>
                          <SelectTrigger className="w-32">
                            <SelectValue placeholder="Category" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All</SelectItem>
                            <SelectItem value="completeness">Completeness</SelectItem>
                            <SelectItem value="conformance">Conformance</SelectItem>
                            <SelectItem value="plausibility">Plausibility</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2">
                        {filteredDqdChecks.slice(0, 50).map((check) => (
                          <div
                            key={check.check_id}
                            className="rounded-lg border p-3 hover:bg-muted/50"
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-medium text-sm">{check.check_name}</span>
                                  {getStatusBadge(check.status)}
                                </div>
                                <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                  <Badge variant="outline" className="capitalize">{check.category}</Badge>
                                  <span>{check.table}</span>
                                  {check.field && <span>.{check.field}</span>}
                                </div>
                              </div>
                              <div className="text-right">
                                <div className={`text-lg font-bold ${getScoreColor(check.score)}`}>
                                  {check.score.toFixed(1)}%
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  {check.records_passed.toLocaleString()}/{check.records_total.toLocaleString()}
                                </div>
                              </div>
                            </div>
                            {check.status !== "passed" && (
                              <div className="mt-2 text-xs text-muted-foreground">
                                {check.message}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>

                {/* Issues */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Active Issues</CardTitle>
                        <CardDescription>Data quality issues requiring attention</CardDescription>
                      </div>
                      <Select value={dqdSeverityFilter} onValueChange={setDqdSeverityFilter}>
                        <SelectTrigger className="w-32">
                          <SelectValue placeholder="Severity" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All</SelectItem>
                          <SelectItem value="critical">Critical</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2">
                        {filteredDqdIssues.length === 0 ? (
                          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                            <CheckCircle className="h-12 w-12 mb-2" />
                            <p>No issues match the current filter</p>
                          </div>
                        ) : (
                          filteredDqdIssues.slice(0, 50).map((issue) => (
                            <div
                              key={issue.issue_id}
                              className="rounded-lg border p-3 hover:bg-muted/50"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    {getSeverityBadge(issue.severity)}
                                    <span className="font-medium text-sm">{issue.table}</span>
                                    {issue.field && <span className="text-sm text-muted-foreground">.{issue.field}</span>}
                                  </div>
                                  <p className="text-sm mt-1">{issue.description}</p>
                                  {issue.recommendation && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                      {issue.recommendation}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>

        {/* ================================================================
            QUALITY MEASURES TAB
            ================================================================ */}
        <TabsContent value="measures" className="space-y-6">
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Average Performance</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{(avgPerformance * 100).toFixed(1)}%</div>
                <Progress value={avgPerformance * 100} className="mt-2 h-2" />
                <p className="text-xs text-muted-foreground mt-2">
                  {meetsBenchmark}/{measures.length} measures meet benchmark
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Total Care Gaps</CardTitle>
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{totalGaps.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    {criticalGaps} critical
                  </span>{" "}
                  gaps require immediate attention
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Measures Tracked</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{measures.length}</div>
                <p className="text-xs text-muted-foreground">
                  {measures.filter((m) => m.measureType === "hedis").length} HEDIS,{" "}
                  {measures.filter((m) => m.measureType === "cqm").length} CQM
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Eligible Patients</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {measures.reduce((sum, m) => sum + m.eligiblePopulation, 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">Across all quality measures</p>
              </CardContent>
            </Card>
          </div>

          {/* Performance by Category */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Performance by Category
              </CardTitle>
              <CardDescription>Aggregate performance across measure categories</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {categoryPerformance.map((cat) => (
                  <div key={cat.category} className="rounded-lg border p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{cat.category}</span>
                      <Badge variant="outline">{cat.measureCount} measures</Badge>
                    </div>
                    <div className="text-2xl font-bold">{(cat.avgPerformance * 100).toFixed(1)}%</div>
                    <Progress value={cat.avgPerformance * 100} className="h-2" />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>{cat.meetsBenchmark}/{cat.measureCount} meet benchmark</span>
                      <span>{cat.totalGaps.toLocaleString()} gaps</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Measures and Gaps Tabs */}
          <Tabs defaultValue="measures-list" className="space-y-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <TabsList>
                <TabsTrigger value="measures-list" className="gap-2">
                  <Target className="h-4 w-4" />
                  Measures
                </TabsTrigger>
                <TabsTrigger value="gaps-list" className="gap-2">
                  <AlertCircle className="h-4 w-4" />
                  Patient Gaps
                </TabsTrigger>
              </TabsList>

              <div className="flex gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search measures..."
                    value={measureSearchQuery}
                    onChange={(e) => setMeasureSearchQuery(e.target.value)}
                    className="pl-8 w-[200px]"
                  />
                </div>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {cat === "all" ? "All Categories" : cat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Measures List */}
            <TabsContent value="measures-list" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Quality Measure Performance</CardTitle>
                  <CardDescription>Click on a measure to see detailed information</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {filteredMeasures.map((measure) => (
                      <div key={measure.id} className="rounded-lg border transition-colors">
                        <div
                          className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                          onClick={() =>
                            setExpandedMeasure(expandedMeasure === measure.id ? null : measure.id)
                          }
                        >
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium">{measure.name}</span>
                              <Badge className={getMeasureTypeColor(measure.measureType)}>
                                {measure.measureType.toUpperCase()}
                              </Badge>
                              <Badge variant="outline">{measure.category}</Badge>
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{measure.id}</code>
                              <span className="flex items-center gap-1">{getStarDisplay(measure.starRating)}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-6">
                            <div className="text-right">
                              <div className="flex items-center gap-2">
                                <span className="text-lg font-bold">{(measure.performanceRate * 100).toFixed(1)}%</span>
                                {measure.trend === "up" ? (
                                  <TrendingUp className="h-4 w-4 text-green-600" />
                                ) : measure.trend === "down" ? (
                                  <TrendingDown className="h-4 w-4 text-red-600" />
                                ) : null}
                              </div>
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <span>Benchmark: {(measure.benchmark50th * 100).toFixed(0)}%</span>
                                {measure.performanceRate >= measure.benchmark50th ? (
                                  <CheckCircle className="h-3 w-3 text-green-600" />
                                ) : (
                                  <AlertCircle className="h-3 w-3 text-amber-500" />
                                )}
                              </div>
                            </div>

                            <div className="w-32">
                              <Progress value={measure.performanceRate * 100} className="h-2" />
                            </div>

                            <div className="text-right min-w-[80px]">
                              <div className="text-sm font-medium">{measure.totalGaps.toLocaleString()} gaps</div>
                              {measure.criticalGaps > 0 && (
                                <div className="text-xs text-red-600">{measure.criticalGaps} critical</div>
                              )}
                            </div>

                            {expandedMeasure === measure.id ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </div>
                        </div>

                        {expandedMeasure === measure.id && (
                          <div className="border-t p-4 bg-muted/20">
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                              <div>
                                <h4 className="text-sm font-medium mb-2">Description</h4>
                                <p className="text-sm text-muted-foreground">{measure.description}</p>
                              </div>
                              <div>
                                <h4 className="text-sm font-medium mb-2">Population</h4>
                                <div className="space-y-1 text-sm">
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">Eligible:</span>
                                    <span>{measure.eligiblePopulation.toLocaleString()}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">Numerator:</span>
                                    <span>{measure.numeratorCount.toLocaleString()}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">Excluded:</span>
                                    <span>{measure.excludedCount.toLocaleString()}</span>
                                  </div>
                                </div>
                              </div>
                              <div>
                                <h4 className="text-sm font-medium mb-2">Benchmarks</h4>
                                <div className="space-y-1 text-sm">
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">50th percentile:</span>
                                    <span>{(measure.benchmark50th * 100).toFixed(0)}%</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-muted-foreground">90th percentile:</span>
                                    <span>{(measure.benchmark90th * 100).toFixed(0)}%</span>
                                  </div>
                                  {measure.previousRate && (
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">Previous:</span>
                                      <span>{(measure.previousRate * 100).toFixed(0)}%</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                              <div>
                                <h4 className="text-sm font-medium mb-2">Actions</h4>
                                <div className="space-y-2">
                                  <Button variant="outline" size="sm" className="w-full">
                                    View Patient List
                                  </Button>
                                  <Button variant="outline" size="sm" className="w-full">
                                    Export Data
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Patient Gaps List */}
            <TabsContent value="gaps-list" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Patient Care Gaps</CardTitle>
                      <CardDescription>Patients with missing or overdue quality measure requirements</CardDescription>
                    </div>
                    <Button variant="outline" size="sm">
                      <Download className="mr-2 h-4 w-4" />
                      Export Gap List
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Patient</TableHead>
                        <TableHead>Measure</TableHead>
                        <TableHead>Missing Element</TableHead>
                        <TableHead>Due Date</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredGaps.map((gap) => (
                        <TableRow key={gap.id}>
                          <TableCell>
                            <div>
                              <div className="font-medium">{gap.patientName}</div>
                              <div className="text-xs text-muted-foreground">{gap.patientId}</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div>
                              <div className="font-medium text-sm">{gap.measureName}</div>
                              <Badge variant="outline" className="text-xs">{gap.category}</Badge>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="max-w-[250px]">
                              <div className="text-sm">{gap.missingElement}</div>
                              <div className="text-xs text-muted-foreground mt-1">{gap.recommendation}</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Clock className="h-3 w-3 text-muted-foreground" />
                              <span className="text-sm">{gap.dueDate}</span>
                            </div>
                            {gap.daysOverdue > 0 && (
                              <div className="text-xs text-red-600">{gap.daysOverdue} days overdue</div>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge className={getPriorityColor(gap.priority)}>{gap.priority}</Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-2">
                              <Link href={`/patients/${gap.patientId}/graph`}>
                                <Button variant="outline" size="sm">View Patient</Button>
                              </Link>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </TabsContent>
      </Tabs>
    </div>
  );
}
