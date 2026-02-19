/**
 * Synthea synthetic patient data ingestion React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  importSyntheaFromPath,
  validateSyntheaPath,
  getSyntheaImportProgress,
  getSyntheaMetrics,
  getSyntheaPipelineResults,
  type SyntheaImportResponse,
  type SyntheaValidateResponse,
  type SyntheaMetricsResponse,
  type MimicPipelineResultsResponse,
  type SyntheaDirectoryRequest,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// Synthea Hooks
// ============================================================================

export function useImportSyntheaFromPath(
  options?: UseMutationOptions<SyntheaImportResponse, Error, SyntheaDirectoryRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SyntheaDirectoryRequest) => importSyntheaFromPath(request),
    onSuccess: () => {
      invalidationHelpers.invalidateDocuments(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.synthea.all });
    },
    ...options,
  });
}

export function useValidateSyntheaPath(
  options?: UseMutationOptions<SyntheaValidateResponse, Error, string>
) {
  return useMutation({
    mutationFn: (csvDir: string) => validateSyntheaPath(csvDir),
    ...options,
  });
}

export function useSyntheaImportProgress(batchId: string | null) {
  return useQuery({
    queryKey: queryKeys.synthea.progress(batchId ?? ""),
    queryFn: () => getSyntheaImportProgress(batchId!),
    enabled: !!batchId,
    ...queryConfigs.polling(2000),
  });
}

export function useSyntheaMetrics() {
  return useQuery<SyntheaMetricsResponse>({
    queryKey: queryKeys.synthea.metrics(),
    queryFn: getSyntheaMetrics,
  });
}

export function useSyntheaPipelineResults(documentId: string | null) {
  return useQuery<MimicPipelineResultsResponse>({
    queryKey: queryKeys.synthea.pipelineResults(documentId ?? ""),
    queryFn: () => getSyntheaPipelineResults(documentId!),
    enabled: !!documentId,
  });
}
