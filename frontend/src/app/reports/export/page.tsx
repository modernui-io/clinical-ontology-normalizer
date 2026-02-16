"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import {
  FileText,
  Download,
  Settings,
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  FileSpreadsheet,
  FilePieChart,
  FileBarChart,
  Loader2,
  Image,
  Table as TableIcon,
  Eye,
  Send,
  Archive,
} from "lucide-react";

// Types
interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  category: "clinical" | "analytics" | "quality" | "financial" | "operational";
  formats: ("pdf" | "xlsx" | "csv" | "html")[];
  lastExported?: string;
  exportCount: number;
}

interface ExportJob {
  id: string;
  reportName: string;
  format: string;
  status: "queued" | "generating" | "completed" | "failed";
  progress: number;
  createdAt: string;
  completedAt?: string;
  fileSize?: string;
  downloadUrl?: string;
  templateId?: string;
  operator?: string;
  parameters?: Record<string, unknown>;
}

// Mock data
const mockTemplates: ReportTemplate[] = [
  { id: "rpt-1", name: "Patient Demographics Summary", description: "Overview of patient demographics and population statistics", category: "clinical", formats: ["pdf", "xlsx", "csv"], lastExported: "2026-01-24T09:30:00Z", exportCount: 156 },
  { id: "rpt-2", name: "Data Quality Dashboard", description: "OHDSI DQD metrics and completeness analysis", category: "quality", formats: ["pdf", "xlsx", "html"], lastExported: "2026-01-24T08:15:00Z", exportCount: 89 },
  { id: "rpt-3", name: "Risk Stratification Report", description: "Patient risk scores and tier distribution", category: "analytics", formats: ["pdf", "xlsx"], lastExported: "2026-01-23T16:45:00Z", exportCount: 234 },
  { id: "rpt-4", name: "Cohort Analysis Results", description: "Comparative analysis of patient cohorts", category: "analytics", formats: ["pdf", "xlsx", "csv"], lastExported: "2026-01-24T10:00:00Z", exportCount: 67 },
  { id: "rpt-5", name: "Revenue Cycle Summary", description: "Financial metrics and billing analysis", category: "financial", formats: ["pdf", "xlsx"], lastExported: "2026-01-22T14:30:00Z", exportCount: 45 },
  { id: "rpt-6", name: "Care Gap Analysis", description: "Quality measure gaps and intervention opportunities", category: "quality", formats: ["pdf", "xlsx", "html"], lastExported: "2026-01-24T07:00:00Z", exportCount: 178 },
  { id: "rpt-7", name: "Terminology Coverage Report", description: "OMOP vocabulary mapping statistics", category: "operational", formats: ["pdf", "xlsx", "csv"], lastExported: "2026-01-21T11:00:00Z", exportCount: 34 },
  { id: "rpt-8", name: "Study Timeline Report", description: "Clinical trial timeline and milestone status", category: "clinical", formats: ["pdf", "html"], lastExported: "2026-01-20T09:15:00Z", exportCount: 23 },
];

const mockExportJobs: ExportJob[] = [
  { id: "job-1", reportName: "Data Quality Dashboard", format: "pdf", status: "completed", progress: 100, createdAt: "2026-01-24T10:15:00Z", completedAt: "2026-01-24T10:16:30Z", fileSize: "2.4 MB", downloadUrl: "#", templateId: "rpt-2", operator: "Quality Team", parameters: { dateRange: "last30days" } },
  { id: "job-2", reportName: "Risk Stratification Report", format: "xlsx", status: "generating", progress: 65, createdAt: "2026-01-24T10:18:00Z", templateId: "rpt-3", operator: "Analytics", parameters: { dateRange: "lastQuarter" } },
  { id: "job-3", reportName: "Patient Demographics Summary", format: "csv", status: "queued", progress: 0, createdAt: "2026-01-24T10:19:00Z", templateId: "rpt-1", operator: "Data Team", parameters: { dateRange: "last7days" } },
  { id: "job-4", reportName: "Cohort Analysis Results", format: "pdf", status: "failed", progress: 45, createdAt: "2026-01-24T09:30:00Z", templateId: "rpt-4", operator: "Research", parameters: { dateRange: "lastYear" } },
];

const categoryIcons: Record<string, React.ReactNode> = {
  clinical: <FileText className="h-4 w-4" />,
  analytics: <FilePieChart className="h-4 w-4" />,
  quality: <FileBarChart className="h-4 w-4" />,
  financial: <FileSpreadsheet className="h-4 w-4" />,
  operational: <TableIcon className="h-4 w-4" />,
};

