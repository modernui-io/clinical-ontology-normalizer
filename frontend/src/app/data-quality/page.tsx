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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Database,
  Shield,
  CheckCircle,
  AlertTriangle,
  XCircle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Download,
  FileText,
  Table2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  BarChart3,
  Clock,
  Search,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

// Types
interface DimensionScore {
  dimension: "Completeness" | "Conformance" | "Plausibility" | "Uniqueness";
  score: number;
  trend: "up" | "down" | "stable";
  issueCount: number;
  checksPassed: number;
  checksTotal: number;
}

interface TableQuality {
  tableName: string;
  recordCount: number;
  overallScore: number;
  completeness: number;
  conformance: number;
  plausibility: number;
  uniqueness: number;
  lastChecked: string;
  issueCount: number;
}

interface QualityIssue {
  id: string;
  table: string;
  field: string;
  dimension: string;
  severity: "critical" | "warning" | "info";
  description: string;
  affectedRows: number;
  percentAffected: number;
  suggestion: string;
}

interface TrendPoint {
  date: string;
  overall: number;
  completeness: number;
  conformance: number;
  plausibility: number;
  uniqueness: number;
}

interface QualitySummary {
  overallScore: number;
  trend: number;
  totalRecords: number;
  totalIssues: number;
  criticalIssues: number;
  lastRunTime: string;
  runDuration: number;
}

// Mock Data
const mockSummary: QualitySummary = {
  overallScore: 87.5,
  trend: 2.3,
  totalRecords: 1254890,
  totalIssues: 156,
  criticalIssues: 12,
  lastRunTime: "2026-01-24T08:30:00Z",
  runDuration: 342,
};

const mockDimensionScores: DimensionScore[] = [
  { dimension: "Completeness", score: 92.1, trend: "up", issueCount: 28, checksPassed: 145, checksTotal: 158 },
  { dimension: "Conformance", score: 88.5, trend: "stable", issueCount: 42, checksPassed: 112, checksTotal: 127 },
  { dimension: "Plausibility", score: 84.2, trend: "up", issueCount: 56, checksPassed: 89, checksTotal: 106 },
  { dimension: "Uniqueness", score: 95.8, trend: "down", issueCount: 30, checksPassed: 78, checksTotal: 82 },
];

const mockTableQuality: TableQuality[] = [
  { tableName: "person", recordCount: 45230, overallScore: 94.2, completeness: 96.5, conformance: 93.1, plausibility: 92.8, uniqueness: 98.5, lastChecked: "2026-01-24T08:30:00Z", issueCount: 8 },
  { tableName: "visit_occurrence", recordCount: 287450, overallScore: 89.1, completeness: 91.2, conformance: 87.8, plausibility: 85.4, uniqueness: 96.2, lastChecked: "2026-01-24T08:30:00Z", issueCount: 24 },
  { tableName: "condition_occurrence", recordCount: 512340, overallScore: 86.5, completeness: 88.1, conformance: 85.2, plausibility: 82.3, uniqueness: 94.8, lastChecked: "2026-01-24T08:30:00Z", issueCount: 35 },
  { tableName: "drug_exposure", recordCount: 198650, overallScore: 88.7, completeness: 90.5, conformance: 89.1, plausibility: 84.7, uniqueness: 95.1, lastChecked: "2026-01-24T08:30:00Z", issueCount: 28 },
  { tableName: "procedure_occurrence", recordCount: 142890, overallScore: 91.2, completeness: 93.4, conformance: 90.5, plausibility: 87.6, uniqueness: 97.2, lastChecked: "2026-01-24T08:30:00Z", issueCount: 15 },
  { tableName: "measurement", recordCount: 689420, overallScore: 82.8, completeness: 84.2, conformance: 81.5, plausibility: 79.8, uniqueness: 93.5, lastChecked: "2026-01-24T08:30:00Z", issueCount: 46 },
  { tableName: "observation", recordCount: 234560, overallScore: 85.4, completeness: 87.1, conformance: 84.2, plausibility: 81.5, uniqueness: 94.1, lastChecked: "2026-01-24T08:30:00Z", issueCount: 32 },
  { tableName: "death", recordCount: 8920, overallScore: 78.5, completeness: 75.2, conformance: 82.1, plausibility: 78.4, uniqueness: 99.1, lastChecked: "2026-01-24T08:30:00Z", issueCount: 18 },
];

