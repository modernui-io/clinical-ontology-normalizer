/**
 * Document-related React Query hooks.
 *
 * These hooks provide type-safe, cached access to document API endpoints.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  getDocuments,
  getDocument,
  getDocumentMentions,
  uploadDocument,
  previewExtraction,
  type Document,
  type DocumentCreate,
  type DocumentUploadResponse,
  type DocumentListResponse,
  type Mention,
  type ExtractPreviewResponse,
  type PaginationParams,
} from "@/lib/api";

import {
  queryKeys,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// Document Hooks
// ============================================================================

/**
 * Fetch a paginated list of documents.
 */
export function useDocuments(
  params?: PaginationParams,
  options?: Omit<UseQueryOptions<DocumentListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.list(params),
    queryFn: () => getDocuments(params),
    ...options,
  });
}

/**
 * Fetch a single document by ID.
 */
export function useDocument(
  documentId: string,
  options?: Omit<UseQueryOptions<Document>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.detail(documentId),
    queryFn: () => getDocument(documentId),
    enabled: !!documentId,
    ...options,
  });
}

/**
 * Fetch mentions for a specific document.
 */
export function useDocumentMentions(
  documentId: string,
  options?: Omit<UseQueryOptions<Mention[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.documents.mentions(documentId),
    queryFn: () => getDocumentMentions(documentId),
    enabled: !!documentId,
    ...options,
  });
}

/**
 * Upload a new document.
 * Automatically invalidates document and job caches on success.
 */
export function useUploadDocument(
  options?: UseMutationOptions<DocumentUploadResponse, Error, DocumentCreate>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      // Invalidate related caches
      invalidationHelpers.invalidateDocuments(queryClient);
      invalidationHelpers.invalidateJobs(queryClient);
      invalidationHelpers.invalidateDashboard(queryClient);
    },
    ...options,
  });
}

/**
 * Preview extraction results without saving.
 */
export function usePreviewExtraction(
  options?: UseMutationOptions<
    ExtractPreviewResponse,
    Error,
    { text: string; noteType?: string }
  >
) {
  return useMutation({
    mutationFn: ({ text, noteType }) => previewExtraction(text, noteType),
    ...options,
  });
}
