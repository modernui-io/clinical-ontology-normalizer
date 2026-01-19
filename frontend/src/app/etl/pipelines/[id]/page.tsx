"use client";

import { useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  FileText,
  Loader2,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Save,
  Settings,
  Trash2,
  XCircle,
  Workflow,
  ChevronRight,
  Zap,
  Filter,
  ArrowRightLeft,
  Upload,
} from "lucide-react";
import {
  usePipeline,
  usePipelineRuns,
  useSource,
  useUpdatePipeline,
  useUpdatePipelineSchedule,
  useTriggerPipelineRun,
  useDeletePipeline,
} from "@/hooks/use-api";
import type { Pipeline, PipelineRun, PipelineStage, PipelineSchedule } from "@/lib/api";

// =============================================================================
// Status Badge Component
// =============================================================================

const STATUS_CONFIG: Record<
  Pipeline["status"],
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  active: {
    label: "Active",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3 text-green-500" />,
  },
  paused: {
    label: "Paused",
    variant: "secondary",
    icon: <Pause className="h-3 w-3" />,
  },
  disabled: {
    label: "Disabled",
    variant: "secondary",
    icon: <XCircle className="h-3 w-3" />,
  },
  error: {
    label: "Error",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
};

function StatusBadge({ status }: { status: Pipeline["status"] }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {config.label}
    </Badge>
  );
}

// =============================================================================
// Run Status Badge Component
// =============================================================================

const RUN_STATUS_CONFIG: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  completed: {
    label: "Completed",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3 text-green-500" />,
  },
  running: {
    label: "Running",
    variant: "default",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: <XCircle className="h-3 w-3" />,
  },
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: <Clock className="h-3 w-3" />,
  },
};

function RunStatusBadge({ status }: { status: string }) {
  const config = RUN_STATUS_CONFIG[status] || RUN_STATUS_CONFIG.pending;
  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {config.label}
    </Badge>
  );
}

// =============================================================================
// Stage Icon Component
// =============================================================================

const STAGE_TYPE_CONFIG: Record<
  string,
  { icon: React.ReactNode; label: string; color: string }
> = {
  extract: {
    icon: <Database className="h-4 w-4" />,
    label: "Extract",
    color: "bg-blue-100 text-blue-700 border-blue-200",
  },
  transform: {
    icon: <ArrowRightLeft className="h-4 w-4" />,
    label: "Transform",
    color: "bg-purple-100 text-purple-700 border-purple-200",
  },
  filter: {
    icon: <Filter className="h-4 w-4" />,
    label: "Filter",
    color: "bg-orange-100 text-orange-700 border-orange-200",
  },
  validate: {
    icon: <CheckCircle className="h-4 w-4" />,
    label: "Validate",
    color: "bg-green-100 text-green-700 border-green-200",
  },
  load: {
    icon: <Upload className="h-4 w-4" />,
    label: "Load",
    color: "bg-indigo-100 text-indigo-700 border-indigo-200",
  },
  enrich: {
    icon: <Zap className="h-4 w-4" />,
    label: "Enrich",
    color: "bg-yellow-100 text-yellow-700 border-yellow-200",
  },
};

// =============================================================================
// Pipeline Stages Visual Component
// =============================================================================

interface PipelineStagesProps {
  stages: PipelineStage[];
}

