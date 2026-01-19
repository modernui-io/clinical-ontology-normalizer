"use client";

import { useState } from "react";
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
} from "lucide-react";

// Types
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

// Mock Data
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

// Helper functions
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

export default function QualityMeasuresPage() {
  const [measures] = useState<QualityMeasure[]>(mockMeasures);
  const [patientGaps] = useState<PatientGap[]>(mockPatientGaps);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [expandedMeasure, setExpandedMeasure] = useState<string | null>(null);

  const categories = ["all", ...new Set(measures.map((m) => m.category))];
  const categoryPerformance = getCategoryPerformance(measures);

  const filteredMeasures = measures.filter((m) => {
    const matchesSearch =
      searchQuery === "" ||
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.id.toLowerCase().includes(searchQuery.toLowerCase());
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

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Quality Measures</h1>
          <p className="text-muted-foreground">
            HEDIS, CQM, and MIPS measure performance and care gap tracking
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Average Performance
            </CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(avgPerformance * 100).toFixed(1)}%
            </div>
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
            <CardTitle className="text-sm font-medium">
              Measures Tracked
            </CardTitle>
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
            <CardTitle className="text-sm font-medium">
              Eligible Patients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {measures
                .reduce((sum, m) => sum + m.eligiblePopulation, 0)
                .toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Across all quality measures
            </p>
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
          <CardDescription>
            Aggregate performance across measure categories
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {categoryPerformance.map((cat) => (
              <div
                key={cat.category}
                className="rounded-lg border p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{cat.category}</span>
                  <Badge variant="outline">
                    {cat.measureCount} measures
                  </Badge>
                </div>
                <div className="text-2xl font-bold">
                  {(cat.avgPerformance * 100).toFixed(1)}%
                </div>
                <Progress
                  value={cat.avgPerformance * 100}
                  className="h-2"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>
                    {cat.meetsBenchmark}/{cat.measureCount} meet benchmark
                  </span>
                  <span>{cat.totalGaps.toLocaleString()} gaps</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Trend Chart Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Performance Trends
          </CardTitle>
          <CardDescription>
            Measure performance over the past 12 months
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed bg-muted/30">
            <div className="text-center">
              <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                Trend chart will display here
              </p>
              <p className="text-xs text-muted-foreground">
                Showing performance over time with benchmarks
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue="measures" className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <TabsList>
            <TabsTrigger value="measures" className="gap-2">
              <Target className="h-4 w-4" />
              Measures
            </TabsTrigger>
            <TabsTrigger value="gaps" className="gap-2">
              <AlertCircle className="h-4 w-4" />
              Patient Gaps
            </TabsTrigger>
          </TabsList>

          <div className="flex gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search measures..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 w-[200px]"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat === "all" ? "All Categories" : cat}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Measures Tab */}
        <TabsContent value="measures" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Quality Measure Performance</CardTitle>
              <CardDescription>
                Click on a measure to see detailed information
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {filteredMeasures.map((measure) => (
                  <div
                    key={measure.id}
                    className="rounded-lg border transition-colors"
                  >
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                      onClick={() =>
                        setExpandedMeasure(
                          expandedMeasure === measure.id ? null : measure.id
                        )
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
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {measure.id}
                          </code>
                          <span className="flex items-center gap-1">
                            {getStarDisplay(measure.starRating)}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className="flex items-center gap-2">
                            <span className="text-lg font-bold">
                              {(measure.performanceRate * 100).toFixed(1)}%
                            </span>
                            {measure.trend === "up" ? (
                              <TrendingUp className="h-4 w-4 text-green-600" />
                            ) : measure.trend === "down" ? (
                              <TrendingDown className="h-4 w-4 text-red-600" />
                            ) : null}
                          </div>
                          <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <span>
                              Benchmark: {(measure.benchmark50th * 100).toFixed(0)}%
                            </span>
                            {measure.performanceRate >= measure.benchmark50th ? (
                              <CheckCircle className="h-3 w-3 text-green-600" />
                            ) : (
                              <AlertCircle className="h-3 w-3 text-amber-500" />
                            )}
                          </div>
                        </div>

                        <div className="w-32">
                          <Progress
                            value={measure.performanceRate * 100}
                            className="h-2"
                          />
                        </div>

                        <div className="text-right min-w-[80px]">
                          <div className="text-sm font-medium">
                            {measure.totalGaps.toLocaleString()} gaps
                          </div>
                          {measure.criticalGaps > 0 && (
                            <div className="text-xs text-red-600">
                              {measure.criticalGaps} critical
                            </div>
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
                            <p className="text-sm text-muted-foreground">
                              {measure.description}
                            </p>
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

        {/* Patient Gaps Tab */}
        <TabsContent value="gaps" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Patient Care Gaps</CardTitle>
                  <CardDescription>
                    Patients with missing or overdue quality measure requirements
                  </CardDescription>
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
                          <div className="text-xs text-muted-foreground">
                            {gap.patientId}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium text-sm">{gap.measureName}</div>
                          <Badge variant="outline" className="text-xs">
                            {gap.category}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[250px]">
                          <div className="text-sm">{gap.missingElement}</div>
                          <div className="text-xs text-muted-foreground mt-1">
                            {gap.recommendation}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span className="text-sm">{gap.dueDate}</span>
                        </div>
                        {gap.daysOverdue > 0 && (
                          <div className="text-xs text-red-600">
                            {gap.daysOverdue} days overdue
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={getPriorityColor(gap.priority)}>
                          {gap.priority}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Link href={`/patients/${gap.patientId}/graph`}>
                            <Button variant="outline" size="sm">
                              View Patient
                            </Button>
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
    </div>
  );
}
