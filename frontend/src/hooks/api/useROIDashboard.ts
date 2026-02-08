/**
 * ROI Dashboard React Query hook.
 */

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import {
  getROISummary,
  type ROISummaryParams,
  type ROISummaryResponse,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useROISummary(
  params?: ROISummaryParams,
  options?: Omit<UseQueryOptions<ROISummaryResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.dashboard.roiSummary(params as Record<string, unknown>),
    queryFn: () => getROISummary(params),
    ...options,
  });
}
