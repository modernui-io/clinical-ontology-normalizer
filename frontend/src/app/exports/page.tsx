"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertCircle,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  Download,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface ExportFile {
  resource_type: string;
  url: string;
  count: number;
  size_bytes: number;
}

interface ExportJob {
  job_id: string;
  status: "pending" | "in-progress" | "completed" | "failed" | "cancelled" | "expired";
  export_type: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  resource_types: string[];
  since: string | null;
  output_files: ExportFile[];
  errors_count: number;
  progress: {
    total_resources: number;
    exported_resources: number;
    percent_complete: number;
  };
}

interface ExportStats {
  total_jobs: number;
  running_jobs: number;
  jobs_by_status: Record<string, number>;
  total_files_exported: number;
  export_base_dir: string;
  file_retention_hours: number;
}

// =============================================================================
// Constants
// =============================================================================

const API_BASE = "/api";

const RESOURCE_TYPES = [
  { value: "Patient", label: "Patient", description: "Patient demographics" },
  { value: "Condition", label: "Condition", description: "Diagnoses and problems" },
  { value: "MedicationRequest", label: "MedicationRequest", description: "Prescriptions and orders" },
  { value: "Observation", label: "Observation", description: "Lab results and vitals" },
  { value: "Procedure", label: "Procedure", description: "Clinical procedures" },
  { value: "AllergyIntolerance", label: "AllergyIntolerance", description: "Allergies" },
  { value: "Encounter", label: "Encounter", description: "Healthcare encounters" },
];

const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
  "in-progress": {
    label: "In Progress",
    variant: "default",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  completed: {
    label: "Completed",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3 text-green-500" />,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  cancelled: {
    label: "Cancelled",
    variant: "secondary",
    icon: <XCircle className="h-3 w-3" />,
  },
  expired: {
    label: "Expired",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
};

// =============================================================================
// API Functions
// =============================================================================

async function fetchJobs(): Promise<ExportJob[]> {
  const response = await fetch(`${API_BASE}/fhir/$export/admin/jobs`);
  if (!response.ok) throw new Error("Failed to fetch export jobs");
  const data = await response.json();
  return data.jobs;
}

async function fetchStats(): Promise<ExportStats> {
  const response = await fetch(`${API_BASE}/fhir/$export/admin/stats`);
  if (!response.ok) throw new Error("Failed to fetch export stats");
  return response.json();
}

async function startExport(resourceTypes: string[], since?: string): Promise<string> {
  const params = new URLSearchParams();
  if (resourceTypes.length > 0) {
    params.set("_type", resourceTypes.join(","));
  }
  if (since) {
    params.set("_since", since);
  }

  const response = await fetch(`${API_BASE}/fhir/$export?${params.toString()}`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to start export");
  }

  // Get job ID from Content-Location header
  const contentLocation = response.headers.get("Content-Location");
  if (contentLocation) {
    const jobId = contentLocation.split("/").pop();
    return jobId || "unknown";
  }
  return "unknown";
}

async function cancelExport(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/fhir/$export/${jobId}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error("Failed to cancel export");
  }
}

async function downloadFile(jobId: string, filename: string): Promise<void> {
  const url = `${API_BASE}/fhir/$export/${jobId}/download/${filename}`;
  window.open(url, "_blank");
}

// =============================================================================
// Helper Functions
// =============================================================================

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleString();
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "-";
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const diff = (endDate.getTime() - startDate.getTime()) / 1000;
  if (diff < 60) return `${diff.toFixed(1)}s`;
  return `${Math.floor(diff / 60)}m ${Math.floor(diff % 60)}s`;
}

// =============================================================================
// Status Badge Component
// =============================================================================

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {config.label}
    </Badge>
  );
}

// =============================================================================
// Export Row Component
// =============================================================================

interface ExportRowProps {
  job: ExportJob;
  onCancel: (jobId: string) => void;
  onDownload: (jobId: string, filename: string) => void;
  isCancelling: boolean;
}

