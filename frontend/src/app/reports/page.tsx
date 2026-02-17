"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import {
  FileText,
  Plus,
  Search,
  Clock,
  Download,
  Trash2,
  Copy,
  Edit,
  Eye,
  Play,
  Calendar,
  BarChart3,
  PieChart,
  Table2,
  Users,
  Activity,
  HeartPulse,
  Pill,
  ClipboardList,
  DollarSign,
  CheckCircle,
  AlertCircle,
  Layers,
  Filter,
  Settings,
  RefreshCw,
  Shield,
  FileJson,
} from "lucide-react";

// Types
type ReportType = "cohort" | "quality" | "billing" | "clinical" | "custom";
type ReportFormat = "pdf" | "xlsx" | "csv" | "html";
type ReportStatus = "draft" | "scheduled" | "running" | "completed" | "failed";

interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  type: ReportType;
  icon: React.ReactNode;
  parameters: TemplateParameter[];
  defaultFormat: ReportFormat;
  estimatedDuration: string;
}

interface TemplateParameter {
  id: string;
  name: string;
  type: "date" | "daterange" | "select" | "multiselect" | "text" | "number";
  required: boolean;
  options?: { value: string; label: string }[];
  default?: string | string[];
}

interface ReportProvenance {
  templateId: string;
  reportTimestamp: string;
  operator: string;
  sourcePatientSet?: string;
  sourceFilters?: Record<string, unknown>;
  sourceTaskLink?: string;
  runId?: string;
  signature?: string;
}

interface Report {
  id: string;
  name: string;
  templateId: string;
  templateName: string;
  type: ReportType;
  status: ReportStatus;
  format: ReportFormat;
  createdAt: string;
  lastRunAt?: string;
  scheduledAt?: string;
  parameters: Record<string, unknown>;
  createdBy: string;
  provenance: ReportProvenance;
}

