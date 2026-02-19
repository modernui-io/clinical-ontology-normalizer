/**
 * MTSamples ingestion React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  uploadMtsamplesCsv,
  validateMtsamplesCsv,
  importMtsamplesFromPath,
  validateMtsamplesPath,
  getMtsamplesImportProgress,
  getMtsamplesMetrics,
  getMtsamplesPipelineResults,
  type MtsamplesImportResponse,
  type MtsamplesValidateResponse,
  type MtsamplesMetricsResponse,
  type MimicPipelineResultsResponse,
  type MtsamplesFilePathRequest,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// MTSamples Hooks
// ============================================================================

interface UploadMtsamplesParams {
  file: File;
  chunkSize?: number;
  maxRows?: number;
  skipDuplicates?: boolean;
  enqueueProcessing?: boolean;
}

export function useUploadMtsamplesCsv(
  options?: UseMutationOptions<MtsamplesImportResponse, Error, UploadMtsamplesParams>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, chunkSize, maxRows, skipDuplicates, enqueueProcessing }: UploadMtsamplesParams) =>
      uploadMtsamplesCsv(file, { chunkSize, maxRows, skipDuplicates, enqueueProcessing }),
    onSuccess: () => {
      invalidationHelpers.invalidateDocuments(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.mtsamples.all });
    },
    ...options,
  });
}

export function useImportMtsamplesFromPath(
  options?: UseMutationOptions<MtsamplesImportResponse, Error, MtsamplesFilePathRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: MtsamplesFilePathRequest) => importMtsamplesFromPath(request),
    onSuccess: () => {
      invalidationHelpers.invalidateDocuments(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.mtsamples.all });
    },
    ...options,
  });
}

export function useValidateMtsamplesCsv(
  options?: UseMutationOptions<MtsamplesValidateResponse, Error, File>
) {
  return useMutation({
    mutationFn: (file: File) => validateMtsamplesCsv(file),
    ...options,
  });
}

export function useValidateMtsamplesPath(
  options?: UseMutationOptions<MtsamplesValidateResponse, Error, string>
) {
  return useMutation({
    mutationFn: (filePath: string) => validateMtsamplesPath(filePath),
    ...options,
  });
}

export function useMtsamplesImportProgress(batchId: string | null) {
  return useQuery({
    queryKey: queryKeys.mtsamples.progress(batchId ?? ""),
    queryFn: () => getMtsamplesImportProgress(batchId!),
    enabled: !!batchId,
    ...queryConfigs.polling(2000),
  });
}

export function useMtsamplesMetrics() {
  return useQuery<MtsamplesMetricsResponse>({
    queryKey: queryKeys.mtsamples.metrics(),
    queryFn: getMtsamplesMetrics,
  });
}

export function useMtsamplesPipelineResults(documentId: string | null) {
  return useQuery<MimicPipelineResultsResponse>({
    queryKey: queryKeys.mtsamples.pipelineResults(documentId ?? ""),
    queryFn: () => getMtsamplesPipelineResults(documentId!),
    enabled: !!documentId,
  });
}
