"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
  getQueueStats,
  getQueueDepth,
  getProcessingRate,
  getWorkers,
  QueueStats,
  QueueDepthPoint,
  ProcessingRate,
  WorkerStatus,
} from "@/lib/api";

const WORKER_STATE_COLORS: Record<string, string> = {
  idle: "bg-green-500",
  busy: "bg-blue-500",
  offline: "bg-gray-500",
  draining: "bg-yellow-500",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "#94a3b8",
  normal: "#3b82f6",
  high: "#f59e0b",
  critical: "#ef4444",
};

const CHART_COLORS = {
  pending: "#f59e0b",
  running: "#3b82f6",
  completed: "#22c55e",
  failed: "#ef4444",
};

export default function JobQueueVisualizationPage() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [depthHistory, setDepthHistory] = useState<QueueDepthPoint[]>([]);
  const [processingRate, setProcessingRate] = useState<ProcessingRate | null>(null);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState(5000);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, depthData, rateData, workersData] = await Promise.all([
        getQueueStats(),
        getQueueDepth(24),
        getProcessingRate(),
        getWorkers(),
      ]);

      setStats(statsData);
      setDepthHistory(depthData.history);
      setProcessingRate(rateData);
      setWorkers(workersData.workers);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch queue data:", err);
      setError("Failed to fetch queue data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchData, refreshInterval]);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  // Prepare priority pie chart data
  const priorityData = stats
    ? Object.entries(stats.by_priority).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
        color: PRIORITY_COLORS[name] || "#6b7280",
      }))
    : [];

  // Sample depth data for chart (reduce to last 48 points for readability)
  const chartDepthData = depthHistory.slice(-48).map((point) => ({
    ...point,
    time: formatTimestamp(point.timestamp),
  }));

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Home
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Job Queue Visualization
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <Link href="/jobs">
                <Button variant="outline">View All Jobs</Button>
              </Link>
              <select
                className="rounded-md border bg-white px-3 py-2 text-sm dark:bg-zinc-800 dark:border-zinc-700"
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
              >
                <option value={5000}>Refresh: 5s</option>
                <option value={10000}>Refresh: 10s</option>
                <option value={30000}>Refresh: 30s</option>
                <option value={60000}>Refresh: 1m</option>
              </select>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        <div className="mb-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Pending</CardDescription>
              <CardTitle className="text-3xl text-amber-600">
                {stats ? stats.pending_count + stats.queued_count : 0}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-zinc-500">
                Oldest: {stats ? formatDuration(stats.oldest_pending_job_age_seconds) : "N/A"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Running</CardDescription>
              <CardTitle className="text-3xl text-blue-600">
                {stats?.running_count || 0}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-zinc-500">
                {workers.filter((w) => w.state === "busy").length} workers busy
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed (24h)</CardDescription>
              <CardTitle className="text-3xl text-green-600">
                {stats?.completed_count || 0}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-zinc-500">
                {processingRate ? `${processingRate.success_rate}% success rate` : "N/A"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Failed</CardDescription>
              <CardTitle className="text-3xl text-red-600">
                {stats?.failed_count || 0}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-zinc-500">
                {processingRate ? `${processingRate.error_rate}% error rate` : "N/A"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Processing Rate & Estimated Wait */}
        <div className="mb-8 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Processing Rate</CardTitle>
              <CardDescription>Current throughput metrics</CardDescription>
            </CardHeader>
            <CardContent>
              {processingRate && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-500">Jobs/minute</span>
                    <span className="text-lg font-semibold">
                      {processingRate.jobs_per_minute.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-500">Jobs/hour</span>
                    <span className="text-lg font-semibold">
                      {processingRate.jobs_per_hour}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-500">Avg duration</span>
                    <span className="text-lg font-semibold">
                      {formatDuration(processingRate.avg_duration_seconds)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-500">Trend</span>
                    <Badge
                      className={
                        processingRate.trend === "increasing"
                          ? "bg-amber-500"
                          : processingRate.trend === "decreasing"
                            ? "bg-green-500"
                            : "bg-blue-500"
                      }
                    >
                      {processingRate.trend}
                    </Badge>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Estimated Wait Time</CardTitle>
              <CardDescription>Based on current queue depth and throughput</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500">Avg wait time</span>
                  <span className="text-lg font-semibold">
                    {stats ? formatDuration(stats.avg_wait_time_seconds) : "N/A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500">Avg processing time</span>
                  <span className="text-lg font-semibold">
                    {stats ? formatDuration(stats.avg_processing_time_seconds) : "N/A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500">Throughput</span>
                  <span className="text-lg font-semibold">
                    {stats ? `${stats.throughput_per_minute.toFixed(2)}/min` : "N/A"}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Queue Depth Chart */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Queue Depth Over Time</CardTitle>
            <CardDescription>Jobs by status over the last 24 hours</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartDepthData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="pending"
                    name="Pending"
                    stackId="1"
                    stroke={CHART_COLORS.pending}
                    fill={CHART_COLORS.pending}
                    fillOpacity={0.6}
                  />
                  <Area
                    type="monotone"
                    dataKey="running"
                    name="Running"
                    stackId="1"
                    stroke={CHART_COLORS.running}
                    fill={CHART_COLORS.running}
                    fillOpacity={0.6}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Processing Rate Chart & Priority Breakdown */}
        <div className="mb-8 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Job Completion Trend</CardTitle>
              <CardDescription>Completed vs failed jobs over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDepthData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="time"
                      tick={{ fontSize: 12 }}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="completed"
                      name="Completed"
                      stroke={CHART_COLORS.completed}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="failed"
                      name="Failed"
                      stroke={CHART_COLORS.failed}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Priority Breakdown</CardTitle>
              <CardDescription>Jobs by priority level</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={priorityData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, percent }) =>
                        `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                      }
                    >
                      {priorityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Worker Status Table */}
        <Card>
          <CardHeader>
            <CardTitle>Worker Status</CardTitle>
            <CardDescription>Status of all queue workers</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current Job</TableHead>
                  <TableHead className="text-right">Completed</TableHead>
                  <TableHead className="text-right">Avg Time</TableHead>
                  <TableHead className="text-right">CPU</TableHead>
                  <TableHead className="text-right">Memory</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {workers.map((worker) => (
                  <TableRow key={worker.worker_id}>
                    <TableCell className="font-medium">{worker.name}</TableCell>
                    <TableCell>
                      <Badge
                        className={
                          WORKER_STATE_COLORS[worker.state] || "bg-gray-500"
                        }
                      >
                        {worker.state.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {worker.current_job_id ? (
                        <div className="flex flex-col">
                          <code className="text-xs">{worker.current_job_id.slice(0, 12)}...</code>
                          <span className="text-xs text-zinc-500">
                            {worker.current_job_type}
                          </span>
                        </div>
                      ) : (
                        <span className="text-zinc-400">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {worker.jobs_completed}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatDuration(worker.avg_processing_time_seconds)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Progress
                          value={worker.cpu_usage_percent}
                          className="w-16 h-2"
                        />
                        <span className="text-xs w-10">
                          {worker.cpu_usage_percent.toFixed(0)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {worker.memory_usage_mb.toFixed(0)} MB
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