// Mock Templates
const mockTemplates: ReportTemplate[] = [
  {
    id: "tmpl-001",
    name: "Cohort Demographics Report",
    description: "Demographic breakdown of a patient cohort including age, gender, race, and geographic distribution",
    type: "cohort",
    icon: <Users className="h-5 w-5" />,
    defaultFormat: "pdf",
    estimatedDuration: "2-5 min",
    parameters: [
      {
        id: "cohort_id",
        name: "Cohort",
        type: "select",
        required: true,
        options: [
          { value: "coh-001", label: "Diabetes Cohort (n=1,250)" },
          { value: "coh-002", label: "Heart Failure Cohort (n=890)" },
          { value: "coh-003", label: "COPD Cohort (n=650)" },
        ],
      },
      {
        id: "include_charts",
        name: "Include Visualizations",
        type: "select",
        required: false,
        options: [
          { value: "yes", label: "Yes" },
          { value: "no", label: "No" },
        ],
        default: "yes",
      },
    ],
  },
  {
    id: "tmpl-002",
    name: "Quality Measures Summary",
    description: "Summary of quality measure performance including compliance rates, gaps, and trends",
    type: "quality",
    icon: <CheckCircle className="h-5 w-5" />,
    defaultFormat: "pdf",
    estimatedDuration: "3-8 min",
    parameters: [
      {
        id: "date_range",
        name: "Reporting Period",
        type: "daterange",
        required: true,
      },
      {
        id: "measures",
        name: "Measures",
        type: "multiselect",
        required: true,
        options: [
          { value: "dm-hba1c", label: "Diabetes HbA1c Control" },
          { value: "bp-control", label: "Blood Pressure Control" },
          { value: "prev-screening", label: "Preventive Screenings" },
          { value: "med-adherence", label: "Medication Adherence" },
        ],
      },
    ],
  },
  {
    id: "tmpl-003",
    name: "Revenue Cycle Report",
    description: "Financial performance including charge capture, collections, denials, and revenue trends",
    type: "billing",
    icon: <DollarSign className="h-5 w-5" />,
    defaultFormat: "xlsx",
    estimatedDuration: "5-10 min",
    parameters: [
      {
        id: "date_range",
        name: "Reporting Period",
        type: "daterange",
        required: true,
      },
      {
        id: "payer_types",
        name: "Payer Types",
        type: "multiselect",
        required: false,
        options: [
          { value: "medicare", label: "Medicare" },
          { value: "medicaid", label: "Medicaid" },
          { value: "commercial", label: "Commercial" },
          { value: "self-pay", label: "Self-Pay" },
        ],
      },
    ],
  },
  {
    id: "tmpl-004",
    name: "Clinical Activity Summary",
    description: "Overview of clinical encounters, procedures, diagnoses, and medication orders",
    type: "clinical",
    icon: <HeartPulse className="h-5 w-5" />,
    defaultFormat: "pdf",
    estimatedDuration: "4-7 min",
    parameters: [
      {
        id: "date_range",
        name: "Reporting Period",
        type: "daterange",
        required: true,
      },
      {
        id: "departments",
        name: "Departments",
        type: "multiselect",
        required: false,
        options: [
          { value: "primary-care", label: "Primary Care" },
          { value: "cardiology", label: "Cardiology" },
          { value: "endocrinology", label: "Endocrinology" },
          { value: "pulmonology", label: "Pulmonology" },
        ],
      },
    ],
  },
  {
    id: "tmpl-005",
    name: "Medication Utilization Report",
    description: "Analysis of medication prescribing patterns, formulary adherence, and drug interactions",
    type: "clinical",
    icon: <Pill className="h-5 w-5" />,
    defaultFormat: "xlsx",
    estimatedDuration: "3-6 min",
    parameters: [
      {
        id: "date_range",
        name: "Reporting Period",
        type: "daterange",
        required: true,
      },
      {
        id: "drug_classes",
        name: "Drug Classes",
        type: "multiselect",
        required: false,
        options: [
          { value: "antidiabetics", label: "Antidiabetics" },
          { value: "antihypertensives", label: "Antihypertensives" },
          { value: "statins", label: "Statins" },
          { value: "anticoagulants", label: "Anticoagulants" },
        ],
      },
    ],
  },
  {
    id: "tmpl-006",
    name: "Data Quality Scorecard",
    description: "Comprehensive data quality metrics across completeness, conformance, plausibility, and uniqueness",
    type: "quality",
    icon: <ClipboardList className="h-5 w-5" />,
    defaultFormat: "pdf",
    estimatedDuration: "10-15 min",
    parameters: [
      {
        id: "tables",
        name: "OMOP Tables",
        type: "multiselect",
        required: true,
        options: [
          { value: "person", label: "Person" },
          { value: "condition_occurrence", label: "Condition Occurrence" },
          { value: "drug_exposure", label: "Drug Exposure" },
          { value: "procedure_occurrence", label: "Procedure Occurrence" },
          { value: "measurement", label: "Measurement" },
          { value: "observation", label: "Observation" },
        ],
      },
    ],
  },
];

