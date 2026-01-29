/**
 * Base utilities and shared exports for API hooks.
 *
 * This module provides:
 * - Re-exports of query utilities from @tanstack/react-query
 * - Re-exports of query keys, configs, and invalidation helpers
 * - Prefetch helper functions
 */

import { useQueryClient } from "@tanstack/react-query";

import {
  getDocument,
  getPatient,
  getPatientGraph,
  getDashboardStats,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

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
