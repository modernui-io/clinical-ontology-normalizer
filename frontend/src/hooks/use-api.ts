/**
 * Custom React Query hooks for the Clinical Ontology Normalizer API.
 *
 * These hooks provide type-safe, cached access to all API endpoints with:
 * - Automatic caching and background refetching
 * - Loading, error, and success states
 * - Optimistic updates for mutations
 * - Query invalidation helpers
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  // API functions
  getDocuments,
  getDocument,
  getDocumentMentions,
  uploadDocument,
  previewExtraction,
  getPatients,
  getPatient,
  getPatientGraph,
  getPatientFacts,
  buildPatientGraph,
  getJobs,
  getJobStatus,
  getDashboardStats,
  healthCheck,
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
  // Types
  type Document,
  type DocumentCreate,
  type DocumentUploadResponse,
  type DocumentListResponse,
  type Mention,
  type ExtractPreviewResponse,
  type Patient,
  type PatientListResponse,
  type PatientGraph,
  type ClinicalFact,
  type JobInfo,
  type JobListResponse,
  type DashboardStats,
  type PaginationParams,
  type FactFilterParams,
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
// Document Hooks
// ============================================================================

/**
 * Fetch a paginated list of documents.
 */
export function useDocuments(
  params?: PaginationParams,
  options?: Omit<UseQueryOptions<DocumentListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.list(params),
    queryFn: () => getDocuments(params),
    ...options,
  });
}

/**
 * Fetch a single document by ID.
 */
export function useDocument(
  documentId: string,
  options?: Omit<UseQueryOptions<Document>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.detail(documentId),
    queryFn: () => getDocument(documentId),
    enabled: !!documentId,
    ...options,
  });
}

/**
 * Fetch mentions for a specific document.
 */
export function useDocumentMentions(
  documentId: string,
  options?: Omit<UseQueryOptions<Mention[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.mentions(documentId),
    queryFn: () => getDocumentMentions(documentId),
    enabled: !!documentId,
    ...options,
  });
}

/**
 * Upload a new document.
 * Automatically invalidates document and job caches on success.
 */
export function useUploadDocument(
  options?: UseMutationOptions<DocumentUploadResponse, Error, DocumentCreate>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      // Invalidate related caches
      invalidationHelpers.invalidateDocuments(queryClient);
      invalidationHelpers.invalidateJobs(queryClient);
      invalidationHelpers.invalidateDashboard(queryClient);
    },
    ...options,
  });
}

/**
 * Preview extraction results without saving.
 */
export function usePreviewExtraction(
  options?: UseMutationOptions<
    ExtractPreviewResponse,
    Error,
    { text: string; noteType?: string }
  >
) {
  return useMutation({
    mutationFn: ({ text, noteType }) => previewExtraction(text, noteType),
    ...options,
  });
}

// ============================================================================
// Patient Hooks
// ============================================================================

/**
 * Fetch a paginated list of patients.
 */
export function usePatients(
  params?: PaginationParams,
  options?: Omit<UseQueryOptions<PatientListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.patients.list(params),
    queryFn: () => getPatients(params),
    ...options,
  });
}

/**
 * Fetch a single patient by ID.
 */
export function usePatient(
  patientId: string,
  options?: Omit<UseQueryOptions<Patient>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.patients.detail(patientId),
    queryFn: () => getPatient(patientId),
    enabled: !!patientId,
    ...options,
  });
}

/**
 * Fetch the knowledge graph for a patient.
 */
export function usePatientGraph(
  patientId: string,
  options?: Omit<UseQueryOptions<PatientGraph>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.patients.graph(patientId),
    queryFn: () => getPatientGraph(patientId),
    enabled: !!patientId,
    // Graphs can be expensive to compute, use longer stale time
    staleTime: queryConfigs.static.staleTime,
    ...options,
  });
}

/**
 * Fetch clinical facts for a patient with optional filters.
 */
export function usePatientFacts(
  patientId: string,
  params?: FactFilterParams,
  options?: Omit<UseQueryOptions<ClinicalFact[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.patients.facts(patientId, params),
    queryFn: () => getPatientFacts(patientId, params),
    enabled: !!patientId,
    ...options,
  });
}

/**
 * Build/rebuild a patient's knowledge graph.
 * Automatically invalidates the graph cache on success.
 */
export function useBuildPatientGraph(
  options?: UseMutationOptions<PatientGraph, Error, string>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: buildPatientGraph,
    onSuccess: (data, patientId) => {
      // Update the graph cache immediately
      queryClient.setQueryData(queryKeys.patients.graph(patientId), data);
      // Invalidate patient details (node/edge counts might have changed)
      queryClient.invalidateQueries({
        queryKey: queryKeys.patients.detail(patientId),
      });
    },
    ...options,
  });
}

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

// ============================================================================
// Health Check Hooks
// ============================================================================

/**
 * Check API health status.
 */
export function useHealthCheck(
  options?: Omit<UseQueryOptions<{ status: string }>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.health.check(),
    queryFn: healthCheck,
    // Health checks should be lightweight
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 60 * 1000, // 1 minute
    retry: 1, // Quick failure
    ...options,
  });
}

// ============================================================================
// ETL Hooks
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

// ============================================================================
// Prefetch Helpers
// ============================================================================

/**
 * Prefetch functions for preloading data.
 * Useful for hover prefetching or route transitions.
 */
export const prefetchHelpers = {
  /**
   * Prefetch a document's data.
   */
  prefetchDocument: (
    queryClient: ReturnType<typeof useQueryClient>,
    documentId: string
  ) => {
    return queryClient.prefetchQuery({
      queryKey: queryKeys.documents.detail(documentId),
      queryFn: () => getDocument(documentId),
    });
  },

  /**
   * Prefetch a patient's data.
   */
  prefetchPatient: (
    queryClient: ReturnType<typeof useQueryClient>,
    patientId: string
  ) => {
    return queryClient.prefetchQuery({
      queryKey: queryKeys.patients.detail(patientId),
      queryFn: () => getPatient(patientId),
    });
  },

  /**
   * Prefetch a patient's graph.
   */
  prefetchPatientGraph: (
    queryClient: ReturnType<typeof useQueryClient>,
    patientId: string
  ) => {
    return queryClient.prefetchQuery({
      queryKey: queryKeys.patients.graph(patientId),
      queryFn: () => getPatientGraph(patientId),
    });
  },

  /**
   * Prefetch dashboard stats.
   */
  prefetchDashboardStats: (
    queryClient: ReturnType<typeof useQueryClient>
  ) => {
    return queryClient.prefetchQuery({
      queryKey: queryKeys.dashboard.stats(),
      queryFn: getDashboardStats,
    });
  },
} as const;

// ============================================================================
// Re-export Utilities
// ============================================================================

// Re-export for convenience
export { queryKeys, queryConfigs, invalidationHelpers };

// Export query client hook for direct access
export { useQueryClient } from "@tanstack/react-query";
