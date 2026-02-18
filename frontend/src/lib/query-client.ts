/**
 * React Query client configuration for the Clinical Ontology Normalizer.
 *
 * This module configures the QueryClient with optimized defaults for:
 * - Stale time and cache time management
 * - Retry behavior
 * - Error handling
 * - Refetch policies
 */

import { QueryClient, QueryCache, MutationCache } from "@tanstack/react-query";
import { ApiError, NetworkError } from "./api";

// ============================================================================
// Constants
// ============================================================================

// Time in milliseconds
const ONE_MINUTE = 60 * 1000;
const FIVE_MINUTES = 5 * ONE_MINUTE;
const TEN_MINUTES = 10 * ONE_MINUTE;
const THIRTY_MINUTES = 30 * ONE_MINUTE;

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Centralized query key factory for consistent cache management.
 * Using arrays for hierarchical invalidation support.
 */
export const queryKeys = {
  // Documents
  documents: {
    all: ["documents"] as const,
    lists: () => [...queryKeys.documents.all, "list"] as const,
    list: (params?: { page?: number; pageSize?: number }) =>
      [...queryKeys.documents.lists(), params] as const,
    details: () => [...queryKeys.documents.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.documents.details(), id] as const,
    mentions: (id: string) =>
      [...queryKeys.documents.detail(id), "mentions"] as const,
  },

  // Patients
  patients: {
    all: ["patients"] as const,
    lists: () => [...queryKeys.patients.all, "list"] as const,
    list: (params?: { page?: number; pageSize?: number }) =>
      [...queryKeys.patients.lists(), params] as const,
    details: () => [...queryKeys.patients.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.patients.details(), id] as const,
    graph: (id: string) =>
      [...queryKeys.patients.detail(id), "graph"] as const,
    facts: (id: string, params?: { domain?: string; assertion?: string }) =>
      [...queryKeys.patients.detail(id), "facts", params] as const,
  },

  // Jobs
  jobs: {
    all: ["jobs"] as const,
    lists: () => [...queryKeys.jobs.all, "list"] as const,
    list: (params?: { limit?: number; offset?: number }) =>
      [...queryKeys.jobs.lists(), params] as const,
    details: () => [...queryKeys.jobs.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.jobs.details(), id] as const,
  },

  // ETL Jobs
  etl: {
    all: ["etl"] as const,
    connectors: () => [...queryKeys.etl.all, "connectors"] as const,
    jobs: {
      all: () => [...queryKeys.etl.all, "jobs"] as const,
      lists: () => [...queryKeys.etl.jobs.all(), "list"] as const,
      list: (params?: { state?: string; limit?: number }) =>
        [...queryKeys.etl.jobs.lists(), params] as const,
      details: () => [...queryKeys.etl.jobs.all(), "detail"] as const,
      detail: (id: string) => [...queryKeys.etl.jobs.details(), id] as const,
    },
    sources: {
      all: () => [...queryKeys.etl.all, "sources"] as const,
      lists: () => [...queryKeys.etl.sources.all(), "list"] as const,
      list: (params?: { source_type?: string; enabled_only?: boolean; limit?: number }) =>
        [...queryKeys.etl.sources.lists(), params] as const,
      details: () => [...queryKeys.etl.sources.all(), "detail"] as const,
      detail: (id: string) => [...queryKeys.etl.sources.details(), id] as const,
      preview: (id: string) => [...queryKeys.etl.sources.detail(id), "preview"] as const,
    },
    pipelines: {
      all: () => [...queryKeys.etl.all, "pipelines"] as const,
      lists: () => [...queryKeys.etl.pipelines.all(), "list"] as const,
      list: (params?: { source_id?: string; status?: string; limit?: number }) =>
        [...queryKeys.etl.pipelines.lists(), params] as const,
      details: () => [...queryKeys.etl.pipelines.all(), "detail"] as const,
      detail: (id: string) => [...queryKeys.etl.pipelines.details(), id] as const,
      runs: (id: string) => [...queryKeys.etl.pipelines.detail(id), "runs"] as const,
    },
  },

  // Dashboard
  dashboard: {
    all: ["dashboard"] as const,
    stats: () => [...queryKeys.dashboard.all, "stats"] as const,
    roiSummary: (params?: Record<string, unknown>) =>
      [...queryKeys.dashboard.all, "roi-summary", params] as const,
  },

  // Health
  health: {
    all: ["health"] as const,
    check: () => [...queryKeys.health.all, "check"] as const,
  },

  // Clinical Trials
  trials: {
    all: ["trials"] as const,
    lists: () => [...queryKeys.trials.all, "list"] as const,
    list: (params?: { offset?: number; limit?: number; status?: string; search?: string }) =>
      [...queryKeys.trials.lists(), params] as const,
    details: () => [...queryKeys.trials.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.trials.details(), id] as const,
    dashboard: (id: string) => [...queryKeys.trials.detail(id), "dashboard"] as const,
    screening: (id: string) => [...queryKeys.trials.detail(id), "screening"] as const,
    enrollments: (id: string, params?: { status?: string }) =>
      [...queryKeys.trials.detail(id), "enrollments", params] as const,
    dualEnrollment: (params?: { trial_id?: string | null; min_match_score?: number }) =>
      [...queryKeys.trials.all, "dual-enrollment", params] as const,
  },

  // Bulk Screening Results
  screening: {
    all: ["screening"] as const,
    lists: () => [...queryKeys.screening.all, "list"] as const,
    list: (params?: { patient_id?: string; trial_id?: string; status?: string; triggered_by?: string; offset?: number; limit?: number }) =>
      [...queryKeys.screening.lists(), params] as const,
  },

  // Sites
  sites: {
    all: ["sites"] as const,
    lists: () => [...queryKeys.sites.all, "list"] as const,
    list: (params?: { search?: string; offset?: number; limit?: number }) =>
      [...queryKeys.sites.lists(), params] as const,
    details: () => [...queryKeys.sites.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.sites.details(), id] as const,
    patients: (id: string) => [...queryKeys.sites.detail(id), "patients"] as const,
    screening: (id: string) => [...queryKeys.sites.detail(id), "screening"] as const,
  },

  // Metriport HIE Integration
  metriport: {
    all: ["metriport"] as const,
    status: () => [...queryKeys.metriport.all, "status"] as const,
    patients: (facilityId?: string) =>
      [...queryKeys.metriport.all, "patients", facilityId] as const,
    patient: (patientId: string) =>
      [...queryKeys.metriport.all, "patient", patientId] as const,
    documents: (patientId: string) =>
      [...queryKeys.metriport.all, "documents", patientId] as const,
    facilities: () => [...queryKeys.metriport.all, "facilities"] as const,
  },

  // Medidata Rave Integration
  medidataRave: {
    all: ["medidata-rave"] as const,
    status: () => [...queryKeys.medidataRave.all, "status"] as const,
    studies: () => [...queryKeys.medidataRave.all, "studies"] as const,
  },

  // Veeva Vault CDMS Integration
  veevaVault: {
    all: ["veeva-vault"] as const,
    status: () => [...queryKeys.veevaVault.all, "status"] as const,
    studies: () => [...queryKeys.veevaVault.all, "studies"] as const,
  },

  // MIMIC-IV-Note Ingestion
  mimic: {
    all: ["mimic"] as const,
    progress: (batchId: string) => [...queryKeys.mimic.all, "progress", batchId] as const,
    metrics: () => [...queryKeys.mimic.all, "metrics"] as const,
    pipelineResults: (documentId: string) => [...queryKeys.mimic.all, "pipeline-results", documentId] as const,
  },
} as const;

