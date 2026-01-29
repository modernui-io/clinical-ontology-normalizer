/**
 * Admin and settings-related React Query hooks.
 *
 * These hooks provide type-safe, cached access to:
 * - Health checks
 * - System administration endpoints
 */

import {
  useQuery,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  healthCheck,
} from "@/lib/api";

import {
  queryKeys,
} from "@/lib/query-client";

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
