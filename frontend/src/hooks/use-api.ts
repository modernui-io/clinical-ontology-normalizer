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
