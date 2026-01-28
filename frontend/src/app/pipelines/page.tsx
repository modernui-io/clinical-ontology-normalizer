"use client";

/**
 * Pipelines Management UI
 *
 * Interface for managing data ingestion pipelines.
 * Allows creating, editing, and monitoring pipeline execution.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Plus,
  Trash2,
  Edit,
  RefreshCw,
  Loader2,
  Play,
  Pause,
  RotateCcw,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Zap,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

type PipelineStatus = "active" | "paused" | "disabled";
type ScheduleType = "manual" | "interval" | "cron";

interface Pipeline {
  id: string;
  name: string;
  description: string | null;
  source_id: string;
  source_name: string | null;
  status: PipelineStatus;
  is_active: boolean;
  schedule_type: ScheduleType;
  schedule_cron: string | null;
  schedule_interval_minutes: number | null;
  transformation_config: Record<string, unknown>;
  last_run_at: string | null;
  last_run_status: string | null;
  next_run_at: string | null;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  created_at: string;
  updated_at: string;
}

interface DataSource {
  id: string;
  name: string;
  source_type: string;
}

interface PipelineForm {
  name: string;
  description: string;
  source_id: string;
  schedule_type: ScheduleType;
  schedule_cron: string;
  schedule_interval_minutes: number;
  patient_matching_strategy: string;
  nlp_enrichment_enabled: boolean;
  code_mapping_prefer_standard: boolean;
}

const STATUS_CONFIG: Record<PipelineStatus, { label: string; variant: "default" | "secondary" | "destructive" }> = {
  active: { label: "Active", variant: "default" },
  paused: { label: "Paused", variant: "secondary" },
  disabled: { label: "Disabled", variant: "destructive" },
};

const SCHEDULE_OPTIONS: { value: ScheduleType; label: string }[] = [
  { value: "manual", label: "Manual Only" },
  { value: "interval", label: "Fixed Interval" },
  { value: "cron", label: "Cron Schedule" },
];

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at 2 AM", value: "0 2 * * *" },
  { label: "Weekly (Sunday 2 AM)", value: "0 2 * * 0" },
];

const DEFAULT_FORM: PipelineForm = {
  name: "",
  description: "",
  source_id: "",
  schedule_type: "manual",
  schedule_cron: "",
  schedule_interval_minutes: 60,
  patient_matching_strategy: "deterministic",
  nlp_enrichment_enabled: true,
  code_mapping_prefer_standard: true,
};

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [form, setForm] = useState<PipelineForm>(DEFAULT_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    loadPipelines();
    loadDataSources();
  }, []);

  async function loadPipelines() {
    setLoading(true);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/pipelines`, {
        headers: getAuthHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        setPipelines(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      toast.error("Failed to load pipelines");
    } finally {
      setLoading(false);
    }
  }

  async function loadDataSources() {
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/data-sources?is_active=true`, {
        headers: getAuthHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        setDataSources(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error("Failed to load data sources");
    }
  }

  async function savePipeline() {
    setSaving(true);
    try {
      const token = getStoredToken();
      const url = editingId
        ? `${API_BASE_URL}/api/v1/pipelines/${editingId}`
        : `${API_BASE_URL}/api/v1/pipelines`;

      const response = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          source_id: form.source_id,
          schedule_type: form.schedule_type,
          schedule_cron: form.schedule_type === "cron" ? form.schedule_cron : null,
          schedule_interval_minutes: form.schedule_type === "interval" ? form.schedule_interval_minutes : null,
          patient_matching_strategy: form.patient_matching_strategy,
          nlp_enrichment_enabled: form.nlp_enrichment_enabled,
          code_mapping_prefer_standard: form.code_mapping_prefer_standard,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Failed to save");
      }

      await loadPipelines();
      toast.success(editingId ? "Pipeline updated" : "Pipeline created");
      closeDialog();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save pipeline");
    } finally {
      setSaving(false);
    }
  }

  async function deletePipeline(id: string) {
    if (!confirm("Are you sure you want to delete this pipeline?")) return;

    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/pipelines/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to delete");
      }

      await loadPipelines();
      toast.success("Pipeline deleted");
    } catch (err) {
      toast.error("Failed to delete pipeline");
    }
  }

  async function runPipeline(id: string) {
    setRunning(id);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/pipelines/${id}/run`, {
        method: "POST",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to trigger run");
      }

      toast.success("Pipeline run started");
      await loadPipelines();
    } catch (err) {
      toast.error("Failed to start pipeline run");
    } finally {
      setRunning(null);
    }
  }

  async function pausePipeline(id: string) {
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/pipelines/${id}/pause`, {
        method: "POST",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to pause");
      }

      toast.success("Pipeline paused");
      await loadPipelines();
    } catch (err) {
      toast.error("Failed to pause pipeline");
    }
  }

  async function resumePipeline(id: string) {
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/pipelines/${id}/resume`, {
        method: "POST",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to resume");
      }

      toast.success("Pipeline resumed");
      await loadPipelines();
    } catch (err) {
      toast.error("Failed to resume pipeline");
    }
  }

  function openEditDialog(pipeline: Pipeline) {
    setEditingId(pipeline.id);
    setForm({
      name: pipeline.name,
      description: pipeline.description || "",
      source_id: pipeline.source_id,
      schedule_type: pipeline.schedule_type,
      schedule_cron: pipeline.schedule_cron || "",
      schedule_interval_minutes: pipeline.schedule_interval_minutes || 60,
      patient_matching_strategy:
        (pipeline.transformation_config?.patient_matching as { strategy?: string })?.strategy || "deterministic",
      nlp_enrichment_enabled:
        (pipeline.transformation_config?.nlp_enrichment as { enabled?: boolean })?.enabled ?? true,
      code_mapping_prefer_standard:
        (pipeline.transformation_config?.code_mapping as { prefer_standard?: boolean })?.prefer_standard ?? true,
    });
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditingId(null);
    setForm(DEFAULT_FORM);
  }

  function formatNextRun(nextRun: string | null): string {
    if (!nextRun) return "Not scheduled";
    const date = new Date(nextRun);
    const now = new Date();
    const diff = date.getTime() - now.getTime();
    if (diff < 0) return "Overdue";
    if (diff < 3600000) return `${Math.round(diff / 60000)} min`;
    if (diff < 86400000) return `${Math.round(diff / 3600000)} hr`;
    return date.toLocaleDateString();
  }

  function getSuccessRate(pipeline: Pipeline): string {
    if (pipeline.total_runs === 0) return "N/A";
    return `${Math.round((pipeline.successful_runs / pipeline.total_runs) * 100)}%`;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Data Pipelines</h1>
          <p className="text-muted-foreground">Manage data ingestion workflows</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadPipelines} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button
                onClick={() => {
                  setEditingId(null);
                  setForm(DEFAULT_FORM);
                }}
                disabled={dataSources.length === 0}
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Pipeline
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editingId ? "Edit Pipeline" : "Create Pipeline"}</DialogTitle>
                <DialogDescription>
                  Configure a data ingestion pipeline
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4">
                {/* Basic Info */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <Label htmlFor="name">Name</Label>
                    <Input
                      id="name"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Daily Patient Sync"
                    />
                  </div>

                  <div className="col-span-2">
                    <Label htmlFor="description">Description</Label>
                    <Input
                      id="description"
                      value={form.description}
                      onChange={(e) => setForm({ ...form, description: e.target.value })}
                      placeholder="Sync patient data from EHR every night"
                    />
                  </div>

                  <div className="col-span-2">
                    <Label htmlFor="source_id">Data Source</Label>
                    <Select
                      value={form.source_id}
                      onValueChange={(v) => setForm({ ...form, source_id: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a data source" />
                      </SelectTrigger>
                      <SelectContent>
                        {dataSources.map((source) => (
                          <SelectItem key={source.id} value={source.id}>
                            {source.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Schedule */}
                <div className="border-t pt-4">
                  <h4 className="font-medium mb-3">Schedule</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Schedule Type</Label>
                      <Select
                        value={form.schedule_type}
                        onValueChange={(v) => setForm({ ...form, schedule_type: v as ScheduleType })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SCHEDULE_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {form.schedule_type === "interval" && (
                      <div>
                        <Label>Interval (minutes)</Label>
                        <Input
                          type="number"
                          value={form.schedule_interval_minutes}
                          onChange={(e) =>
                            setForm({ ...form, schedule_interval_minutes: parseInt(e.target.value) || 60 })
                          }
                        />
                      </div>
                    )}

                    {form.schedule_type === "cron" && (
                      <div className="col-span-2">
                        <Label>Cron Expression</Label>
                        <Input
                          value={form.schedule_cron}
                          onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })}
                          placeholder="0 2 * * *"
                        />
                        <div className="flex gap-2 mt-2">
                          {CRON_PRESETS.map((preset) => (
                            <Button
                              key={preset.value}
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setForm({ ...form, schedule_cron: preset.value })}
                            >
                              {preset.label}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Transformation Settings */}
                <div className="border-t pt-4">
                  <h4 className="font-medium mb-3">Transformation Settings</h4>
                  <div className="space-y-3">
                    <div>
                      <Label>Patient Matching Strategy</Label>
                      <Select
                        value={form.patient_matching_strategy}
                        onValueChange={(v) => setForm({ ...form, patient_matching_strategy: v })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="deterministic">Deterministic (exact match)</SelectItem>
                          <SelectItem value="probabilistic">Probabilistic (fuzzy match)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="nlp_enabled"
                        checked={form.nlp_enrichment_enabled}
                        onCheckedChange={(c) => setForm({ ...form, nlp_enrichment_enabled: c === true })}
                      />
                      <Label htmlFor="nlp_enabled">Enable NLP enrichment for clinical notes</Label>
                    </div>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="prefer_standard"
                        checked={form.code_mapping_prefer_standard}
                        onCheckedChange={(c) => setForm({ ...form, code_mapping_prefer_standard: c === true })}
                      />
                      <Label htmlFor="prefer_standard">Prefer standard OMOP concepts for code mapping</Label>
                    </div>
                  </div>
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={closeDialog}>
                  Cancel
                </Button>
                <Button onClick={savePipeline} disabled={saving || !form.name || !form.source_id}>
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {dataSources.length === 0 && !loading && (
        <Card className="border-dashed">
          <CardContent className="py-8 text-center">
            <Zap className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-medium">No Data Sources Configured</p>
            <p className="text-muted-foreground mb-4">
              You need to configure at least one data source before creating pipelines.
            </p>
            <Link href="/admin/data-sources">
              <Button>
                Configure Data Sources
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Pipelines</CardTitle>
          <CardDescription>
            {pipelines.length} pipeline{pipelines.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : pipelines.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Zap className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No pipelines configured.</p>
              <p className="text-sm">Create a pipeline to start importing data.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Success Rate</TableHead>
                  <TableHead>Next Run</TableHead>
                  <TableHead className="w-[180px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pipelines.map((pipeline) => {
                  const statusConfig = STATUS_CONFIG[pipeline.status];
                  return (
                    <TableRow key={pipeline.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{pipeline.name}</div>
                          {pipeline.description && (
                            <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                              {pipeline.description}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">{pipeline.source_name || "Unknown"}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {pipeline.schedule_type === "manual" ? (
                            <Badge variant="outline">Manual</Badge>
                          ) : pipeline.schedule_type === "cron" ? (
                            <Badge variant="secondary" className="gap-1">
                              <Calendar className="h-3 w-3" />
                              {pipeline.schedule_cron}
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <Clock className="h-3 w-3" />
                              Every {pipeline.schedule_interval_minutes}m
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
                      </TableCell>
                      <TableCell>
                        {pipeline.last_run_at ? (
                          <div className="flex items-center gap-1">
                            {pipeline.last_run_status === "completed" ? (
                              <CheckCircle className="h-3 w-3 text-green-500" />
                            ) : pipeline.last_run_status === "failed" ? (
                              <XCircle className="h-3 w-3 text-red-500" />
                            ) : (
                              <AlertCircle className="h-3 w-3 text-yellow-500" />
                            )}
                            <span className="text-sm">
                              {new Date(pipeline.last_run_at).toLocaleDateString()}
                            </span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">Never</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">{getSuccessRate(pipeline)}</span>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">{formatNextRun(pipeline.next_run_at)}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => runPipeline(pipeline.id)}
                            disabled={running === pipeline.id}
                            title="Run Now"
                          >
                            {running === pipeline.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                          </Button>
                          {pipeline.status === "paused" ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => resumePipeline(pipeline.id)}
                              title="Resume"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => pausePipeline(pipeline.id)}
                              title="Pause"
                            >
                              <Pause className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openEditDialog(pipeline)}
                            title="Edit"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive"
                            onClick={() => deletePipeline(pipeline.id)}
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
