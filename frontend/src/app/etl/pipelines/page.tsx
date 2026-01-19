"use client";

import { useState } from "react";
import Link from "next/link";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  AlertCircle,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  Loader2,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
  Workflow,
} from "lucide-react";
import {
  usePipelines,
  useSources,
  useCreatePipeline,
  useDeletePipeline,
  useTriggerPipelineRun,
  useUpdatePipeline,
} from "@/hooks/use-api";
import type { Pipeline, Source, CreatePipelineRequest } from "@/lib/api";

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
// Schedule Display Component
// =============================================================================

function ScheduleDisplay({ schedule }: { schedule: Pipeline["schedule"] }) {
  if (!schedule.enabled || schedule.frequency === "manual") {
    return <span className="text-muted-foreground">Manual</span>;
  }

  const getScheduleText = () => {
    switch (schedule.frequency) {
      case "hourly":
        return "Every hour";
      case "daily":
        return `Daily at ${schedule.time_of_day}`;
      case "weekly":
        const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        const day = schedule.day_of_week !== null ? days[schedule.day_of_week] : "";
        return `${day} at ${schedule.time_of_day}`;
      case "monthly":
        return `${schedule.day_of_month}th at ${schedule.time_of_day}`;
      case "custom":
        return schedule.cron_expression || "Custom";
      default:
        return schedule.frequency;
    }
  };

  return (
    <div className="flex items-center gap-1 text-sm">
      <Calendar className="h-3 w-3 text-muted-foreground" />
      <span>{getScheduleText()}</span>
    </div>
  );
}

// =============================================================================
// Create Pipeline Dialog
// =============================================================================

interface CreatePipelineDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: Source[];
  onSubmit: (request: CreatePipelineRequest) => void;
  isCreating: boolean;
}

