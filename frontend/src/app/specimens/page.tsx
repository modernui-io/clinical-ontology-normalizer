"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  FlaskConical,
  Package,
  Thermometer,
  Truck,
  RefreshCw,
  Loader2,
  AlertCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SpecimenMetrics {
  total_specimens: number;
  in_transit: number;
  processing: number;
  stored: number;
}

interface Specimen {
  id: string;
  trial_id: string;
  subject_id: string;
  site_id: string;
  specimen_type: string;
  collection_status: string;
  visit_number: number;
  collection_date: string | null;
  scheduled_date: string;
  tube_count: number;
  volume_ml: number;
  fasting_required: boolean;
  fasting_confirmed: boolean;
  collection_time_critical: boolean;
  protocol_timepoint: string;
  collected_by: string | null;
  notes: string | null;
  created_at: string;
}

interface ListResponse<T> {
  items: T[];
  total: number;
}

// ---------------------------------------------------------------------------
// Badge color helpers
// ---------------------------------------------------------------------------

const statusColors: Record<string, string> = {
  scheduled: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  collected: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  in_transit: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  received: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  processing: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  stored: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  shipped: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-300",
  destroyed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  lost: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

const specimenTypeColors: Record<string, string> = {
  blood: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  urine: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
  tissue: "bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
  saliva: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  serum: "bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  plasma: "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SpecimenManagementPage() {
  const [metrics, setMetrics] = useState<SpecimenMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const [specimens, setSpecimens] = useState<Specimen[]>([]);
  const [specimensLoading, setSpecimensLoading] = useState(true);
  const [specimensError, setSpecimensError] = useState<string | null>(null);

  // ---- Fetchers ----

  const fetchMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsError(null);
    try {
      const res = await fetch("/api/specimen-management/metrics");
      if (!res.ok) throw new Error(`Failed to fetch metrics (${res.status})`);
      const data: SpecimenMetrics = await res.json();
      setMetrics(data);
    } catch (err) {
      setMetricsError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setMetricsLoading(false);
    }
  }, []);

  const fetchSpecimens = useCallback(async () => {
    setSpecimensLoading(true);
    setSpecimensError(null);
    try {
      const res = await fetch("/api/specimen-management/collection-records");
      if (!res.ok) throw new Error(`Failed to fetch specimens (${res.status})`);
      const data: ListResponse<Specimen> = await res.json();
      setSpecimens(data.items);
    } catch (err) {
      setSpecimensError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSpecimensLoading(false);
    }
  }, []);

  // ---- Initial load ----

  useEffect(() => {
    fetchMetrics();
    fetchSpecimens();
  }, [fetchMetrics, fetchSpecimens]);

  const handleRefresh = () => {
    fetchMetrics();
    fetchSpecimens();
  };

  // ---- Helpers ----

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString();
  }

  function formatDateTime(dateStr: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString();
  }

  function renderLoading(label: string) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading {label}...</span>
      </div>
    );
  }

  function renderError(message: string) {
    return (
      <div className="flex items-center justify-center py-12 text-red-600">
        <AlertCircle className="h-5 w-5 mr-2" />
        <span>{message}</span>
      </div>
    );
  }

  function renderEmpty() {
    return (
      <Card className="border-2 border-dashed">
        <CardContent className="py-12">
          <div className="flex flex-col items-center justify-center text-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-blue-50 dark:bg-blue-950 flex items-center justify-center">
              <FlaskConical className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Specimen tracking coming soon</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Track biological sample collection, processing, storage, and chain of custody.
                Full specimen lifecycle management with temperature monitoring and shipment tracking.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // ---- Render ----

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FlaskConical className="h-6 w-6 text-blue-600" />
            Specimen Management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track biological samples from collection to storage with full chain of custody
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Specimens</CardTitle>
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.total_specimens ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  All collected samples
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">In Transit</CardTitle>
            <Truck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.in_transit ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Being shipped to labs
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Processing</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.processing ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Under analysis
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Stored</CardTitle>
            <Thermometer className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.stored ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  In long-term storage
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Specimens Table */}
      <Card>
        <CardHeader>
          <CardTitle>Specimen Inventory</CardTitle>
          <CardDescription>
            All biological samples collected across trial sites
          </CardDescription>
        </CardHeader>
        <CardContent>
          {specimensLoading ? (
            renderLoading("specimens")
          ) : specimensError ? (
            renderError(specimensError)
          ) : specimens.length === 0 ? (
            renderEmpty()
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Site</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Timepoint</TableHead>
                    <TableHead>Scheduled</TableHead>
                    <TableHead>Collected</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Tubes</TableHead>
                    <TableHead>Volume (mL)</TableHead>
                    <TableHead>Collected By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {specimens.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-mono text-sm">{s.id}</TableCell>
                      <TableCell className="font-mono text-sm">{s.subject_id}</TableCell>
                      <TableCell className="text-sm">{s.site_id}</TableCell>
                      <TableCell>
                        <Badge className={specimenTypeColors[s.specimen_type.toLowerCase()] || "bg-gray-100 text-gray-800"}>
                          {s.specimen_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">{s.protocol_timepoint}</TableCell>
                      <TableCell>{formatDateTime(s.scheduled_date)}</TableCell>
                      <TableCell>{formatDateTime(s.collection_date)}</TableCell>
                      <TableCell>
                        <Badge className={statusColors[s.collection_status?.toLowerCase()] || "bg-gray-100 text-gray-800"}>
                          {(s.collection_status || "unknown").replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">{s.tube_count}</TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {s.volume_ml > 0 ? s.volume_ml.toFixed(1) : "-"}
                      </TableCell>
                      <TableCell className="text-sm">{s.collected_by || "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
