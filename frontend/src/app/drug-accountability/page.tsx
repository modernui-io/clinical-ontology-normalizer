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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Pill,
  Package,
  RotateCcw,
  AlertTriangle,
  RefreshCw,
  Loader2,
  AlertCircle,
  TrendingUp,
  ShieldAlert,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface DrugAccountabilityMetrics {
  total_dispensations: number;
  dispensations_by_type: Record<string, number>;
  dispensations_by_status: Record<string, number>;
  total_returns: number;
  total_quantity_dispensed: number;
  total_quantity_returned: number;
  total_quantity_destroyed: number;
  total_reconciliations: number;
  reconciliations_with_discrepancy: number;
  total_deviations: number;
  deviations_by_severity: Record<string, number>;
  open_deviations: number;
  destruction_records: number;
}

// ============================================================================
// Badge color helpers
// ============================================================================

function getDispensationTypeBadgeClass(type: string): string {
  switch (type) {
    case "initial":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "refill":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "emergency":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "open_label":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
}

function getSeverityBadgeClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-red-600 text-white";
    case "major":
      return "bg-red-500 text-white";
    case "moderate":
      return "bg-amber-500 text-white";
    case "minor":
      return "bg-blue-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
}

// ============================================================================
// Main Component
// ============================================================================

export default function DrugAccountabilityPage() {
  const [metrics, setMetrics] = useState<DrugAccountabilityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/drug-accountability/metrics");
      if (!response.ok) throw new Error("Failed to fetch drug accountability metrics");
      const data: DrugAccountabilityMetrics = await response.json();
      setMetrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading drug accountability data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Drug Accountability</h1>
          <p className="text-muted-foreground">
            Track dispensations, returns, reconciliations, and deviations
          </p>
        </div>
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <span className="text-red-700 dark:text-red-300">{error}</span>
            <Button variant="outline" size="sm" onClick={loadMetrics} className="ml-auto">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!metrics) return null;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Drug Accountability</h1>
          <p className="text-muted-foreground">
            Track dispensations, returns, reconciliations, and deviations
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadMetrics}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Dispensations</CardTitle>
            <Pill className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_dispensations}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.total_quantity_dispensed} units dispensed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Returns</CardTitle>
            <RotateCcw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_returns}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.total_quantity_returned} units returned, {metrics.total_quantity_destroyed} destroyed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Open Deviations</CardTitle>
            <AlertTriangle className={`h-4 w-4 ${metrics.open_deviations > 0 ? "text-red-500" : "text-muted-foreground"}`} />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${metrics.open_deviations > 0 ? "text-red-600 dark:text-red-400" : ""}`}>
              {metrics.open_deviations}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.total_deviations} total deviations recorded
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Discrepancies</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${metrics.reconciliations_with_discrepancy > 0 ? "text-amber-600 dark:text-amber-400" : ""}`}>
              {metrics.reconciliations_with_discrepancy}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              of {metrics.total_reconciliations} reconciliations
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full max-w-lg grid-cols-4">
          <TabsTrigger value="overview" className="gap-2">
            <TrendingUp className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="dispensations" className="gap-2">
            <Pill className="h-4 w-4" />
            Dispensations
          </TabsTrigger>
          <TabsTrigger value="returns" className="gap-2">
            <Package className="h-4 w-4" />
            Returns
          </TabsTrigger>
          <TabsTrigger value="deviations" className="gap-2">
            <AlertTriangle className="h-4 w-4" />
            Deviations
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Dispensations by Type */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Pill className="h-5 w-5" />
                  Dispensations by Type
                </CardTitle>
                <CardDescription>
                  Breakdown of {metrics.total_dispensations} total dispensations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(metrics.dispensations_by_type).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Badge className={getDispensationTypeBadgeClass(type)}>
                          {type.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-32 bg-muted rounded-full h-2">
                          <div
                            className="bg-primary rounded-full h-2 transition-all"
                            style={{
                              width: `${(count / metrics.total_dispensations) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm font-medium w-8 text-right">{count}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-3">By Status</h4>
                  <div className="space-y-2">
                    {Object.entries(metrics.dispensations_by_status).map(([status, count]) => (
                      <div key={status} className="flex items-center justify-between text-sm">
                        <span className="capitalize text-muted-foreground">{status}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Deviations by Severity */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" />
                  Deviations by Severity
                </CardTitle>
                <CardDescription>
                  {metrics.open_deviations} open of {metrics.total_deviations} total deviations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(metrics.deviations_by_severity)
                    .sort(([a], [b]) => {
                      const order = ["critical", "major", "moderate", "minor"];
                      return order.indexOf(a) - order.indexOf(b);
                    })
                    .map(([severity, count]) => (
                      <div key={severity} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Badge className={getSeverityBadgeClass(severity)}>
                            {severity}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-32 bg-muted rounded-full h-2">
                            <div
                              className="rounded-full h-2 transition-all"
                              style={{
                                width: `${(count / metrics.total_deviations) * 100}%`,
                                backgroundColor:
                                  severity === "critical"
                                    ? "rgb(220, 38, 38)"
                                    : severity === "major"
                                    ? "rgb(239, 68, 68)"
                                    : severity === "moderate"
                                    ? "rgb(245, 158, 11)"
                                    : "rgb(59, 130, 246)",
                              }}
                            />
                          </div>
                          <span className="text-sm font-medium w-8 text-right">{count}</span>
                        </div>
                      </div>
                    ))}
                </div>

                <div className="mt-6 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-3">Inventory Summary</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total quantity dispensed</span>
                      <span className="font-medium">{metrics.total_quantity_dispensed}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total quantity returned</span>
                      <span className="font-medium">{metrics.total_quantity_returned}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total quantity destroyed</span>
                      <span className="font-medium">{metrics.total_quantity_destroyed}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Destruction records</span>
                      <span className="font-medium">{metrics.destruction_records}</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Dispensations Tab */}
        <TabsContent value="dispensations" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pill className="h-5 w-5" />
                Dispensation Records
              </CardTitle>
              <CardDescription>
                Drug dispensation tracking and history
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <Package className="h-12 w-12 mb-3" />
                <p className="text-lg font-medium">{metrics.total_dispensations} records available</p>
                <p className="text-sm mt-1">
                  {metrics.total_quantity_dispensed} total units across{" "}
                  {Object.keys(metrics.dispensations_by_type).length} dispensation types
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Returns Tab */}
        <TabsContent value="returns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RotateCcw className="h-5 w-5" />
                Drug Returns
              </CardTitle>
              <CardDescription>
                Returned drug tracking and destruction records
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <RotateCcw className="h-12 w-12 mb-3" />
                <p className="text-lg font-medium">{metrics.total_returns} records available</p>
                <p className="text-sm mt-1">
                  {metrics.total_quantity_returned} units returned, {metrics.total_quantity_destroyed} units destroyed
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Deviations Tab */}
        <TabsContent value="deviations" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Deviations
              </CardTitle>
              <CardDescription>
                Protocol deviations and compliance issues
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <ShieldAlert className="h-12 w-12 mb-3" />
                <p className="text-lg font-medium">{metrics.total_deviations} records available</p>
                <p className="text-sm mt-1">
                  {metrics.open_deviations > 0 ? (
                    <span className="text-red-600 dark:text-red-400 font-medium">
                      {metrics.open_deviations} open deviations require attention
                    </span>
                  ) : (
                    "All deviations have been resolved"
                  )}
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