const formatIcons: Record<string, React.ReactNode> = {
  pdf: <FileText className="h-4 w-4 text-red-500" />,
  xlsx: <FileSpreadsheet className="h-4 w-4 text-green-500" />,
  csv: <TableIcon className="h-4 w-4 text-blue-500" />,
  html: <Eye className="h-4 w-4 text-purple-500" />,
};

export default function ReportExportPage() {
  const [templates] = useState<ReportTemplate[]>(mockTemplates);
  const [exportJobs, setExportJobs] = useState<ExportJob[]>(mockExportJobs);
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(null);
  const [exportConfig, setExportConfig] = useState({
    format: "pdf",
    dateRange: "last30days",
    customStart: "",
    customEnd: "",
    includeCharts: true,
    includeRawData: false,
    orientation: "portrait",
    pageSize: "letter",
    compress: true,
    watermark: false,
    password: "",
    emailOnComplete: false,
    emailRecipients: "",
  });
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "queued":
        return <Clock className="h-4 w-4 text-gray-500" />;
      case "failed":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "generating":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return null;
    }
  };

  const handleExport = () => {
    if (!selectedTemplate) return;

    const newJob: ExportJob = {
      id: `job-${Date.now()}`,
      reportName: selectedTemplate.name,
      format: exportConfig.format,
      status: "queued",
      progress: 0,
      createdAt: new Date().toISOString(),
    };

    setExportJobs([newJob, ...exportJobs]);

    // Simulate progress
    let progress = 0;
    const interval = setInterval(() => {
      progress += 10;
      setExportJobs((jobs) =>
        jobs.map((j) =>
          j.id === newJob.id
            ? {
                ...j,
                status: progress < 100 ? "generating" : "completed",
                progress: Math.min(progress, 100),
                completedAt: progress >= 100 ? new Date().toISOString() : undefined,
                fileSize: progress >= 100 ? "1.8 MB" : undefined,
                downloadUrl: progress >= 100 ? "#" : undefined,
              }
            : j
        )
      );

      if (progress >= 100) {
        clearInterval(interval);
      }
    }, 500);
  };

  const filteredTemplates =
    categoryFilter === "all"
      ? templates
      : templates.filter((t) => t.category === categoryFilter);

  const completedExports = exportJobs.filter((j) => j.status === "completed").length;
  const pendingExports = exportJobs.filter((j) => j.status === "queued" || j.status === "generating").length;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Report Export</h1>
          <p className="text-muted-foreground">
            Export reports in PDF, Excel, CSV, and HTML formats
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Archive className="h-4 w-4 mr-2" />
            Export History
          </Button>
        </div>
      </div>

      <DataSourceModeBanner
        mode="simulation"
        title="Export data source mode"
        description="Report templates, exports, and queue behavior are simulated placeholders. Connect this workspace to production report jobs and parameterized run metadata before external use."
        evidencePath="tasks/09_master_change_backlog_p0_p4.md"
        lastUpdatedAt="2026-02-16"
        signoffText="Simulation only — export actions on this page do not generate real files or write to the backend."
        backendEndpoints={["/api/v1/reports/export", "/api/v1/reports/export/{job_id}/status", "/api/v1/reports/export/{job_id}/download"]}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Report Templates</p>
                <p className="text-2xl font-bold">{templates.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Completed Today</p>
                <p className="text-2xl font-bold">{completedExports}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">In Progress</p>
                <p className="text-2xl font-bold">{pendingExports}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Download className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Total Exports</p>
                <p className="text-2xl font-bold">
                  {templates.reduce((sum, t) => sum + t.exportCount, 0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Report Selection */}
        <Card className="col-span-2">
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>Available Reports</CardTitle>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="clinical">Clinical</SelectItem>
                  <SelectItem value="analytics">Analytics</SelectItem>
                  <SelectItem value="quality">Quality</SelectItem>
                  <SelectItem value="financial">Financial</SelectItem>
                  <SelectItem value="operational">Operational</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Select</TableHead>
                  <TableHead>Report</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Formats</TableHead>
                  <TableHead>Last Export</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTemplates.map((template) => (
                  <TableRow
                    key={template.id}
                    className={`cursor-pointer ${
                      selectedTemplate?.id === template.id ? "bg-blue-50" : ""
                    }`}
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <TableCell>
                      <Checkbox
                        checked={selectedTemplate?.id === template.id}
                        onCheckedChange={() => setSelectedTemplate(template)}
                      />
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium">{template.name}</p>
                        <p className="text-sm text-muted-foreground truncate max-w-[250px]">
                          {template.description}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="flex items-center gap-1 w-fit">
                        {categoryIcons[template.category]}
                        <span className="capitalize">{template.category}</span>
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {template.formats.map((f) => (
                          <span key={f} title={f.toUpperCase()}>
                            {formatIcons[f]}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {template.lastExported
                        ? new Date(template.lastExported).toLocaleDateString()
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Export Options */}
        <Card>
          <CardHeader>
            <CardTitle>Export Options</CardTitle>
            <CardDescription>
              {selectedTemplate
                ? `Configuring: ${selectedTemplate.name}`
                : "Select a report to configure"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Output Format</Label>
              <Select
                value={exportConfig.format}
                onValueChange={(v) => setExportConfig({ ...exportConfig, format: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {selectedTemplate?.formats.map((f) => (
                    <SelectItem key={f} value={f}>
                      {f.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Date Range</Label>
              <Select
                value={exportConfig.dateRange}
                onValueChange={(v) => setExportConfig({ ...exportConfig, dateRange: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="last7days">Last 7 Days</SelectItem>
                  <SelectItem value="last30days">Last 30 Days</SelectItem>
                  <SelectItem value="lastQuarter">Last Quarter</SelectItem>
                  <SelectItem value="lastYear">Last Year</SelectItem>
                  <SelectItem value="custom">Custom Range</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {exportConfig.dateRange === "custom" && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Start</Label>
                  <Input
                    type="date"
                    value={exportConfig.customStart}
                    onChange={(e) =>
                      setExportConfig({ ...exportConfig, customStart: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">End</Label>
                  <Input
                    type="date"
                    value={exportConfig.customEnd}
                    onChange={(e) =>
                      setExportConfig({ ...exportConfig, customEnd: e.target.value })
                    }
                  />
                </div>
              </div>
            )}

            {exportConfig.format === "pdf" && (
              <>
                <div className="space-y-2">
                  <Label>Page Size</Label>
                  <Select
                    value={exportConfig.pageSize}
                    onValueChange={(v) => setExportConfig({ ...exportConfig, pageSize: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="letter">Letter (8.5x11)</SelectItem>
                      <SelectItem value="a4">A4</SelectItem>
                      <SelectItem value="legal">Legal</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Orientation</Label>
                  <Select
                    value={exportConfig.orientation}
                    onValueChange={(v) => setExportConfig({ ...exportConfig, orientation: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="portrait">Portrait</SelectItem>
                      <SelectItem value="landscape">Landscape</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <Switch
                  checked={exportConfig.includeCharts}
                  onCheckedChange={(c) =>
                    setExportConfig({ ...exportConfig, includeCharts: c })
                  }
                />
                <span className="text-sm">Include Charts</span>
              </label>
              <label className="flex items-center gap-2">
                <Switch
                  checked={exportConfig.includeRawData}
                  onCheckedChange={(c) =>
                    setExportConfig({ ...exportConfig, includeRawData: c })
                  }
                />
                <span className="text-sm">Include Raw Data</span>
              </label>
              <label className="flex items-center gap-2">
                <Switch
                  checked={exportConfig.compress}
                  onCheckedChange={(c) =>
                    setExportConfig({ ...exportConfig, compress: c })
                  }
                />
                <span className="text-sm">Compress Output</span>
              </label>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <Switch
                  checked={exportConfig.emailOnComplete}
                  onCheckedChange={(c) =>
                    setExportConfig({ ...exportConfig, emailOnComplete: c })
                  }
                />
                <span className="text-sm">Email on Complete</span>
              </label>
              {exportConfig.emailOnComplete && (
                <Input
                  placeholder="email@example.com"
                  value={exportConfig.emailRecipients}
                  onChange={(e) =>
                    setExportConfig({ ...exportConfig, emailRecipients: e.target.value })
                  }
                />
              )}
            </div>

            <Button
              className="w-full"
              disabled={!selectedTemplate}
              onClick={handleExport}
            >
              <Download className="h-4 w-4 mr-2" />
              Export Report
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Export Queue */}
      <Card>
        <CardHeader>
          <CardTitle>Export Queue</CardTitle>
          <CardDescription>
            Monitor and download your generated reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Report</TableHead>
                <TableHead>Format</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Provenance</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {exportJobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>{getStatusIcon(job.status)}</TableCell>
                  <TableCell className="font-medium">{job.reportName}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="uppercase">
                      {job.format}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={job.progress} className="w-[100px] h-2" />
                      <span className="text-sm">{job.progress}%</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">{formatDate(job.createdAt)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {job.templateId && <div>Tmpl: <span className="font-mono">{job.templateId}</span></div>}
                    {job.operator && <div>Op: {job.operator}</div>}
                  </TableCell>
                  <TableCell>{job.fileSize || "-"}</TableCell>
                  <TableCell>
                    {job.status === "completed" && (
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm">
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm">
                          <Send className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                    {job.status === "failed" && (
                      <Button variant="ghost" size="sm">
                        Retry
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
