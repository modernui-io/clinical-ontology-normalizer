/**
 * Medidata Rave EDC Integration React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  testRaveConnection,
  getRaveStudies,
  importRaveStudy,
  pushScreeningToRave,
  syncRaveEnrollment,
  getRaveStatus,
  type RaveConnectionTestRequest,
  type RaveConnectionTestResponse,
  type RaveStudyListResponse,
  type RaveStudyImportResponse,
  type RaveScreeningPushRequest,
  type RaveScreeningPushResponse,
  type RaveEnrollmentSyncResponse,
  type RaveIntegrationStatus,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useRaveConnectionTest() {
  return useMutation({
    mutationFn: (data: RaveConnectionTestRequest) => testRaveConnection(data),
  });
}

export function useRaveStudies(
  options?: Omit<UseQueryOptions<RaveStudyListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.medidataRave.studies(),
    queryFn: () => getRaveStudies(),
    ...options,
  });
}

export function useRaveStudyImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (studyOid: string) => importRaveStudy(studyOid),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.medidataRave.all,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.trials.all,
      });
    },
  });
}

export function useRaveScreeningPush() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RaveScreeningPushRequest) => pushScreeningToRave(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.medidataRave.all,
      });
    },
  });
}

export function useRaveEnrollmentSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => syncRaveEnrollment(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.medidataRave.all,
      });
    },
  });
}

export function useRaveStatus(
  options?: Omit<UseQueryOptions<RaveIntegrationStatus>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.medidataRave.status(),
    queryFn: () => getRaveStatus(),
    ...options,
  });
}
