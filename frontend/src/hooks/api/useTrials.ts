/**
 * Clinical Trials React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  getTrials,
  getTrial,
  screenTrialPatients,
  getTrialDashboard,
  getTrialEnrollments,
  getTrialStats,
  type TrialListResponse,
  type TrialResponse,
  type ScreeningResponse,
  type TrialDashboard,
  type EnrollmentListResponse,
  type TrialListParams,
} from "@/lib/api";

import { queryKeys, queryConfigs } from "@/lib/query-client";

export function useTrials(
  params?: TrialListParams,
  options?: Omit<UseQueryOptions<TrialListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.trials.list(params),
    queryFn: () => getTrials(params),
    ...options,
  });
}

export function useTrial(
  trialId: string,
  options?: Omit<UseQueryOptions<TrialResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.trials.detail(trialId),
    queryFn: () => getTrial(trialId),
    enabled: !!trialId,
    ...options,
  });
}

export function useTrialDashboard(
  trialId: string,
  options?: Omit<UseQueryOptions<TrialDashboard>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.trials.dashboard(trialId),
    queryFn: () => getTrialDashboard(trialId),
    enabled: !!trialId,
    ...options,
  });
}

export function useTrialScreening(trialId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => screenTrialPatients(trialId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.trials.detail(trialId),
      });
    },
  });
}

export function useTrialEnrollments(
  trialId: string,
  params?: { status?: string; offset?: number; limit?: number },
  options?: Omit<UseQueryOptions<EnrollmentListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.trials.enrollments(trialId, params),
    queryFn: () => getTrialEnrollments(trialId, params),
    enabled: !!trialId,
    ...options,
  });
}

export function useTrialStats(
  options?: Omit<UseQueryOptions<Record<string, unknown>>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.trials.all, "stats"],
    queryFn: () => getTrialStats(),
    staleTime: queryConfigs.static.staleTime,
    ...options,
  });
}
