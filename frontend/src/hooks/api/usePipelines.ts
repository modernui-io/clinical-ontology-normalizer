/**
 * Pipeline and ETL-related React Query hooks.
 *
 * These hooks provide type-safe, cached access to:
 * - ETL pipelines (create, update, delete, schedule, trigger)
 * - ETL jobs (create, cancel, delete, polling)
 * - ETL sources (CRUD, connection testing, previews)
 * - ETL connectors
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  // ETL API functions
  getETLConnectors,
  getETLJobs,
  getETLJob,
  createETLJob,
  cancelETLJob,
  deleteETLJob,
  // Source API functions
  getSources,
  getSource,
  createSource,
  updateSource,
  deleteSource,
  testSourceConnection,
  getSourcePreview,
  // Pipeline API functions
  getPipelines,
  getPipeline,
  createPipeline,
  updatePipeline,
  deletePipeline,
  updatePipelineSchedule,
  triggerPipelineRun,
  getPipelineRuns,
  // ETL Types
  type ConnectorListResponse,
  type ETLJob,
  type ETLJobListResponse,
  type ETLJobFilterParams,
  type CreateETLJobRequest,
  type CreateETLJobResponse,
  type CancelETLJobResponse,
  type DeleteETLJobResponse,
  // Source Types
  type Source,
  type SourceListResponse,
  type SourceFilterParams,
  type CreateSourceRequest,
  type UpdateSourceRequest,
  type ConnectionTestResponse,
  type SampleDataResponse,
  // Pipeline Types
  type Pipeline,
  type PipelineListResponse,
  type PipelineFilterParams,
  type CreatePipelineRequest,
  type UpdatePipelineRequest,
  type PipelineRunListResponse,
  type TriggerPipelineResponse,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// ETL Connector Hooks
// ============================================================================

/**
 * Fetch available ETL connector types.
 */
export function useETLConnectors(
  options?: Omit<UseQueryOptions<ConnectorListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.connectors(),
    queryFn: getETLConnectors,
    // Connector types are relatively static
    ...queryConfigs.static,
    ...options,
  });
}

// ============================================================================
// ETL Job Hooks
// ============================================================================

/**
 * Fetch a list of ETL jobs.
 */
export function useETLJobs(
  params?: ETLJobFilterParams,
  options?: Omit<UseQueryOptions<ETLJobListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.jobs.list(params),
    queryFn: () => getETLJobs(params),
    // ETL jobs change frequently while running
    ...queryConfigs.frequent,
    ...options,
  });
}

/**
 * Fetch a single ETL job by ID.
 */
export function useETLJob(
  jobId: string,
  options?: Omit<UseQueryOptions<ETLJob>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.jobs.detail(jobId),
    queryFn: () => getETLJob(jobId),
    enabled: !!jobId,
    ...options,
  });
}

/**
 * Poll an ETL job's status until it completes.
 * Automatically stops polling when job is no longer pending/running.
 */
export function useETLJobPolling(
  jobId: string,
  options?: Omit<UseQueryOptions<ETLJob>, "queryKey" | "queryFn"> & {
    pollingInterval?: number;
  }
) {
  const { pollingInterval = 2000, ...queryOptions } = options || {};
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: queryKeys.etl.jobs.detail(jobId),
    queryFn: () => getETLJob(jobId),
    enabled: !!jobId,
    // Use polling config
    ...queryConfigs.polling(pollingInterval),
    // Stop polling when job is complete
    refetchInterval: (query) => {
      const data = query.state.data as ETLJob | undefined;
      if (
        data?.state === "completed" ||
        data?.state === "failed" ||
        data?.state === "cancelled"
      ) {
        // Job finished, invalidate related caches
        invalidationHelpers.invalidateETLJobs(queryClient);
        return false; // Stop polling
      }
      return pollingInterval;
    },
    ...queryOptions,
  });
}

/**
 * Create a new ETL job.
 * Automatically invalidates ETL job caches on success.
 */
export function useCreateETLJob(
  options?: UseMutationOptions<CreateETLJobResponse, Error, CreateETLJobRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createETLJob,
    onSuccess: () => {
      // Invalidate ETL jobs cache
      invalidationHelpers.invalidateETLJobs(queryClient);
    },
    ...options,
  });
}

/**
 * Cancel an ETL job.
 * Automatically invalidates the job cache on success.
 */
export function useCancelETLJob(
  options?: UseMutationOptions<CancelETLJobResponse, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cancelETLJob,
    onSuccess: (data, jobId) => {
      // Invalidate specific job and job list
      queryClient.invalidateQueries({
        queryKey: queryKeys.etl.jobs.detail(jobId),
      });
      invalidationHelpers.invalidateETLJobs(queryClient);
    },
    ...options,
  });
}

/**
 * Delete an ETL job.
 * Automatically invalidates the job cache on success.
 */
export function useDeleteETLJob(
  options?: UseMutationOptions<DeleteETLJobResponse, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteETLJob,
    onSuccess: (data, jobId) => {
      // Remove from cache
      queryClient.removeQueries({
        queryKey: queryKeys.etl.jobs.detail(jobId),
      });
      invalidationHelpers.invalidateETLJobs(queryClient);
    },
    ...options,
  });
}

// ============================================================================
// ETL Source Hooks
// ============================================================================

/**
 * Fetch a list of ETL sources.
 */
export function useSources(
  params?: SourceFilterParams,
  options?: Omit<UseQueryOptions<SourceListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.sources.list(params),
    queryFn: () => getSources(params),
    ...options,
  });
}

