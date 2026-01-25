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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  XCircle,
  Search,
  Filter,
  Download,
  RefreshCw,
  Clock,
  FileText,
  Database,
  ArrowRight,
  ChevronDown,
  Eye,
  ExternalLink,
  Info,
  BarChart3,
  Shield,
  Zap,
  Bug,
  ListChecks,
  Layers,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

type ValidationSeverity = "error" | "warning" | "info" | "pass";
type ValidationCategory = "completeness" | "conformance" | "plausibility" | "uniqueness" | "consistency";
type ValidationStatus = "running" | "completed" | "failed" | "pending";

interface ValidationRule {
  id: string;
  name: string;
  description: string;
  category: ValidationCategory;
  table: string;
  column?: string;
  expression: string;
  severity: ValidationSeverity;
  threshold?: number;
}

interface ValidationResult {
  id: string;
  ruleId: string;
  ruleName: string;
  category: ValidationCategory;
  table: string;
  column?: string;
  severity: ValidationSeverity;
  status: "pass" | "fail" | "skip";
  recordsChecked: number;
  recordsFailed: number;
  failureRate: number;
  message: string;
  details?: string;
  sampleFailures?: SampleFailure[];
  executionTime: number;
}

interface SampleFailure {
  recordId: string;
  field: string;
  value: string;
  expectedValue?: string;
  reason: string;
}

