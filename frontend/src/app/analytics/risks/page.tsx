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
import {
  AlertTriangle,
  Activity,
  TrendingUp,
  Users,
  Stethoscope,
  RefreshCw,
  Download,
  Search,
  ChevronRight,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Clock,
  Gauge,
  Brain,
  Loader2,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface RiskScoreDetail {
  score: number;
  tier: string;
  score_raw: number | null;
}

interface PatientRisk {
  patient_id: string;
  patient_name: string;
  age: number;
  department: string;
  readmission_risk: RiskScoreDetail | null;
  deterioration_risk: RiskScoreDetail | null;
  mortality_risk: RiskScoreDetail | null;
  overall_tier: string;
  overall_score: number;
  trend: "improving" | "worsening" | "stable" | null;
  last_updated: string;
}

interface RiskDistribution {
  tier: string;
  count: number;
  percentage: number;
}

interface DepartmentSummary {
  department: string;
  patient_count: number;
  avg_risk_score: number;
  critical_count: number;
  high_count: number;
}

interface PopulationRiskData {
  total_patients: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  average_score: number;
  worsening_count: number;
  tier_distribution: RiskDistribution[];
  department_summary: DepartmentSummary[];
}

interface RiskScoresResponse {
  total: number;
  patients: PatientRisk[];
}

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

const getTierBgColor = (tier: string): string => {
  switch (tier) {
    case "critical":
      return "bg-red-50 dark:bg-red-950";
    case "high":
      return "bg-red-50/50 dark:bg-red-950/50";
    case "medium":
      return "bg-amber-50 dark:bg-amber-950";
    case "low":
      return "bg-green-50 dark:bg-green-950";
    default:
      return "";
  }
};

const getScoreColor = (score: number): string => {
  if (score >= 0.7) return "text-red-600 dark:text-red-400";
  if (score >= 0.5) return "text-orange-600 dark:text-orange-400";
  if (score >= 0.3) return "text-amber-600 dark:text-amber-400";
  return "text-green-600 dark:text-green-400";
};

const getTrendIcon = (trend: string | null) => {
  switch (trend) {
    case "worsening":
      return <ArrowUpRight className="h-4 w-4 text-red-500" />;
    case "improving":
      return <ArrowDownRight className="h-4 w-4 text-green-500" />;
    default:
      return <Minus className="h-4 w-4 text-gray-500" />;
  }
};

const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
};

// ============================================================================
// Sparkline Component
// ============================================================================