function ExportRow({ job, onCancel, onDownload, isCancelling }: ExportRowProps) {
  const isActive = job.status === "in-progress" || job.status === "pending";
  const isCompleted = job.status === "completed";

  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-mono text-sm">{job.job_id.slice(0, 8)}...</span>
          <span className="text-xs text-muted-foreground capitalize">
            {job.export_type}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={job.status} />
      </TableCell>
      <TableCell>
        {isActive ? (
          <div className="w-32 space-y-1">
            <Progress value={job.progress.percent_complete} />
            <p className="text-xs text-muted-foreground">
              {job.progress.percent_complete.toFixed(1)}%
            </p>
          </div>
        ) : isCompleted ? (
          <span className="text-green-600">100%</span>
        ) : (
          "-"
        )}
      </TableCell>
      <TableCell>
        <div className="text-sm">
          <p>{job.resource_types.length} types</p>
          <p className="text-xs text-muted-foreground">
            {job.output_files.reduce((sum, f) => sum + f.count, 0).toLocaleString()} resources
          </p>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {formatDate(job.created_at)}
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {formatDuration(job.started_at, job.completed_at)}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          {isCompleted && job.output_files.length > 0 && (
            <Button
              variant="ghost"
              size="icon"
              title="Download files"
              onClick={() => onDownload(job.job_id, `${job.output_files[0].resource_type}.ndjson`)}
            >
              <Download className="h-4 w-4" />
            </Button>
          )}
          {isActive && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onCancel(job.job_id)}
              disabled={isCancelling}
              title="Cancel export"
            >
              {isCancelling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" />
              )}
            </Button>
          )}
          {!isActive && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onCancel(job.job_id)}
              disabled={isCancelling}
              title="Delete export"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// Export Details Panel
// =============================================================================

interface ExportDetailsPanelProps {
  job: ExportJob;
  onClose: () => void;
  onDownload: (filename: string) => void;
}