const mockIssues: QualityIssue[] = [
  { id: "iss-001", table: "death", field: "death_date", dimension: "Completeness", severity: "critical", description: "Missing death_date for 24.8% of records", affectedRows: 2212, percentAffected: 24.8, suggestion: "Review death records and populate missing dates from source systems" },
  { id: "iss-002", table: "measurement", field: "value_as_number", dimension: "Plausibility", severity: "critical", description: "Implausible values (outside 3 SD) detected", affectedRows: 15230, percentAffected: 2.2, suggestion: "Review extreme values and correct data entry errors" },
  { id: "iss-003", table: "condition_occurrence", field: "condition_concept_id", dimension: "Conformance", severity: "critical", description: "Non-standard concept IDs found (concept_id = 0)", affectedRows: 8450, percentAffected: 1.6, suggestion: "Map local codes to standard OMOP concepts" },
  { id: "iss-004", table: "drug_exposure", field: "drug_exposure_end_date", dimension: "Completeness", severity: "warning", description: "Missing end dates for 12.3% of drug exposures", affectedRows: 24433, percentAffected: 12.3, suggestion: "Infer end dates from days_supply where available" },
  { id: "iss-005", table: "visit_occurrence", field: "visit_end_date", dimension: "Plausibility", severity: "warning", description: "Visit end date before start date", affectedRows: 342, percentAffected: 0.1, suggestion: "Correct date ordering in source ETL" },
  { id: "iss-006", table: "person", field: "year_of_birth", dimension: "Plausibility", severity: "warning", description: "Implausible birth years (< 1900 or > current year)", affectedRows: 156, percentAffected: 0.3, suggestion: "Review and correct birth year data" },
  { id: "iss-007", table: "measurement", field: "unit_concept_id", dimension: "Conformance", severity: "warning", description: "Missing or non-standard unit concept IDs", affectedRows: 45670, percentAffected: 6.6, suggestion: "Map units to standard UCUM concepts" },
  { id: "iss-008", table: "observation", field: "observation_concept_id", dimension: "Conformance", severity: "info", description: "High proportion of concept_id = 0 observations", affectedRows: 28450, percentAffected: 12.1, suggestion: "Review unmapped observation codes" },
];

const mockTrendData: TrendPoint[] = [
  { date: "Week 1", overall: 82.5, completeness: 88.2, conformance: 84.1, plausibility: 78.5, uniqueness: 93.2 },
  { date: "Week 2", overall: 83.8, completeness: 89.1, conformance: 85.2, plausibility: 79.8, uniqueness: 94.1 },
  { date: "Week 3", overall: 84.9, completeness: 90.0, conformance: 86.5, plausibility: 80.5, uniqueness: 94.8 },
  { date: "Week 4", overall: 85.8, completeness: 90.8, conformance: 87.2, plausibility: 81.8, uniqueness: 95.2 },
  { date: "Week 5", overall: 86.5, completeness: 91.5, conformance: 87.8, plausibility: 83.1, uniqueness: 95.5 },
  { date: "Week 6", overall: 87.5, completeness: 92.1, conformance: 88.5, plausibility: 84.2, uniqueness: 95.8 },
];

const DIMENSION_COLORS = {
  Completeness: "#22c55e",
  Conformance: "#3b82f6",
  Plausibility: "#f59e0b",
  Uniqueness: "#8b5cf6",
};

const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
};

const severityIcons: Record<string, typeof XCircle> = {
  critical: XCircle,
  warning: AlertTriangle,
  info: AlertCircle,
};

function getScoreColor(score: number): string {
  if (score >= 90) return "text-green-600";
  if (score >= 80) return "text-amber-600";
  return "text-red-600";
}

function getScoreBadgeColor(score: number): string {
  if (score >= 90) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (score >= 80) return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}

