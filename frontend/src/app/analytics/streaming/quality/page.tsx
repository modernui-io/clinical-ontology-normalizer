"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
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
  AlertTriangle,
  ArrowLeft,
  Bug,
  CheckCircle,
  Clock,
  FileWarning,
  Loader2,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  Trash2,
  XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface DataQualityMetric {
  timestamp: string;
  total_messages: number;
  validation_errors: number;
  schema_errors: number;
  transformation_errors: number;
  error_rate: number;
}

interface DeadLetterEntry {
  entry_id: string;
  original_message: {
    message_id: string;
    message_type: string;
    topic: string;
    timestamp: string;
    value: Record<string, unknown>;
  } | null;
  error_message: string;
  error_type: string;
  retry_count: number;
  max_retries: number;
  created_at: string;
  last_retry_at: string | null;
  can_retry: boolean;
}

interface ErrorsResponse {
  errors: DeadLetterEntry[];
  total_errors: number;
  error_rate: number;
}

// =============================================================================
// Mock Data
// =============================================================================

function generateMockQualityMetrics(): DataQualityMetric[] {
  const now = Date.now();
  return Array.from({ length: 60 }, (_, i) => {
    const timestamp = new Date(now - (60 - i) * 60000);
    const totalMessages = Math.floor(2000 + Math.random() * 1000);
    const validationErrors = Math.floor(Math.random() * 30);
    const schemaErrors = Math.floor(Math.random() * 10);
    const transformationErrors = Math.floor(Math.random() * 15);

    return {
      timestamp: timestamp.toISOString(),
      total_messages: totalMessages,
      validation_errors: validationErrors,
      schema_errors: schemaErrors,
      transformation_errors: transformationErrors,
      error_rate:
        ((validationErrors + schemaErrors + transformationErrors) /
          totalMessages) *
        100,
    };
  });
}

function generateMockDeadLetterEntries(): DeadLetterEntry[] {
  const errorTypes = [
    { type: "validation_error", message: "Required field 'patient_id' is missing" },
    { type: "schema_error", message: "Invalid field type for 'birth_date': expected date, got string" },
    { type: "transformation_error", message: "Failed to map ICD-10 code 'X99.9' to OMOP concept" },
    { type: "parse_error", message: "Invalid HL7v2 message structure: missing MSH segment" },
    { type: "serialization_error", message: "Failed to deserialize Avro message: schema mismatch" },
  ];

  const topics = [
    "clinical.hl7v2.inbound",
    "clinical.fhir.inbound",
    "clinical.documents.processed",
  ];

  const now = Date.now();
  return Array.from({ length: 12 }, (_, i) => {
    const errorConfig = errorTypes[i % errorTypes.length];
    const topic = topics[i % topics.length];
    const createdAt = new Date(now - i * 120000 - Math.random() * 60000);
    const retryCount = Math.floor(Math.random() * 3);

    return {
      entry_id: `dlq-${i + 1}-${Date.now()}`,
      original_message: {
        message_id: `msg-${i + 1}`,
        message_type: topic.includes("hl7") ? "hl7v2_message" : "fhir_resource",
        topic,
        timestamp: createdAt.toISOString(),
        value: {
          sample_field: "sample_value",
          error_trigger: i,
        },
      },
      error_message: errorConfig.message,
      error_type: errorConfig.type,
      retry_count: retryCount,
      max_retries: 3,
      created_at: createdAt.toISOString(),
      last_retry_at: retryCount > 0 ? new Date(createdAt.getTime() + 30000).toISOString() : null,
      can_retry: retryCount < 3,
    };
  });
}

// =============================================================================
// Components
// =============================================================================

function ErrorTypeBadge({ errorType }: { errorType: string }) {
  switch (errorType) {
    case "validation_error":
      return (
        <Badge variant="secondary" className="gap-1">
          <AlertTriangle className="h-3 w-3" />
          Validation
        </Badge>
      );
    case "schema_error":
      return (
        <Badge variant="destructive" className="gap-1">
          <ShieldAlert className="h-3 w-3" />
          Schema
        </Badge>
      );
    case "transformation_error":
      return (
        <Badge variant="outline" className="gap-1">
          <Bug className="h-3 w-3" />
          Transform
        </Badge>
      );
    case "parse_error":
      return (
        <Badge variant="secondary" className="gap-1">
          <FileWarning className="h-3 w-3" />
          Parse
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          {errorType}
        </Badge>
      );
  }
}