function ExportDetailsPanel({ job, onClose, onDownload }: ExportDetailsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Export Details
            </CardTitle>
            <CardDescription>Job ID: {job.job_id}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={job.status} />
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Progress */}
        {(job.status === "in-progress" || job.status === "pending") && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Progress</span>
              <span>{job.progress.percent_complete.toFixed(1)}%</span>
            </div>
            <Progress value={job.progress.percent_complete} className="h-3" />
            <p className="text-sm text-muted-foreground">
              {job.progress.exported_resources.toLocaleString()} /{" "}
              {job.progress.total_resources.toLocaleString()} resources
            </p>
          </div>
        )}

        {/* Resource Types */}
        <div>
          <h4 className="text-sm font-medium mb-2">Resource Types</h4>
          <div className="flex flex-wrap gap-2">
            {job.resource_types.map((type) => (
              <Badge key={type} variant="secondary">
                {type}
              </Badge>
            ))}
          </div>
        </div>

        {/* Output Files */}
        {job.status === "completed" && job.output_files.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2">Output Files</h4>
            <div className="space-y-2">
              {job.output_files.map((file) => (
                <div
                  key={file.resource_type}
                  className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{file.resource_type}.ndjson</p>
                      <p className="text-xs text-muted-foreground">
                        {file.count.toLocaleString()} resources - {formatBytes(file.size_bytes)}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onDownload(`${file.resource_type}.ndjson`)}
                  >
                    <Download className="h-3 w-3 mr-1" />
                    Download
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Created</p>
            <p>{formatDate(job.created_at)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Started</p>
            <p>{formatDate(job.started_at)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Completed</p>
            <p>{formatDate(job.completed_at)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Expires</p>
            <p>{formatDate(job.expires_at)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function ExportsPage() {
  // State
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [stats, setStats] = useState<ExportStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // Form state
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["Patient", "Condition", "MedicationRequest"]);
  const [sinceDate, setSinceDate] = useState("");

  // Load data
  const loadData = useCallback(async () => {
    try {
      const [jobsData, statsData] = await Promise.all([fetchJobs(), fetchStats()]);
      setJobs(jobsData);
      setStats(statsData);
    } catch (error) {
      console.error("Failed to load export data:", error);
      toast.error("Failed to load export data");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Poll for updates when there are active jobs
    const interval = setInterval(() => {
      if (jobs.some((j) => j.status === "in-progress" || j.status === "pending")) {
        loadData();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [loadData, jobs]);

  // Toggle resource type
  const toggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  // Start export
  const handleStartExport = async () => {
    if (selectedTypes.length === 0) {
      toast.error("Please select at least one resource type");
      return;
    }

    setIsStarting(true);
    try {
      const jobId = await startExport(selectedTypes, sinceDate || undefined);
      toast.success(`Export started: ${jobId.slice(0, 8)}...`);
      loadData();
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : "Failed to start export");
    } finally {
      setIsStarting(false);
    }
  };

  // Cancel export
  const handleCancel = async (jobId: string) => {
    setCancellingJobId(jobId);
    try {
      await cancelExport(jobId);
      toast.success("Export cancelled/deleted");
      if (selectedJobId === jobId) {
        setSelectedJobId(null);
      }
      loadData();
    } catch (error) {
      toast.error("Failed to cancel export");
    } finally {
      setCancellingJobId(null);
    }
  };

  // Download file
  const handleDownload = (jobId: string, filename: string) => {
    downloadFile(jobId, filename);
  };

  // Get selected job
  const selectedJob = jobs.find((j) => j.job_id === selectedJobId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bulk Data Export</h1>
          <p className="text-muted-foreground">
            FHIR Bulk Data Export (Flat FHIR) for large-scale data extraction
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadData}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Exports</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_jobs || 0}</div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
            <Loader2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.running_jobs || 0}</div>
            <p className="text-xs text-muted-foreground">Active exports</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Files Generated</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_files_exported || 0}</div>
            <p className="text-xs text-muted-foreground">NDJSON files</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Retention</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.file_retention_hours || 24}h</div>
            <p className="text-xs text-muted-foreground">File retention</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className={`grid gap-6 ${selectedJob ? "lg:grid-cols-2" : ""}`}>
        {/* New Export Card */}
        <Card>
          <CardHeader>
            <CardTitle>Start New Export</CardTitle>
            <CardDescription>
              Configure and start a FHIR Bulk Data Export
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Resource Types */}
            <div className="space-y-2">
              <Label>Resource Types</Label>
              <div className="grid grid-cols-2 gap-2">
                {RESOURCE_TYPES.map((type) => (
                  <div
                    key={type.value}
                    className="flex items-start space-x-2 p-2 rounded-lg border hover:bg-muted/50 cursor-pointer"
                    onClick={() => toggleType(type.value)}
                  >
                    <Checkbox
                      checked={selectedTypes.includes(type.value)}
                      onCheckedChange={() => toggleType(type.value)}
                    />
                    <div className="grid gap-1 leading-none">
                      <label className="text-sm font-medium cursor-pointer">
                        {type.label}
                      </label>
                      <p className="text-xs text-muted-foreground">
                        {type.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Since Date */}
            <div className="space-y-2">
              <Label htmlFor="since">Since (optional)</Label>
              <div className="flex gap-2">
                <Input
                  id="since"
                  type="datetime-local"
                  value={sinceDate}
                  onChange={(e) => setSinceDate(e.target.value)}
                  className="flex-1"
                />
                {sinceDate && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setSinceDate("")}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Only export resources modified after this date
              </p>
            </div>

            {/* Start Button */}
            <Button
              className="w-full"
              onClick={handleStartExport}
              disabled={isStarting || selectedTypes.length === 0}
            >
              {isStarting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting Export...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Start Export
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Export Details Panel */}
        {selectedJob && (
          <ExportDetailsPanel
            job={selectedJob}
            onClose={() => setSelectedJobId(null)}
            onDownload={(filename) => handleDownload(selectedJob.job_id, filename)}
          />
        )}
      </div>

      {/* Export Jobs Table */}
      <Card>
        <CardHeader>
          <CardTitle>Export History</CardTitle>
          <CardDescription>
            {jobs.length} export job{jobs.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No export jobs yet</p>
              <p className="text-sm mt-1">Start a new export above</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Resources</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="w-20">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow
                    key={job.job_id}
                    className={`cursor-pointer ${
                      selectedJobId === job.job_id ? "bg-muted/50" : ""
                    }`}
                    onClick={() => setSelectedJobId(job.job_id)}
                  >
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-mono text-sm">
                          {job.job_id.slice(0, 8)}...
                        </span>
                        <span className="text-xs text-muted-foreground capitalize">
                          {job.export_type}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={job.status} />
                    </TableCell>
                    <TableCell>
                      {job.status === "in-progress" ? (
                        <div className="w-24 space-y-1">
                          <Progress value={job.progress.percent_complete} />
                          <p className="text-xs text-muted-foreground">
                            {job.progress.percent_complete.toFixed(0)}%
                          </p>
                        </div>
                      ) : job.status === "completed" ? (
                        <span className="text-green-600">100%</span>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell>
                      {job.output_files
                        .reduce((sum, f) => sum + f.count, 0)
                        .toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(job.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatDuration(job.started_at, job.completed_at)}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1">
                        {job.status === "completed" && job.output_files.length > 0 && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Download"
                            onClick={() =>
                              handleDownload(
                                job.job_id,
                                `${job.output_files[0].resource_type}.ndjson`
                              )
                            }
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleCancel(job.job_id)}
                          disabled={cancellingJobId === job.job_id}
                          title={
                            job.status === "in-progress" || job.status === "pending"
                              ? "Cancel"
                              : "Delete"
                          }
                        >
                          {cancellingJobId === job.job_id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : job.status === "in-progress" ||
                            job.status === "pending" ? (
                            <X className="h-4 w-4" />
                          ) : (
                            <Trash2 className="h-4 w-4 text-destructive" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