function CreatePipelineDialog({
  open,
  onOpenChange,
  sources,
  onSubmit,
  isCreating,
}: CreatePipelineDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [batchSize, setBatchSize] = useState("100");

  const handleSubmit = () => {
    if (!name.trim() || !sourceId) {
      toast.error("Please fill in all required fields");
      return;
    }

    onSubmit({
      name: name.trim(),
      description: description.trim(),
      source_id: sourceId,
      batch_size: parseInt(batchSize, 10) || 100,
    });
  };

  const handleClose = () => {
    setName("");
    setDescription("");
    setSourceId("");
    setBatchSize("100");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Pipeline</DialogTitle>
          <DialogDescription>
            Create a new ETL pipeline for data extraction and transformation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="name">
              Pipeline Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Daily Patient Sync"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="source">
              Data Source <span className="text-destructive">*</span>
            </Label>
            <Select value={sourceId} onValueChange={setSourceId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a data source" />
              </SelectTrigger>
              <SelectContent>
                {sources.map((source) => (
                  <SelectItem key={source.id} value={source.id}>
                    <div className="flex items-center gap-2">
                      <Database className="h-4 w-4" />
                      {source.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {sources.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No sources configured.{" "}
                <Link href="/etl/sources/new" className="text-primary hover:underline">
                  Add a source
                </Link>{" "}
                first.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="batchSize">Batch Size</Label>
            <Input
              id="batchSize"
              type="number"
              min={1}
              max={10000}
              value={batchSize}
              onChange={(e) => setBatchSize(e.target.value)}
              placeholder="100"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isCreating || !name.trim() || !sourceId}>
            {isCreating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Create Pipeline
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
// Pipeline Row Component
// =============================================================================

interface PipelineRowProps {
  pipeline: Pipeline;
  source: Source | undefined;
  onRun: (pipelineId: string) => void;
  onToggleStatus: (pipeline: Pipeline) => void;
  onDelete: (pipeline: Pipeline) => void;
  isRunning: boolean;
}

function PipelineRow({
  pipeline,
  source,
  onRun,
  onToggleStatus,
  onDelete,
  isRunning,
}: PipelineRowProps) {
  // Format date
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Format duration
  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${(seconds % 60).toFixed(0)}s`;
  };

  return (
    <TableRow>
      <TableCell>
        <div>
          <Link
            href={`/etl/pipelines/${pipeline.id}`}
            className="font-medium hover:underline"
          >
            {pipeline.name}
          </Link>
          <p className="text-xs text-muted-foreground">
            {pipeline.description || "No description"}
          </p>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm">{source?.name || "Unknown"}</span>
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={pipeline.status} />
      </TableCell>
      <TableCell>
        <ScheduleDisplay schedule={pipeline.schedule} />
      </TableCell>
      <TableCell className="text-sm">
        <div className="flex items-center gap-1">
          {pipeline.last_run_status === "completed" ? (
            <CheckCircle className="h-3 w-3 text-green-500" />
          ) : pipeline.last_run_status === "failed" ? (
            <XCircle className="h-3 w-3 text-red-500" />
          ) : pipeline.last_run_status === "running" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Clock className="h-3 w-3 text-muted-foreground" />
          )}
          <span className="text-muted-foreground">
            {pipeline.last_run_status || "Never run"}
          </span>
        </div>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDate(pipeline.last_run_at)}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {pipeline.run_count}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onRun(pipeline.id)}
            disabled={isRunning || pipeline.status === "disabled"}
            title="Run now"
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/etl/pipelines/${pipeline.id}`}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onToggleStatus(pipeline)}>
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
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => onDelete(pipeline)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// Main Pipelines Page Component
// =============================================================================

export default function PipelinesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [deletePipeline, setDeletePipeline] = useState<Pipeline | null>(null);
  const [runningPipelineId, setRunningPipelineId] = useState<string | null>(null);

  // Queries
  const {
    data: pipelinesData,
    isLoading,
    refetch,
  } = usePipelines(
    { status: statusFilter || undefined },
    { refetchInterval: 10000 }
  );

  const { data: sourcesData } = useSources();

  // Mutations
  const createPipelineMutation = useCreatePipeline({
    onSuccess: () => {
      toast.success("Pipeline created successfully");
      setShowCreateDialog(false);
    },
    onError: (error) => {
      toast.error(`Failed to create pipeline: ${error.message}`);
    },
  });

  const deletePipelineMutation = useDeletePipeline({
    onSuccess: () => {
      toast.success("Pipeline deleted successfully");
      setDeletePipeline(null);
    },
    onError: (error) => {
      toast.error(`Failed to delete pipeline: ${error.message}`);
    },
  });

  const triggerRunMutation = useTriggerPipelineRun({
    onSuccess: (data) => {
      toast.success(`Pipeline run started: ${data.run_id.slice(0, 8)}...`);
      setRunningPipelineId(null);
    },
    onError: (error) => {
      toast.error(`Failed to trigger run: ${error.message}`);
      setRunningPipelineId(null);
    },
  });

  const updatePipelineMutation = useUpdatePipeline({
    onSuccess: () => {
      toast.success("Pipeline updated");
    },
    onError: (error) => {
      toast.error(`Failed to update pipeline: ${error.message}`);
    },
  });

  const handleRunPipeline = (pipelineId: string) => {
    setRunningPipelineId(pipelineId);
    triggerRunMutation.mutate(pipelineId);
  };

  const handleToggleStatus = (pipeline: Pipeline) => {
    const newStatus = pipeline.status === "active" ? "paused" : "active";
    updatePipelineMutation.mutate({
      pipelineId: pipeline.id,
      request: { status: newStatus },
    });
  };

  const handleDeleteConfirm = () => {
    if (deletePipeline) {
      deletePipelineMutation.mutate(deletePipeline.id);
    }
  };

  const handleCreatePipeline = (request: CreatePipelineRequest) => {
    createPipelineMutation.mutate(request);
  };

  const pipelines = pipelinesData?.pipelines || [];
  const sources = sourcesData?.sources || [];

  // Create a lookup map for sources
  const sourceMap = new Map(sources.map((s) => [s.id, s]));

  // Count pipelines by status for filter
  const statusCounts = pipelines.reduce(
    (acc, pipeline) => {
      acc[pipeline.status] = (acc[pipeline.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">ETL Pipelines</h1>
          <p className="text-muted-foreground">
            Configure and manage data extraction pipelines
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreateDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Pipeline
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={statusFilter === "" ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter("")}
        >
          All ({pipelines.length})
        </Button>
        {Object.entries(STATUS_CONFIG).map(([status, config]) => (
          <Button
            key={status}
            variant={statusFilter === status ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(status)}
            className="gap-1"
          >
            {config.icon}
            {config.label} ({statusCounts[status] || 0})
          </Button>
        ))}
      </div>

      {/* Pipelines Table */}
      <Card>
        <CardHeader>
          <CardTitle>Configured Pipelines</CardTitle>
          <CardDescription>
            {pipelines.length} pipeline{pipelines.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : pipelines.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Workflow className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">No pipelines configured</h3>
              <p className="mt-2 text-muted-foreground">
                Create your first ETL pipeline to start extracting data.
              </p>
              <Button className="mt-4" onClick={() => setShowCreateDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Pipeline
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Last Run Time</TableHead>
                  <TableHead>Total Runs</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pipelines.map((pipeline) => (
                  <PipelineRow
                    key={pipeline.id}
                    pipeline={pipeline}
                    source={sourceMap.get(pipeline.source_id)}
                    onRun={handleRunPipeline}
                    onToggleStatus={handleToggleStatus}
                    onDelete={setDeletePipeline}
                    isRunning={runningPipelineId === pipeline.id}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create Pipeline Dialog */}
      <CreatePipelineDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        sources={sources}
        onSubmit={handleCreatePipeline}
        isCreating={createPipelineMutation.isPending}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        pipeline={deletePipeline}
        open={!!deletePipeline}
        onOpenChange={(open) => !open && setDeletePipeline(null)}
        onConfirm={handleDeleteConfirm}
        isDeleting={deletePipelineMutation.isPending}
      />
    </div>
  );
}
