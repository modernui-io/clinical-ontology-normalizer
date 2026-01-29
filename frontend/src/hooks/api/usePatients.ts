/**
 * Patient-related React Query hooks.
 *
 * These hooks provide type-safe, cached access to patient API endpoints.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  getPatients,
  getPatient,
  getPatientGraph,
  getPatientFacts,
  buildPatientGraph,
  type Patient,
  type PatientListResponse,
  type PatientGraph,
  type ClinicalFact,
  type PaginationParams,
  type FactFilterParams,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
} from "@/lib/query-client";

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
