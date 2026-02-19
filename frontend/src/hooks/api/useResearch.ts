/**
 * React Query hooks for Research Experiment tracking.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import {
  createResearchExperiment,
  listResearchExperiments,
  getResearchExperiment,
  updateResearchExperiment,
  deleteResearchExperiment,
  startResearchExperiment,
  completeResearchExperiment,
  createResearchRun,
  listResearchRuns,
  getResearchRun,
  getResearchRunProgress,
  getResearchRunMetrics,
  getResearchAssertionAnalytics,
  getResearchMappingQuality,
  getResearchKGMetrics,
  getResearchPipelineTiming,
  compareResearchRuns,
  exportResearchMetrics,
  getMimicNoteStats,
  searchMimicNotes,
  type ResearchExperiment,
  type ResearchExperimentCreate,
  type ResearchExperimentUpdate,
  type ResearchExperimentListResponse,
  type ResearchRun,
  type ResearchRunCreate,
  type ResearchRunListResponse,
  type ResearchRunProgress,
  type ResearchMetricListResponse,
  type ResearchAssertionAnalytics,
  type ResearchMappingQuality,
  type ResearchKGMetrics,
  type ResearchPipelineTiming,
  type ResearchComparisonRequest,
  type ResearchComparisonResponse,
  type ResearchExportRequest,
  type ResearchExportResponse,
  type MimicNoteStats,
  type MimicNoteSearchResult,
} from "@/lib/api";
import {
  queryKeys,
  queryConfigs,
  invalidationHelpers,
} from "@/lib/query-client";

// ============================================================================
// Experiment Hooks
// ============================================================================

export function useCreateExperiment(
  options?: UseMutationOptions<ResearchExperiment, Error, ResearchExperimentCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ResearchExperimentCreate) => createResearchExperiment(data),
    onSuccess: () => {
      invalidationHelpers.invalidateResearchExperiments(queryClient);
    },
    ...options,
  });
}

export function useExperiments(params?: {
  status?: string;
  offset?: number;
  limit?: number;
}) {
  return useQuery<ResearchExperimentListResponse>({
    queryKey: queryKeys.research.experiments.list(params),
    queryFn: () => listResearchExperiments(params),
  });
}

export function useExperiment(experimentId: string | null) {
  return useQuery<ResearchExperiment>({
    queryKey: queryKeys.research.experiments.detail(experimentId ?? ""),
    queryFn: () => getResearchExperiment(experimentId!),
    enabled: !!experimentId,
  });
}

export function useUpdateExperiment(
  options?: UseMutationOptions<
    ResearchExperiment,
    Error,
    { id: string; data: ResearchExperimentUpdate }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ResearchExperimentUpdate }) =>
      updateResearchExperiment(id, data),
    onSuccess: () => {
      invalidationHelpers.invalidateResearchExperiments(queryClient);
    },
    ...options,
  });
}

export function useDeleteExperiment(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteResearchExperiment(id),
    onSuccess: () => {
      invalidationHelpers.invalidateResearchExperiments(queryClient);
    },
    ...options,
  });
}

export function useStartExperiment(
  options?: UseMutationOptions<ResearchExperiment, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => startResearchExperiment(id),
    onSuccess: () => {
      invalidationHelpers.invalidateResearchExperiments(queryClient);
    },
    ...options,
  });
}

export function useCompleteExperiment(
  options?: UseMutationOptions<ResearchExperiment, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => completeResearchExperiment(id),
    onSuccess: () => {
      invalidationHelpers.invalidateResearch(queryClient);
    },
    ...options,
  });
}

// ============================================================================
// Run Hooks
// ============================================================================

export function useCreateRun(
  options?: UseMutationOptions<ResearchRun, Error, ResearchRunCreate>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ResearchRunCreate) => createResearchRun(data),
    onSuccess: () => {
      invalidationHelpers.invalidateResearchRuns(queryClient);
    },
    ...options,
  });
}

export function useRuns(experimentId: string | null, params?: { offset?: number; limit?: number }) {
  return useQuery<ResearchRunListResponse>({
    queryKey: queryKeys.research.runs.lists(experimentId ?? ""),
    queryFn: () =>
      listResearchRuns({
        experiment_id: experimentId!,
        ...params,
      }),
    enabled: !!experimentId,
  });
}

export function useRun(runId: string | null) {
  return useQuery<ResearchRun>({
    queryKey: queryKeys.research.runs.detail(runId ?? ""),
    queryFn: () => getResearchRun(runId!),
    enabled: !!runId,
  });
}

export function useRunProgress(runId: string | null) {
  return useQuery<ResearchRunProgress>({
    queryKey: queryKeys.research.runs.progress(runId ?? ""),
    queryFn: () => getResearchRunProgress(runId!),
    enabled: !!runId,
    ...queryConfigs.polling(2000),
  });
}

// ============================================================================
// Metrics Hooks
// ============================================================================

export function useRunMetrics(runId: string | null, category?: string) {
  return useQuery<ResearchMetricListResponse>({
    queryKey: queryKeys.research.runs.metrics(runId ?? ""),
    queryFn: () => getResearchRunMetrics(runId!, category),
    enabled: !!runId,
  });
}

export function useAssertionAnalytics(runId: string | null) {
  return useQuery<ResearchAssertionAnalytics>({
    queryKey: queryKeys.research.runs.assertions(runId ?? ""),
    queryFn: () => getResearchAssertionAnalytics(runId!),
    enabled: !!runId,
  });
}

export function useMappingQuality(runId: string | null) {
  return useQuery<ResearchMappingQuality>({
    queryKey: queryKeys.research.runs.mappingQuality(runId ?? ""),
    queryFn: () => getResearchMappingQuality(runId!),
    enabled: !!runId,
  });
}

export function useKGMetrics(runId: string | null) {
  return useQuery<ResearchKGMetrics>({
    queryKey: queryKeys.research.runs.kgMetrics(runId ?? ""),
    queryFn: () => getResearchKGMetrics(runId!),
    enabled: !!runId,
  });
}

export function usePipelineTiming(runId: string | null) {
  return useQuery<ResearchPipelineTiming>({
    queryKey: queryKeys.research.runs.timing(runId ?? ""),
    queryFn: () => getResearchPipelineTiming(runId!),
    enabled: !!runId,
  });
}

// ============================================================================
// Comparison & Export Hooks
// ============================================================================

export function useCompareRuns(
  options?: UseMutationOptions<ResearchComparisonResponse, Error, ResearchComparisonRequest>
) {
  return useMutation({
    mutationFn: (data: ResearchComparisonRequest) => compareResearchRuns(data),
    ...options,
  });
}

export function useExportMetrics(
  options?: UseMutationOptions<ResearchExportResponse, Error, ResearchExportRequest>
) {
  return useMutation({
    mutationFn: (data: ResearchExportRequest) => exportResearchMetrics(data),
    ...options,
  });
}

// ============================================================================
// MIMIC Note Browser Hooks
// ============================================================================

export function useMimicNoteStats() {
  return useQuery<MimicNoteStats>({
    queryKey: ["research", "notes", "stats"],
    queryFn: getMimicNoteStats,
    staleTime: 60_000 * 10,
  });
}

export function useMimicNoteSearch(params: {
  q: string;
  category: string;
  offset: number;
  limit: number;
}) {
  return useQuery<MimicNoteSearchResult>({
    queryKey: ["research", "notes", "search", params],
    queryFn: () => searchMimicNotes(params),
    placeholderData: (prev) => prev,
  });
}