function QualityTrendChart({ metrics }: { metrics: DataQualityMetric[] }) {
  const maxErrorRate = Math.max(...metrics.map((m) => m.error_rate), 5);
  const chartHeight = 100;

  return (
    <div className="relative h-[100px] w-full">
      <svg className="w-full h-full" preserveAspectRatio="none">
        {/* Warning threshold line */}
        <line
          x1="0"
          y1={chartHeight - (5 / maxErrorRate) * chartHeight}
          x2="100%"
          y2={chartHeight - (5 / maxErrorRate) * chartHeight}
          stroke="hsl(var(--destructive))"
          strokeDasharray="4 4"
          strokeOpacity="0.5"
        />

        {/* Area chart */}
        <defs>
          <linearGradient id="errorRateGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--destructive))" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(var(--destructive))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d={`M 0 ${chartHeight} ${metrics
            .map(
              (m, i) =>
                `L ${(i / (metrics.length - 1)) * 100}% ${
                  chartHeight - (m.error_rate / maxErrorRate) * chartHeight
                }`
            )
            .join(" ")} L 100% ${chartHeight} Z`}
          fill="url(#errorRateGradient)"
        />
        <path
          d={`M 0 ${chartHeight - (metrics[0]?.error_rate || 0) / maxErrorRate * chartHeight} ${metrics
            .map(
              (m, i) =>
                `L ${(i / (metrics.length - 1)) * 100}% ${
                  chartHeight - (m.error_rate / maxErrorRate) * chartHeight
                }`
            )
            .join(" ")}`}
          fill="none"
          stroke="hsl(var(--destructive))"
          strokeWidth="2"
        />
      </svg>

      {/* Labels */}
      <div className="absolute left-0 top-0 text-[10px] text-muted-foreground">
        {maxErrorRate.toFixed(1)}%
      </div>
      <div className="absolute left-0 bottom-0 text-[10px] text-muted-foreground">
        0%
      </div>
      <div className="absolute right-2 top-[calc(100%-5/var(--maxErr)*100%)] text-[10px] text-destructive">
        5% threshold
      </div>
    </div>
  );
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function StreamingQualityPage() {
  const [qualityMetrics, setQualityMetrics] = useState<DataQualityMetric[]>([]);
  const [deadLetterEntries, setDeadLetterEntries] = useState<DeadLetterEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState<string | null>(null);
  const [currentErrorRate, setCurrentErrorRate] = useState(0);
  const [totalErrors, setTotalErrors] = useState(0);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [metricsRes, errorsRes] = await Promise.all([
        fetch("/api/streaming/metrics?minutes=60"),
        fetch("/api/streaming/errors?limit=50"),
      ]);

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setQualityMetrics(metricsData.quality?.history || []);
        setCurrentErrorRate(metricsData.quality?.error_rate_1min || 0);
      } else {
        // Use mock data
        const mockMetrics = generateMockQualityMetrics();
        setQualityMetrics(mockMetrics);
        setCurrentErrorRate(mockMetrics[mockMetrics.length - 1]?.error_rate || 0);
      }

      if (errorsRes.ok) {
        const errorsData: ErrorsResponse = await errorsRes.json();
        setDeadLetterEntries(errorsData.errors);
        setTotalErrors(errorsData.total_errors);
      } else {
        // Use mock data
        const mockErrors = generateMockDeadLetterEntries();
        setDeadLetterEntries(mockErrors);
        setTotalErrors(mockErrors.length);
      }
    } catch (error) {
      console.error("Failed to fetch quality data:", error);
      // Use mock data
      const mockMetrics = generateMockQualityMetrics();
      const mockErrors = generateMockDeadLetterEntries();
      setQualityMetrics(mockMetrics);
      setDeadLetterEntries(mockErrors);
      setCurrentErrorRate(mockMetrics[mockMetrics.length - 1]?.error_rate || 0);
      setTotalErrors(mockErrors.length);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Retry a dead letter entry
  const retryEntry = async (entryId: string) => {
    setIsRetrying(entryId);
    try {
      const response = await fetch(
        `/api/streaming/errors/${entryId}/retry`,
        { method: "POST" }
      );

      if (response.ok) {
        // Remove from list
        setDeadLetterEntries((prev) =>
          prev.filter((e) => e.entry_id !== entryId)
        );
        setTotalErrors((prev) => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error("Failed to retry entry:", error);
      // Update locally for demo
      setDeadLetterEntries((prev) =>
        prev.map((e) =>
          e.entry_id === entryId
            ? { ...e, retry_count: e.retry_count + 1, can_retry: e.retry_count + 1 < e.max_retries }
            : e
        )
      );
    } finally {
      setIsRetrying(null);
    }
  };

  // Calculate error breakdown from metrics
  const errorBreakdown = qualityMetrics.length > 0 ? {
    validation: qualityMetrics.reduce((sum, m) => sum + m.validation_errors, 0),
    schema: qualityMetrics.reduce((sum, m) => sum + m.schema_errors, 0),
    transformation: qualityMetrics.reduce((sum, m) => sum + m.transformation_errors, 0),
    total: qualityMetrics.reduce(
      (sum, m) => sum + m.validation_errors + m.schema_errors + m.transformation_errors,
      0
    ),
  } : { validation: 42, schema: 15, transformation: 28, total: 85 };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link href="/analytics/streaming">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold tracking-tight">
              Data Quality Monitor
            </h1>
          </div>
          <p className="text-muted-foreground">
            Track validation errors, schema drift, and retry queue status
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={isLoading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        {/* Current Error Rate */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Error Rate (1min)</CardTitle>
            {currentErrorRate > 5 ? (
              <AlertCircle className="h-4 w-4 text-destructive" />
            ) : (
              <CheckCircle className="h-4 w-4 text-green-500" />
            )}
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                currentErrorRate > 5 ? "text-destructive" : ""
              }`}
            >
              {currentErrorRate.toFixed(2)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {currentErrorRate <= 5 ? "Within threshold" : "Above 5% threshold"}
            </p>
          </CardContent>
        </Card>

        {/* Dead Letter Queue */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Dead Letter Queue</CardTitle>
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalErrors}</div>
            <p className="text-xs text-muted-foreground">Failed messages</p>
          </CardContent>
        </Card>

        {/* Validation Errors */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Validation Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{errorBreakdown.validation}</div>
            <p className="text-xs text-muted-foreground">In last hour</p>
          </CardContent>
        </Card>

        {/* Schema Errors */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Schema Errors</CardTitle>
            <ShieldAlert className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{errorBreakdown.schema}</div>
            <p className="text-xs text-muted-foreground">In last hour</p>
          </CardContent>
        </Card>
      </div>

      {/* Error Rate Trend */}
      <Card>
        <CardHeader>
          <CardTitle>Error Rate Trend</CardTitle>
          <CardDescription>
            Error rate over the last 60 minutes
          </CardDescription>
        </CardHeader>
        <CardContent>
          {qualityMetrics.length > 0 ? (
            <>
              <QualityTrendChart metrics={qualityMetrics} />
              <div className="flex items-center justify-between mt-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Current: </span>
                  <span
                    className={`font-medium ${
                      currentErrorRate > 5 ? "text-destructive" : ""
                    }`}
                  >
                    {currentErrorRate.toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-destructive/50" />
                  <span className="text-muted-foreground">
                    5% warning threshold
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-[100px]">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Breakdown */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Error Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Error Distribution</CardTitle>
            <CardDescription>Breakdown by error type</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Validation Errors */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  Validation Errors
                </span>
                <span className="font-medium">{errorBreakdown.validation}</span>
              </div>
              <Progress
                value={
                  errorBreakdown.total > 0
                    ? (errorBreakdown.validation / errorBreakdown.total) * 100
                    : 0
                }
                className="h-2"
              />
            </div>

            {/* Schema Errors */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-destructive" />
                  Schema Errors
                </span>
                <span className="font-medium">{errorBreakdown.schema}</span>
              </div>
              <Progress
                value={
                  errorBreakdown.total > 0
                    ? (errorBreakdown.schema / errorBreakdown.total) * 100
                    : 0
                }
                className="h-2 [&>div]:bg-destructive"
              />
            </div>

            {/* Transformation Errors */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <Bug className="h-4 w-4 text-blue-500" />
                  Transformation Errors
                </span>
                <span className="font-medium">{errorBreakdown.transformation}</span>
              </div>
              <Progress
                value={
                  errorBreakdown.total > 0
                    ? (errorBreakdown.transformation / errorBreakdown.total) * 100
                    : 0
                }
                className="h-2 [&>div]:bg-blue-500"
              />
            </div>

            <div className="pt-2 border-t">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Total Errors</span>
                <span className="font-bold">{errorBreakdown.total}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Retry Queue Status */}
        <Card>
          <CardHeader>
            <CardTitle>Retry Queue Status</CardTitle>
            <CardDescription>Messages awaiting retry</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Queue stats */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xl font-bold">
                    {deadLetterEntries.filter((e) => e.can_retry).length}
                  </p>
                  <p className="text-xs text-muted-foreground">Can Retry</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xl font-bold">
                    {deadLetterEntries.filter((e) => e.retry_count > 0).length}
                  </p>
                  <p className="text-xs text-muted-foreground">Retried</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xl font-bold">
                    {deadLetterEntries.filter((e) => !e.can_retry).length}
                  </p>
                  <p className="text-xs text-muted-foreground">Max Retries</p>
                </div>
              </div>

              {/* Top error types */}
              <div className="space-y-2">
                <p className="text-sm font-medium">Top Error Types</p>
                {["validation_error", "schema_error", "transformation_error"].map(
                  (errorType) => {
                    const count = deadLetterEntries.filter(
                      (e) => e.error_type === errorType
                    ).length;
                    return (
                      <div
                        key={errorType}
                        className="flex items-center justify-between text-sm"
                      >
                        <ErrorTypeBadge errorType={errorType} />
                        <span className="text-muted-foreground">{count}</span>
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dead Letter Queue Table */}
      <Card>
        <CardHeader>
          <CardTitle>Failed Messages</CardTitle>
          <CardDescription>
            Sample of failed messages in the dead letter queue
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : deadLetterEntries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <CheckCircle className="h-12 w-12 text-green-500/50" />
              <p className="mt-4 text-lg font-medium">No failed messages</p>
              <p className="text-sm text-muted-foreground">
                The dead letter queue is empty
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Type</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="w-[120px]">Topic</TableHead>
                  <TableHead className="w-[80px]">Retries</TableHead>
                  <TableHead className="w-[100px]">Time</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deadLetterEntries.slice(0, 10).map((entry) => (
                  <TableRow key={entry.entry_id}>
                    <TableCell>
                      <ErrorTypeBadge errorType={entry.error_type} />
                    </TableCell>
                    <TableCell>
                      <p className="text-sm line-clamp-2">{entry.error_message}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        ID: {entry.entry_id.slice(0, 12)}...
                      </p>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {entry.original_message?.topic?.split(".").pop() || "unknown"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          entry.retry_count >= entry.max_retries
                            ? "destructive"
                            : "outline"
                        }
                      >
                        {entry.retry_count}/{entry.max_retries}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelativeTime(entry.created_at)}
                    </TableCell>
                    <TableCell>
                      {entry.can_retry ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => retryEntry(entry.entry_id)}
                          disabled={isRetrying === entry.entry_id}
                        >
                          {isRetrying === entry.entry_id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RotateCw className="h-4 w-4" />
                          )}
                        </Button>
                      ) : (
                        <XCircle className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Schema Drift Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Schema Drift Detection</CardTitle>
          <CardDescription>
            Recent schema changes and drift alerts
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              {
                topic: "clinical.fhir.inbound",
                field: "patient.identifier",
                change: "New field added",
                severity: "info",
                time: "2 hours ago",
              },
              {
                topic: "clinical.hl7v2.inbound",
                field: "PID.3",
                change: "Field type changed: string -> array",
                severity: "warning",
                time: "5 hours ago",
              },
              {
                topic: "clinical.omop.outbound",
                field: "condition_occurrence.condition_source_value",
                change: "Max length increased from 50 to 100",
                severity: "info",
                time: "1 day ago",
              },
            ].map((drift, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg border"
              >
                <div className="mt-0.5">
                  {drift.severity === "warning" ? (
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  ) : (
                    <Clock className="h-4 w-4 text-blue-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm">{drift.topic}</p>
                    <Badge variant="outline" className="text-[10px]">
                      {drift.field}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{drift.change}</p>
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {drift.time}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