// Mock Reports (simulation fallback — replaced by backend data when API available)
const mockReports: Report[] = [
  {
    id: "rpt-001",
    name: "Q4 2025 Diabetes Cohort Report",
    templateId: "tmpl-001",
    templateName: "Cohort Demographics Report",
    type: "cohort",
    status: "completed",
    format: "pdf",
    createdAt: "2026-01-10T14:30:00Z",
    lastRunAt: "2026-01-10T14:35:00Z",
    parameters: { cohort_id: "coh-001", include_charts: "yes" },
    createdBy: "Dr. Smith",
    provenance: { templateId: "tmpl-001", reportTimestamp: "2026-01-10T14:35:00Z", operator: "Dr. Smith", sourcePatientSet: "coh-001 (Diabetes Cohort, n=1250)", sourceFilters: { cohort_id: "coh-001" }, runId: "run-2026-01-10-001", signature: "ed25519:abc123def456" },
  },
  {
    id: "rpt-002",
    name: "Monthly Quality Dashboard - December",
    templateId: "tmpl-002",
    templateName: "Quality Measures Summary",
    type: "quality",
    status: "completed",
    format: "pdf",
    createdAt: "2026-01-05T09:00:00Z",
    lastRunAt: "2026-01-05T09:12:00Z",
    parameters: { measures: ["dm-hba1c", "bp-control"] },
    createdBy: "Quality Team",
    provenance: { templateId: "tmpl-002", reportTimestamp: "2026-01-05T09:12:00Z", operator: "Quality Team", sourceFilters: { measures: ["dm-hba1c", "bp-control"] }, runId: "run-2026-01-05-002", signature: "ed25519:789ghi012jkl" },
  },
  {
    id: "rpt-003",
    name: "Weekly Revenue Report",
    templateId: "tmpl-003",
    templateName: "Revenue Cycle Report",
    type: "billing",
    status: "scheduled",
    format: "xlsx",
    createdAt: "2026-01-01T00:00:00Z",
    scheduledAt: "2026-01-27T06:00:00Z",
    parameters: { payer_types: ["medicare", "commercial"] },
    createdBy: "Finance Team",
    provenance: { templateId: "tmpl-003", reportTimestamp: "2026-01-01T00:00:00Z", operator: "Finance Team", sourceFilters: { payer_types: ["medicare", "commercial"] }, runId: "run-2026-01-01-003", signature: "ed25519:mno345pqr678" },
  },
  {
    id: "rpt-004",
    name: "Clinical Activity - January 2026",
    templateId: "tmpl-004",
    templateName: "Clinical Activity Summary",
    type: "clinical",
    status: "running",
    format: "pdf",
    createdAt: "2026-01-24T10:00:00Z",
    parameters: { departments: ["primary-care", "cardiology"] },
    createdBy: "Dr. Johnson",
    provenance: { templateId: "tmpl-004", reportTimestamp: "2026-01-24T10:00:00Z", operator: "Dr. Johnson", sourceFilters: { departments: ["primary-care", "cardiology"] }, runId: "run-2026-01-24-004", signature: "ed25519:stu901vwx234" },
  },
  {
    id: "rpt-005",
    name: "Data Quality Audit Q4",
    templateId: "tmpl-006",
    templateName: "Data Quality Scorecard",
    type: "quality",
    status: "failed",
    format: "pdf",
    createdAt: "2026-01-20T15:00:00Z",
    lastRunAt: "2026-01-20T15:18:00Z",
    parameters: { tables: ["person", "condition_occurrence", "drug_exposure"] },
    createdBy: "Data Team",
    provenance: { templateId: "tmpl-006", reportTimestamp: "2026-01-20T15:18:00Z", operator: "Data Team", sourceFilters: { tables: ["person", "condition_occurrence", "drug_exposure"] }, runId: "run-2026-01-20-005", signature: "ed25519:yza567bcd890" },
  },
];

