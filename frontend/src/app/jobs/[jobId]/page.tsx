"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getJobStatus,
  getJobEstimate,
  getRetryHistory,
  retryQueueJob,
  cancelQueueJob,
  JobInfo,
  JobEstimate,
  RetryHistoryResponse,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500",
  queued: "bg-yellow-400",
  running: "bg-blue-500",
  processing: "bg-blue-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
  cancelled: "bg-gray-500",
  retrying: "bg-orange-500",
};

const STATUS_PROGRESS: Record<string, number> = {
  pending: 5,
  queued: 10,
  running: 50,
  processing: 50,
  completed: 100,
  failed: 100,
  cancelled: 100,
};

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<JobInfo | null>(null);
  const [estimate, setEstimate] = useState<JobEstimate | null>(null);
  const [retryHistory, setRetryHistory] = useState<RetryHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("details");

  const fetchJobData = useCallback(async () => {
    try {
      const [statusData, estimateData] = await Promise.all([
        getJobStatus(jobId),
        getJobEstimate(jobId).catch(() => null),
      ]);

      setJob(statusData);
      setEstimate(estimateData);
      setError(null);

      // Stop polling if job is completed, failed, or cancelled
      if (
        statusData.status === "completed" ||
        statusData.status === "failed" ||
        statusData.status === "cancelled"
      ) {
        setPolling(false);
      }
    } catch (err) {
      console.error("Failed to fetch job status:", err);
      setError("Failed to fetch job status. Is the backend running?");
      setPolling(false);
    }
  }, [jobId]);

  const fetchRetryHistory = useCallback(async () => {
    try {
      const historyData = await getRetryHistory(jobId);
      setRetryHistory(historyData);
    } catch (err) {
      console.error("Failed to fetch retry history:", err);
      // Don't set error here, retry history is optional
    }
  }, [jobId]);

  useEffect(() => {
    fetchJobData();
    fetchRetryHistory();

    if (polling) {
      const interval = setInterval(fetchJobData, 2000);
      return () => clearInterval(interval);
    }
  }, [fetchJobData, fetchRetryHistory, polling]);

  const handleRetry = async () => {
    try {
      setActionLoading(true);
      await retryQueueJob(jobId);
      setPolling(true);
      await fetchJobData();
      await fetchRetryHistory();
    } catch (err) {
      console.error("Failed to retry job:", err);
      setError("Failed to retry job");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    try {
      setActionLoading(true);
      await cancelQueueJob(jobId);
      await fetchJobData();
    } catch (err) {
      console.error("Failed to cancel job:", err);
      setError("Failed to cancel job");
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const formatDuration = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined) return "-";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  };

  const canRetry = job?.status === "failed" || job?.status === "cancelled";
  const canCancel =
    job?.status === "pending" ||
    job?.status === "queued" ||
    job?.status === "running" ||
    job?.status === "processing";

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/jobs"
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Jobs
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Job Details
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {canRetry && (
                <Button
                  onClick={handleRetry}
                  disabled={actionLoading}
                  variant="outline"
                >
                  Retry Job
                </Button>
              )}
              {canCancel && (
                <Button
                  onClick={handleCancel}
                  disabled={actionLoading}
                  variant="destructive"
                >
                  Cancel Job
                </Button>
              )}
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

        <div className="mx-auto max-w-4xl">
          {/* Job Summary Card */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Job Summary</span>
                {job && (
                  <Badge className={STATUS_COLORS[job.status] || "bg-gray-500"}>
                    {job.status.toUpperCase()}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Job ID: <code className="text-xs font-mono">{jobId}</code>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {!job ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
                </div>
              ) : (
                <>
                  {/* Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Progress</span>
                      <span>{STATUS_PROGRESS[job.status] || 0}%</span>
                    </div>
                    <Progress value={STATUS_PROGRESS[job.status] || 0} />
                  </div>

                  {/* Position in Queue */}
                  {estimate?.position_in_queue && (
                    <div className="rounded-lg bg-amber-50 p-4 dark:bg-amber-900/20">
                      <h3 className="font-semibold text-amber-800 dark:text-amber-200">
                        Position in Queue: #{estimate.position_in_queue}
                      </h3>
                      {estimate.estimated_wait_seconds && (
                        <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
                          Estimated wait time: {formatDuration(estimate.estimated_wait_seconds)}
                        </p>
                      )}
                      {estimate.estimated_completion && (
                        <p className="text-sm text-amber-700 dark:text-amber-300">
                          Expected start: {formatDate(estimate.estimated_completion)}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Running Status */}
                  {(job.status === "running" || job.status === "processing") && (
                    <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
                      <h3 className="font-semibold text-blue-800 dark:text-blue-200">
                        Processing...
                      </h3>
                      {estimate?.elapsed_seconds !== undefined && (
                        <p className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                          Elapsed: {formatDuration(estimate.elapsed_seconds)}
                        </p>
                      )}
                      {estimate?.estimated_remaining_seconds !== undefined && (
                        <p className="text-sm text-blue-700 dark:text-blue-300">
                          Estimated remaining: {formatDuration(estimate.estimated_remaining_seconds)}
                        </p>
                      )}
                      <p className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                        This page will update automatically.
                      </p>
                    </div>
                  )}

                  {/* Completed Status */}
                  {job.status === "completed" && job.result && (
                    <div className="space-y-4">
                      <div className="rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
                        <h3 className="font-semibold text-green-800 dark:text-green-200">
                          Processing Complete
                        </h3>
                        <p className="mt-2 text-sm text-green-700 dark:text-green-300">
                          Extracted{" "}
                          {(job.result as Record<string, number>).mention_count || 0} mentions
                          with{" "}
                          {(job.result as Record<string, number>).candidate_count || 0} concept
                          candidates.
                        </p>
                      </div>

                      <div className="flex gap-4">
                        {(job.result as Record<string, string>).document_id && (
                          <Link
                            href={`/documents/${(job.result as Record<string, string>).document_id}`}
                          >
                            <Button>View Document</Button>
                          </Link>
                        )}
                        {(job.result as Record<string, string>).patient_id && (
                          <Link
                            href={`/patients/${(job.result as Record<string, string>).patient_id}/graph`}
                          >
                            <Button variant="outline">View Patient Graph</Button>
                          </Link>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Failed Status */}
                  {job.status === "failed" && (
                    <div className="rounded-lg bg-red-50 p-4 dark:bg-red-900/20">
                      <h3 className="font-semibold text-red-800 dark:text-red-200">
                        Processing Failed
                      </h3>
                      <p className="mt-2 text-sm text-red-700 dark:text-red-300">
                        {job.error || "Unknown error occurred"}
                      </p>
                      {retryHistory && retryHistory.retry_count < retryHistory.max_retries && (
                        <p className="mt-2 text-sm text-red-700 dark:text-red-300">
                          Retries: {retryHistory.retry_count}/{retryHistory.max_retries}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Cancelled Status */}
                  {job.status === "cancelled" && (
                    <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-800">
                      <h3 className="font-semibold text-gray-800 dark:text-gray-200">
                        Job Cancelled
                      </h3>
                      <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                        This job was cancelled and will not be processed.
                      </p>
                    </div>
                  )}

                  {/* Pending/Queued Status */}
                  {(job.status === "pending" || job.status === "queued") && !estimate?.position_in_queue && (
                    <div className="rounded-lg bg-yellow-50 p-4 dark:bg-yellow-900/20">
                      <h3 className="font-semibold text-yellow-800 dark:text-yellow-200">
                        Waiting in Queue
                      </h3>
                      <p className="mt-2 text-sm text-yellow-700 dark:text-yellow-300">
                        Your job is queued for processing. This page will update automatically.
                      </p>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Tabs for Details and Retry History */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="retry-history">
                Retry History{" "}
                {retryHistory && retryHistory.attempts.length > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {retryHistory.attempts.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="details">
              <Card>
                <CardHeader>
                  <CardTitle>Job Details</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <dt className="text-sm font-medium text-zinc-500">Status</dt>
                      <dd className="mt-1">
                        {job && (
                          <Badge className={STATUS_COLORS[job.status] || "bg-gray-500"}>
                            {job.status.toUpperCase()}
                          </Badge>
                        )}
                      </dd>
                    </div>
                    {estimate?.position_in_queue && (
                      <div>
                        <dt className="text-sm font-medium text-zinc-500">
                          Position in Queue
                        </dt>
                        <dd className="mt-1 text-lg font-semibold">
                          #{estimate.position_in_queue}
                        </dd>
                      </div>
                    )}
                    {estimate?.elapsed_seconds !== undefined && estimate.elapsed_seconds !== null && (
                      <div>
                        <dt className="text-sm font-medium text-zinc-500">
                          Elapsed Time
                        </dt>
                        <dd className="mt-1">
                          {formatDuration(estimate.elapsed_seconds)}
                        </dd>
                      </div>
                    )}
                    {estimate?.estimated_remaining_seconds !== undefined &&
                      estimate.estimated_remaining_seconds !== null && (
                        <div>
                          <dt className="text-sm font-medium text-zinc-500">
                            Estimated Remaining
                          </dt>
                          <dd className="mt-1">
                            {formatDuration(estimate.estimated_remaining_seconds)}
                          </dd>
                        </div>
                      )}
                    {estimate?.estimated_completion && (
                      <div>
                        <dt className="text-sm font-medium text-zinc-500">
                          Estimated Completion
                        </dt>
                        <dd className="mt-1">
                          {formatDate(estimate.estimated_completion)}
                        </dd>
                      </div>
                    )}
                    {retryHistory && (
                      <>
                        <div>
                          <dt className="text-sm font-medium text-zinc-500">
                            Retry Count
                          </dt>
                          <dd className="mt-1">
                            {retryHistory.retry_count}/{retryHistory.max_retries}
                          </dd>
                        </div>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="retry-history">
              <Card>
                <CardHeader>
                  <CardTitle>Retry History</CardTitle>
                  <CardDescription>
                    {retryHistory
                      ? `${retryHistory.retry_count} of ${retryHistory.max_retries} retries used`
                      : "Loading..."}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {retryHistory && retryHistory.attempts.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Attempt</TableHead>
                          <TableHead>Timestamp</TableHead>
                          <TableHead>Error</TableHead>
                          <TableHead>Duration</TableHead>
                          <TableHead>Worker</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {retryHistory.attempts.map((attempt) => (
                          <TableRow key={attempt.attempt_number}>
                            <TableCell className="font-medium">
                              #{attempt.attempt_number}
                            </TableCell>
                            <TableCell>{formatDate(attempt.timestamp)}</TableCell>
                            <TableCell className="max-w-xs truncate text-red-600">
                              {attempt.error}
                            </TableCell>
                            <TableCell>
                              {attempt.duration_seconds
                                ? formatDuration(attempt.duration_seconds)
                                : "-"}
                            </TableCell>
                            <TableCell>
                              {attempt.worker_id ? (
                                <code className="text-xs">
                                  {attempt.worker_id.slice(0, 12)}...
                                </code>
                              ) : (
                                "-"
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="py-8 text-center text-zinc-500">
                      No retry attempts recorded for this job.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}
