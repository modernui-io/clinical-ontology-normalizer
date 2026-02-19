/**
 * MIMIC-IV-Note ingestion React Query hooks.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  uploadMimicCsv,
  validateMimicCsv,
  importMimicFromPath,
  validateMimicPath,
  getMimicImportProgress,
  getMimicMetrics,
  getMimicPipelineResults,
  type MimicImportResponse,
  type MimicValidateResponse,
  type MimicImportProgressResponse,
  type MimicMetricsResponse,
  type MimicPipelineResultsResponse,
  type MimicFilePathRequest,
} from "@/lib/api";

import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// MIMIC Hooks
// ============================================================================

interface UploadMimicParams {
  file: File;
  chunkSize?: number;
  maxRows?: number;
  skipDuplicates?: boolean;
  enqueueProcessing?: boolean;
}

/**
 * Upload a MIMIC CSV for ingestion (browser upload).
 */
export function useUploadMimicCsv(
  options?: UseMutationOptions<MimicImportResponse, Error, UploadMimicParams>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, chunkSize, maxRows, skipDuplicates, enqueueProcessing }: UploadMimicParams) =>
      uploadMimicCsv(file, { chunkSize, maxRows, skipDuplicates, enqueueProcessing }),
    onSuccess: () => {
      invalidationHelpers.invalidateDocuments(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.mimic.all });
    },
    ...options,
  });
}

/**
 * Import from a server-side file path (no upload needed).
 */
export function useImportMimicFromPath(
  options?: UseMutationOptions<MimicImportResponse, Error, MimicFilePathRequest>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: MimicFilePathRequest) => importMimicFromPath(request),
    onSuccess: () => {
      invalidationHelpers.invalidateDocuments(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.mimic.all });
    },
    ...options,
  });
}

/**
 * Validate a MIMIC CSV structure without importing (browser upload).
 */
export function useValidateMimicCsv(
  options?: UseMutationOptions<MimicValidateResponse, Error, File>
) {
  return useMutation({
    mutationFn: (file: File) => validateMimicCsv(file),
    ...options,
  });
}

/**
 * Validate a server-side MIMIC CSV path without importing.
 */
export function useValidateMimicPath(
  options?: UseMutationOptions<MimicValidateResponse, Error, string>
) {
  return useMutation({
    mutationFn: (filePath: string) => validateMimicPath(filePath),
    ...options,
  });
}

/**
 * Poll MIMIC import progress every 2 seconds.
 */
export function useMimicImportProgress(
  batchId: string | null,
) {
  return useQuery({
    queryKey: queryKeys.mimic.progress(batchId ?? ""),
    queryFn: () => getMimicImportProgress(batchId!),
    enabled: !!batchId,
    ...queryConfigs.polling(2000),
  });
}

/**
 * Fetch MIMIC validation metrics.
 */
export function useMimicMetrics() {
  return useQuery({
    queryKey: queryKeys.mimic.metrics(),
    queryFn: getMimicMetrics,
  });
}

/**
 * Fetch full pipeline results for a single MIMIC document.
 * Only fetches when documentId is provided (on-demand drill-down).
 */
export function useMimicPipelineResults(documentId: string | null) {
  return useQuery<MimicPipelineResultsResponse>({
    queryKey: queryKeys.mimic.pipelineResults(documentId ?? ""),
    queryFn: () => getMimicPipelineResults(documentId!),
    enabled: !!documentId,
  });
}
