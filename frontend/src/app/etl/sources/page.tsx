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
  CheckCircle,
  Database,
  FileText,
  Loader2,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Server,
  Trash2,
  XCircle,
  AlertCircle,
  HelpCircle,
  Zap,
} from "lucide-react";
import {
  useSources,
  useDeleteSource,
  useTestSourceConnection,
} from "@/hooks/use-api";
import type { Source } from "@/lib/api";

// =============================================================================
// Status Badge Component
// =============================================================================

const STATUS_CONFIG: Record<
  Source["status"],
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
> = {
  unknown: {
    label: "Unknown",
    variant: "secondary",
    icon: <HelpCircle className="h-3 w-3" />,
  },
  connected: {
    label: "Connected",
    variant: "outline",
    icon: <CheckCircle className="h-3 w-3 text-green-500" />,
  },
  disconnected: {
    label: "Disconnected",
    variant: "secondary",
    icon: <XCircle className="h-3 w-3" />,
  },
  error: {
    label: "Error",
    variant: "destructive",
    icon: <AlertCircle className="h-3 w-3" />,
  },
  testing: {
    label: "Testing...",
    variant: "default",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
};

function StatusBadge({ status }: { status: Source["status"] }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant={config.variant} className="gap-1">
      {config.icon}
      {config.label}
    </Badge>
  );
}

// =============================================================================
// Source Type Icon Component
// =============================================================================

const SOURCE_TYPE_CONFIG: Record<
  Source["source_type"],
  { icon: React.ReactNode; label: string; color: string }
> = {
  fhir: {
    icon: <Server className="h-4 w-4" />,
    label: "FHIR R4",
    color: "text-blue-500",
  },
  hl7v2: {
    icon: <FileText className="h-4 w-4" />,
    label: "HL7 v2",
    color: "text-purple-500",
  },
  ccda: {
    icon: <FileText className="h-4 w-4" />,
    label: "C-CDA",
    color: "text-green-500",
  },
  csv: {
    icon: <FileText className="h-4 w-4" />,
    label: "CSV",
    color: "text-orange-500",
  },
  database: {
    icon: <Database className="h-4 w-4" />,
    label: "Database",
    color: "text-indigo-500",
  },
};

function SourceTypeIcon({ type }: { type: Source["source_type"] }) {
  const config = SOURCE_TYPE_CONFIG[type];
  return (
    <div className={`flex items-center gap-2 ${config.color}`}>
      {config.icon}
      <span className="text-sm font-medium text-foreground">{config.label}</span>
    </div>
  );
}

// =============================================================================
// Delete Confirmation Dialog
// =============================================================================

interface DeleteDialogProps {
  source: Source | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isDeleting: boolean;
}