// ============================================================================
// Retry Configuration
// ============================================================================

/**
 * Determines if a failed query should be retried.
 * - Network errors: retry with exponential backoff
 * - 5xx errors: retry (server might recover)
 * - 429 rate limiting: retry with longer delay
 * - 4xx errors: don't retry (client error)
 */
function shouldRetry(failureCount: number, error: Error): boolean {
  // Max 3 retries
  if (failureCount >= 3) {
    return false;
  }

  // Always retry network errors
  if (NetworkError.isNetworkError(error)) {
    return true;
  }

  // For API errors, only retry on server errors or rate limiting
  if (ApiError.isApiError(error)) {
    return error.status >= 500 || error.status === 429;
  }

  return false;
}

/**
 * Calculate retry delay with exponential backoff.
 * Rate limiting (429) gets longer delays.
 */
function getRetryDelay(attemptIndex: number, error: Error): number {
  const baseDelay = 1000;

  // Rate limiting gets a longer base delay
  if (ApiError.isApiError(error) && error.status === 429) {
    return Math.min(baseDelay * Math.pow(2, attemptIndex + 2), 30000);
  }

  // Exponential backoff with max 10 seconds
  return Math.min(baseDelay * Math.pow(2, attemptIndex), 10000);
}

// ============================================================================
// Error Handlers
// ============================================================================

/**
 * Global error handler for queries.
 * Logs errors and can be extended for error reporting/analytics.
 */
function handleQueryError(error: Error): void {
  if (ApiError.isApiError(error)) {
    console.error(`[Query Error] API ${error.status}: ${error.message}`, {
      details: error.details,
    });
  } else if (NetworkError.isNetworkError(error)) {
    console.error(`[Query Error] Network: ${error.message}`);
  } else {
    console.error(`[Query Error] Unknown: ${error.message}`);
  }
}

/**
 * Global error handler for mutations.
 */
function handleMutationError(error: Error): void {
  if (ApiError.isApiError(error)) {
    console.error(`[Mutation Error] API ${error.status}: ${error.message}`, {
      details: error.details,
    });
  } else if (NetworkError.isNetworkError(error)) {
    console.error(`[Mutation Error] Network: ${error.message}`);
  } else {
    console.error(`[Mutation Error] Unknown: ${error.message}`);
  }
}