function PipelineStagesVisual({ stages }: PipelineStagesProps) {
  const sortedStages = [...stages].sort((a, b) => a.order - b.order);

  if (sortedStages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Workflow className="h-12 w-12 text-muted-foreground/50" />
        <p className="mt-4 text-muted-foreground">
          No stages configured for this pipeline.
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-4">
      {sortedStages.map((stage, index) => {
        const config = STAGE_TYPE_CONFIG[stage.stage_type] || {
          icon: <FileText className="h-4 w-4" />,
          label: stage.stage_type,
          color: "bg-gray-100 text-gray-700 border-gray-200",
        };

        return (
          <div key={stage.name} className="flex items-center">
            <div
              className={`
                flex flex-col items-center gap-2 rounded-lg border p-4 min-w-[140px]
                ${config.color}
                ${!stage.enabled ? "opacity-50" : ""}
              `}
            >
              <div className="flex items-center gap-2">
                {config.icon}
                <span className="text-xs font-medium uppercase">{config.label}</span>
              </div>
              <span className="text-sm font-medium">{stage.name}</span>
              {!stage.enabled && (
                <Badge variant="secondary" className="text-xs">
                  Disabled
                </Badge>
              )}
            </div>
            {index < sortedStages.length - 1 && (
              <ChevronRight className="h-5 w-5 text-muted-foreground mx-2 flex-shrink-0" />
            )}
          </div>
        );
      })}
    </div>
  );
}

// =============================================================================
// Schedule Configuration Component
// =============================================================================

interface ScheduleConfigProps {
  schedule: PipelineSchedule;
  onSave: (schedule: Partial<PipelineSchedule>) => void;
  isSaving: boolean;
}