/**
 * Fetch a single source by ID.
 */
export function useSource(
  sourceId: string,
  options?: Omit<UseQueryOptions<Source>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.sources.detail(sourceId),
    queryFn: () => getSource(sourceId),
    enabled: !!sourceId,
    ...options,
  });
}

/**
 * Fetch sample data preview for a source.
 */
export function useSourcePreview(
  sourceId: string,
  limit: number = 10,
  options?: Omit<UseQueryOptions<SampleDataResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.sources.preview(sourceId),
    queryFn: () => getSourcePreview(sourceId, limit),
    enabled: !!sourceId,
    ...options,
  });
}

/**
 * Create a new source.
 */
export function useCreateSource(
  options?: UseMutationOptions<Source, Error, CreateSourceRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      invalidationHelpers.invalidateETLSources(queryClient);
    },
    ...options,
  });
}

/**
 * Update a source.
 */
export function useUpdateSource(
  options?: UseMutationOptions<Source, Error, { sourceId: string; request: UpdateSourceRequest }>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sourceId, request }) => updateSource(sourceId, request),
    onSuccess: (data, { sourceId }) => {
      queryClient.setQueryData(queryKeys.etl.sources.detail(sourceId), data);
      invalidationHelpers.invalidateETLSources(queryClient);
    },
    ...options,
  });
}

/**
 * Delete a source.
 */
export function useDeleteSource(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSource,
    onSuccess: (_, sourceId) => {
      queryClient.removeQueries({
        queryKey: queryKeys.etl.sources.detail(sourceId),
      });
      invalidationHelpers.invalidateETLSources(queryClient);
      // Also invalidate pipelines since they depend on sources
      invalidationHelpers.invalidateETLPipelines(queryClient);
    },
    ...options,
  });
}

/**
 * Test source connection.
 */
export function useTestSourceConnection(
  options?: UseMutationOptions<ConnectionTestResponse, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: testSourceConnection,
    onSuccess: (_, sourceId) => {
      // Refetch the source to get updated status
      queryClient.invalidateQueries({
        queryKey: queryKeys.etl.sources.detail(sourceId),
      });
    },
    ...options,
  });
}

// ============================================================================
// ETL Pipeline Hooks
// ============================================================================

/**
 * Fetch a list of ETL pipelines.
 */
export function usePipelines(
  params?: PipelineFilterParams,
  options?: Omit<UseQueryOptions<PipelineListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.pipelines.list(params),
    queryFn: () => getPipelines(params),
    ...options,
  });
}

/**
 * Fetch a single pipeline by ID.
 */
export function usePipeline(
  pipelineId: string,
  options?: Omit<UseQueryOptions<Pipeline>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.pipelines.detail(pipelineId),
    queryFn: () => getPipeline(pipelineId),
    enabled: !!pipelineId,
    ...options,
  });
}

/**
 * Fetch pipeline run history.
 */
export function usePipelineRuns(
  pipelineId: string,
  limit: number = 20,
  options?: Omit<UseQueryOptions<PipelineRunListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.etl.pipelines.runs(pipelineId),
    queryFn: () => getPipelineRuns(pipelineId, limit),
    enabled: !!pipelineId,
    ...queryConfigs.frequent,
    ...options,
  });
}

/**
 * Create a new pipeline.
 */
export function useCreatePipeline(
  options?: UseMutationOptions<Pipeline, Error, CreatePipelineRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createPipeline,
    onSuccess: () => {
      invalidationHelpers.invalidateETLPipelines(queryClient);
    },
    ...options,
  });
}

/**
 * Update a pipeline.
 */
export function useUpdatePipeline(
  options?: UseMutationOptions<Pipeline, Error, { pipelineId: string; request: UpdatePipelineRequest }>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ pipelineId, request }) => updatePipeline(pipelineId, request),
    onSuccess: (data, { pipelineId }) => {
      queryClient.setQueryData(queryKeys.etl.pipelines.detail(pipelineId), data);
      invalidationHelpers.invalidateETLPipelines(queryClient);
    },
    ...options,
  });
}

/**
 * Delete a pipeline.
 */
export function useDeletePipeline(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deletePipeline,
    onSuccess: (_, pipelineId) => {
      queryClient.removeQueries({
        queryKey: queryKeys.etl.pipelines.detail(pipelineId),
      });
      invalidationHelpers.invalidateETLPipelines(queryClient);
    },
    ...options,
  });
}

/**
 * Update pipeline schedule.
 */
export function useUpdatePipelineSchedule(
  options?: UseMutationOptions<
    Pipeline,
    Error,
    { pipelineId: string; schedule: Parameters<typeof updatePipelineSchedule>[1] }
  >
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ pipelineId, schedule }) => updatePipelineSchedule(pipelineId, schedule),
    onSuccess: (data, { pipelineId }) => {
      queryClient.setQueryData(queryKeys.etl.pipelines.detail(pipelineId), data);
      invalidationHelpers.invalidateETLPipelines(queryClient);
    },
    ...options,
  });
}

/**
 * Trigger a pipeline run.
 */
export function useTriggerPipelineRun(
  options?: UseMutationOptions<TriggerPipelineResponse, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: triggerPipelineRun,
    onSuccess: (_, pipelineId) => {
      // Refetch pipeline to get updated run status
      queryClient.invalidateQueries({
        queryKey: queryKeys.etl.pipelines.detail(pipelineId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.etl.pipelines.runs(pipelineId),
      });
    },
    ...options,
  });
}