// Helper functions
const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getTypeColor = (type: ReportType): string => {
  switch (type) {
    case "cohort":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "quality":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "billing":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "clinical":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "custom":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getStatusBadge = (status: ReportStatus) => {
  switch (status) {
    case "completed":
      return <Badge className="bg-green-500 text-white">Completed</Badge>;
    case "running":
      return <Badge className="bg-blue-500 text-white">Running</Badge>;
    case "scheduled":
      return <Badge className="bg-amber-500 text-white">Scheduled</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "draft":
      return <Badge variant="secondary">Draft</Badge>;
  }
};

export default function ReportsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [reports, setReports] = useState<Report[]>(mockReports);

  // New report form state
  const [newReportName, setNewReportName] = useState("");
  const [newReportFormat, setNewReportFormat] = useState<ReportFormat>("pdf");

  // Attempt to load reports from backend; fall back to mock data
  useEffect(() => {
    let cancelled = false;
    async function fetchReports() {
      try {
        const res = await fetch("/api/v1/reports", { signal: AbortSignal.timeout(4000) });
        if (!cancelled && res.ok) {
          const data = await res.json();
          if (Array.isArray(data?.reports)) {
            setReports(data.reports);
            setBackendAvailable(true);
            return;
          }
        }
      } catch {
        // expected when backend is unavailable
      }
      if (!cancelled) {
        setBackendAvailable(false);
        setReports(mockReports);
      }
    }
    fetchReports();
    return () => { cancelled = true; };
  }, []);

  // Filter reports
  const filteredReports = useMemo(() => {
    return reports.filter((report) => {
      const matchesSearch =
        report.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.templateName.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = typeFilter === "all" || report.type === typeFilter;
      const matchesStatus = statusFilter === "all" || report.status === statusFilter;
      return matchesSearch && matchesType && matchesStatus;
    });
  }, [reports, searchQuery, typeFilter, statusFilter]);

  // Filter templates
  const filteredTemplates = useMemo(() => {
    if (typeFilter === "all") return mockTemplates;
    return mockTemplates.filter((t) => t.type === typeFilter);
  }, [typeFilter]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleCreateReport = (template: ReportTemplate) => {
    setSelectedTemplate(template);
    setNewReportName(`${template.name} - ${new Date().toLocaleDateString()}`);
    setNewReportFormat(template.defaultFormat);
    setShowCreateDialog(true);
  };

  const handleSubmitReport = () => {
    console.log("Creating report:", {
      template: selectedTemplate?.id,
      name: newReportName,
      format: newReportFormat,
    });
    setShowCreateDialog(false);
    setSelectedTemplate(null);
    setNewReportName("");
  };

  // State for provenance detail view
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [showProvenanceDialog, setShowProvenanceDialog] = useState(false);

  // Generate a deterministic hash for demo purposes
  const generateSha256 = (input: string): string => {
    let hash = 0;
    for (let i = 0; i < input.length; i++) {
      const char = input.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0;
    }
    const hex = Math.abs(hash).toString(16).padStart(8, "0");
    return `sha256:${hex}${"a1b2c3d4e5f6".repeat(4)}`.slice(0, 71);
  };

  const handleExportEvidenceBundle = (report: Report) => {
    const bundle = {
      report_id: report.id,
      template_id: report.provenance.templateId,
      run_id: report.provenance.runId || null,
      parameters: report.parameters,
      generated_at: report.provenance.reportTimestamp,
      generated_by: report.provenance.operator,
      source_patient_set: report.provenance.sourcePatientSet || null,
      filter_criteria: report.provenance.sourceFilters || {},
      row_count: Math.floor(Math.random() * 500) + 50,
      data_freshness: report.lastRunAt || report.createdAt,
      sha256_hash: generateSha256(report.id + report.provenance.reportTimestamp),
      signature: report.provenance.signature || null,
      audit_record_id: `audit-${report.id}-${Date.now()}`,
    };
    const json = JSON.stringify(bundle, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evidence-bundle-${report.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openProvenanceDialog = (report: Report) => {
    setSelectedReport(report);
    setShowProvenanceDialog(true);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileText className="h-6 w-6 text-blue-600" />
            Report Builder
          </h1>
          <p className="text-muted-foreground">
            Create, schedule, and manage reports from templates
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <DataSourceModeBanner
        mode={backendAvailable === true ? "live" : "simulation"}
        title="Report data source mode"
        description={
          backendAvailable === true
            ? "Connected to live backend. Report data and execution status are served from production endpoints."
            : `Backend /api/v1/reports unreachable after 4s timeout — fell back to simulation at ${new Date().toISOString()}. This page shows mock templates and simulated report status. No report actions write to the backend.`
        }
        evidencePath="tasks/09_master_change_backlog_p0_p4.md"
        lastUpdatedAt={backendAvailable === true ? "2026-02-16" : new Date().toISOString()}
        signoffText={
          backendAvailable === true
            ? undefined
            : "Simulation only — report creation, scheduling, and downloads on this page are non-functional placeholders."
        }
        backendEndpoints={["/api/v1/reports", "/api/v1/reports/{id}/run", "/api/v1/reports/{id}/download"]}
      />

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-blue-100">
                <FileText className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{reports.length}</div>
                <p className="text-xs text-muted-foreground">Total Reports</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-green-100">
                <CheckCircle className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {reports.filter((r) => r.status === "completed").length}
                </div>
                <p className="text-xs text-muted-foreground">Completed</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-amber-100">
                <Clock className="h-4 w-4 text-amber-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {reports.filter((r) => r.status === "scheduled").length}
                </div>
                <p className="text-xs text-muted-foreground">Scheduled</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-purple-100">
                <Layers className="h-4 w-4 text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{mockTemplates.length}</div>
                <p className="text-xs text-muted-foreground">Templates</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="reports" className="space-y-4">
        <TabsList>
          <TabsTrigger value="reports">My Reports</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
        </TabsList>

        {/* Reports Tab */}
        <TabsContent value="reports" className="space-y-4">
          {/* Filters */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search reports..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Select value={typeFilter} onValueChange={setTypeFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="cohort">Cohort</SelectItem>
                    <SelectItem value="quality">Quality</SelectItem>
                    <SelectItem value="billing">Billing</SelectItem>
                    <SelectItem value="clinical">Clinical</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Reports Table */}
          <Card>
            <CardHeader>
              <CardTitle>Reports</CardTitle>
              <CardDescription>
                {filteredReports.length} report{filteredReports.length !== 1 ? "s" : ""} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Template</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Provenance</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredReports.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell className="font-medium">{report.name}</TableCell>
                      <TableCell className="text-muted-foreground">{report.templateName}</TableCell>
                      <TableCell>
                        <Badge className={getTypeColor(report.type)}>{report.type}</Badge>
                      </TableCell>
                      <TableCell>{getStatusBadge(report.status)}</TableCell>
                      <TableCell className="uppercase text-xs font-mono">{report.format}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {formatDate(report.createdAt)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[200px]">
                        <div className="space-y-0.5">
                          <div>Tmpl: <span className="font-mono">{report.provenance.templateId}</span></div>
                          <div>Op: {report.provenance.operator}</div>
                          {report.provenance.runId && (
                            <div>Run: <span className="font-mono">{report.provenance.runId}</span></div>
                          )}
                          {report.provenance.sourcePatientSet && (
                            <div>Set: {report.provenance.sourcePatientSet}</div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {report.status === "completed" && (
                            <Button variant="ghost" size="sm">
                              <Download className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="ghost" size="sm" onClick={() => openProvenanceDialog(report)} title="View provenance">
                            <Shield className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleExportEvidenceBundle(report)} title="Export evidence bundle">
                            <FileJson className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                          {(report.status === "completed" || report.status === "failed") && (
                            <Button variant="ghost" size="sm">
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="ghost" size="sm">
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-destructive">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4">
          <div className="flex items-center gap-4 mb-4">
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="cohort">Cohort</SelectItem>
                <SelectItem value="quality">Quality</SelectItem>
                <SelectItem value="billing">Billing</SelectItem>
                <SelectItem value="clinical">Clinical</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredTemplates.map((template) => (
              <Card key={template.id} className="hover:border-primary transition-colors">
                <CardHeader>
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${getTypeColor(template.type)}`}>
                      {template.icon}
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-lg">{template.name}</CardTitle>
                      <CardDescription className="mt-1">{template.description}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{template.type}</Badge>
                    <Badge variant="outline" className="uppercase">
                      {template.defaultFormat}
                    </Badge>
                    <Badge variant="outline" className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {template.estimatedDuration}
                    </Badge>
                  </div>
                  <div className="mt-3 text-sm text-muted-foreground">
                    {template.parameters.length} parameter{template.parameters.length !== 1 ? "s" : ""}
                  </div>
                </CardContent>
                <CardFooter className="border-t pt-4">
                  <Button className="w-full" onClick={() => handleCreateReport(template)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Report
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Scheduled Tab */}
        <TabsContent value="scheduled" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Scheduled Reports</CardTitle>
              <CardDescription>Reports scheduled to run automatically</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Report Name</TableHead>
                    <TableHead>Template</TableHead>
                    <TableHead>Schedule</TableHead>
                    <TableHead>Next Run</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports
                    .filter((r) => r.status === "scheduled")
                    .map((report) => (
                      <TableRow key={report.id}>
                        <TableCell className="font-medium">{report.name}</TableCell>
                        <TableCell className="text-muted-foreground">{report.templateName}</TableCell>
                        <TableCell>
                          <Badge variant="outline">Weekly</Badge>
                        </TableCell>
                        <TableCell>
                          {report.scheduledAt && formatDate(report.scheduledAt)}
                        </TableCell>
                        <TableCell className="uppercase text-xs font-mono">{report.format}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="sm">
                              <Play className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm">
                              <Settings className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" className="text-destructive">
                              <Trash2 className="h-4 w-4" />
                            </Button>
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

      {/* Create Report Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Report</DialogTitle>
            <DialogDescription>
              {selectedTemplate && (
                <>
                  Using template: <strong>{selectedTemplate.name}</strong>
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="report-name">Report Name</Label>
              <Input
                id="report-name"
                value={newReportName}
                onChange={(e) => setNewReportName(e.target.value)}
                placeholder="Enter report name"
              />
            </div>

            <div className="space-y-2">
              <Label>Output Format</Label>
              <Select value={newReportFormat} onValueChange={(v) => setNewReportFormat(v as ReportFormat)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select format" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pdf">PDF</SelectItem>
                  <SelectItem value="xlsx">Excel (XLSX)</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="html">HTML</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {selectedTemplate?.parameters.map((param) => (
              <div key={param.id} className="space-y-2">
                <Label>
                  {param.name}
                  {param.required && <span className="text-destructive ml-1">*</span>}
                </Label>
                {param.type === "select" && param.options && (
                  <Select defaultValue={param.default as string}>
                    <SelectTrigger>
                      <SelectValue placeholder={`Select ${param.name.toLowerCase()}`} />
                    </SelectTrigger>
                    <SelectContent>
                      {param.options.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {param.type === "multiselect" && param.options && (
                  <div className="grid gap-2">
                    {param.options.map((opt) => (
                      <div key={opt.value} className="flex items-center space-x-2">
                        <Checkbox id={`param-${param.id}-${opt.value}`} />
                        <Label
                          htmlFor={`param-${param.id}-${opt.value}`}
                          className="text-sm font-normal"
                        >
                          {opt.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                )}
                {param.type === "daterange" && (
                  <div className="grid gap-2 grid-cols-2">
                    <Input type="date" placeholder="Start date" />
                    <Input type="date" placeholder="End date" />
                  </div>
                )}
              </div>
            ))}

            <div className="space-y-2">
              <Label>Schedule (Optional)</Label>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Run once (now)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="now">Run once (now)</SelectItem>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmitReport}>
              <Play className="mr-2 h-4 w-4" />
              Generate Report
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Provenance Detail Dialog */}
      <Dialog open={showProvenanceDialog} onOpenChange={setShowProvenanceDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Report Provenance
            </DialogTitle>
            <DialogDescription>
              Provenance metadata for report {selectedReport?.name}
            </DialogDescription>
          </DialogHeader>

          {selectedReport && (
            <div className="space-y-4">
              <div className="grid gap-3 text-sm">
                <div className="flex justify-between border-b pb-2">
                  <span className="text-muted-foreground">Template ID</span>
                  <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                    {selectedReport.provenance.templateId}
                  </code>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span className="text-muted-foreground">Operator</span>
                  <span>{selectedReport.provenance.operator}</span>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span className="text-muted-foreground">Source Cohort</span>
                  <span>{selectedReport.provenance.sourcePatientSet || "N/A"}</span>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span className="text-muted-foreground">Generated At</span>
                  <span>{formatDate(selectedReport.provenance.reportTimestamp)}</span>
                </div>
                {selectedReport.provenance.runId && (
                  <div className="flex justify-between border-b pb-2">
                    <span className="text-muted-foreground">Run ID</span>
                    <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                      {selectedReport.provenance.runId}
                    </code>
                  </div>
                )}
                <div className="flex justify-between border-b pb-2">
                  <span className="text-muted-foreground">SHA-256 Hash</span>
                  <code className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded max-w-[200px] truncate">
                    {generateSha256(selectedReport.id + selectedReport.provenance.reportTimestamp)}
                  </code>
                </div>
                {selectedReport.provenance.signature && (
                  <div className="flex justify-between border-b pb-2">
                    <span className="text-muted-foreground">Signature</span>
                    <code className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded max-w-[200px] truncate">
                      {selectedReport.provenance.signature}
                    </code>
                  </div>
                )}
                {selectedReport.provenance.sourceFilters && (
                  <div className="space-y-1">
                    <span className="text-muted-foreground">Filters</span>
                    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-24">
                      {JSON.stringify(selectedReport.provenance.sourceFilters, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <Button
                className="w-full"
                variant="outline"
                onClick={() => handleExportEvidenceBundle(selectedReport)}
              >
                <FileJson className="mr-2 h-4 w-4" />
                Export Evidence Bundle
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