export default function DataQualityScorecard() {
  const [tableFilter, setTableFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(false);

  // Radial bar data for overall score
  const overallScoreData = [
    { name: "Score", value: mockSummary.overallScore, fill: "#22c55e" },
  ];

  // Dimension pie data
  const dimensionPieData = mockDimensionScores.map((d) => ({
    name: d.dimension,
    value: d.score,
    color: DIMENSION_COLORS[d.dimension],
  }));

  // Filtered issues
  const filteredIssues = useMemo(() => {
    return mockIssues.filter((issue) => {
      const matchesTable = tableFilter === "all" || issue.table === tableFilter;
      const matchesSeverity = severityFilter === "all" || issue.severity === severityFilter;
      return matchesTable && matchesSeverity;
    });
  }, [tableFilter, severityFilter]);

  // Filtered table quality
  const filteredTables = useMemo(() => {
    if (tableFilter === "all") return mockTableQuality;
    return mockTableQuality.filter((t) => t.tableName === tableFilter);
  }, [tableFilter]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleRunCheck = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 2000));
    setIsLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Shield className="h-6 w-6 text-green-600" />
            Data Quality Scorecard
          </h1>
          <p className="text-muted-foreground">
            OHDSI Data Quality Dashboard (DQD) results and issue tracking
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleRunCheck} disabled={isLoading}>
            <Activity className={`mr-2 h-4 w-4 ${isLoading ? "animate-pulse" : ""}`} />
            Run DQD Check
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Overall Score Card */}
      <div className="grid gap-6 lg:grid-cols-4">
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Overall Quality Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center">
              <div className="h-40 w-40">
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="70%"
                    outerRadius="100%"
                    data={overallScoreData}
                    startAngle={180}
                    endAngle={0}
                  >
                    <RadialBar
                      background
                      dataKey="value"
                      cornerRadius={10}
                      fill={mockSummary.overallScore >= 80 ? "#22c55e" : "#f59e0b"}
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
              </div>
              <div className={`text-4xl font-bold -mt-16 ${getScoreColor(mockSummary.overallScore)}`}>
                {mockSummary.overallScore}%
              </div>
              <div className="flex items-center gap-1 mt-2 text-sm">
                {mockSummary.trend >= 0 ? (
                  <>
                    <ArrowUpRight className="h-4 w-4 text-green-600" />
                    <span className="text-green-600">+{mockSummary.trend}%</span>
                  </>
                ) : (
                  <>
                    <ArrowDownRight className="h-4 w-4 text-red-600" />
                    <span className="text-red-600">{mockSummary.trend}%</span>
                  </>
                )}
                <span className="text-muted-foreground">vs last week</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Dimension Scores */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Quality Dimensions</CardTitle>
            <CardDescription>Scores by OHDSI DQD dimension</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4">
              {mockDimensionScores.map((dim) => (
                <div key={dim.dimension} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{dim.dimension}</span>
                    {dim.trend === "up" && <TrendingUp className="h-4 w-4 text-green-600" />}
                    {dim.trend === "down" && <TrendingDown className="h-4 w-4 text-red-600" />}
                    {dim.trend === "stable" && <Activity className="h-4 w-4 text-blue-600" />}
                  </div>
                  <div className={`text-2xl font-bold ${getScoreColor(dim.score)}`}>
                    {dim.score}%
                  </div>
                  <Progress
                    value={dim.score}
                    className="h-2"
                    style={{ "--progress-color": DIMENSION_COLORS[dim.dimension] } as React.CSSProperties}
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{dim.checksPassed}/{dim.checksTotal} checks passed</span>
                    <span>{dim.issueCount} issues</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Records</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockSummary.totalRecords.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">Across all tables</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Issues</CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{mockSummary.totalIssues}</div>
            <p className="text-xs text-muted-foreground">
              {mockSummary.criticalIssues} critical
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Last Check</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {new Date(mockSummary.lastRunTime).toLocaleDateString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Duration: {Math.round(mockSummary.runDuration / 60)}m {mockSummary.runDuration % 60}s
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Tables Checked</CardTitle>
            <Table2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockTableQuality.length}</div>
            <p className="text-xs text-muted-foreground">OMOP CDM tables</p>
          </CardContent>
        </Card>
      </div>

      {/* Trend Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Quality Trend</CardTitle>
          <CardDescription>Score trends over the past 6 weeks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockTrendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis domain={[70, 100]} tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="completeness"
                  name="Completeness"
                  stroke={DIMENSION_COLORS.Completeness}
                  fill={DIMENSION_COLORS.Completeness}
                  fillOpacity={0.2}
                />
                <Area
                  type="monotone"
                  dataKey="conformance"
                  name="Conformance"
                  stroke={DIMENSION_COLORS.Conformance}
                  fill={DIMENSION_COLORS.Conformance}
                  fillOpacity={0.2}
                />
                <Area
                  type="monotone"
                  dataKey="plausibility"
                  name="Plausibility"
                  stroke={DIMENSION_COLORS.Plausibility}
                  fill={DIMENSION_COLORS.Plausibility}
                  fillOpacity={0.2}
                />
                <Area
                  type="monotone"
                  dataKey="uniqueness"
                  name="Uniqueness"
                  stroke={DIMENSION_COLORS.Uniqueness}
                  fill={DIMENSION_COLORS.Uniqueness}
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Table Quality and Issues */}
      <Tabs defaultValue="tables" className="space-y-4">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="tables">Table Quality</TabsTrigger>
            <TabsTrigger value="issues">Issues ({filteredIssues.length})</TabsTrigger>
          </TabsList>
          <div className="flex gap-2">
            <Select value={tableFilter} onValueChange={setTableFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Table" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Tables</SelectItem>
                {mockTableQuality.map((t) => (
                  <SelectItem key={t.tableName} value={t.tableName}>
                    {t.tableName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <TabsContent value="tables">
          <Card>
            <CardHeader>
              <CardTitle>Table Quality Details</CardTitle>
              <CardDescription>Quality scores by OMOP CDM table</CardDescription>
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
                    <TableHead className="text-right">Uniqueness</TableHead>
                    <TableHead className="text-right">Issues</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTables.map((table) => (
                    <TableRow key={table.tableName}>
                      <TableCell className="font-medium font-mono">{table.tableName}</TableCell>
                      <TableCell className="text-right">{table.recordCount.toLocaleString()}</TableCell>
                      <TableCell className="text-right">
                        <Badge className={getScoreBadgeColor(table.overallScore)}>
                          {table.overallScore}%
                        </Badge>
                      </TableCell>
                      <TableCell className={`text-right ${getScoreColor(table.completeness)}`}>
                        {table.completeness}%
                      </TableCell>
                      <TableCell className={`text-right ${getScoreColor(table.conformance)}`}>
                        {table.conformance}%
                      </TableCell>
                      <TableCell className={`text-right ${getScoreColor(table.plausibility)}`}>
                        {table.plausibility}%
                      </TableCell>
                      <TableCell className={`text-right ${getScoreColor(table.uniqueness)}`}>
                        {table.uniqueness}%
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline">{table.issueCount}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="issues">
          <Card>
            <CardHeader>
              <CardTitle>Data Quality Issues</CardTitle>
              <CardDescription>Issues requiring attention sorted by severity</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible className="w-full">
                {filteredIssues.map((issue) => {
                  const SeverityIcon = severityIcons[issue.severity];
                  return (
                    <AccordionItem key={issue.id} value={issue.id}>
                      <AccordionTrigger className="hover:no-underline">
                        <div className="flex items-center gap-4 text-left">
                          <SeverityIcon className={`h-5 w-5 ${
                            issue.severity === "critical" ? "text-red-600" :
                            issue.severity === "warning" ? "text-amber-600" : "text-blue-600"
                          }`} />
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="font-mono">{issue.table}</Badge>
                              <span className="font-medium">{issue.field}</span>
                              <Badge className={severityColors[issue.severity]}>{issue.severity}</Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">{issue.description}</p>
                          </div>
                          <div className="text-right mr-4">
                            <div className="text-sm font-medium">{issue.affectedRows.toLocaleString()} rows</div>
                            <div className="text-xs text-muted-foreground">{issue.percentAffected}% affected</div>
                          </div>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="ml-9 pl-4 border-l-2 space-y-3">
                          <div>
                            <span className="text-sm font-medium">Dimension: </span>
                            <Badge style={{ backgroundColor: DIMENSION_COLORS[issue.dimension as keyof typeof DIMENSION_COLORS] || "#6b7280" }} className="text-white">
                              {issue.dimension}
                            </Badge>
                          </div>
                          <div>
                            <span className="text-sm font-medium">Suggested Action:</span>
                            <p className="text-sm text-muted-foreground mt-1">{issue.suggestion}</p>
                          </div>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline">
                              <Search className="mr-2 h-4 w-4" />
                              View Affected Records
                            </Button>
                            <Button size="sm" variant="outline">
                              <FileText className="mr-2 h-4 w-4" />
                              Export Details
                            </Button>
                          </div>
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