function ScheduleConfig({ schedule, onSave, isSaving }: ScheduleConfigProps) {
  const [enabled, setEnabled] = useState(schedule.enabled);
  const [frequency, setFrequency] = useState(schedule.frequency);
  const [timeOfDay, setTimeOfDay] = useState(schedule.time_of_day || "00:00");
  const [dayOfWeek, setDayOfWeek] = useState<number>(schedule.day_of_week ?? 0);
  const [dayOfMonth, setDayOfMonth] = useState<number>(schedule.day_of_month ?? 1);
  const [cronExpression, setCronExpression] = useState(schedule.cron_expression || "");
  const [timezone, setTimezone] = useState(schedule.timezone || "UTC");

  const handleSave = () => {
    const newSchedule: Partial<PipelineSchedule> = {
      enabled,
      frequency,
      timezone,
    };

    if (frequency !== "manual" && frequency !== "hourly") {
      newSchedule.time_of_day = timeOfDay;
    }

    if (frequency === "weekly") {
      newSchedule.day_of_week = dayOfWeek;
    }

    if (frequency === "monthly") {
      newSchedule.day_of_month = dayOfMonth;
    }

    if (frequency === "custom") {
      newSchedule.cron_expression = cronExpression;
    }

    onSave(newSchedule);
  };

  const daysOfWeek = [
    { value: 0, label: "Monday" },
    { value: 1, label: "Tuesday" },
    { value: 2, label: "Wednesday" },
    { value: 3, label: "Thursday" },
    { value: 4, label: "Friday" },
    { value: 5, label: "Saturday" },
    { value: 6, label: "Sunday" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Schedule Enabled</Label>
          <p className="text-sm text-muted-foreground">
            Enable automatic pipeline runs
          </p>
        </div>
        <Switch checked={enabled} onCheckedChange={setEnabled} />
      </div>

      <Separator />

      <div className="space-y-4">
        <div className="space-y-2">
          <Label>Frequency</Label>
          <Select value={frequency} onValueChange={(v) => setFrequency(v as typeof frequency)} disabled={!enabled}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="manual">Manual</SelectItem>
              <SelectItem value="hourly">Hourly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="custom">Custom (Cron)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {frequency !== "manual" && frequency !== "hourly" && frequency !== "custom" && (
          <div className="space-y-2">
            <Label>Time of Day</Label>
            <Input
              type="time"
              value={timeOfDay}
              onChange={(e) => setTimeOfDay(e.target.value)}
              disabled={!enabled}
            />
          </div>
        )}

        {frequency === "weekly" && (
          <div className="space-y-2">
            <Label>Day of Week</Label>
            <Select
              value={dayOfWeek.toString()}
              onValueChange={(v) => setDayOfWeek(parseInt(v))}
              disabled={!enabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {daysOfWeek.map((day) => (
                  <SelectItem key={day.value} value={day.value.toString()}>
                    {day.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {frequency === "monthly" && (
          <div className="space-y-2">
            <Label>Day of Month</Label>
            <Select
              value={dayOfMonth.toString()}
              onValueChange={(v) => setDayOfMonth(parseInt(v))}
              disabled={!enabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                  <SelectItem key={day} value={day.toString()}>
                    {day}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {frequency === "custom" && (
          <div className="space-y-2">
            <Label>Cron Expression</Label>
            <Input
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              placeholder="0 0 * * *"
              disabled={!enabled}
            />
            <p className="text-xs text-muted-foreground">
              Standard cron format: minute hour day month weekday
            </p>
          </div>
        )}

        <div className="space-y-2">
          <Label>Timezone</Label>
          <Select value={timezone} onValueChange={setTimezone} disabled={!enabled}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="UTC">UTC</SelectItem>
              <SelectItem value="America/New_York">Eastern (ET)</SelectItem>
              <SelectItem value="America/Chicago">Central (CT)</SelectItem>
              <SelectItem value="America/Denver">Mountain (MT)</SelectItem>
              <SelectItem value="America/Los_Angeles">Pacific (PT)</SelectItem>
              <SelectItem value="Europe/London">London (GMT)</SelectItem>
              <SelectItem value="Europe/Paris">Paris (CET)</SelectItem>
              <SelectItem value="Asia/Tokyo">Tokyo (JST)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button onClick={handleSave} disabled={isSaving} className="w-full">
        {isSaving ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Saving...
          </>
        ) : (
          <>
            <Save className="mr-2 h-4 w-4" />
            Save Schedule
          </>
        )}
      </Button>
    </div>
  );
}

// =============================================================================
// Run History Table Component
// =============================================================================

interface RunHistoryTableProps {
  runs: PipelineRun[];
  isLoading: boolean;
}

function RunHistoryTable({ runs, isLoading }: RunHistoryTableProps) {
  // Format date
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs.toFixed(0)}s`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Clock className="h-12 w-12 text-muted-foreground/50" />
        <p className="mt-4 text-muted-foreground">
          No run history available. Trigger a manual run to get started.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run ID</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Records</TableHead>
          <TableHead>Errors</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell className="font-mono text-xs">
              {run.id.slice(0, 8)}...
            </TableCell>
            <TableCell>
              <RunStatusBadge status={run.status} />
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatDate(run.started_at)}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatDuration(run.duration_seconds)}
            </TableCell>
            <TableCell className="text-sm">
              <span className="text-green-600 font-medium">
                {run.records_processed.toLocaleString()}
              </span>
            </TableCell>
            <TableCell className="text-sm">
              {run.records_failed > 0 ? (
                <span className="text-red-600 font-medium">
                  {run.records_failed.toLocaleString()}
                </span>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// =============================================================================
// Delete Confirmation Dialog
// =============================================================================

interface DeleteDialogProps {
  pipeline: Pipeline | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isDeleting: boolean;
}

function DeleteDialog({ pipeline, open, onOpenChange, onConfirm, isDeleting }: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Pipeline</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{pipeline?.name}&quot;? This action cannot be undone
            and will delete all associated run history.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Edit Pipeline Dialog
// =============================================================================

interface EditDialogProps {
  pipeline: Pipeline | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (updates: { name: string; description: string; batch_size: number; skip_on_error: boolean }) => void;
  isSaving: boolean;
}

function EditDialog({ pipeline, open, onOpenChange, onSave, isSaving }: EditDialogProps) {
  const [name, setName] = useState(pipeline?.name || "");
  const [description, setDescription] = useState(pipeline?.description || "");
  const [batchSize, setBatchSize] = useState(pipeline?.batch_size.toString() || "100");
  const [skipOnError, setSkipOnError] = useState(pipeline?.skip_on_error || false);

  // Reset form when pipeline changes
  useState(() => {
    if (pipeline) {
      setName(pipeline.name);
      setDescription(pipeline.description);
      setBatchSize(pipeline.batch_size.toString());
      setSkipOnError(pipeline.skip_on_error);
    }
  });

  const handleSave = () => {
    if (!name.trim()) {
      toast.error("Pipeline name is required");
      return;
    }
    onSave({
      name: name.trim(),
      description: description.trim(),
      batch_size: parseInt(batchSize) || 100,
      skip_on_error: skipOnError,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Pipeline</DialogTitle>
          <DialogDescription>
            Update the pipeline configuration.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="edit-name">
              Pipeline Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Pipeline name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-description">Description</Label>
            <Input
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-batch-size">Batch Size</Label>
            <Input
              id="edit-batch-size"
              type="number"
              min={1}
              max={10000}
              value={batchSize}
              onChange={(e) => setBatchSize(e.target.value)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Skip on Error</Label>
              <p className="text-sm text-muted-foreground">
                Continue processing if individual records fail
              </p>
            </div>
            <Switch checked={skipOnError} onCheckedChange={setSkipOnError} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !name.trim()}>
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Main Pipeline Detail Page Component
// =============================================================================

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function PipelineDetailPage({ params }: PageProps) {
  const { id: pipelineId } = use(params);
  const router = useRouter();

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  // Queries
  const {
    data: pipeline,
    isLoading: isPipelineLoading,
    refetch: refetchPipeline,
  } = usePipeline(pipelineId, { refetchInterval: 10000 });

  const {
    data: runsData,
    isLoading: isRunsLoading,
    refetch: refetchRuns,
  } = usePipelineRuns(pipelineId, 20, { refetchInterval: 10000 });

  const { data: source } = useSource(pipeline?.source_id || "", {
    enabled: !!pipeline?.source_id,
  });

  // Mutations
  const updatePipelineMutation = useUpdatePipeline({
    onSuccess: () => {
      toast.success("Pipeline updated");
      setShowEditDialog(false);
      refetchPipeline();
    },
    onError: (error) => {
      toast.error(`Failed to update pipeline: ${error.message}`);
    },
  });

  const updateScheduleMutation = useUpdatePipelineSchedule({
    onSuccess: () => {
      toast.success("Schedule updated");
      refetchPipeline();
    },
    onError: (error) => {
      toast.error(`Failed to update schedule: ${error.message}`);
    },
  });

  const triggerRunMutation = useTriggerPipelineRun({
    onSuccess: (data) => {
      toast.success(`Pipeline run started: ${data.run_id.slice(0, 8)}...`);
      setIsRunning(false);
      refetchRuns();
    },
    onError: (error) => {
      toast.error(`Failed to trigger run: ${error.message}`);
      setIsRunning(false);
    },
  });

  const deletePipelineMutation = useDeletePipeline({
    onSuccess: () => {
      toast.success("Pipeline deleted");
      router.push("/etl/pipelines");
    },
    onError: (error) => {
      toast.error(`Failed to delete pipeline: ${error.message}`);
    },
  });

  const handleRunPipeline = () => {
    setIsRunning(true);
    triggerRunMutation.mutate(pipelineId);
  };

  const handleToggleStatus = () => {
    if (!pipeline) return;
    const newStatus = pipeline.status === "active" ? "paused" : "active";
    updatePipelineMutation.mutate({
      pipelineId,
      request: { status: newStatus },
    });
  };

  const handleEditSave = (updates: { name: string; description: string; batch_size: number; skip_on_error: boolean }) => {
    updatePipelineMutation.mutate({
      pipelineId,
      request: updates,
    });
  };

  const handleScheduleSave = (schedule: Partial<PipelineSchedule>) => {
    // Convert null values to undefined for API compatibility
    const cleanSchedule: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(schedule)) {
      if (value !== null) {
        cleanSchedule[key] = value;
      }
    }
    updateScheduleMutation.mutate({
      pipelineId,
      schedule: cleanSchedule as Parameters<typeof updateScheduleMutation.mutate>[0]["schedule"],
    });
  };

  const handleDeleteConfirm = () => {
    deletePipelineMutation.mutate(pipelineId);
  };

  // Format date
  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isPipelineLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!pipeline) {
    return (
      <div className="p-6">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-medium">Pipeline Not Found</h3>
          <p className="mt-2 text-muted-foreground">
            The pipeline you&apos;re looking for doesn&apos;t exist or has been deleted.
          </p>
          <Button className="mt-4" asChild>
            <Link href="/etl/pipelines">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Pipelines
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const runs = runsData?.runs || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/etl/pipelines">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <h1 className="text-2xl font-bold tracking-tight">{pipeline.name}</h1>
            <StatusBadge status={pipeline.status} />
          </div>
          <p className="text-muted-foreground pl-10">
            {pipeline.description || "No description"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              refetchPipeline();
              refetchRuns();
            }}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggleStatus}
            disabled={updatePipelineMutation.isPending}
          >
            {pipeline.status === "active" ? (
              <>
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Activate
              </>
            )}
          </Button>
          <Button
            size="sm"
            onClick={handleRunPipeline}
            disabled={isRunning || pipeline.status === "disabled"}
          >
            {isRunning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Run Now
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Source</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              {source?.name || "Unknown"}
            </div>
            <p className="text-xs text-muted-foreground">
              {source?.source_type || "-"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Last Run</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold capitalize">
              {pipeline.last_run_status || "Never"}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatDate(pipeline.last_run_at)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pipeline.run_count}</div>
            <p className="text-xs text-muted-foreground">
              Since {formatDate(pipeline.created_at)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Batch Size</CardTitle>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pipeline.batch_size}</div>
            <p className="text-xs text-muted-foreground">
              Records per batch
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="stages" className="space-y-4">
        <TabsList>
          <TabsTrigger value="stages" className="gap-2">
            <Workflow className="h-4 w-4" />
            Stages
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-2">
            <Clock className="h-4 w-4" />
            Run History
          </TabsTrigger>
          <TabsTrigger value="schedule" className="gap-2">
            <Calendar className="h-4 w-4" />
            Schedule
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Stages Tab */}
        <TabsContent value="stages">
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Stages</CardTitle>
              <CardDescription>
                Visual representation of the data processing stages
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PipelineStagesVisual stages={pipeline.stages} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Run History Tab */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Run History</CardTitle>
              <CardDescription>
                Recent pipeline execution history
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RunHistoryTable runs={runs} isLoading={isRunsLoading} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Schedule Tab */}
        <TabsContent value="schedule">
          <Card>
            <CardHeader>
              <CardTitle>Schedule Configuration</CardTitle>
              <CardDescription>
                Configure when this pipeline should run automatically
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScheduleConfig
                schedule={pipeline.schedule}
                onSave={handleScheduleSave}
                isSaving={updateScheduleMutation.isPending}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Settings</CardTitle>
              <CardDescription>
                Configure pipeline behavior and options
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Pipeline ID</Label>
                  <p className="font-mono text-sm">{pipeline.id}</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Created</Label>
                  <p className="text-sm">{formatDate(pipeline.created_at)}</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Last Updated</Label>
                  <p className="text-sm">{formatDate(pipeline.updated_at)}</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Skip on Error</Label>
                  <p className="text-sm">{pipeline.skip_on_error ? "Yes" : "No"}</p>
                </div>
                {pipeline.max_records && (
                  <div className="space-y-2">
                    <Label className="text-muted-foreground">Max Records</Label>
                    <p className="text-sm">{pipeline.max_records.toLocaleString()}</p>
                  </div>
                )}
              </div>

              <Separator />

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowEditDialog(true)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit Pipeline
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => setShowDeleteDialog(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Pipeline
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <EditDialog
        pipeline={pipeline}
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        onSave={handleEditSave}
        isSaving={updatePipelineMutation.isPending}
      />

      {/* Delete Dialog */}
      <DeleteDialog
        pipeline={pipeline}
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDeleteConfirm}
        isDeleting={deletePipelineMutation.isPending}
      />
    </div>
  );
}