function DeleteDialog({ source, open, onOpenChange, onConfirm, isDeleting }: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Data Source</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{source?.name}&quot;? This action cannot be undone
            and will also delete all associated pipelines.
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
// Source Row Component
// =============================================================================

interface SourceRowProps {
  source: Source;
  onTest: (sourceId: string) => void;
  onDelete: (source: Source) => void;
  isTesting: boolean;
}

function SourceRow({ source, onTest, onDelete, isTesting }: SourceRowProps) {
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

  // Get connection info summary
  const getConnectionSummary = () => {
    const params = source.connection_params;
    if (params.host) {
      const port = params.port ? `:${params.port}` : "";
      return `${params.host}${port}`;
    }
    if (params.path) {
      return params.path.length > 40 ? `...${params.path.slice(-40)}` : params.path;
    }
    return "-";
  };

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2 ${SOURCE_TYPE_CONFIG[source.source_type].color} bg-muted`}>
            {SOURCE_TYPE_CONFIG[source.source_type].icon}
          </div>
          <div>
            <Link
              href={`/etl/sources/${source.id}`}
              className="font-medium hover:underline"
            >
              {source.name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {source.description || "No description"}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <SourceTypeIcon type={source.source_type} />
      </TableCell>
      <TableCell>
        <StatusBadge status={source.status} />
      </TableCell>
      <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
        {getConnectionSummary()}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDate(source.last_sync_at)}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDate(source.last_tested_at)}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onTest(source.id)}
            disabled={isTesting || source.status === "testing"}
            title="Test connection"
          >
            {isTesting || source.status === "testing" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
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
                <Link href={`/etl/sources/${source.id}`}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`/etl/sources/${source.id}/preview`}>
                  <Play className="mr-2 h-4 w-4" />
                  Preview Data
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => onDelete(source)}
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
// Main Sources Page Component
// =============================================================================

export default function SourcesPage() {
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string>("");
  const [deleteSource, setDeleteSource] = useState<Source | null>(null);
  const [testingSourceId, setTestingSourceId] = useState<string | null>(null);

  // Queries
  const {
    data: sourcesData,
    isLoading,
    refetch,
  } = useSources(
    { source_type: sourceTypeFilter || undefined },
    { refetchInterval: 30000 }
  );

  // Mutations
  const deleteSourceMutation = useDeleteSource({
    onSuccess: () => {
      toast.success("Source deleted successfully");
      setDeleteSource(null);
    },
    onError: (error) => {
      toast.error(`Failed to delete source: ${error.message}`);
    },
  });

  const testConnectionMutation = useTestSourceConnection({
    onSuccess: (data) => {
      if (data.success) {
        toast.success(`Connection successful (${data.latency_ms?.toFixed(0)}ms)`);
      } else {
        toast.error(`Connection failed: ${data.message}`);
      }
      setTestingSourceId(null);
    },
    onError: (error) => {
      toast.error(`Connection test failed: ${error.message}`);
      setTestingSourceId(null);
    },
  });

  const handleTestConnection = (sourceId: string) => {
    setTestingSourceId(sourceId);
    testConnectionMutation.mutate(sourceId);
  };

  const handleDeleteConfirm = () => {
    if (deleteSource) {
      deleteSourceMutation.mutate(deleteSource.id);
    }
  };

  const sources = sourcesData?.sources || [];

  // Count sources by type for filter
  const typeCounts = sources.reduce(
    (acc, source) => {
      acc[source.source_type] = (acc[source.source_type] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Sources</h1>
          <p className="text-muted-foreground">
            Configure and manage connections to clinical data sources
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
          <Button size="sm" asChild>
            <Link href="/etl/sources/new">
              <Plus className="mr-2 h-4 w-4" />
              New Source
            </Link>
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={sourceTypeFilter === "" ? "default" : "outline"}
          size="sm"
          onClick={() => setSourceTypeFilter("")}
        >
          All ({sources.length})
        </Button>
        {Object.entries(SOURCE_TYPE_CONFIG).map(([type, config]) => (
          <Button
            key={type}
            variant={sourceTypeFilter === type ? "default" : "outline"}
            size="sm"
            onClick={() => setSourceTypeFilter(type)}
            className="gap-2"
          >
            <span className={config.color}>{config.icon}</span>
            {config.label} ({typeCounts[type] || 0})
          </Button>
        ))}
      </div>

      {/* Sources Table */}
      <Card>
        <CardHeader>
          <CardTitle>Configured Sources</CardTitle>
          <CardDescription>
            {sources.length} source{sources.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : sources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Database className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">No data sources configured</h3>
              <p className="mt-2 text-muted-foreground">
                Get started by adding your first data source connection.
              </p>
              <Button className="mt-4" asChild>
                <Link href="/etl/sources/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Data Source
                </Link>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Connection</TableHead>
                  <TableHead>Last Sync</TableHead>
                  <TableHead>Last Tested</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <SourceRow
                    key={source.id}
                    source={source}
                    onTest={handleTestConnection}
                    onDelete={setDeleteSource}
                    isTesting={testingSourceId === source.id}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        source={deleteSource}
        open={!!deleteSource}
        onOpenChange={(open) => !open && setDeleteSource(null)}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteSourceMutation.isPending}
      />
    </div>
  );
}
