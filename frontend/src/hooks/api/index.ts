/**
 * API Hooks barrel export.
 *
 * Re-exports all domain-specific API hooks for convenient imports:
 *
 * @example
 * import { useDocuments, usePatients, useDashboardStats } from '@/hooks/api';
 */

// Base utilities and shared exports
export {
  prefetchHelpers,
  queryKeys,
  queryConfigs,
  invalidationHelpers,
  useQueryClient,
} from "./base";

// Document hooks
export {
  useDocuments,
  useDocument,
  useDocumentMentions,
  useUploadDocument,
  usePreviewExtraction,
} from "./useDocuments";

// Patient hooks
export {
  usePatients,
  usePatient,
  usePatientGraph,
  usePatientFacts,
  useBuildPatientGraph,
} from "./usePatients";

// Pipeline and ETL hooks
export {
  // ETL Connectors
  useETLConnectors,
  // ETL Jobs
  useETLJobs,
  useETLJob,
  useETLJobPolling,
  useCreateETLJob,
  useCancelETLJob,
  useDeleteETLJob,
  // ETL Sources
  useSources,
  useSource,
  useSourcePreview,
  useCreateSource,
  useUpdateSource,
  useDeleteSource,
  useTestSourceConnection,
  // ETL Pipelines
  usePipelines,
  usePipeline,
  usePipelineRuns,
  useCreatePipeline,
  useUpdatePipeline,
  useDeletePipeline,
  useUpdatePipelineSchedule,
  useTriggerPipelineRun,
} from "./usePipelines";

// Analytics and dashboard hooks
export {
  useJobs,
  useJob,
  useJobPolling,
  useDashboardStats,
} from "./useAnalytics";

// Admin and settings hooks
export {
  useHealthCheck,
} from "./useAdmin";

// Clinical Trials hooks
export {
  useTrials,
  useTrial,
  useTrialDashboard,
  useTrialScreening,
  useTrialEnrollments,
  useTrialStats,
} from "./useTrials";

// Search hooks (placeholder for future implementation)
// export {} from "./useSearch";

// NLP hooks (placeholder for future implementation)
// export {} from "./useNLP";
