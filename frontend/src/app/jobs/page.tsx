"use client";

import { useEffect, useState, useCallback } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
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
import {
  getQueueJobs,
  getQueueStats,
  retryAllFailedJobs,
  cancelSelectedJobs,
  retryQueueJob,
  cancelQueueJob,
  QueueJob,
  QueueStats,
  QueueJobStatus,
  JobPriority,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500",
  queued: "bg-yellow-400",
  running: "bg-blue-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
  cancelled: "bg-gray-500",
  retrying: "bg-orange-500",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-slate-400",
  normal: "bg-blue-400",
  high: "bg-amber-500",
  critical: "bg-red-600",
};

export default function JobsListPage() {
  const [jobs, setJobs] = useState<QueueJob[]>([]);
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<QueueJobStatus | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState<JobPriority | "all">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (statusFilter !== "all") params.status = statusFilter;
      if (priorityFilter !== "all") params.priority = priorityFilter;
      if (typeFilter !== "all") params.job_type = typeFilter;

      const [jobsData, statsData] = await Promise.all([
        getQueueJobs(params as Parameters<typeof getQueueJobs>[0]),
        getQueueStats(),
      ]);

      setJobs(jobsData.jobs);
      setTotal(jobsData.total);
      setStats(statsData);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
      setError("Failed to fetch jobs. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, priorityFilter, typeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSelectJob = (jobId: string, checked: boolean) => {
    const newSelected = new Set(selectedJobs);
    if (checked) {
      newSelected.add(jobId);
    } else {
      newSelected.delete(jobId);
    }
    setSelectedJobs(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedJobs(new Set(jobs.map((j) => j.id)));
    } else {
      setSelectedJobs(new Set());
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      setActionLoading(true);
      await retryQueueJob(jobId);
      await fetchData();
    } catch (err) {
      console.error("Failed to retry job:", err);
      setError("Failed to retry job");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      setActionLoading(true);
      await cancelQueueJob(jobId);
      await fetchData();
    } catch (err) {
      console.error("Failed to cancel job:", err);
      setError("Failed to cancel job");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetryAllFailed = async () => {
    try {
      setActionLoading(true);
      await retryAllFailedJobs();
      await fetchData();
    } catch (err) {
      console.error("Failed to retry all failed jobs:", err);
      setError("Failed to retry all failed jobs");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelSelected = async () => {
    if (selectedJobs.size === 0) return;

    try {
      setActionLoading(true);
      await cancelSelectedJobs(Array.from(selectedJobs));
      setSelectedJobs(new Set());
      await fetchData();
    } catch (err) {
      console.error("Failed to cancel selected jobs:", err);
      setError("Failed to cancel selected jobs");
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const jobTypes = stats ? Object.keys(stats.by_type) : [];
  const totalPages = Math.ceil(total / pageSize);

  const canRetry = (job: QueueJob) =>
    (job.status === "failed" || job.status === "cancelled") &&
    job.retry_count < job.max_retries;

  const canCancel = (job: QueueJob) =>
    job.status === "pending" || job.status === "queued" || job.status === "running";

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
                Jobs
              </h1>
            </div>
            <Link href="/jobs/queue">
              <Button variant="outline">Queue Visualization</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Quick Stats Row */}
        <div className="mb-6 grid gap-4 md:grid-cols-5">
          <Card className="bg-amber-50 dark:bg-amber-900/20">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-amber-600">
                {stats ? stats.pending_count + stats.queued_count : 0}
              </div>
              <p className="text-sm text-amber-700 dark:text-amber-400">Pending</p>
            </CardContent>
          </Card>
          <Card className="bg-blue-50 dark:bg-blue-900/20">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-blue-600">
                {stats?.running_count || 0}
              </div>
              <p className="text-sm text-blue-700 dark:text-blue-400">Running</p>
            </CardContent>
          </Card>
          <Card className="bg-green-50 dark:bg-green-900/20">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">
                {stats?.completed_count || 0}
              </div>
              <p className="text-sm text-green-700 dark:text-green-400">Completed</p>
            </CardContent>
          </Card>
          <Card className="bg-red-50 dark:bg-red-900/20">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-red-600">
                {stats?.failed_count || 0}
              </div>
              <p className="text-sm text-red-700 dark:text-red-400">Failed</p>
            </CardContent>
          </Card>
          <Card className="bg-zinc-100 dark:bg-zinc-800">
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-zinc-600 dark:text-zinc-300">
                {stats?.total_count || 0}
              </div>
              <p className="text-sm text-zinc-500">Total</p>
            </CardContent>
          </Card>
        </div>

        {/* Filters and Actions */}
        <Card className="mb-6">
          <CardContent className="pt-4">
            <div className="flex flex-wrap items-center gap-4">
              {/* Filters */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-zinc-500">Status:</span>
                <Select
                  value={statusFilter}
                  onValueChange={(v) => {
                    setStatusFilter(v as QueueJobStatus | "all");
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="queued">Queued</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm text-zinc-500">Priority:</span>
                <Select
                  value={priorityFilter}
                  onValueChange={(v) => {
                    setPriorityFilter(v as JobPriority | "all");
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm text-zinc-500">Type:</span>
                <Select
                  value={typeFilter}
                  onValueChange={(v) => {
                    setTypeFilter(v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    {jobTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex-1" />

              {/* Bulk Actions */}
              <div className="flex items-center gap-2">
                {selectedJobs.size > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleCancelSelected}
                    disabled={actionLoading}
                  >
                    Cancel Selected ({selectedJobs.size})
                  </Button>
                )}
                {(stats?.failed_count ?? 0) > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRetryAllFailed}
                    disabled={actionLoading}
                  >
                    Retry All Failed
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchData}
                  disabled={loading}
                >
                  Refresh
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Jobs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Job List</CardTitle>
            <CardDescription>
              Showing {jobs.length} of {total} jobs
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">
                        <Checkbox
                          checked={
                            selectedJobs.size === jobs.length && jobs.length > 0
                          }
                          onCheckedChange={handleSelectAll}
                        />
                      </TableHead>
                      <TableHead>Job ID</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Retries</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.map((job) => (
                      <TableRow key={job.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedJobs.has(job.id)}
                            onCheckedChange={(checked) =>
                              handleSelectJob(job.id, checked as boolean)
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/jobs/${job.id}`}
                            className="font-mono text-sm text-blue-600 hover:underline"
                          >
                            {job.id.slice(0, 16)}...
                          </Link>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm">{job.job_type}</span>
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={STATUS_COLORS[job.status] || "bg-gray-500"}
                          >
                            {job.status.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`border-0 ${PRIORITY_COLORS[job.priority] || "bg-gray-400"}`}
                          >
                            {job.priority}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-zinc-500">
                          {formatDate(job.created_at)}
                        </TableCell>
                        <TableCell>
                          <span className="text-sm">
                            {job.retry_count}/{job.max_retries}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            {canRetry(job) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRetryJob(job.id)}
                                disabled={actionLoading}
                              >
                                Retry
                              </Button>
                            )}
                            {canCancel(job) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-600"
                                onClick={() => handleCancelJob(job.id)}
                                disabled={actionLoading}
                              >
                                Cancel
                              </Button>
                            )}
                            <Link href={`/jobs/${job.id}`}>
                              <Button variant="ghost" size="sm">
                                View
                              </Button>
                            </Link>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {jobs.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-zinc-500">
                          No jobs found
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-4 flex items-center justify-between">
                    <div className="text-sm text-zinc-500">
                      Page {page} of {totalPages}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