// ============================================================================
// Query Client Factory
// ============================================================================

/**
 * Creates a configured QueryClient instance.
 * Exported as a function to support SSR scenarios where
 * each request needs its own client.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: handleQueryError,
    }),
    mutationCache: new MutationCache({
      onError: handleMutationError,
    }),
    defaultOptions: {
      queries: {
        // Time until data is considered stale
        // Stale data will be refetched in the background
        staleTime: FIVE_MINUTES,

        // Time to keep unused data in cache
        // After this, data is garbage collected
        gcTime: THIRTY_MINUTES,

        // Retry configuration
        retry: shouldRetry,
        retryDelay: getRetryDelay,

        // Refetch policies
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        refetchOnMount: true,

        // Keep previous data while fetching new data
        // Prevents UI flickering on pagination
        placeholderData: (previousData: unknown) => previousData,

        // Network mode: always try to fetch when online
        networkMode: "online",
      },
      mutations: {
        // Mutations also benefit from retry logic
        retry: (failureCount, error) => {
          // Only retry network errors for mutations
          if (failureCount >= 2) return false;
          return NetworkError.isNetworkError(error as Error);
        },
        retryDelay: (attemptIndex) => Math.min(1000 * Math.pow(2, attemptIndex), 5000),
        networkMode: "online",
      },
    },
  });
}

// ============================================================================
// Singleton Instance
// ============================================================================

// Singleton for client-side usage
let browserQueryClient: QueryClient | undefined;

/**
 * Gets the QueryClient singleton for browser usage.
 * Creates a new instance on first call.
 * This ensures we don't share state between requests on the server.
 */
export function getQueryClient(): QueryClient {
  // Server: always create a new client
  if (typeof window === "undefined") {
    return createQueryClient();
  }

  // Browser: reuse the singleton
  if (!browserQueryClient) {
    browserQueryClient = createQueryClient();
  }

  return browserQueryClient;
}

// ============================================================================
// Query Configuration Presets
// ============================================================================

/**
 * Preset configurations for common query patterns.
 * Use these with the `options` parameter in hooks.
 */
export const queryConfigs = {
  /**
   * For data that changes frequently (e.g., job status)
   */
  frequent: {
    staleTime: ONE_MINUTE,
    gcTime: FIVE_MINUTES,
    refetchInterval: ONE_MINUTE,
  },

  /**
   * For relatively static data (e.g., reference data)
   */
  static: {
    staleTime: THIRTY_MINUTES,
    gcTime: THIRTY_MINUTES * 2,
    refetchOnWindowFocus: false,
  },

  /**
   * For real-time polling (e.g., processing status)
   */
  polling: (intervalMs: number = 2000) => ({
    staleTime: 0,
    gcTime: FIVE_MINUTES,
    refetchInterval: intervalMs,
    refetchIntervalInBackground: false,
  }),

  /**
   * For one-time fetches (e.g., initial data load)
   */
  once: {
    staleTime: Infinity,
    gcTime: THIRTY_MINUTES,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  },
} as const;

// ============================================================================
// Cache Invalidation Helpers
// ============================================================================

/**
 * Helper to invalidate related caches after mutations.
 */
export const invalidationHelpers = {
  /**
   * Invalidate all document-related queries
   */
  invalidateDocuments: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.documents.all });
  },

  /**
   * Invalidate all patient-related queries
   */
  invalidatePatients: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.patients.all });
  },

  /**
   * Invalidate all job-related queries
   */
  invalidateJobs: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.jobs.all });
  },

  /**
   * Invalidate dashboard stats
   */
  invalidateDashboard: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  },

  /**
   * Invalidate all ETL-related queries
   */
  invalidateETL: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.etl.all });
  },

  /**
   * Invalidate ETL jobs
   */
  invalidateETLJobs: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.etl.jobs.all() });
  },

  /**
   * Invalidate ETL sources
   */
  invalidateETLSources: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.etl.sources.all() });
  },

  /**
   * Invalidate ETL pipelines
   */
  invalidateETLPipelines: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.etl.pipelines.all() });
  },

  /**
   * Invalidate all trial-related queries
   */
  invalidateTrials: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.trials.all });
  },

  /**
   * Invalidate all Metriport-related queries
   */
  invalidateMetriport: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.metriport.all });
  },

  /**
   * Invalidate all Medidata Rave-related queries
   */
  invalidateMedidataRave: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.medidataRave.all });
  },

  /**
   * Invalidate all Veeva Vault-related queries
   */
  invalidateVeevaVault: (client: QueryClient) => {
    return client.invalidateQueries({ queryKey: queryKeys.veevaVault.all });
  },

  /**
   * Invalidate everything (use sparingly)
   */
  invalidateAll: (client: QueryClient) => {
    return client.invalidateQueries();
  },
} as const;
