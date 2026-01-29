/**
 * Analytics and Dashboard-related React Query hooks.
 *
 * These hooks provide type-safe, cached access to:
 * - Dashboard statistics
 * - Job monitoring and polling
 */

import {
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  getJobs,
  getJobStatus,
  getDashboardStats,
  type JobInfo,
  type JobListResponse,
  type DashboardStats,
  type PaginationParams,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// Job Hooks
// ============================================================================

/**
 * Fetch a paginated list of jobs.
 */
export function useJobs(
  params?: PaginationParams,
  options?: Omit<UseQueryOptions<JobListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => getJobs(params),
    // Jobs change frequently, use shorter stale time
    ...queryConfigs.frequent,
    ...options,
  });
}

/**
 * Fetch a single job's status by ID.
 */
export function useJob(
  jobId: string,
  options?: Omit<UseQueryOptions<JobInfo>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: () => getJobStatus(jobId),
    enabled: !!jobId,
    ...options,
  });
}

/**
 * Poll a job's status until it completes.
 * Automatically stops polling when job is no longer pending/processing.
 */
export function useJobPolling(
  jobId: string,
  options?: Omit<UseQueryOptions<JobInfo>, "queryKey" | "queryFn"> & {
    pollingInterval?: number;
  }
) {
  const { pollingInterval = 2000, ...queryOptions } = options || {};
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: () => getJobStatus(jobId),
    enabled: !!jobId,
    // Use polling config
    ...queryConfigs.polling(pollingInterval),
    // Stop polling when job is complete
    refetchInterval: (query) => {
      const data = query.state.data as JobInfo | undefined;
      if (data?.status === "completed" || data?.status === "failed") {
        // Job finished, invalidate related caches
        invalidationHelpers.invalidateDocuments(queryClient);
        invalidationHelpers.invalidateDashboard(queryClient);
        return false; // Stop polling
      }
      return pollingInterval;
    },
    ...queryOptions,
  });
}

// ============================================================================
// Dashboard Hooks
// ============================================================================

/**
 * Fetch dashboard statistics.
 */
export function useDashboardStats(
  options?: Omit<UseQueryOptions<DashboardStats>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.dashboard.stats(),
    queryFn: getDashboardStats,
    // Dashboard stats should refresh fairly often
    ...queryConfigs.frequent,
    ...options,
  });
}