function RiskSparkline({ data, trend }: { data: number[]; trend: string | null }) {
  const height = 24;
  const width = 60;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);

  const points = data
    .map((v, i) => `${i * stepX},${height - ((v - min) / range) * (height - 4) - 2}`)
    .join(" ");

  const color = trend === "worsening" ? "#ef4444" : trend === "improving" ? "#22c55e" : "#6b7280";

  return (
    <svg width={width} height={height}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ============================================================================
// Score Gauge Component
// ============================================================================

function MiniScoreGauge({ score, size = 40 }: { score: number; size?: number }) {
  const circumference = 2 * Math.PI * 15;
  const strokeDashoffset = circumference - score * circumference;

  const getColor = (s: number) => {
    if (s >= 0.7) return "#dc2626";
    if (s >= 0.5) return "#ea580c";
    if (s >= 0.3) return "#d97706";
    return "#16a34a";
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 40 40">
        <circle
          cx="20"
          cy="20"
          r="15"
          fill="none"
          stroke="currentColor"
          className="text-gray-200 dark:text-gray-700"
          strokeWidth="4"
        />
        <circle
          cx="20"
          cy="20"
          r="15"
          fill="none"
          stroke={getColor(score)}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 0.3s ease-in-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold" style={{ color: getColor(score) }}>
          {Math.round(score * 100)}
        </span>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function RiskDashboardPage() {
  // Data states
  const [patients, setPatients] = useState<PatientRisk[]>([]);
  const [populationData, setPopulationData] = useState<PopulationRiskData | null>(null);

  // Loading / error states
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter / sort states
  const [searchQuery, setSearchQuery] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("overall_score");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // -------------------------------------------------------------------
  // Fetch data from backend
  // -------------------------------------------------------------------
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [riskScoresRes, populationRes] = await Promise.all([
        fetch("/api/predictions/risk-scores?limit=500"),
        fetch("/api/predictions/population-risk"),
      ]);

      if (!riskScoresRes.ok) {
        throw new Error(
          `Failed to fetch risk scores: ${riskScoresRes.status} ${riskScoresRes.statusText}`
        );
      }
      if (!populationRes.ok) {
        throw new Error(
          `Failed to fetch population risk: ${populationRes.status} ${populationRes.statusText}`
        );
      }

      const riskScoresJson: RiskScoresResponse = await riskScoresRes.json();
      const populationJson: PopulationRiskData = await populationRes.json();

      setPatients(riskScoresJson.patients);
      setPopulationData(populationJson);
    } catch (err) {
      const message = err instanceof Error ? err.message : "An unknown error occurred";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // -------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------
  const departments = ["all", ...new Set(patients.map((p) => p.department))];

  const distribution: RiskDistribution[] = populationData?.tier_distribution ?? [];
  const departmentSummary: DepartmentSummary[] = populationData?.department_summary ?? [];

  // Filter and sort patients
  const filteredPatients = patients
    .filter((p) => {
      const matchesSearch =
        searchQuery === "" ||
        p.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.patient_id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesTier = tierFilter === "all" || p.overall_tier === tierFilter;
      const matchesDept = departmentFilter === "all" || p.department === departmentFilter;
      return matchesSearch && matchesTier && matchesDept;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case "overall_score":
          comparison = a.overall_score - b.overall_score;
          break;
        case "patient_name":
          comparison = a.patient_name.localeCompare(b.patient_name);
          break;
        case "age":
          comparison = a.age - b.age;
          break;
        case "last_updated":
          comparison = new Date(a.last_updated).getTime() - new Date(b.last_updated).getTime();
          break;
        default:
          comparison = 0;
      }
      return sortOrder === "desc" ? -comparison : comparison;
    });

  // Summary stats from population data or derived from patients list
  const totalPatients = populationData?.total_patients ?? patients.length;
  const criticalCount = populationData?.critical_count ?? patients.filter((p) => p.overall_tier === "critical").length;
  const highCount = populationData?.high_count ?? patients.filter((p) => p.overall_tier === "high").length;
  const avgScore = populationData?.average_score ?? (patients.length > 0 ? patients.reduce((sum, p) => sum + p.overall_score, 0) / patients.length : 0);
  const worseningCount = populationData?.worsening_count ?? patients.filter((p) => p.trend === "worsening").length;

  const handleRefresh = async () => {
    await fetchData();
  };

  const handleExport = () => {
    const exportData = filteredPatients.map((p) => ({
      patient_id: p.patient_id,
      patient_name: p.patient_name,
      age: p.age,
      department: p.department,
      overall_tier: p.overall_tier,
      overall_score: p.overall_score,
      readmission_risk: p.readmission_risk?.score,
      deterioration_risk: p.deterioration_risk?.score,
      mortality_risk: p.mortality_risk?.score,
      trend: p.trend,
      last_updated: p.last_updated,
    }));

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `risk-dashboard-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // -------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------
  if (isLoading && patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading risk dashboard...</p>
      </div>
    );
  }

  // -------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------
  if (error && patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-lg font-medium">Failed to load risk data</p>
        <p className="text-sm text-muted-foreground max-w-md text-center">{error}</p>
        <Button variant="outline" onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Risk Dashboard</h1>
          <p className="text-muted-foreground">
            Patient risk stratification and predictive analytics
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Link href="/analytics/models">
            <Button variant="outline" size="sm">
              <Brain className="mr-2 h-4 w-4" />
              Models
            </Button>
          </Link>
        </div>
      </div>

      {/* Inline error banner (when we have stale data but refresh failed) */}
      {error && patients.length > 0 && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950 text-red-700 dark:text-red-300 text-sm">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>Failed to refresh data: {error}. Showing last loaded data.</span>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalPatients}</div>
            <p className="text-xs text-muted-foreground">
              Actively monitored
            </p>
          </CardContent>
        </Card>

        <Card className="border-red-200 dark:border-red-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Critical Risk</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{criticalCount}</div>
            <p className="text-xs text-muted-foreground">
              Immediate attention required
            </p>
          </CardContent>
        </Card>

        <Card className="border-orange-200 dark:border-orange-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">High Risk</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{highCount}</div>
            <p className="text-xs text-muted-foreground">
              Close monitoring needed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Risk Score</CardTitle>
            <Gauge className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getScoreColor(avgScore)}`}>
              {(avgScore * 100).toFixed(1)}%
            </div>
            <Progress value={avgScore * 100} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Worsening</CardTitle>
            <TrendingUp className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{worseningCount}</div>
            <p className="text-xs text-muted-foreground">
              Risk increasing
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Risk Distribution and Department Summary */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Risk Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Risk Distribution
            </CardTitle>
            <CardDescription>Patient count by risk tier</CardDescription>
          </CardHeader>
          <CardContent>
            {distribution.length > 0 ? (
              <div className="space-y-4">
                {distribution.map((d) => (
                  <div key={d.tier} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge className={getTierColor(d.tier)}>{d.tier}</Badge>
                        <span className="text-sm text-muted-foreground">
                          {d.count} patients
                        </span>
                      </div>
                      <span className="text-sm font-medium">
                        {d.percentage.toFixed(1)}%
                      </span>
                    </div>
                    <Progress
                      value={d.percentage}
                      className={`h-2 ${
                        d.tier === "critical"
                          ? "[&>div]:bg-red-600"
                          : d.tier === "high"
                          ? "[&>div]:bg-red-500"
                          : d.tier === "medium"
                          ? "[&>div]:bg-amber-500"
                          : "[&>div]:bg-green-500"
                      }`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No distribution data available</p>
            )}
          </CardContent>
        </Card>

        {/* Department Summary */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5" />
              By Department
            </CardTitle>
            <CardDescription>Risk summary by department</CardDescription>
          </CardHeader>
          <CardContent>
            {departmentSummary.length > 0 ? (
              <div className="space-y-4">
                {departmentSummary.map((dept) => (
                  <div
                    key={dept.department}
                    className="flex items-center justify-between p-3 rounded-lg border"
                  >
                    <div>
                      <div className="font-medium">{dept.department}</div>
                      <div className="text-xs text-muted-foreground">
                        {dept.patient_count} patients
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className={`text-sm font-bold ${getScoreColor(dept.avg_risk_score)}`}>
                          {(dept.avg_risk_score * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-muted-foreground">avg risk</div>
                      </div>
                      {(dept.critical_count > 0 || dept.high_count > 0) && (
                        <div className="flex gap-1">
                          {dept.critical_count > 0 && (
                            <Badge className="bg-red-600 text-white text-xs">
                              {dept.critical_count}
                            </Badge>
                          )}
                          {dept.high_count > 0 && (
                            <Badge className="bg-red-500 text-white text-xs">
                              {dept.high_count}
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No department data available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Patient Risk Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Patient Risk Scores</CardTitle>
              <CardDescription>
                Click on a patient to view detailed risk analysis
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search patients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 w-[200px]"
                />
              </div>
              <Select value={tierFilter} onValueChange={setTierFilter}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="Risk Tier" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Tiers</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
              <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Department" />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((dept) => (
                    <SelectItem key={dept} value={dept}>
                      {dept === "all" ? "All Departments" : dept}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Patient</TableHead>
                <TableHead>Department</TableHead>
                <TableHead className="text-center">Overall</TableHead>
                <TableHead className="text-center">Readmission</TableHead>
                <TableHead className="text-center">Deterioration</TableHead>
                <TableHead className="text-center">Mortality</TableHead>
                <TableHead className="text-center">Trend</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredPatients.map((patient) => (
                <TableRow
                  key={patient.patient_id}
                  className={`cursor-pointer hover:bg-muted/50 ${getTierBgColor(patient.overall_tier)}`}
                >
                  <TableCell>
                    <div>
                      <div className="font-medium">{patient.patient_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {patient.patient_id} - {patient.age}yo
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{patient.department}</Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex flex-col items-center gap-1">
                      <MiniScoreGauge score={patient.overall_score} />
                      <Badge className={getTierColor(patient.overall_tier)}>
                        {patient.overall_tier}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    {patient.readmission_risk && (
                      <div className={`font-mono text-sm ${getScoreColor(patient.readmission_risk.score)}`}>
                        {(patient.readmission_risk.score * 100).toFixed(0)}%
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {patient.deterioration_risk && (
                      <div className={`font-mono text-sm ${getScoreColor(patient.deterioration_risk.score)}`}>
                        {(patient.deterioration_risk.score * 100).toFixed(0)}%
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {patient.mortality_risk && (
                      <div className={`font-mono text-sm ${getScoreColor(patient.mortality_risk.score)}`}>
                        {(patient.mortality_risk.score * 100).toFixed(0)}%
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      {getTrendIcon(patient.trend)}
                      <RiskSparkline
                        data={[0.3, 0.35, 0.4, 0.38, 0.45, patient.overall_score]}
                        trend={patient.trend}
                      />
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(patient.last_updated)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Link href={`/analytics/risks/${patient.patient_id}`}>
                      <Button variant="ghost" size="sm">
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {filteredPatients.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Users className="h-12 w-12 mb-4" />
              <p className="text-lg font-medium">No patients found</p>
              <p className="text-sm">
                {patients.length === 0
                  ? "No risk assessments have been recorded yet. Run predictions via the API to populate data."
                  : "Try adjusting your search or filters"}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
