/**
 * Metriport HIE Integration React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  getMetriportStatus,
  getMetriportPatients,
  createMetriportPatient,
  startDocumentQuery,
  getMetriportDocuments,
  startConsolidatedQuery,
  onboardMetriportPatient,
  getMetriportFacilities,
  type MetriportStatus,
  type MetriportQueryResponse,
  type MetriportPatientCreate,
} from "@/lib/api";

import { queryKeys } from "@/lib/query-client";

export function useMetriportStatus(
  options?: Omit<UseQueryOptions<MetriportStatus>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.metriport.status(),
    queryFn: () => getMetriportStatus(),
    ...options,
  });
}

export function useMetriportPatients(
  facilityId?: string,
  options?: Omit<UseQueryOptions<MetriportQueryResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.metriport.patients(facilityId),
    queryFn: () => getMetriportPatients(facilityId),
    ...options,
  });
}

export function useMetriportDocuments(
  patientId: string,
  options?: Omit<UseQueryOptions<MetriportQueryResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.metriport.documents(patientId),
    queryFn: () => getMetriportDocuments(patientId),
    enabled: !!patientId,
    ...options,
  });
}

export function useMetriportFacilities(
  options?: Omit<UseQueryOptions<MetriportQueryResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.metriport.facilities(),
    queryFn: () => getMetriportFacilities(),
    ...options,
  });
}

export function useCreateMetriportPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MetriportPatientCreate) => createMetriportPatient(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metriport.all,
      });
    },
  });
}

export function useOnboardMetriportPatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MetriportPatientCreate) => onboardMetriportPatient(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metriport.all,
      });
    },
  });
}

export function useStartDocumentQuery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ patientId, facilityId }: { patientId: string; facilityId?: string }) =>
      startDocumentQuery(patientId, facilityId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metriport.all,
      });
    },
  });
}

export function useStartConsolidatedQuery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ patientId, resources }: { patientId: string; resources?: string[] }) =>
      startConsolidatedQuery(patientId, resources),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metriport.all,
      });
    },
  });
}