interface ValidationRun {
  id: string;
  name: string;
  status: ValidationStatus;
  startTime: string;
  endTime?: string;
  duration?: number;
  tablesChecked: number;
  rulesExecuted: number;
  passCount: number;
  failCount: number;
  warnCount: number;
  skipCount: number;
  overallScore: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockValidationRun: ValidationRun = {
  id: "run-001",
  name: "Daily DQD Check",
  status: "completed",
  startTime: "2024-02-15T08:00:00Z",
  endTime: "2024-02-15T08:15:32Z",
  duration: 932,
  tablesChecked: 12,
  rulesExecuted: 156,
  passCount: 138,
  failCount: 12,
  warnCount: 4,
  skipCount: 2,
  overallScore: 88.5,
};

const mockResults: ValidationResult[] = [
  // Completeness checks
  {
    id: "1",
    ruleId: "COMP-001",
    ruleName: "person.birth_datetime completeness",
    category: "completeness",
    table: "person",
    column: "birth_datetime",
    severity: "error",
    status: "fail",
    recordsChecked: 15000,
    recordsFailed: 245,
    failureRate: 1.63,
    message: "1.63% of records have NULL birth_datetime",
    details: "Expected: < 1% NULL values",
    executionTime: 125,
    sampleFailures: [
      { recordId: "12345", field: "birth_datetime", value: "NULL", reason: "Missing required field" },
      { recordId: "12456", field: "birth_datetime", value: "NULL", reason: "Missing required field" },
      { recordId: "12567", field: "birth_datetime", value: "NULL", reason: "Missing required field" },
    ],
  },
  {
    id: "2",
    ruleId: "COMP-002",
    ruleName: "person.gender_concept_id completeness",
    category: "completeness",
    table: "person",
    column: "gender_concept_id",
    severity: "warning",
    status: "pass",
    recordsChecked: 15000,
    recordsFailed: 12,
    failureRate: 0.08,
    message: "0.08% of records have NULL gender_concept_id",
    details: "Within acceptable threshold",
    executionTime: 98,
  },
  {
    id: "3",
    ruleId: "COMP-003",
    ruleName: "visit_occurrence.visit_start_date completeness",
    category: "completeness",
    table: "visit_occurrence",
    column: "visit_start_date",
    severity: "error",
    status: "pass",
    recordsChecked: 125000,
    recordsFailed: 0,
    failureRate: 0,
    message: "All records have visit_start_date",
    executionTime: 234,
  },
  // Conformance checks
  {
    id: "4",
    ruleId: "CONF-001",
    ruleName: "person.gender_concept_id valid vocabulary",
    category: "conformance",
    table: "person",
    column: "gender_concept_id",
    severity: "error",
    status: "fail",
    recordsChecked: 15000,
    recordsFailed: 89,
    failureRate: 0.59,
    message: "89 records have invalid gender_concept_id values",
    details: "Values not in OMOP Gender vocabulary (concept_class = 'Gender')",
    executionTime: 156,
    sampleFailures: [
      { recordId: "23456", field: "gender_concept_id", value: "99999", expectedValue: "8507, 8532, 8551", reason: "Invalid concept ID" },
      { recordId: "23567", field: "gender_concept_id", value: "-1", expectedValue: "8507, 8532, 8551", reason: "Negative value not allowed" },
    ],
  },
  {
    id: "5",
    ruleId: "CONF-002",
    ruleName: "measurement.value_as_number range check",
    category: "conformance",
    table: "measurement",
    column: "value_as_number",
    severity: "warning",
    status: "fail",
    recordsChecked: 450000,
    recordsFailed: 1234,
    failureRate: 0.27,
    message: "1,234 measurements outside expected ranges",
    details: "Values outside 3 standard deviations for each measurement concept",
    executionTime: 567,
    sampleFailures: [
      { recordId: "34567", field: "value_as_number", value: "450", expectedValue: "< 200", reason: "Glucose value unusually high" },
      { recordId: "34678", field: "value_as_number", value: "-5", expectedValue: "> 0", reason: "Negative value for lab result" },
    ],
  },
  {
    id: "6",
    ruleId: "CONF-003",
    ruleName: "drug_exposure.drug_concept_id valid RxNorm",
    category: "conformance",
    table: "drug_exposure",
    column: "drug_concept_id",
    severity: "error",
    status: "pass",
    recordsChecked: 280000,
    recordsFailed: 0,
    failureRate: 0,
    message: "All drug concepts are valid RxNorm codes",
    executionTime: 345,
  },
  // Plausibility checks
  {
    id: "7",
    ruleId: "PLAU-001",
    ruleName: "person.birth_datetime temporal plausibility",
    category: "plausibility",
    table: "person",
    column: "birth_datetime",
    severity: "error",
    status: "fail",
    recordsChecked: 15000,
    recordsFailed: 23,
    failureRate: 0.15,
    message: "23 patients have birth dates in the future",
    executionTime: 112,
    sampleFailures: [
      { recordId: "45678", field: "birth_datetime", value: "2025-05-15", expectedValue: "< current_date", reason: "Future date" },
    ],
  },
  {
    id: "8",
    ruleId: "PLAU-002",
    ruleName: "visit_occurrence date sequence",
    category: "plausibility",
    table: "visit_occurrence",
    severity: "warning",
    status: "fail",
    recordsChecked: 125000,
    recordsFailed: 456,
    failureRate: 0.36,
    message: "456 visits have end_date before start_date",
    executionTime: 289,
    sampleFailures: [
      { recordId: "56789", field: "visit_end_date", value: "2024-01-10", expectedValue: "> 2024-01-15", reason: "End before start" },
    ],
  },
  {
    id: "9",
    ruleId: "PLAU-003",
    ruleName: "condition before death",
    category: "plausibility",
    table: "condition_occurrence",
    severity: "error",
    status: "pass",
    recordsChecked: 350000,
    recordsFailed: 0,
    failureRate: 0,
    message: "All conditions occur before death date",
    executionTime: 445,
  },
  // Uniqueness checks
  {
    id: "10",
    ruleId: "UNIQ-001",
    ruleName: "person.person_id uniqueness",
    category: "uniqueness",
    table: "person",
    column: "person_id",
    severity: "error",
    status: "pass",
    recordsChecked: 15000,
    recordsFailed: 0,
    failureRate: 0,
    message: "All person_id values are unique",
    executionTime: 78,
  },
  {
    id: "11",
    ruleId: "UNIQ-002",
    ruleName: "person duplicate detection",
    category: "uniqueness",
    table: "person",
    severity: "warning",
    status: "fail",
    recordsChecked: 15000,
    recordsFailed: 34,
    failureRate: 0.23,
    message: "34 potential duplicate patient records",
    details: "Based on matching first_name, last_name, birth_datetime",
    executionTime: 234,
    sampleFailures: [
      { recordId: "67890", field: "person", value: "John Smith (1955-03-15)", reason: "Duplicate of person_id 67891" },
    ],
  },
  // Consistency checks
  {
    id: "12",
    ruleId: "CONS-001",
    ruleName: "visit_detail parent visit exists",
    category: "consistency",
    table: "visit_detail",
    column: "visit_occurrence_id",
    severity: "error",
    status: "fail",
    recordsChecked: 450000,
    recordsFailed: 156,
    failureRate: 0.03,
    message: "156 visit_details reference non-existent visits",
    executionTime: 567,
    sampleFailures: [
      { recordId: "78901", field: "visit_occurrence_id", value: "999999", reason: "Foreign key violation" },
    ],
  },
  {
    id: "13",
    ruleId: "CONS-002",
    ruleName: "observation_period coverage",
    category: "consistency",
    table: "observation_period",
    severity: "warning",
    status: "pass",
    recordsChecked: 15000,
    recordsFailed: 0,
    failureRate: 0,
    message: "All patients have observation periods",
    executionTime: 145,
  },
];

// ============================================================================
// Helper Functions
// ============================================================================

const getSeverityColor = (severity: ValidationSeverity | string) => {
  switch (severity) {
    case "error":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "warning":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "info":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "pass":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case "pass":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "fail":
      return <XCircle className="h-4 w-4 text-red-600" />;
    case "skip":
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
    default:
      return null;
  }
};

const getCategoryIcon = (category: ValidationCategory) => {
  switch (category) {
    case "completeness":
      return <ListChecks className="h-4 w-4" />;
    case "conformance":
      return <Shield className="h-4 w-4" />;
    case "plausibility":
      return <Zap className="h-4 w-4" />;
    case "uniqueness":
      return <Layers className="h-4 w-4" />;
    case "consistency":
      return <Database className="h-4 w-4" />;
    default:
      return <Info className="h-4 w-4" />;
  }
};

const getCategoryColor = (category: ValidationCategory) => {
  switch (category) {
    case "completeness":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "conformance":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "plausibility":
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200";
    case "uniqueness":
      return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200";
    case "consistency":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
};

// ============================================================================
// Main Component
// ============================================================================

export default function ValidationResultsPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [results] = useState<ValidationResult[]>(mockResults);
  const [run] = useState<ValidationRun>(mockValidationRun);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  // Filter results
  const filteredResults = useMemo(() => {
    return results.filter(r => {
      const matchesSearch = searchQuery === "" ||
        r.ruleName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.table.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = categoryFilter === "all" || r.category === categoryFilter;
      const matchesStatus = statusFilter === "all" || r.status === statusFilter;
      const matchesSeverity = severityFilter === "all" || r.severity === severityFilter;
      return matchesSearch && matchesCategory && matchesStatus && matchesSeverity;
    });
  }, [results, searchQuery, categoryFilter, statusFilter, severityFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const byCategory: Record<ValidationCategory, { pass: number; fail: number; total: number }> = {
      completeness: { pass: 0, fail: 0, total: 0 },
      conformance: { pass: 0, fail: 0, total: 0 },
      plausibility: { pass: 0, fail: 0, total: 0 },
      uniqueness: { pass: 0, fail: 0, total: 0 },
      consistency: { pass: 0, fail: 0, total: 0 },
    };

    results.forEach(r => {
      byCategory[r.category].total++;
      if (r.status === "pass") byCategory[r.category].pass++;
      else if (r.status === "fail") byCategory[r.category].fail++;
    });

    const byTable = results.reduce((acc, r) => {
      if (!acc[r.table]) acc[r.table] = { pass: 0, fail: 0, total: 0 };
      acc[r.table].total++;
      if (r.status === "pass") acc[r.table].pass++;
      else if (r.status === "fail") acc[r.table].fail++;
      return acc;
    }, {} as Record<string, { pass: number; fail: number; total: number }>);

    return { byCategory, byTable };
  }, [results]);

  const failedResults = results.filter(r => r.status === "fail");

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Validation Results</h1>
          <p className="text-muted-foreground">
            OHDSI Data Quality Dashboard check results
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Run New Check
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
          <Link href="/data-quality">
            <Button variant="outline" size="sm">
              <BarChart3 className="mr-2 h-4 w-4" />
              Dashboard
            </Button>
          </Link>
        </div>
      </div>

      {/* Run Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                {run.name}
              </CardTitle>
              <CardDescription className="flex items-center gap-4 mt-1">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {new Date(run.startTime).toLocaleString()}
                </span>
                <span>Duration: {formatDuration(run.duration || 0)}</span>
              </CardDescription>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold">{run.overallScore.toFixed(1)}%</div>
              <div className="text-sm text-muted-foreground">Quality Score</div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-6">
            <div className="text-center p-3 rounded-lg bg-muted">
              <div className="text-2xl font-bold">{run.tablesChecked}</div>
              <div className="text-xs text-muted-foreground">Tables</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted">
              <div className="text-2xl font-bold">{run.rulesExecuted}</div>
              <div className="text-xs text-muted-foreground">Rules</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-950">
              <div className="text-2xl font-bold text-green-600">{run.passCount}</div>
              <div className="text-xs text-muted-foreground">Passed</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950">
              <div className="text-2xl font-bold text-red-600">{run.failCount}</div>
              <div className="text-xs text-muted-foreground">Failed</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-amber-50 dark:bg-amber-950">
              <div className="text-2xl font-bold text-amber-600">{run.warnCount}</div>
              <div className="text-xs text-muted-foreground">Warnings</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
              <div className="text-2xl font-bold text-gray-600">{run.skipCount}</div>
              <div className="text-xs text-muted-foreground">Skipped</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="failures">Failures ({failedResults.length})</TabsTrigger>
          <TabsTrigger value="all">All Results</TabsTrigger>
          <TabsTrigger value="by-table">By Table</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Category Summary */}
          <div className="grid gap-4 md:grid-cols-5">
            {Object.entries(stats.byCategory).map(([category, data]) => {
              const passRate = data.total > 0 ? (data.pass / data.total) * 100 : 0;
              return (
                <Card key={category}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      {getCategoryIcon(category as ValidationCategory)}
                      {category.charAt(0).toUpperCase() + category.slice(1)}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{passRate.toFixed(0)}%</div>
                    <Progress value={passRate} className="h-2 mt-2" />
                    <div className="text-xs text-muted-foreground mt-1">
                      {data.pass}/{data.total} passed
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Critical Issues */}
          {failedResults.filter(r => r.severity === "error").length > 0 && (
            <Card className="border-red-200 dark:border-red-800">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-5 w-5" />
                  Critical Issues Requiring Attention
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {failedResults
                    .filter(r => r.severity === "error")
                    .map(result => (
                      <div
                        key={result.id}
                        className="flex items-center justify-between p-3 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800"
                      >
                        <div className="flex items-center gap-3">
                          <XCircle className="h-5 w-5 text-red-600" />
                          <div>
                            <div className="font-medium">{result.ruleName}</div>
                            <div className="text-sm text-muted-foreground">
                              {result.message}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-red-600">
                            {result.recordsFailed.toLocaleString()}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            records affected
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="failures" className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <Accordion type="single" collapsible value={expandedResult || undefined} onValueChange={(v) => setExpandedResult(v)}>
                {failedResults.map((result) => (
                  <AccordionItem key={result.id} value={result.id}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center gap-4 flex-1 text-left">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(result.status)}
                          <Badge className={getSeverityColor(result.severity)}>
                            {result.severity}
                          </Badge>
                        </div>
                        <div className="flex-1">
                          <div className="font-medium">{result.ruleName}</div>
                          <div className="text-sm text-muted-foreground">{result.message}</div>
                        </div>
                        <div className="text-right mr-4">
                          <div className="text-lg font-bold text-red-600">
                            {result.failureRate.toFixed(2)}%
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {result.recordsFailed.toLocaleString()} / {result.recordsChecked.toLocaleString()}
                          </div>
                        </div>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="pl-6 space-y-4">
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Rule ID:</span>
                            <span className="ml-2 font-mono">{result.ruleId}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Table:</span>
                            <Badge variant="outline" className="ml-2">{result.table}</Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Execution Time:</span>
                            <span className="ml-2">{formatDuration(result.executionTime)}</span>
                          </div>
                        </div>

                        {result.details && (
                          <div className="p-3 rounded-lg bg-muted text-sm">
                            {result.details}
                          </div>
                        )}

                        {result.sampleFailures && result.sampleFailures.length > 0 && (
                          <div>
                            <h5 className="font-medium mb-2">Sample Failures</h5>
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Record ID</TableHead>
                                  <TableHead>Field</TableHead>
                                  <TableHead>Value</TableHead>
                                  <TableHead>Expected</TableHead>
                                  <TableHead>Reason</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {result.sampleFailures.map((failure, i) => (
                                  <TableRow key={i}>
                                    <TableCell className="font-mono text-sm">{failure.recordId}</TableCell>
                                    <TableCell>{failure.field}</TableCell>
                                    <TableCell className="font-mono text-sm text-red-600">{failure.value}</TableCell>
                                    <TableCell className="font-mono text-sm text-green-600">{failure.expectedValue || "-"}</TableCell>
                                    <TableCell className="text-muted-foreground">{failure.reason}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        )}

                        <div className="flex gap-2">
                          <Button variant="outline" size="sm">
                            <Eye className="mr-2 h-4 w-4" />
                            View All Records
                          </Button>
                          <Button variant="outline" size="sm">
                            <Download className="mr-2 h-4 w-4" />
                            Export Failures
                          </Button>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="all" className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search rules..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="completeness">Completeness</SelectItem>
                <SelectItem value="conformance">Conformance</SelectItem>
                <SelectItem value="plausibility">Plausibility</SelectItem>
                <SelectItem value="uniqueness">Uniqueness</SelectItem>
                <SelectItem value="consistency">Consistency</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="pass">Pass</SelectItem>
                <SelectItem value="fail">Fail</SelectItem>
                <SelectItem value="skip">Skip</SelectItem>
              </SelectContent>
            </Select>
            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severity</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Results Table */}
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">Status</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Table</TableHead>
                    <TableHead className="text-right">Records</TableHead>
                    <TableHead className="text-right">Failures</TableHead>
                    <TableHead className="text-right">Rate</TableHead>
                    <TableHead className="text-right">Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredResults.map((result) => (
                    <TableRow
                      key={result.id}
                      className={result.status === "fail" ? "bg-red-50/50 dark:bg-red-950/20" : ""}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(result.status)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{result.ruleName}</div>
                          <div className="text-xs text-muted-foreground">{result.ruleId}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={getCategoryColor(result.category)}>
                          {result.category}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{result.table}</Badge>
                        {result.column && (
                          <span className="text-xs text-muted-foreground ml-1">.{result.column}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {result.recordsChecked.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        <span className={result.recordsFailed > 0 ? "text-red-600" : ""}>
                          {result.recordsFailed.toLocaleString()}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={result.failureRate > 1 ? "text-red-600 font-medium" : ""}>
                          {result.failureRate.toFixed(2)}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {formatDuration(result.executionTime)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="by-table" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Object.entries(stats.byTable).map(([table, data]) => {
              const passRate = data.total > 0 ? (data.pass / data.total) * 100 : 0;
              const tableResults = results.filter(r => r.table === table);
              return (
                <Card key={table}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Database className="h-4 w-4" />
                        {table}
                      </CardTitle>
                      <Badge className={passRate === 100 ? "bg-green-100 text-green-800" : passRate >= 80 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800"}>
                        {passRate.toFixed(0)}%
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <Progress value={passRate} className="h-2" />
                      <div className="flex justify-between text-sm">
                        <span className="text-green-600">{data.pass} passed</span>
                        <span className="text-red-600">{data.fail} failed</span>
                      </div>
                      <div className="space-y-1">
                        {tableResults.filter(r => r.status === "fail").slice(0, 3).map(r => (
                          <div key={r.id} className="text-xs flex items-center gap-1 text-muted-foreground">
                            <XCircle className="h-3 w-3 text-red-500" />
                            {r.ruleName.split(" ").slice(0, 4).join(" ")}...
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
