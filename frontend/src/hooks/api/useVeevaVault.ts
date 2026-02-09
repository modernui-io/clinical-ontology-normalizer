/**
 * Veeva Vault CDMS Integration React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  testVeevaConnection,
  getVeevaStudies,
  importVeevaStudy,
  pushScreeningToVeeva,
  syncVeevaEnrollment,
  getVeevaStatus,
  type VeevaConnectionTestRequest,
  type VeevaConnectionTestResponse,
  type VeevaStudyListResponse,
  type VeevaStudyImportResponse,
  type VeevaScreeningPushRequest,
  type VeevaScreeningPushResponse,
  type VeevaEnrollmentSyncResponse,
  type VeevaIntegrationStatus,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useVeevaConnectionTest() {
  return useMutation({
    mutationFn: (data: VeevaConnectionTestRequest) => testVeevaConnection(data),
  });
}

export function useVeevaStudies(
  options?: Omit<UseQueryOptions<VeevaStudyListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.veevaVault.studies(),
    queryFn: () => getVeevaStudies(),
    ...options,
  });
}

export function useVeevaStudyImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (studyName: string) => importVeevaStudy(studyName),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.veevaVault.all,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.trials.all,
      });
    },
  });
}

export function useVeevaScreeningPush() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: VeevaScreeningPushRequest) => pushScreeningToVeeva(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.veevaVault.all,
      });
    },
  });
}

export function useVeevaEnrollmentSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => syncVeevaEnrollment(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.veevaVault.all,
      });
    },
  });
}

export function useVeevaStatus(
  options?: Omit<UseQueryOptions<VeevaIntegrationStatus>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.veevaVault.status(),
    queryFn: () => getVeevaStatus(),
    ...options,
  });
}
