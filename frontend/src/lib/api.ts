/**
 * API client for the Clinical Ontology Normalizer backend.
 *
 * Features:
 * - Base URL configuration from environment
 * - Fetch wrapper with comprehensive error handling
 * - Automatic retry on network errors
 * - Type definitions for all API responses
 */

// Base URL configuration
const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    // Browser: use Next.js API proxy
    return "/api";
  }
  // Server: direct backend call
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

const API_BASE_URL = getApiBaseUrl();

// ============================================================================
// Type Definitions
// ============================================================================

export interface DocumentCreate {
  patient_id: string;
  note_type: string;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadResponse {
  document_id: string;
  job_id: string;
  status: string;
}

export interface Document {
  id: string;
  patient_id: string;
  note_type: string;
  text: string;
  metadata: Record<string, unknown>;
  status: string;
  job_id: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobInfo {
  job_id: string;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface JobListResponse {
  jobs: JobInfo[];
  total: number;
}

export interface Patient {
  id: string;
  external_id: string;
  name: string;
  gender: string;
  birth_date: string;
  created_at: string;
  document_count: number;
  fact_count: number;
  node_count: number;
  conditions: string[];
  medications: string[];
}

export interface PatientListResponse {
  patients: Patient[];
  total: number;
  page: number;
  page_size: number;
}

export interface PatientGraph {
  patient_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface GraphNode {
  id: string;
  patient_id: string;
  node_type: string;
  omop_concept_id: number | null;
  label: string;
  properties: Record<string, unknown>;
  created_at: string;
}

export interface GraphEdge {
  id: string;
  patient_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  fact_id: string | null;
  properties: Record<string, unknown>;
  // Valid Time: When the clinical event happened
  event_date: string | null;
  valid_from: string | null;
  valid_to: string | null;
  // Transaction Time: Provenance
  recorded_at: string | null;
  source_document_date: string | null;
  // Temporal Assertion
  temporality: string | null; // "current", "past", "future"
  temporal_order: string | null;
  temporal_confidence: number | null;
  created_at: string;
}

export interface ClinicalFact {
  id: string;
  patient_id: string;
  domain: string;
  omop_concept_id: number;
  concept_name: string;
  assertion: string;
  temporality: string;
  experiencer: string;
  confidence: number;
  value: string | null;
  unit: string | null;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

export interface Mention {
  id: string;
  document_id: string;
  text: string;
  start_offset: number;
  end_offset: number;
  lexical_variant: string;
  section: string | null;
  assertion: string;
  temporality: string;
  experiencer: string;
  confidence: number;
  created_at: string;
}

export interface ExtractedMentionPreview {
  text: string;
  start_offset: number;
  end_offset: number;
  lexical_variant: string;
  section: string | null;
  assertion: string;
  temporality: string;
  experiencer: string;
  confidence: number;
  domain: string | null;
  omop_concept_id: number | null;
}

export interface ExtractPreviewResponse {
  mentions: ExtractedMentionPreview[];
  extraction_time_ms: number;
  mention_count: number;
}

export interface DashboardStats {
  total_documents: number;
  total_patients: number;
  total_facts: number;
  total_mentions: number;
  documents_by_status: Record<string, number>;
  documents_by_type: Record<string, number>;
  recent_documents: Document[];
  processing_queue_size: number;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

export interface FactFilterParams extends PaginationParams {
  domain?: string;
  assertion?: string;
}

// ============================================================================
// Error Handling
// ============================================================================

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
  }

  static isApiError(error: unknown): error is ApiError {
    return error instanceof ApiError;
  }
}

export class NetworkError extends Error {
  constructor(message: string, public originalError?: Error) {
    super(message);
    this.name = "NetworkError";
  }

  static isNetworkError(error: unknown): error is NetworkError {
    return error instanceof NetworkError;
  }
}

// ============================================================================
// Fetch Wrapper with Retry Logic
// ============================================================================

interface FetchOptions extends RequestInit {
  retries?: number;
  retryDelay?: number;
  timeout?: number;
}

const DEFAULT_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 1000;
const DEFAULT_TIMEOUT = 30000;

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableError(error: unknown): boolean {
  // Retry on network errors
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return true;
  }
  // Retry on API errors with 5xx status codes or rate limiting
  if (ApiError.isApiError(error)) {
    return error.status >= 500 || error.status === 429;
  }
  return false;
}

async function fetchWithRetry<T>(
  url: string,
  options: FetchOptions = {}
): Promise<T> {
  const {
    retries = DEFAULT_RETRIES,
    retryDelay = DEFAULT_RETRY_DELAY,
    timeout = DEFAULT_TIMEOUT,
    ...fetchOptions
  } = options;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        let errorDetails: Record<string, unknown> | undefined;

        try {
          const errorBody = await response.json();
          if (errorBody.detail) {
            errorMessage = errorBody.detail;
          }
          errorDetails = errorBody;
        } catch {
          // If we can't parse JSON, try text
          try {
            const errorText = await response.text();
            if (errorText) {
              errorMessage = errorText;
            }
          } catch {
            // Use default error message
          }
        }

        throw new ApiError(response.status, errorMessage, errorDetails);
      }

      // Handle empty responses
      const contentType = response.headers.get("content-type");
      if (contentType?.includes("application/json")) {
        return await response.json();
      }

      // For non-JSON responses, return empty object
      return {} as T;
    } catch (error) {
      lastError = error as Error;

      // Check if we should retry
      if (attempt < retries && isRetryableError(error)) {
        // Exponential backoff
        const delay = retryDelay * Math.pow(2, attempt);
        console.warn(
          `API request failed (attempt ${attempt + 1}/${retries + 1}), retrying in ${delay}ms:`,
          error
        );
        await sleep(delay);
        continue;
      }

      // Handle abort errors (timeout)
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new NetworkError(
          `Request timeout after ${timeout}ms`,
          error as Error
        );
      }

      // Re-throw non-retryable errors
      throw error;
    }
  }

  // Should not reach here, but just in case
  throw lastError || new Error("Unknown error during fetch");
}

// ============================================================================
// API Methods
// ============================================================================

// Documents
export async function uploadDocument(
  document: DocumentCreate
): Promise<DocumentUploadResponse> {
  return fetchWithRetry<DocumentUploadResponse>(`${API_BASE_URL}/documents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(document),
  });
}

export async function getDocument(documentId: string): Promise<Document> {
  return fetchWithRetry<Document>(`${API_BASE_URL}/documents/${documentId}`);
}

export async function getDocuments(
  params?: PaginationParams
): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", params.page.toString());
  if (params?.page_size) searchParams.append("page_size", params.page_size.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/documents${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<DocumentListResponse>(url);
}

export async function getDocumentMentions(
  documentId: string
): Promise<Mention[]> {
  return fetchWithRetry<Mention[]>(
    `${API_BASE_URL}/documents/${documentId}/mentions`
  );
}

export async function previewExtraction(
  text: string,
  noteType?: string
): Promise<ExtractPreviewResponse> {
  return fetchWithRetry<ExtractPreviewResponse>(
    `${API_BASE_URL}/documents/preview/extract`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        note_type: noteType,
      }),
    }
  );
}

// Jobs
export async function getJobStatus(jobId: string): Promise<JobInfo> {
  return fetchWithRetry<JobInfo>(`${API_BASE_URL}/jobs/${jobId}`);
}

export async function getJobs(params?: PaginationParams): Promise<JobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.append("limit", params.limit.toString());
  if (params?.offset) searchParams.append("offset", params.offset.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/jobs${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<JobListResponse>(url);
}

// Patients
export async function getPatients(
  params?: PaginationParams
): Promise<PatientListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", params.page.toString());
  if (params?.page_size) searchParams.append("page_size", params.page_size.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/patients${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<PatientListResponse>(url);
}

export async function getPatient(patientId: string): Promise<Patient> {
  return fetchWithRetry<Patient>(`${API_BASE_URL}/patients/${patientId}`);
}

export async function getPatientGraph(patientId: string): Promise<PatientGraph> {
  return fetchWithRetry<PatientGraph>(
    `${API_BASE_URL}/patients/${patientId}/graph`
  );
}

export async function buildPatientGraph(
  patientId: string
): Promise<PatientGraph> {
  return fetchWithRetry<PatientGraph>(
    `${API_BASE_URL}/patients/${patientId}/graph/build`,
    {
      method: "POST",
    }
  );
}

export async function getPatientFacts(
  patientId: string,
  options?: FactFilterParams
): Promise<ClinicalFact[]> {
  const params = new URLSearchParams();
  if (options?.domain) params.append("domain", options.domain);
  if (options?.assertion) params.append("assertion", options.assertion);
  if (options?.limit) params.append("limit", options.limit.toString());
  if (options?.offset) params.append("offset", options.offset.toString());

  const queryString = params.toString();
  const url = `${API_BASE_URL}/patients/${patientId}/facts${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<ClinicalFact[]>(url);
}

// Dashboard
export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchWithRetry<DashboardStats>(`${API_BASE_URL}/dashboard/stats`);
}

// Health check
export async function healthCheck(): Promise<{ status: string }> {
  return fetchWithRetry<{ status: string }>(`${API_BASE_URL}/health`);
}

// ============================================================================
// ETL Types
// ============================================================================

export interface ConnectorInfo {
  type: string;
  name: string;
  description: string;
  connection_string_hint: string;
  required_fields: string[];
  optional_fields: string[];
}

export interface ETLJobConfig {
  connector_type: string;
  connection_string: string;
  source_name: string;
  batch_size: number;
  max_records: number | null;
  patient_ids: string[] | null;
  start_date: string | null;
  end_date: string | null;
  skip_on_error: boolean;
  max_errors: number;
}

export interface ETLJobProgress {
  current_phase: string;
  phase_progress_percent: number;
  overall_progress_percent: number;
  records_in_phase: number;
  total_records_estimate: number;
  current_record_id: string | null;
  phases_completed: string[];
  eta_seconds: number | null;
}

export interface ETLJobStatistics {
  total_records: number;
  patients_processed: number;
  visits_processed: number;
  conditions_processed: number;
  drugs_processed: number;
  procedures_processed: number;
  measurements_processed: number;
  observations_processed: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  unmapped_codes: number;
  retries_performed: number;
}

export interface ETLJobError {
  timestamp: string;
  phase: string;
  record_id: string | null;
  error_type: string;
  error_message: string;
  is_retryable: boolean;
  retry_count: number;
}

export interface ETLJob {
  job_id: string;
  state: "pending" | "running" | "completed" | "failed" | "cancelled";
  config: ETLJobConfig;
  progress: ETLJobProgress;
  statistics: ETLJobStatistics;
  errors: ETLJobError[];
  warnings: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface ETLJobListResponse {
  jobs: ETLJob[];
  total: number;
}

export interface CreateETLJobRequest {
  connector_type: string;
  connection_string: string;
  source_name?: string;
  batch_size?: number;
  max_records?: number | null;
  patient_ids?: string[] | null;
  start_date?: string | null;
  end_date?: string | null;
  skip_on_error?: boolean;
  max_errors?: number;
  connector_options?: Record<string, unknown>;
  etl_options?: Record<string, unknown>;
}

export interface CreateETLJobResponse {
  job_id: string;
  state: string;
  message: string;
}

export interface CancelETLJobResponse {
  job_id: string;
  cancelled: boolean;
  message: string;
}

export interface DeleteETLJobResponse {
  job_id: string;
  deleted: boolean;
  message: string;
}

export interface ConnectorListResponse {
  connectors: ConnectorInfo[];
}

export interface ETLJobFilterParams {
  state?: string;
  limit?: number;
}

// ============================================================================
// ETL API Methods
// ============================================================================

// Get available ETL connectors
export async function getETLConnectors(): Promise<ConnectorListResponse> {
  return fetchWithRetry<ConnectorListResponse>(`${API_BASE_URL}/etl/connectors`);
}

// Create a new ETL job
export async function createETLJob(
  request: CreateETLJobRequest
): Promise<CreateETLJobResponse> {
  return fetchWithRetry<CreateETLJobResponse>(`${API_BASE_URL}/etl/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

// List ETL jobs
export async function getETLJobs(
  params?: ETLJobFilterParams
): Promise<ETLJobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.state) searchParams.append("state", params.state);
  if (params?.limit) searchParams.append("limit", params.limit.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/etl/jobs${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<ETLJobListResponse>(url);
}

// Get a specific ETL job
export async function getETLJob(jobId: string): Promise<ETLJob> {
  return fetchWithRetry<ETLJob>(`${API_BASE_URL}/etl/jobs/${jobId}`);
}

// Cancel an ETL job
export async function cancelETLJob(jobId: string): Promise<CancelETLJobResponse> {
  return fetchWithRetry<CancelETLJobResponse>(
    `${API_BASE_URL}/etl/jobs/${jobId}/cancel`,
    {
      method: "POST",
    }
  );
}

// Delete an ETL job
export async function deleteETLJob(jobId: string): Promise<DeleteETLJobResponse> {
  return fetchWithRetry<DeleteETLJobResponse>(
    `${API_BASE_URL}/etl/jobs/${jobId}`,
    {
      method: "DELETE",
    }
  );
}

// ============================================================================
// ETL Source Types
// ============================================================================

export interface SourceCredentials {
  username: string | null;
  password: string | null;
  api_key: string | null;
  client_id: string | null;
  client_secret: string | null;
  auth_token: string | null;
  extra: Record<string, string> | null;
}

export interface ConnectionParams {
  host: string | null;
  port: number | null;
  path: string | null;
  database: string | null;
  schema: string | null;
  ssl_enabled: boolean;
  verify_ssl: boolean;
  timeout_seconds: number;
  extra: Record<string, unknown>;
}

export interface Source {
  id: string;
  name: string;
  description: string;
  source_type: "fhir" | "hl7v2" | "ccda" | "csv" | "database";
  connection_params: ConnectionParams;
  credentials: SourceCredentials | null;
  status: "unknown" | "connected" | "disconnected" | "error" | "testing";
  enabled: boolean;
  last_tested_at: string | null;
  last_sync_at: string | null;
  test_result: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface SourceListResponse {
  sources: Source[];
  total: number;
}

export interface CreateSourceRequest {
  name: string;
  description?: string;
  source_type: string;
  connection_params: {
    host?: string;
    port?: number;
    path?: string;
    database?: string;
    schema?: string;
    ssl_enabled?: boolean;
    verify_ssl?: boolean;
    timeout_seconds?: number;
    extra?: Record<string, unknown>;
  };
  credentials?: {
    username?: string;
    password?: string;
    api_key?: string;
    client_id?: string;
    client_secret?: string;
    auth_token?: string;
    extra?: Record<string, string>;
  };
  metadata?: Record<string, unknown>;
}

export interface UpdateSourceRequest {
  name?: string;
  description?: string;
  connection_params?: {
    host?: string;
    port?: number;
    path?: string;
    database?: string;
    schema?: string;
    ssl_enabled?: boolean;
    verify_ssl?: boolean;
    timeout_seconds?: number;
    extra?: Record<string, unknown>;
  };
  credentials?: {
    username?: string;
    password?: string;
    api_key?: string;
    client_id?: string;
    client_secret?: string;
    auth_token?: string;
    extra?: Record<string, string>;
  };
  enabled?: boolean;
  metadata?: Record<string, unknown>;
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  latency_ms: number | null;
  server_info: Record<string, unknown>;
  error_details: string | null;
  tested_at: string;
}

export interface SampleDataResponse {
  source_id: string;
  record_count: number;
  records: Record<string, unknown>[];
  schema_info: Record<string, unknown>;
  fetched_at: string;
}

export interface SourceFilterParams {
  source_type?: string;
  enabled_only?: boolean;
  limit?: number;
}

// ============================================================================
// ETL Pipeline Types
// ============================================================================

export interface PipelineSchedule {
  frequency: "manual" | "hourly" | "daily" | "weekly" | "monthly" | "custom";
  cron_expression: string | null;
  time_of_day: string;
  day_of_week: number | null;
  day_of_month: number | null;
  timezone: string;
  enabled: boolean;
}

export interface PipelineStage {
  name: string;
  stage_type: string;
  config: Record<string, unknown>;
  order: number;
  enabled: boolean;
}

export interface PipelineRun {
  id: string;
  pipeline_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  records_processed: number;
  records_failed: number;
  error_message: string | null;
  duration_seconds: number | null;
}

export interface Pipeline {
  id: string;
  name: string;
  description: string;
  source_id: string;
  status: "active" | "paused" | "disabled" | "error";
  schedule: PipelineSchedule;
  stages: PipelineStage[];
  batch_size: number;
  max_records: number | null;
  skip_on_error: boolean;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  last_run_status: string | null;
  run_count: number;
}

export interface PipelineListResponse {
  pipelines: Pipeline[];
  total: number;
}

export interface PipelineRunListResponse {
  runs: PipelineRun[];
  total: number;
}

export interface CreatePipelineRequest {
  name: string;
  description?: string;
  source_id: string;
  schedule?: {
    frequency?: string;
    cron_expression?: string;
    time_of_day?: string;
    day_of_week?: number;
    day_of_month?: number;
    timezone?: string;
    enabled?: boolean;
  };
  stages?: {
    name: string;
    stage_type: string;
    config?: Record<string, unknown>;
    order?: number;
    enabled?: boolean;
  }[];
  batch_size?: number;
  max_records?: number;
  skip_on_error?: boolean;
}

export interface UpdatePipelineRequest {
  name?: string;
  description?: string;
  status?: string;
  schedule?: {
    frequency?: string;
    cron_expression?: string;
    time_of_day?: string;
    day_of_week?: number;
    day_of_month?: number;
    timezone?: string;
    enabled?: boolean;
  };
  stages?: {
    name: string;
    stage_type: string;
    config?: Record<string, unknown>;
    order?: number;
    enabled?: boolean;
  }[];
  batch_size?: number;
  max_records?: number;
  skip_on_error?: boolean;
}

export interface TriggerPipelineResponse {
  run_id: string;
  pipeline_id: string;
  status: string;
  message: string;
}

export interface PipelineFilterParams {
  source_id?: string;
  status?: string;
  limit?: number;
}

// ============================================================================
// ETL Source API Methods
// ============================================================================

// List data sources
export async function getSources(
  params?: SourceFilterParams
): Promise<SourceListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.source_type) searchParams.append("source_type", params.source_type);
  if (params?.enabled_only) searchParams.append("enabled_only", "true");
  if (params?.limit) searchParams.append("limit", params.limit.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/etl/sources${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<SourceListResponse>(url);
}

// Get a single source
export async function getSource(sourceId: string): Promise<Source> {
  return fetchWithRetry<Source>(`${API_BASE_URL}/etl/sources/${sourceId}`);
}

// Create a new source
export async function createSource(
  request: CreateSourceRequest
): Promise<Source> {
  return fetchWithRetry<Source>(`${API_BASE_URL}/etl/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Update a source
export async function updateSource(
  sourceId: string,
  request: UpdateSourceRequest
): Promise<Source> {
  return fetchWithRetry<Source>(`${API_BASE_URL}/etl/sources/${sourceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Delete a source
export async function deleteSource(sourceId: string): Promise<void> {
  return fetchWithRetry<void>(`${API_BASE_URL}/etl/sources/${sourceId}`, {
    method: "DELETE",
  });
}

// Test source connection
export async function testSourceConnection(
  sourceId: string
): Promise<ConnectionTestResponse> {
  return fetchWithRetry<ConnectionTestResponse>(
    `${API_BASE_URL}/etl/sources/${sourceId}/test`,
    { method: "POST" }
  );
}

// Get sample data from source
export async function getSourcePreview(
  sourceId: string,
  limit: number = 10
): Promise<SampleDataResponse> {
  return fetchWithRetry<SampleDataResponse>(
    `${API_BASE_URL}/etl/sources/${sourceId}/preview?limit=${limit}`
  );
}

// ============================================================================
// ETL Pipeline API Methods
// ============================================================================

// List pipelines
export async function getPipelines(
  params?: PipelineFilterParams
): Promise<PipelineListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.source_id) searchParams.append("source_id", params.source_id);
  if (params?.status) searchParams.append("pipeline_status", params.status);
  if (params?.limit) searchParams.append("limit", params.limit.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/etl/pipelines${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<PipelineListResponse>(url);
}

// Get a single pipeline
export async function getPipeline(pipelineId: string): Promise<Pipeline> {
  return fetchWithRetry<Pipeline>(`${API_BASE_URL}/etl/pipelines/${pipelineId}`);
}

// Create a new pipeline
export async function createPipeline(
  request: CreatePipelineRequest
): Promise<Pipeline> {
  return fetchWithRetry<Pipeline>(`${API_BASE_URL}/etl/pipelines`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Update a pipeline
export async function updatePipeline(
  pipelineId: string,
  request: UpdatePipelineRequest
): Promise<Pipeline> {
  return fetchWithRetry<Pipeline>(`${API_BASE_URL}/etl/pipelines/${pipelineId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Delete a pipeline
export async function deletePipeline(pipelineId: string): Promise<void> {
  return fetchWithRetry<void>(`${API_BASE_URL}/etl/pipelines/${pipelineId}`, {
    method: "DELETE",
  });
}

// Update pipeline schedule
export async function updatePipelineSchedule(
  pipelineId: string,
  schedule: {
    frequency?: string;
    cron_expression?: string;
    time_of_day?: string;
    day_of_week?: number;
    day_of_month?: number;
    timezone?: string;
    enabled?: boolean;
  }
): Promise<Pipeline> {
  return fetchWithRetry<Pipeline>(
    `${API_BASE_URL}/etl/pipelines/${pipelineId}/schedule`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schedule),
    }
  );
}

// Trigger a pipeline run
export async function triggerPipelineRun(
  pipelineId: string
): Promise<TriggerPipelineResponse> {
  return fetchWithRetry<TriggerPipelineResponse>(
    `${API_BASE_URL}/etl/pipelines/${pipelineId}/run`,
    { method: "POST" }
  );
}

// Get pipeline run history
export async function getPipelineRuns(
  pipelineId: string,
  limit: number = 20
): Promise<PipelineRunListResponse> {
  return fetchWithRetry<PipelineRunListResponse>(
    `${API_BASE_URL}/etl/pipelines/${pipelineId}/runs?limit=${limit}`
  );
}

// ============================================================================
// Clinical Note Generation Types
// ============================================================================

export type NoteType = "soap" | "hp" | "progress" | "discharge" | "procedure";
export type NoteStatus = "draft" | "complete" | "incomplete" | "needs_review";
export type ConfidenceLevel = "high" | "medium" | "low";
export type SectionStatus = "complete" | "partial" | "missing" | "generated" | "user_provided";
export type LLMProvider = "openai" | "anthropic";

export interface PatientDataInput {
  age?: number;
  sex?: "M" | "F" | "Other";
  chief_complaint?: string;
  history_present_illness?: string;
  past_medical_history?: string[];
  past_surgical_history?: string[];
  medications?: string[];
  allergies?: string[];
  social_history?: string;
  family_history?: string;
  review_of_systems?: Record<string, string>;
  vitals?: Record<string, string | number>;
}

export interface EncounterDataInput {
  encounter_type: string;
  encounter_date?: string;
  provider_type?: string;
  location?: string;
  physical_exam?: Record<string, string>;
  lab_results?: Record<string, string | number | Record<string, unknown>>;
  imaging_results?: Record<string, string>;
  diagnoses?: string[];
  icd10_codes?: string[];
  procedures_performed?: string[];
  cpt_codes?: string[];
  plan_items?: string[];
  interval_history?: string;
  hospital_course?: string;
  follow_up?: string[];
  procedure_name?: string;
  procedure_indication?: string;
  procedure_findings?: string;
  procedure_complications?: string;
  estimated_blood_loss?: string;
  specimens?: string[];
}

export interface NoteGenerationRequest {
  note_type: NoteType;
  patient_data: PatientDataInput;
  encounter_data: EncounterDataInput;
  template_id?: string;
  custom_instructions?: string;
  include_codes?: boolean;
  provider?: LLMProvider;
  model?: string;
}

export interface NoteSectionResponse {
  name: string;
  key: string;
  content: string;
  required: boolean;
  order: number;
  status: SectionStatus;
  word_count: number;
  warnings: string[];
}

export interface NoteValidationResponse {
  is_valid: boolean;
  completeness_score: number;
  missing_sections: string[];
  incomplete_sections: string[];
  warnings: string[];
  suggestions: string[];
}

export interface GeneratedNoteResponse {
  request_id: string;
  note_id: string;
  note_type: NoteType;
  content: string;
  sections: NoteSectionResponse[];
  status: NoteStatus;
  confidence: ConfidenceLevel;
  generated_at: string;
  template_id?: string;
  model_used: string;
  token_usage: number;
  cost_usd: number;
  latency_ms: number;
  validation?: NoteValidationResponse;
  warnings: string[];
}

export interface NoteSectionTemplate {
  name: string;
  key: string;
  required: boolean;
  order: number;
  subsections: string[];
}

export interface NoteTemplate {
  template_id: string;
  note_type: NoteType;
  name: string;
  description: string;
  sections: NoteSectionTemplate[];
}

export interface NoteTemplatesListResponse {
  templates: NoteTemplate[];
  total: number;
}

export interface NoteEnhanceRequest {
  content: string;
  note_type: NoteType;
  patient_data?: PatientDataInput;
  encounter_data?: EncounterDataInput;
  provider?: LLMProvider;
  model?: string;
}

export interface NoteEnhanceResponse {
  request_id: string;
  enhanced_content: string;
  original_word_count: number;
  enhanced_word_count: number;
  sections_enhanced: string[];
  sections_added: string[];
  confidence: ConfidenceLevel;
  token_usage: number;
  cost_usd: number;
  latency_ms: number;
  warnings: string[];
}

export interface NoteValidateRequest {
  content: string;
  note_type: NoteType;
  provider?: LLMProvider;
  model?: string;
}

export interface NoteServiceStats {
  total_notes_generated: number;
  total_tokens_used: number;
  total_cost_usd: number;
  available_templates: number;
}

// Patient Summary Types
export interface PatientFactInput {
  fact_id: string;
  fact_type: string;
  description: string;
  code?: string;
  code_system?: string;
  value?: string;
  unit?: string;
  date?: string;
  status?: string;
  source_document_id?: string;
  confidence?: number;
}

export interface PatientSummaryRequest {
  patient_id: string;
  facts: PatientFactInput[];
  focus_areas?: string[];
  max_length?: number;
  include_citations?: boolean;
  provider?: LLMProvider;
  model?: string;
}

export interface FactCitation {
  text_span: string;
  fact_id: string;
  fact_type: string;
  source_description: string;
}

export interface PatientSummaryResponse {
  summary_id: string;
  patient_id: string;
  content: string;
  sections: Record<string, string>;
  citations: FactCitation[];
  generated_at: string;
  focus_areas: string[];
  fact_count: number;
  model_used: string;
  token_usage: number;
  cost_usd: number;
  latency_ms: number;
  confidence: ConfidenceLevel;
}

// Note History Types
export interface NoteHistoryEntry {
  note_id: string;
  note_type: NoteType;
  patient_id?: string;
  template_id?: string;
  status: NoteStatus;
  generated_at: string;
  model_used: string;
  token_usage: number;
  cost_usd: number;
  preview: string;
}

export interface NoteHistoryResponse {
  history: NoteHistoryEntry[];
  total: number;
}

// Template Customization Types
export interface SectionTemplateInput {
  name: string;
  key: string;
  required?: boolean;
  order?: number;
  prompt_hint?: string;
  subsections?: string[];
}

export interface TemplateCustomizationRequest {
  base_template_id: string;
  new_template_id: string;
  name: string;
  description?: string;
  sections_to_add?: SectionTemplateInput[];
  sections_to_remove?: string[];
  section_order?: string[];
  custom_prompts?: Record<string, string>;
}

// Note Type Info
export interface NoteTypeInfo {
  type: NoteType;
  name: string;
  description: string;
  typical_use: string;
}

export interface NoteTypesResponse {
  note_types: NoteTypeInfo[];
}

// ============================================================================
// Clinical Note Generation API Methods
// ============================================================================

// Generate a clinical note
export async function generateNote(
  request: NoteGenerationRequest
): Promise<GeneratedNoteResponse> {
  return fetchWithRetry<GeneratedNoteResponse>(`${API_BASE_URL}/notes/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 120000, // 2 minute timeout for AI generation
  });
}

// List available note templates
export async function getNoteTemplates(
  noteType?: NoteType
): Promise<NoteTemplatesListResponse> {
  const params = new URLSearchParams();
  if (noteType) params.append("note_type", noteType);
  const queryString = params.toString();
  const url = `${API_BASE_URL}/notes/templates${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<NoteTemplatesListResponse>(url);
}

// Get a specific template
export async function getNoteTemplate(templateId: string): Promise<NoteTemplate> {
  return fetchWithRetry<NoteTemplate>(`${API_BASE_URL}/notes/templates/${templateId}`);
}

// Enhance a partial note
export async function enhanceNote(
  request: NoteEnhanceRequest
): Promise<NoteEnhanceResponse> {
  return fetchWithRetry<NoteEnhanceResponse>(`${API_BASE_URL}/notes/enhance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 120000,
  });
}

// Validate a note
export async function validateNote(
  request: NoteValidateRequest
): Promise<NoteValidationResponse> {
  return fetchWithRetry<NoteValidationResponse>(`${API_BASE_URL}/notes/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 60000,
  });
}

// Get note generation stats
export async function getNoteStats(): Promise<NoteServiceStats> {
  return fetchWithRetry<NoteServiceStats>(`${API_BASE_URL}/notes/stats`);
}

// Get supported note types
export async function getNoteTypes(): Promise<NoteTypesResponse> {
  return fetchWithRetry<NoteTypesResponse>(`${API_BASE_URL}/notes/note-types`);
}

// Generate patient summary
export async function generatePatientSummary(
  request: PatientSummaryRequest
): Promise<PatientSummaryResponse> {
  return fetchWithRetry<PatientSummaryResponse>(`${API_BASE_URL}/notes/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 120000,
  });
}

// Get note generation history
export async function getNoteHistory(params?: {
  limit?: number;
  note_type?: NoteType;
  patient_id?: string;
}): Promise<NoteHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.append("limit", params.limit.toString());
  if (params?.note_type) searchParams.append("note_type", params.note_type);
  if (params?.patient_id) searchParams.append("patient_id", params.patient_id);
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/notes/history${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<NoteHistoryResponse>(url);
}

// Customize a template
export async function customizeNoteTemplate(
  templateId: string,
  request: TemplateCustomizationRequest
): Promise<NoteTemplate> {
  return fetchWithRetry<NoteTemplate>(`${API_BASE_URL}/notes/templates/${templateId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// ============================================================================
// Cohort Builder Types and API Functions
// ============================================================================

// Enums
export type CohortStatus = "draft" | "active" | "archived";
export type LogicOperator = "AND" | "OR" | "NOT";
export type TemporalOperator = "before" | "after" | "during" | "within" | "overlaps";
export type CriterionType = "demographic" | "condition" | "drug" | "procedure" | "measurement" | "visit";
export type Gender = "male" | "female" | "other" | "unknown";
export type Race = "white" | "black" | "asian" | "native_american" | "pacific_islander" | "other" | "unknown";
export type Ethnicity = "hispanic" | "non_hispanic" | "unknown";
export type VisitType = "inpatient" | "outpatient" | "emergency" | "long_term_care" | "telehealth" | "home_health";

// Base criterion interface
export interface BaseCriterion {
  id: string;
  type: CriterionType;
  name: string;
  description?: string;
  exclude?: boolean;
}

// Demographic criterion
export interface DemographicCriterion extends BaseCriterion {
  type: "demographic";
  age_min?: number;
  age_max?: number;
  gender?: Gender[];
  race?: Race[];
  ethnicity?: Ethnicity[];
}

// Condition criterion
export interface ConditionCriterion extends BaseCriterion {
  type: "condition";
  concept_ids?: number[];
  concept_codes?: string[];
  vocabulary_id?: string;
  include_descendants?: boolean;
  start_date?: string;
  end_date?: string;
  min_occurrences?: number;
  condition_status?: string[];
}

// Drug criterion
export interface DrugCriterion extends BaseCriterion {
  type: "drug";
  concept_ids?: number[];
  concept_codes?: string[];
  vocabulary_id?: string;
  include_descendants?: boolean;
  start_date?: string;
  end_date?: string;
  min_days_supply?: number;
  max_days_supply?: number;
  min_quantity?: number;
  route?: string[];
}

// Procedure criterion
export interface ProcedureCriterion extends BaseCriterion {
  type: "procedure";
  concept_ids?: number[];
  concept_codes?: string[];
  vocabulary_id?: string;
  include_descendants?: boolean;
  start_date?: string;
  end_date?: string;
  min_occurrences?: number;
  modifier?: string[];
}

// Measurement criterion
export interface MeasurementCriterion extends BaseCriterion {
  type: "measurement";
  concept_ids?: number[];
  concept_codes?: string[];
  vocabulary_id?: string;
  value_as_number_min?: number;
  value_as_number_max?: number;
  value_as_concept_id?: number;
  operator?: "eq" | "lt" | "le" | "gt" | "ge" | "between";
  unit_concept_id?: number;
  start_date?: string;
  end_date?: string;
  abnormal_only?: boolean;
}

// Visit criterion
export interface VisitCriterion extends BaseCriterion {
  type: "visit";
  visit_type?: VisitType[];
  start_date?: string;
  end_date?: string;
  min_length_of_stay?: number;
  max_length_of_stay?: number;
  min_visits?: number;
  care_site_id?: number;
  provider_id?: number;
}

// Union type for all criteria
export type AnyCriterion =
  | DemographicCriterion
  | ConditionCriterion
  | DrugCriterion
  | ProcedureCriterion
  | MeasurementCriterion
  | VisitCriterion;

// Temporal constraint
export interface TemporalConstraint {
  operator: TemporalOperator;
  reference_criterion_id: string;
  days_before?: number;
  days_after?: number;
  index_date_field?: string;
}

// Criteria group for complex logic
export interface CriteriaGroup {
  id: string;
  operator: LogicOperator;
  criteria: (AnyCriterion | CriteriaGroup)[];
  temporal_constraint?: TemporalConstraint;
}

// Cohort definition
export interface CohortDefinition {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  status: CohortStatus;
  inclusion_criteria: CriteriaGroup;
  exclusion_criteria?: CriteriaGroup;
  index_date_criterion_id?: string;
  observation_period_days?: number;
  created_at: string;
  updated_at: string;
  version: number;
  patient_count?: number;
  last_executed?: string;
  tags?: string[];
}

// Cohort summary (for list views)
export interface CohortSummary {
  id: string;
  name: string;
  description?: string;
  status: CohortStatus;
  patient_count?: number;
  criteria_count: number;
  created_at: string;
  updated_at: string;
  owner_id: string;
  tags?: string[];
}

// Cohort count result
export interface CohortCountResult {
  cohort_id: string;
  count: number;
  execution_time_ms: number;
  cached: boolean;
  criteria_breakdown?: Record<string, number>;
}

// Cohort execution result
export interface CohortExecutionResult {
  cohort_id: string;
  patient_ids: string[];
  total_count: number;
  execution_time_ms: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// Demographic breakdown
export interface DemographicBreakdown {
  cohort_id: string;
  total_patients: number;
  age_distribution: {
    range: string;
    count: number;
    percentage: number;
  }[];
  gender_distribution: {
    gender: string;
    count: number;
    percentage: number;
  }[];
  race_distribution: {
    race: string;
    count: number;
    percentage: number;
  }[];
  ethnicity_distribution: {
    ethnicity: string;
    count: number;
    percentage: number;
  }[];
}

// Cohort comparison result
export interface CohortComparisonResult {
  cohort_a_id: string;
  cohort_b_id: string;
  cohort_a_count: number;
  cohort_b_count: number;
  intersection_count: number;
  union_count: number;
  cohort_a_only: number;
  cohort_b_only: number;
  jaccard_similarity: number;
  demographics_comparison: {
    cohort_a: DemographicBreakdown;
    cohort_b: DemographicBreakdown;
  };
  condition_comparison?: {
    concept_id: number;
    concept_name: string;
    cohort_a_count: number;
    cohort_a_percentage: number;
    cohort_b_count: number;
    cohort_b_percentage: number;
    difference: number;
  }[];
  drug_comparison?: {
    concept_id: number;
    concept_name: string;
    cohort_a_count: number;
    cohort_a_percentage: number;
    cohort_b_count: number;
    cohort_b_percentage: number;
    difference: number;
  }[];
}

// Cohort version history
export interface CohortVersion {
  version: number;
  created_at: string;
  created_by: string;
  changes_summary: string;
  patient_count?: number;
}

// Saved criterion for criteria library
export interface SavedCriterion {
  id: string;
  name: string;
  description?: string;
  criterion: AnyCriterion;
  category: string;
  usage_count: number;
  created_by: string;
  created_at: string;
  is_public: boolean;
  tags?: string[];
}

// Criteria library response
export interface CriteriaLibraryResponse {
  criteria: SavedCriterion[];
  total: number;
  categories: string[];
}

// Cohort list response
export interface CohortListResponse {
  cohorts: CohortSummary[];
  total: number;
  page: number;
  page_size: number;
}

// Create/Update cohort request
export interface CohortRequest {
  name: string;
  description?: string;
  status?: CohortStatus;
  inclusion_criteria: CriteriaGroup;
  exclusion_criteria?: CriteriaGroup;
  index_date_criterion_id?: string;
  observation_period_days?: number;
  tags?: string[];
}

// Export options
export interface CohortExportOptions {
  format: "json" | "sql" | "csv";
  include_patients?: boolean;
  include_demographics?: boolean;
}

// ============================================================================
// Cohort API Functions
// ============================================================================

// List cohorts with optional filters
export async function fetchCohorts(params?: {
  page?: number;
  page_size?: number;
  status?: CohortStatus;
  search?: string;
  owner_id?: string;
  tags?: string[];
}): Promise<CohortListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", params.page.toString());
  if (params?.page_size) searchParams.append("page_size", params.page_size.toString());
  if (params?.status) searchParams.append("status", params.status);
  if (params?.search) searchParams.append("search", params.search);
  if (params?.owner_id) searchParams.append("owner_id", params.owner_id);
  if (params?.tags) params.tags.forEach(tag => searchParams.append("tags", tag));
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/cohorts${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<CohortListResponse>(url);
}

// Get a single cohort by ID
export async function getCohort(id: string): Promise<CohortDefinition> {
  return fetchWithRetry<CohortDefinition>(`${API_BASE_URL}/cohorts/${id}`);
}

// Create a new cohort
export async function createCohort(request: CohortRequest): Promise<CohortDefinition> {
  return fetchWithRetry<CohortDefinition>(`${API_BASE_URL}/cohorts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Update an existing cohort
export async function updateCohort(id: string, request: Partial<CohortRequest>): Promise<CohortDefinition> {
  return fetchWithRetry<CohortDefinition>(`${API_BASE_URL}/cohorts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Delete a cohort
export async function deleteCohort(id: string): Promise<{ success: boolean; message: string }> {
  return fetchWithRetry<{ success: boolean; message: string }>(`${API_BASE_URL}/cohorts/${id}`, {
    method: "DELETE",
  });
}

// Get cohort patient count
export async function getCohortCount(id: string, useCache?: boolean): Promise<CohortCountResult> {
  const searchParams = new URLSearchParams();
  if (useCache !== undefined) searchParams.append("use_cache", useCache.toString());
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/cohorts/${id}/count${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<CohortCountResult>(url, {
    method: "POST",
    timeout: 60000, // Longer timeout for count queries
  });
}

// Execute cohort and get patient list
export async function executeCohort(
  id: string,
  params?: { page?: number; page_size?: number }
): Promise<CohortExecutionResult> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", params.page.toString());
  if (params?.page_size) searchParams.append("page_size", params.page_size.toString());
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/cohorts/${id}/execute${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<CohortExecutionResult>(url, {
    method: "POST",
    timeout: 120000, // Longer timeout for execution
  });
}

// Get cohort demographics breakdown
export async function getCohortDemographics(id: string): Promise<DemographicBreakdown> {
  return fetchWithRetry<DemographicBreakdown>(`${API_BASE_URL}/cohorts/${id}/demographics`);
}

// Compare two cohorts
export async function compareCohorts(
  cohortAId: string,
  cohortBId: string,
  options?: { include_conditions?: boolean; include_drugs?: boolean }
): Promise<CohortComparisonResult> {
  const searchParams = new URLSearchParams();
  searchParams.append("cohort_b_id", cohortBId);
  if (options?.include_conditions !== undefined) {
    searchParams.append("include_conditions", options.include_conditions.toString());
  }
  if (options?.include_drugs !== undefined) {
    searchParams.append("include_drugs", options.include_drugs.toString());
  }
  const url = `${API_BASE_URL}/cohorts/${cohortAId}/compare?${searchParams.toString()}`;
  return fetchWithRetry<CohortComparisonResult>(url, {
    method: "POST",
    timeout: 120000, // Longer timeout for comparison
  });
}

// Get cohort version history
export async function getCohortVersions(id: string): Promise<{ versions: CohortVersion[] }> {
  return fetchWithRetry<{ versions: CohortVersion[] }>(`${API_BASE_URL}/cohorts/${id}/versions`);
}

// Export cohort
export async function exportCohort(
  id: string,
  options: CohortExportOptions
): Promise<{ data: string; filename: string; content_type: string }> {
  const searchParams = new URLSearchParams();
  searchParams.append("format", options.format);
  if (options.include_patients !== undefined) {
    searchParams.append("include_patients", options.include_patients.toString());
  }
  if (options.include_demographics !== undefined) {
    searchParams.append("include_demographics", options.include_demographics.toString());
  }
  const url = `${API_BASE_URL}/cohorts/${id}/export?${searchParams.toString()}`;
  return fetchWithRetry<{ data: string; filename: string; content_type: string }>(url, {
    method: "POST",
  });
}

// Clone a cohort
export async function cloneCohort(id: string, newName?: string): Promise<CohortDefinition> {
  const body = newName ? { name: newName } : {};
  return fetchWithRetry<CohortDefinition>(`${API_BASE_URL}/cohorts/${id}/clone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// Get criteria library
export async function getCriteriaLibrary(params?: {
  category?: string;
  search?: string;
  is_public?: boolean;
}): Promise<CriteriaLibraryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.append("category", params.category);
  if (params?.search) searchParams.append("search", params.search);
  if (params?.is_public !== undefined) searchParams.append("is_public", params.is_public.toString());
  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/cohorts/criteria-library${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<CriteriaLibraryResponse>(url);
}

// Save criterion to library
export async function saveCriterionToLibrary(
  criterion: AnyCriterion,
  metadata: {
    name: string;
    description?: string;
    category: string;
    is_public?: boolean;
    tags?: string[];
  }
): Promise<SavedCriterion> {
  return fetchWithRetry<SavedCriterion>(`${API_BASE_URL}/cohorts/criteria-library`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ criterion, ...metadata }),
  });
}

// Preview cohort count (for real-time builder)
export async function previewCohortCount(
  criteria: CriteriaGroup,
  exclusion?: CriteriaGroup
): Promise<{ count: number; execution_time_ms: number }> {
  return fetchWithRetry<{ count: number; execution_time_ms: number }>(
    `${API_BASE_URL}/cohorts/preview/count`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inclusion_criteria: criteria, exclusion_criteria: exclusion }),
      timeout: 30000,
    }
  );
}

// Get SQL preview for cohort definition
export async function getCohortSQLPreview(
  criteria: CriteriaGroup,
  exclusion?: CriteriaGroup
): Promise<{ sql: string; parameters: Record<string, unknown> }> {
  return fetchWithRetry<{ sql: string; parameters: Record<string, unknown> }>(
    `${API_BASE_URL}/cohorts/preview/sql`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inclusion_criteria: criteria, exclusion_criteria: exclusion }),
    }
  );
}

// ============================================================================
// Job Queue Types
// ============================================================================

export type QueueJobStatus = "pending" | "queued" | "running" | "completed" | "failed" | "cancelled" | "retrying";
export type JobPriority = "low" | "normal" | "high" | "critical";
export type WorkerState = "idle" | "busy" | "offline" | "draining";

export interface QueueStats {
  pending_count: number;
  queued_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
  cancelled_count: number;
  total_count: number;
  avg_wait_time_seconds: number;
  avg_processing_time_seconds: number;
  throughput_per_minute: number;
  oldest_pending_job_age_seconds: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
}

export interface QueueDepthPoint {
  timestamp: string;
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

export interface QueueDepthResponse {
  history: QueueDepthPoint[];
  hours: number;
}

export interface ProcessingRate {
  jobs_per_minute: number;
  jobs_per_hour: number;
  avg_duration_seconds: number;
  success_rate: number;
  error_rate: number;
  trend: "increasing" | "decreasing" | "stable";
}

export interface WorkerStatus {
  worker_id: string;
  name: string;
  state: WorkerState;
  current_job_id: string | null;
  current_job_type: string | null;
  jobs_completed: number;
  jobs_failed: number;
  started_at: string;
  last_heartbeat: string;
  avg_processing_time_seconds: number;
  memory_usage_mb: number;
  cpu_usage_percent: number;
}

export interface WorkerListResponse {
  workers: WorkerStatus[];
  total: number;
}

export interface QueueJob {
  id: string;
  job_type: string;
  status: QueueJobStatus;
  priority: JobPriority;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  worker_id: string | null;
  error: string | null;
  retry_count: number;
  max_retries: number;
  position_in_queue: number | null;
  estimated_duration_seconds: number | null;
}

export interface QueueJobListResponse {
  jobs: QueueJob[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobEstimate {
  job_id: string;
  status: string;
  position_in_queue: number | null;
  started_at: string | null;
  elapsed_seconds: number | null;
  estimated_wait_seconds: number | null;
  estimated_remaining_seconds: number | null;
  estimated_completion: string | null;
}

export interface RetryAttempt {
  attempt_number: number;
  timestamp: string;
  error: string;
  worker_id: string | null;
  duration_seconds: number | null;
}

export interface RetryHistoryResponse {
  job_id: string;
  retry_count: number;
  max_retries: number;
  attempts: RetryAttempt[];
}

export interface WaitTimeEstimate {
  job_type: string;
  estimated_wait_seconds: number;
  estimated_wait_formatted: string;
}

export interface BulkActionResponse {
  succeeded: number;
  failed: number;
  jobs: QueueJob[];
}

export interface JobQueueFilterParams {
  status?: QueueJobStatus;
  job_type?: string;
  priority?: JobPriority;
  page?: number;
  page_size?: number;
}

// ============================================================================
// Job Queue API Functions
// ============================================================================

// Get queue statistics
export async function getQueueStats(): Promise<QueueStats> {
  return fetchWithRetry<QueueStats>(`${API_BASE_URL}/jobs/queue/stats`);
}

// Get queue depth history
export async function getQueueDepth(hours: number = 24): Promise<QueueDepthResponse> {
  return fetchWithRetry<QueueDepthResponse>(`${API_BASE_URL}/jobs/queue/depth?hours=${hours}`);
}

// Get processing rate
export async function getProcessingRate(): Promise<ProcessingRate> {
  return fetchWithRetry<ProcessingRate>(`${API_BASE_URL}/jobs/queue/rate`);
}

// Get worker status
export async function getWorkers(): Promise<WorkerListResponse> {
  return fetchWithRetry<WorkerListResponse>(`${API_BASE_URL}/jobs/queue/workers`);
}

// Get wait time estimate for job type
export async function getWaitTimeEstimate(jobType: string): Promise<WaitTimeEstimate> {
  return fetchWithRetry<WaitTimeEstimate>(`${API_BASE_URL}/jobs/queue/estimate/${encodeURIComponent(jobType)}`);
}

// List queue jobs with filtering
export async function getQueueJobs(params?: JobQueueFilterParams): Promise<QueueJobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.append("status", params.status);
  if (params?.job_type) searchParams.append("job_type", params.job_type);
  if (params?.priority) searchParams.append("priority", params.priority);
  if (params?.page) searchParams.append("page", params.page.toString());
  if (params?.page_size) searchParams.append("page_size", params.page_size.toString());

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/jobs/list${queryString ? `?${queryString}` : ""}`;
  return fetchWithRetry<QueueJobListResponse>(url);
}

// Get job estimate
export async function getJobEstimate(jobId: string): Promise<JobEstimate> {
  return fetchWithRetry<JobEstimate>(`${API_BASE_URL}/jobs/${jobId}/estimate`);
}

// Retry a failed job
export async function retryQueueJob(jobId: string): Promise<QueueJob> {
  return fetchWithRetry<QueueJob>(`${API_BASE_URL}/jobs/${jobId}/retry`, {
    method: "POST",
  });
}

// Cancel a job
export async function cancelQueueJob(jobId: string): Promise<QueueJob> {
  return fetchWithRetry<QueueJob>(`${API_BASE_URL}/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

// Get retry history for a job
export async function getRetryHistory(jobId: string): Promise<RetryHistoryResponse> {
  return fetchWithRetry<RetryHistoryResponse>(`${API_BASE_URL}/jobs/${jobId}/retries`);
}

// Retry all failed jobs
export async function retryAllFailedJobs(): Promise<BulkActionResponse> {
  return fetchWithRetry<BulkActionResponse>(`${API_BASE_URL}/jobs/bulk/retry`, {
    method: "POST",
  });
}

// Cancel selected jobs
export async function cancelSelectedJobs(jobIds: string[]): Promise<BulkActionResponse> {
  return fetchWithRetry<BulkActionResponse>(`${API_BASE_URL}/jobs/bulk/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

// ============================================================================
// Synthetic Data Types
// ============================================================================

export interface SyntheticTemplate {
  template_id: string;
  name: string;
  description: string;
  patient_count: number;
  has_privacy_config: boolean;
}

export interface SyntheticTemplateListResponse {
  templates: SyntheticTemplate[];
  total: number;
}

export interface SyntheticStats {
  total_patients_generated: number;
  total_jobs: number;
  completed_jobs: number;
  available_templates: number;
  default_conditions: number;
  default_medications: number;
  default_labs: number;
}

export interface SyntheticJob {
  job_id: string;
  status: string;
  progress_percent: number;
  patients_generated: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  result_path: string | null;
}

export interface SyntheticGenerateResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface AgeDistributionRequest {
  min_age: number;
  max_age: number;
  mean_age: number;
  std_dev: number;
}

export interface GenderDistributionRequest {
  male_ratio: number;
  female_ratio: number;
  other_ratio: number;
}

export interface PrivacyConfigRequest {
  epsilon: number;
  delta: number;
  k_anonymity: number;
  l_diversity: number;
  t_closeness: number;
}

export interface SyntheticGenerateRequest {
  patient_count: number;
  output_format?: string;
  template_id?: string;
  age_distribution?: AgeDistributionRequest;
  gender_distribution?: GenderDistributionRequest;
  privacy_config?: PrivacyConfigRequest;
  seed?: number;
}

export interface SyntheticPreviewResponse {
  patient_count: number;
  preview: SyntheticPatientPreview[];
}

export interface SyntheticPatientPreview {
  patient_id: string;
  gender: string;
  race: string;
  ethnicity: string;
  age: number;
  birth_date: string;
  conditions: { code: string; name: string }[];
  medications: { code: string; name: string }[];
  observation_count: number;
  encounter_count: number;
}

export interface ValidationReportResponse {
  generated_at: string;
  synthetic_row_count: number;
  real_row_count: number;
  overall_score: number;
  passed: boolean;
  metrics: ValidationMetric[];
}

export interface ValidationMetric {
  metric_name: string;
  column: string | null;
  expected_value: number;
  actual_value: number;
  passed: boolean;
  message: string;
}

export interface PrivacyReportResponse {
  generated_at: string;
  epsilon: number;
  delta: number;
  k_anonymity_satisfied: boolean;
  actual_k: number;
  l_diversity_satisfied: boolean;
  actual_l: number;
  t_closeness_satisfied: boolean;
  actual_t: number;
  privacy_score: number;
  utility_score: number;
  recommendations: string[];
}

// ============================================================================
// Synthetic Data API Functions
// ============================================================================

// Get available templates
export async function getSyntheticTemplates(): Promise<SyntheticTemplateListResponse> {
  return fetchWithRetry<SyntheticTemplateListResponse>(`${API_BASE_URL}/synthetic/templates`);
}

// Get service statistics
export async function getSyntheticStats(): Promise<SyntheticStats> {
  return fetchWithRetry<SyntheticStats>(`${API_BASE_URL}/synthetic/stats`);
}

// Start synthetic data generation
export async function generateSyntheticData(request: SyntheticGenerateRequest): Promise<SyntheticGenerateResponse> {
  return fetchWithRetry<SyntheticGenerateResponse>(`${API_BASE_URL}/synthetic/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Get job status
export async function getSyntheticJobStatus(jobId: string): Promise<SyntheticJob> {
  return fetchWithRetry<SyntheticJob>(`${API_BASE_URL}/synthetic/jobs/${jobId}`);
}

// Preview synthetic data
export async function previewSyntheticData(
  patientCount: number = 10,
  templateId?: string
): Promise<SyntheticPreviewResponse> {
  const params = new URLSearchParams({ patient_count: patientCount.toString() });
  if (templateId) {
    params.append("template_id", templateId);
  }
  return fetchWithRetry<SyntheticPreviewResponse>(`${API_BASE_URL}/synthetic/preview?${params}`);
}

// Download generated data
export async function downloadSyntheticData(jobId: string, format: string = "fhir_json"): Promise<void> {
  const url = `${API_BASE_URL}/synthetic/jobs/${jobId}/download?format=${format}`;

  // Use a direct download via anchor element
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Download failed: ${response.statusText}`);
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;

  // Extract filename from content-disposition or use default
  const contentDisposition = response.headers.get("content-disposition");
  let filename = `synthetic_data_${jobId}.json`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename=([^;]+)/);
    if (match) {
      filename = match[1].replace(/"/g, "");
    }
  } else if (format === "csv") {
    filename = `synthetic_data_${jobId}.csv`;
  }

  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(downloadUrl);
}

// Get template details
export async function getSyntheticTemplateDetails(templateId: string): Promise<Record<string, unknown>> {
  return fetchWithRetry<Record<string, unknown>>(`${API_BASE_URL}/synthetic/templates/${templateId}`);
}

// Get default conditions
export async function getDefaultConditions(): Promise<{ conditions: unknown[]; total: number }> {
  return fetchWithRetry<{ conditions: unknown[]; total: number }>(`${API_BASE_URL}/synthetic/default-conditions`);
}

// Get default medications
export async function getDefaultMedications(): Promise<{ medications: unknown[]; total: number }> {
  return fetchWithRetry<{ medications: unknown[]; total: number }>(`${API_BASE_URL}/synthetic/default-medications`);
}

// Get default labs
export async function getDefaultLabs(): Promise<{ labs: unknown[]; total: number }> {
  return fetchWithRetry<{ labs: unknown[]; total: number }>(`${API_BASE_URL}/synthetic/default-labs`);
}

// ============================================================================
// Semantic Search Types
// ============================================================================

export type SemanticMatchType = "exact" | "synonym" | "fuzzy" | "semantic" | "hierarchy" | "crosswalk";

export interface SemanticSearchResult {
  concept_id: number;
  concept_code: string;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  score: number;
  match_type: SemanticMatchType;
  matched_term: string | null;
  explanation: string | null;
  synonyms: string[];
  crosswalk: Record<string, unknown[]>;
}

export interface SemanticSearchRequest {
  query: string;
  vocabularies?: string[];
  domains?: string[];
  top_k?: number;
  threshold?: number;
  include_fuzzy?: boolean;
  expand_query?: boolean;
}

export interface SemanticSearchResponse {
  query: string;
  expanded_queries: string[];
  results: SemanticSearchResult[];
  total: number;
  vocabularies_searched: string[];
  search_time_ms: number;
}

export interface SimilarConceptsRequest {
  concept_id: number;
  vocabularies?: string[];
  top_k?: number;
  threshold?: number;
}

export interface SimilarConceptsResponse {
  source_concept_id: number;
  source_concept_name: string;
  results: SemanticSearchResult[];
  total: number;
}

export interface CrosswalkMapping {
  source_concept_id: number;
  source_vocabulary: string;
  source_code: string;
  source_name: string;
  target_concept_id: number;
  target_vocabulary: string;
  target_code: string;
  target_name: string;
  mapping_type: string;
  confidence: number;
}

export interface CrosswalkRequest {
  concept_id: number;
  target_vocabulary: string;
}

export interface CrosswalkResponse {
  source_concept_id: number;
  source_vocabulary: string;
  source_name: string;
  target_vocabulary: string;
  mappings: CrosswalkMapping[];
  total: number;
}

export interface SearchSuggestion {
  concept_id: number;
  concept_code: string;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  display: string;
}

export interface SuggestionsResponse {
  prefix: string;
  suggestions: SearchSuggestion[];
  total: number;
}

export interface ClusterResult {
  cluster_id: string;
  cluster_name: string;
  concept_type: string;
  results: SemanticSearchResult[];
  total_count: number;
}

export interface ClusterResponse {
  clusters: ClusterResult[];
  total_clusters: number;
  total_results: number;
}

export interface SemanticSearchStats {
  total_concepts: number;
  vocabularies: Record<string, number>;
  domains: Record<string, number>;
  unique_codes: number;
  indexed_synonyms: number;
  load_time_ms: number;
}

export interface ConceptDetails {
  concept_id: number;
  concept_code: string;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  concept_class_id: string | null;
  standard_concept: string | null;
  synonyms: string[];
  semantic_type: string | null;
  parents: number[];
  children: number[];
  crosswalk_mappings: Record<string, number[]>;
}

// ============================================================================
// Semantic Search API Functions
// ============================================================================

// Perform semantic search across vocabularies
export async function semanticSearch(request: SemanticSearchRequest): Promise<SemanticSearchResponse> {
  return fetchWithRetry<SemanticSearchResponse>(`${API_BASE_URL}/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Find similar concepts to a given concept
export async function findSimilarConcepts(request: SimilarConceptsRequest): Promise<SimilarConceptsResponse> {
  return fetchWithRetry<SimilarConceptsResponse>(`${API_BASE_URL}/search/similar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Map concept to another vocabulary (crosswalk)
export async function crosswalkConcept(request: CrosswalkRequest): Promise<CrosswalkResponse> {
  return fetchWithRetry<CrosswalkResponse>(`${API_BASE_URL}/search/crosswalk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Get autocomplete suggestions
export async function getSearchSuggestions(
  prefix: string,
  vocabularies?: string[],
  limit: number = 10
): Promise<SuggestionsResponse> {
  const params = new URLSearchParams({ prefix, limit: limit.toString() });
  if (vocabularies && vocabularies.length > 0) {
    params.append("vocabularies", vocabularies.join(","));
  }
  return fetchWithRetry<SuggestionsResponse>(`${API_BASE_URL}/search/suggest?${params}`);
}

// Cluster search results by type
export async function clusterSearchResults(results: SemanticSearchResult[]): Promise<ClusterResponse> {
  return fetchWithRetry<ClusterResponse>(`${API_BASE_URL}/search/cluster`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ results }),
  });
}

// Get semantic search service statistics
export async function getSemanticSearchStats(): Promise<SemanticSearchStats> {
  return fetchWithRetry<SemanticSearchStats>(`${API_BASE_URL}/search/stats`);
}

// Get concept details by ID
export async function getConceptDetails(conceptId: number): Promise<ConceptDetails> {
  return fetchWithRetry<ConceptDetails>(`${API_BASE_URL}/search/concept/${conceptId}`);
}

// ============================================================================
// NLP Entity Extraction Types
// ============================================================================

export type NLPEntityType =
  | "diagnosis"
  | "medication"
  | "procedure"
  | "lab_result"
  | "vital_sign"
  | "anatomical_location"
  | "temporal"
  | "symptom"
  | "allergy";

export type NLPAssertionStatus =
  | "present"
  | "absent"
  | "possible"
  | "conditional"
  | "hypothetical"
  | "family_history";

export type NLPClinicalSection =
  | "chief_complaint"
  | "hpi"
  | "ros"
  | "pmh"
  | "psh"
  | "fhx"
  | "shx"
  | "medications"
  | "allergies"
  | "vitals"
  | "physical_exam"
  | "labs"
  | "imaging"
  | "assessment"
  | "plan"
  | "unknown";

export type NLPVocabulary =
  | "SNOMED-CT"
  | "RxNorm"
  | "LOINC"
  | "ICD-10-CM"
  | "ICD-10-PCS"
  | "CPT"
  | "NDC"
  | "OMOP";

export interface NLPEntitySpan {
  start: number;
  end: number;
  text: string;
}

export interface NLPNormalizedCode {
  code: string;
  display: string;
  system: NLPVocabulary;
  confidence: number;
  is_preferred: boolean;
}

export interface NLPExtractedEntity {
  id: string;
  entity_type: NLPEntityType;
  text: string;
  normalized_text: string;
  span: NLPEntitySpan;
  section: NLPClinicalSection;
  assertion: NLPAssertionStatus;
  confidence: number;
  normalized_codes: NLPNormalizedCode[];
  value?: string | null;
  unit?: string | null;
  reference_range?: string | null;
  laterality?: string | null;
  dosage?: string | null;
  frequency?: string | null;
  route?: string | null;
  duration?: string | null;
  negation_trigger?: string | null;
  negation_scope_start?: number | null;
  negation_scope_end?: number | null;
}

export interface NLPSectionSpan {
  section: NLPClinicalSection;
  start: number;
  end: number;
  header_text?: string | null;
}

export interface NLPExtractRequest {
  text: string;
  entity_types?: NLPEntityType[];
  use_ml_models?: boolean;
  model_id?: string | null;
  include_normalized_codes?: boolean;
  detect_negation?: boolean;
  detect_sections?: boolean;
  normalize_entities?: boolean;
}

export interface NLPExtractResponse {
  request_id: string;
  text_length: number;
  entities: NLPExtractedEntity[];
  sections: NLPSectionSpan[];
  entity_count: number;
  entities_by_type: Record<string, number>;
  processing_time_ms: number;
  model_used: string;
}

export interface NLPBatchExtractRequest {
  texts: string[];
  entity_types?: NLPEntityType[];
  use_ml_models?: boolean;
  model_id?: string | null;
}

export interface NLPBatchExtractItem {
  index: number;
  text_preview: string;
  entity_count: number;
  entities_by_type: Record<string, number>;
  processing_time_ms: number;
  error?: string | null;
}

export interface NLPBatchExtractResponse {
  request_id: string;
  total_texts: number;
  successful: number;
  failed: number;
  results: NLPBatchExtractItem[];
  total_time_ms: number;
}

export interface NLPModelInfo {
  model_id: string;
  name: string;
  description: string;
  entity_types: NLPEntityType[];
  is_available: boolean;
  requires_gpu: boolean;
  version: string;
}

export interface NLPModelsResponse {
  models: NLPModelInfo[];
  default_model: string;
}

export interface NLPNormalizeRequest {
  entities: NLPExtractedEntity[];
  vocabularies?: NLPVocabulary[];
}

export interface NLPNormalizationResultItem {
  entity_id: string;
  original_text: string;
  normalized_codes: NLPNormalizedCode[];
  best_match?: NLPNormalizedCode | null;
  processing_time_ms: number;
}

export interface NLPNormalizeResponse {
  request_id: string;
  results: NLPNormalizationResultItem[];
  total_entities: number;
  entities_with_codes: number;
  total_time_ms: number;
}

export interface NLPSampleNote {
  id: string;
  title: string;
  text: string;
}

export interface NLPSamplesResponse {
  samples: NLPSampleNote[];
}

// Type alias for backwards compatibility
export type NLPExtractionResult = NLPExtractResponse;

export interface NLPServiceStats {
  registered_ml_models: number;
  available_entity_types: string[];
  negation_patterns: number;
  diagnosis_patterns: number;
  medication_patterns: number;
  procedure_patterns: number;
  lab_patterns: number;
  vital_sign_patterns: number;
}

// ============================================================================
// NLP Entity Extraction API Functions
// ============================================================================

// Extract entities from clinical text
export async function nlpExtractEntities(request: NLPExtractRequest): Promise<NLPExtractResponse> {
  return fetchWithRetry<NLPExtractResponse>(`${API_BASE_URL}/nlp/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 600000, // 10 minutes for LLM processing of large documents
  });
}

// Batch extract entities from multiple texts
export async function nlpBatchExtractEntities(request: NLPBatchExtractRequest): Promise<NLPBatchExtractResponse> {
  return fetchWithRetry<NLPBatchExtractResponse>(`${API_BASE_URL}/nlp/extract/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 120000, // Longer timeout for batch processing
  });
}

// List available NLP models
export async function nlpGetModels(): Promise<NLPModelsResponse> {
  return fetchWithRetry<NLPModelsResponse>(`${API_BASE_URL}/nlp/models`);
}

// Normalize entities to standard codes
export async function nlpNormalizeEntities(request: NLPNormalizeRequest): Promise<NLPNormalizeResponse> {
  return fetchWithRetry<NLPNormalizeResponse>(`${API_BASE_URL}/nlp/normalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 60000,
  });
}

// Get sample clinical notes for testing
export async function nlpGetSamples(): Promise<NLPSamplesResponse> {
  return fetchWithRetry<NLPSamplesResponse>(`${API_BASE_URL}/nlp/samples`);
}

// Get NLP service statistics
export async function nlpGetStats(): Promise<NLPServiceStats> {
  return fetchWithRetry<NLPServiceStats>(`${API_BASE_URL}/nlp/stats`);
}

// ============================================================================
// Ontology Mapper Types
// ============================================================================

export interface OntologyEntity {
  text: string;
  normalized: string;
  category: string;
  subcategory?: string | null;
  vocabulary_code?: string | null;
  vocabulary_system?: string | null;
  confidence: number;
  attributes: Record<string, unknown>;
  negated: boolean;
}

export interface OntologyRelationship {
  subject: string;
  relation: string;
  object: string;
  confidence: number;
}

export interface OntologyMapRequest {
  text: string;
}

export interface OntologyMapResponse {
  request_id: string;
  text_length: number;
  total_tokens: number;
  classified_tokens: number;
  coverage_pct: number;
  entity_count: number;
  entities_by_category: Record<string, number>;
  entities: OntologyEntity[];
  relationships: OntologyRelationship[];
  negated_findings: string[];
  processing_time_ms: number;
}

// ============================================================================
// Hybrid Clinical Analyzer Types
// ============================================================================

export type AnalysisType =
  | "clinical_summary"
  | "risk_assessment"
  | "medication_review"
  | "lab_interpretation";

export interface HybridAnalyzeRequest {
  text: string;
  analysis_type?: AnalysisType;
  use_llm?: boolean;
  extract_narrative?: boolean;
}

// Narrative extraction types
export interface AdmissionReason {
  primary_problem: string;
  contributing_factors: string[];
  presenting_symptoms: string[];
  linked_condition_texts: string[];
  admission_date: string | null;
  admission_source: string | null;
}

export interface ClinicalEvent {
  event_text: string;
  event_type: string;
  event_date: string | null;
  relative_day: number | null;
  caused_by: string | null;
  resulted_in: string | null;
  linked_entity_texts: string[];
  severity: string | null;
}

export interface HospitalCourse {
  summary: string;
  key_events: ClinicalEvent[];
  interventions: string[];
  complications: string[];
  response_to_treatment: string | null;
  length_of_stay_days: number | null;
}

export interface DischargePlan {
  disposition: string;
  discharge_date: string | null;
  follow_up_appointments: string[];
  discharge_medications: string[];
  activity_restrictions: string[];
  diet_instructions: string | null;
  wound_care: string | null;
  return_precautions: string[];
  pending_results: string[];
}

export interface ClinicalEpisode {
  episode_label: string;
  episode_date: string | null;
  admission_reason: AdmissionReason | null;
  hospital_course: HospitalCourse | null;
  discharge_plan: DischargePlan | null;
}

export interface NarrativeResponse {
  admission_reason: AdmissionReason | null;
  hospital_course: HospitalCourse | null;
  discharge_plan: DischargePlan | null;
  episodes: ClinicalEpisode[];
  extraction_confidence: number;
  extraction_method: string;
}

export interface StructuredContext {
  diagnoses: Array<{ name: string; code?: string; negated?: boolean }>;
  medications: Array<{ name: string; dose?: string; frequency?: string }>;
  labs: Array<{ name: string; value?: string; unit?: string; flag?: string }>;
  vitals: Array<{ name: string; value?: string }>;
  symptoms: Array<{ name: string; negated?: boolean }>;
  findings: Array<{ name: string; negated?: boolean }>;
  procedures: Array<{ name: string }>;
  negated_findings: string[];
  relationships: Array<{ subject: string; relation: string; object: string }>;
  entity_count: number;
  coverage_pct: number;
  human_readable_summary?: string;
}

export interface HybridAnalyzeResponse {
  request_id: string;
  analysis_type: string;
  analysis: string | null;
  structured_context: StructuredContext;
  extraction_time_ms: number;
  llm_time_ms: number | null;
  total_time_ms: number;
  llm_model: string | null;
  llm_available: boolean;
  narrative: NarrativeResponse | null;
}

// ============================================================================
// Ontology Mapper & Hybrid Analyzer API Functions
// ============================================================================

// Map clinical text using deterministic ontology mapper
export async function nlpOntologyMap(request: OntologyMapRequest): Promise<OntologyMapResponse> {
  return fetchWithRetry<OntologyMapResponse>(`${API_BASE_URL}/nlp/ontology/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 30000,
  });
}

// Perform hybrid clinical analysis (deterministic + optional LLM)
export async function nlpHybridAnalyze(request: HybridAnalyzeRequest): Promise<HybridAnalyzeResponse> {
  return fetchWithRetry<HybridAnalyzeResponse>(`${API_BASE_URL}/nlp/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 300000, // 5 min timeout for LLM analysis + narrative on large note sets
  });
}

// ============================================================================
// AI Coding Types
// ============================================================================

export interface AIEvidenceSnippet {
  text: string;
  start_offset: number;
  end_offset: number;
  relevance_score: number;
  highlight_terms: string[];
}

export interface AICodeSuggestion {
  code: string;
  code_type: string;
  description: string;
  confidence: string;
  confidence_score: number;
  evidence_snippets: AIEvidenceSnippet[];
  match_reason: string;
  category: string;
  is_billable: boolean;
  parent_code: string | null;
  more_specific_codes: [string, string][];
  related_codes: [string, string][];
  hcc_code: string | null;
  hcc_description: string | null;
  raf_value: number;
  coding_tips: string[];
  use_additional_code: string | null;
  code_first: string | null;
}

export interface AICodingOpportunity {
  opportunity_type: string;
  current_code: string | null;
  suggested_code: string | null;
  description: string;
  impact: string;
  evidence_text: string;
  priority: string;
}

export interface AIValidationIssue {
  issue_type: string;
  severity: string;
  codes_involved: string[];
  message: string;
  suggestion: string;
}

export interface AIHCCDetail {
  hcc_code: string;
  icd10_code: string;
  icd10_description: string;
  raf_value: number;
}

export interface AIHCCRisk {
  total_raf_score: number;
  hcc_codes: string[];
  hcc_details: AIHCCDetail[];
  estimated_annual_revenue: number;
  opportunities: AICodingOpportunity[];
}

export interface AICodingSuggestRequest {
  clinical_text: string;
  max_diagnosis_codes?: number;
  max_procedure_codes?: number;
  include_hcc?: boolean;
  encounter_context?: Record<string, unknown>;
}

export interface AICodingSuggestResponse {
  request_id: string;
  text_length: number;
  analysis_timestamp: string;
  processing_time_ms: number;
  diagnosis_codes: AICodeSuggestion[];
  procedure_codes: AICodeSuggestion[];
  coding_opportunities: AICodingOpportunity[];
  validation_issues: AIValidationIssue[];
  hcc_analysis: AIHCCRisk | null;
  em_code: AICodeSuggestion | null;
  em_rationale: string;
  total_diagnosis_suggestions: number;
  total_procedure_suggestions: number;
  high_confidence_count: number;
}

export interface AICodingValidateRequest {
  diagnosis_codes?: string[];
  procedure_codes?: string[];
}

export interface AICodingValidateResponse {
  is_valid: boolean;
  issues: AIValidationIssue[];
  summary: string;
}

export interface AICodingHCCRequest {
  icd10_codes: string[];
  clinical_text?: string;
}

export interface AICodingHCCResponse {
  total_raf_score: number;
  hcc_codes: string[];
  hcc_details: AIHCCDetail[];
  estimated_annual_revenue: number;
  opportunities: AICodingOpportunity[];
}

export interface AICodingRule {
  rule_id: string;
  category: string;
  title: string;
  description: string;
  codes_affected: string[];
  examples: string[];
  source: string;
}

export interface AICodingRulesResponse {
  rules: AICodingRule[];
  total_count: number;
}

export interface AICodingServiceStats {
  total_icd10_codes: number;
  total_cpt_codes: number;
  total_icd10_synonyms: number;
  total_cpt_synonyms: number;
  hcc_mappings: number;
}

export interface AICodingCodeDetails {
  code: string;
  description: string;
  synonyms: string[];
  category: string | null;
  is_billable: boolean | null;
  hcc_code: string | null;
  raf_value: number | null;
}

export interface AICodingSearchResponse {
  results: AICodingCodeDetails[];
  total_count: number;
}

// ============================================================================
// AI Coding API Functions
// ============================================================================

// Suggest codes from clinical text
export async function suggestCodes(request: AICodingSuggestRequest): Promise<AICodingSuggestResponse> {
  return fetchWithRetry<AICodingSuggestResponse>(`${API_BASE_URL}/ai-coding/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    timeout: 60000, // Longer timeout for AI processing
  });
}

// Validate codes for errors and bundling issues
export async function validateCodes(request: AICodingValidateRequest): Promise<AICodingValidateResponse> {
  return fetchWithRetry<AICodingValidateResponse>(`${API_BASE_URL}/ai-coding/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Calculate HCC risk scores
export async function calculateHCC(request: AICodingHCCRequest): Promise<AICodingHCCResponse> {
  return fetchWithRetry<AICodingHCCResponse>(`${API_BASE_URL}/ai-coding/hcc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// Get coding rules and guidelines
export async function getCodingRules(category?: string): Promise<AICodingRulesResponse> {
  const url = category
    ? `${API_BASE_URL}/ai-coding/rules?category=${encodeURIComponent(category)}`
    : `${API_BASE_URL}/ai-coding/rules`;
  return fetchWithRetry<AICodingRulesResponse>(url);
}

// Get AI coding service statistics
export async function getAICodingStats(): Promise<AICodingServiceStats> {
  return fetchWithRetry<AICodingServiceStats>(`${API_BASE_URL}/ai-coding/stats`);
}

// Get code details
export async function getCodeDetails(code: string, codeType: string = "ICD10"): Promise<AICodingCodeDetails> {
  return fetchWithRetry<AICodingCodeDetails>(
    `${API_BASE_URL}/ai-coding/code/${encodeURIComponent(code)}?code_type=${encodeURIComponent(codeType)}`
  );
}

// Search for codes
export async function searchCodes(
  query: string,
  codeType: string = "ICD10",
  limit: number = 20
): Promise<AICodingSearchResponse> {
  const params = new URLSearchParams({
    query,
    code_type: codeType,
    limit: limit.toString(),
  });
  return fetchWithRetry<AICodingSearchResponse>(`${API_BASE_URL}/ai-coding/search?${params.toString()}`);
}

// ============================================================================
// Clinical Trials
// ============================================================================

export interface TrialSummary {
  id: string;
  name: string;
  nct_number: string | null;
  sponsor: string;
  phase: string;
  status: string;
  therapeutic_area: string | null;
  enrollment_target: number;
  enrolled_count: number;
  enrollment_progress: number;
  created_at: string;
}

export interface TrialResponse {
  id: string;
  name: string;
  nct_number: string | null;
  protocol_id: string | null;
  sponsor: string;
  phase: string;
  status: string;
  description: string | null;
  therapeutic_area: string | null;
  indication_codes: string[];
  inclusion_criteria: { criteria: Record<string, unknown>[] };
  exclusion_criteria: { criteria: Record<string, unknown>[] };
  enrollment_target: number;
  enrolled_count: number;
  site_count: number;
  start_date: string | null;
  end_date: string | null;
  inclusion_cohort_id: string | null;
  exclusion_cohort_id: string | null;
  created_at: string;
}

export interface TrialListResponse {
  trials: TrialSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface CriterionResultDetail {
  criterion_name: string;
  criterion_type: string;
  status: string; // PASS, NOT_MET, FAIL, UNKNOWN, POSSIBLE_MATCH
  evidence_fact_ids: string[];
  confidence: number;
  details: string;
  weight: number;
  missing_domain: string | null;
  evidence_summary: string | null;
  source_documents: string[];
  confidence_explanation: string | null;
  safety_block: boolean;
}

export interface DataCompletenessScore {
  overall_completeness: number;
  evaluable_criteria: number;
  total_criteria: number;
  unknown_criteria: number;
  not_met_criteria: number;
  missing_domains: string[];
  recommendation: string | null;
}

export interface PatientEligibility {
  patient_id: string;
  eligible: boolean;
  match_score: number;
  inclusion_met: string[];
  inclusion_total: number;
  exclusion_triggered: string[];
  exclusion_total: number;
  missing_data: string[];
  criteria_details: CriterionResultDetail[];
  evaluable_criteria: number;
  screening_timestamp: string | null;
  requires_clinician_review: boolean;
  review_disclaimer: string;
  data_completeness: DataCompletenessScore | null;
  safety_blocked: boolean;
  safety_blocked_reasons: string[];
}

export interface ScreeningResponse {
  trial_id: string;
  trial_name: string;
  total_patients_screened: number;
  eligible_count: number;
  ineligible_count: number;
  enrollment_target: number;
  enrollment_rate: number;
  candidates: PatientEligibility[];
  demographics_summary: Record<string, unknown> | null;
  exclusion_breakdown: Record<string, number> | null;
  requires_clinician_review: boolean;
  cds_disclaimer: string;
}

export interface EnrollmentResponse {
  id: string;
  trial_id: string;
  patient_id: string;
  enrollment_status: string;
  match_score: number | null;
  criteria_met: string[] | null;
  criteria_failed: string[] | null;
  screening_date: string | null;
  enrollment_date: string | null;
  withdrawal_date: string | null;
  withdrawal_reason: string | null;
  site_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface EnrollmentListResponse {
  enrollments: EnrollmentResponse[];
  total: number;
  offset: number;
  limit: number;
}

export interface TrialDashboard {
  trial_id: string;
  trial_name: string;
  status: string;
  phase: string;
  enrollment_target: number;
  total_candidates: number;
  total_screened: number;
  total_eligible: number;
  total_enrolled: number;
  total_active: number;
  total_completed: number;
  total_withdrawn: number;
  total_screen_failed: number;
  enrollment_progress: number;
  site_count: number;
}

export interface TrialListParams {
  status?: string;
  sponsor?: string;
  therapeutic_area?: string;
  search?: string;
  offset?: number;
  limit?: number;
}

// List trials
export async function getTrials(params?: TrialListParams): Promise<TrialListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.sponsor) query.set("sponsor", params.sponsor);
  if (params?.therapeutic_area) query.set("therapeutic_area", params.therapeutic_area);
  if (params?.search) query.set("search", params.search);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchWithRetry<TrialListResponse>(`${API_BASE_URL}/trials${qs ? `?${qs}` : ""}`);
}

// Get trial details
export async function getTrial(trialId: string): Promise<TrialResponse> {
  return fetchWithRetry<TrialResponse>(`${API_BASE_URL}/trials/${trialId}`);
}

// Screen patients for a trial
export async function screenTrialPatients(trialId: string): Promise<ScreeningResponse> {
  return fetchWithRetry<ScreeningResponse>(`${API_BASE_URL}/trials/${trialId}/screen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

// Get trial dashboard
export async function getTrialDashboard(trialId: string): Promise<TrialDashboard> {
  return fetchWithRetry<TrialDashboard>(`${API_BASE_URL}/trials/${trialId}/dashboard`);
}

// Get trial enrollments
export async function getTrialEnrollments(
  trialId: string,
  params?: { status?: string; offset?: number; limit?: number }
): Promise<EnrollmentListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchWithRetry<EnrollmentListResponse>(
    `${API_BASE_URL}/trials/${trialId}/enrollments${qs ? `?${qs}` : ""}`
  );
}

// Get trial stats
export async function getTrialStats(): Promise<Record<string, unknown>> {
  return fetchWithRetry<Record<string, unknown>>(`${API_BASE_URL}/trials/stats`);
}

// Get per-match explainability for a patient-trial pair (VP-Product-2)
export async function getMatchExplanation(
  trialId: string,
  patientId: string
): Promise<PatientEligibility> {
  return fetchWithRetry<PatientEligibility>(
    `${API_BASE_URL}/trials/${trialId}/matches/${patientId}/explanation`
  );
}

// ============================================================================
// Dual Enrollment Detection
// ============================================================================

export interface DualEnrollmentRequest {
  trial_id?: string | null;
  min_match_score?: number;
}

export interface CurrentEnrollmentInfo {
  trial_id: string;
  trial_name: string;
  nct_number: string | null;
  enrollment_status: string;
  match_score: number | null;
}

export interface AdditionalTrialMatch {
  trial_id: string;
  trial_name: string;
  nct_number: string | null;
  eligible: boolean;
  match_score: number;
  key_criteria_met: string[];
  exclusion_triggered: string[];
  safety_blocked: boolean;
}

export interface DualEnrollmentCandidate {
  patient_id: string;
  current_enrollments: CurrentEnrollmentInfo[];
  additional_matches: AdditionalTrialMatch[];
  total_additional_matches: number;
}

export interface DualEnrollmentSummary {
  total_enrolled_patients_checked: number;
  total_patients_with_additional_matches: number;
  total_additional_matches: number;
  trials_checked: number;
  screening_duration_ms: number;
}

export interface DualEnrollmentResponse {
  summary: DualEnrollmentSummary;
  candidates: DualEnrollmentCandidate[];
  requires_clinician_review: boolean;
  cds_disclaimer: string;
}

// Find patients eligible for multiple trials
export async function findDualEnrollmentCandidates(
  request?: DualEnrollmentRequest
): Promise<DualEnrollmentResponse> {
  return fetchWithRetry<DualEnrollmentResponse>(
    `${API_BASE_URL}/trials/dual-enrollment-candidates`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request ?? {}),
    }
  );
}

// ============================================================================
// Sites
// ============================================================================

export interface SiteResponse {
  id: string;
  name: string;
  site_code: string | null;
  organization: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  created_at: string;
}

export interface SiteListResponse {
  sites: SiteResponse[];
  total: number;
  offset: number;
  limit: number;
}

export interface SitePatient {
  patient_id: string;
  patient_name: string | null;
  site_id: string;
}

export interface SitePatientListResponse {
  patients: SitePatient[];
  total: number;
  site_id: string;
  site_name: string;
}

export interface SiteTrialMatch {
  trial_id: string;
  trial_name: string;
  matched_patients: number;
  matched_patient_ids: string[];
}

export interface SiteScreeningSummary {
  site_id: string;
  site_name: string;
  total_patients: number;
  patients_screened: number;
  patients_matched: number;
  trial_matches: SiteTrialMatch[];
}

export interface SiteListParams {
  search?: string;
  offset?: number;
  limit?: number;
}

// List sites
export async function getSites(params?: SiteListParams): Promise<SiteListResponse> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchWithRetry<SiteListResponse>(`${API_BASE_URL}/sites${qs ? `?${qs}` : ""}`);
}

// Get site details
export async function getSite(siteId: string): Promise<SiteResponse> {
  return fetchWithRetry<SiteResponse>(`${API_BASE_URL}/sites/${siteId}`);
}

// Get patients at a site
export async function getSitePatients(siteId: string): Promise<SitePatientListResponse> {
  return fetchWithRetry<SitePatientListResponse>(`${API_BASE_URL}/sites/${siteId}/patients`);
}

// Get site screening summary
export async function getSiteScreeningSummary(siteId: string): Promise<SiteScreeningSummary> {
  return fetchWithRetry<SiteScreeningSummary>(`${API_BASE_URL}/sites/${siteId}/screening-summary`);
}

// ============================================================================
// Metriport Integration
// ============================================================================

export interface MetriportStatus {
  configured: boolean;
  api_key_set: boolean;
  webhook_key_set: boolean;
  facility_id_set: boolean;
  base_url: string;
  organization: Record<string, unknown> | null;
  facilities: Record<string, unknown>[] | null;
}

export interface MetriportQueryResponse {
  status: string;
  message: string;
  data: Record<string, unknown> | null;
}

export interface MetriportPatientCreate {
  firstName: string;
  lastName: string;
  dob: string;
  genderAtBirth: string;
  address: {
    addressLine1: string;
    addressLine2?: string;
    city: string;
    state: string;
    zip: string;
    country?: string;
  }[];
  contact?: {
    phone?: string;
    email?: string;
  };
  externalId?: string;
  facility_id?: string;
}

export async function getMetriportStatus(): Promise<MetriportStatus> {
  return fetchWithRetry<MetriportStatus>(`${API_BASE_URL}/metriport/status`);
}

export async function getMetriportPatients(facilityId?: string): Promise<MetriportQueryResponse> {
  const qs = facilityId ? `?facility_id=${facilityId}` : "";
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/patients${qs}`);
}

export async function createMetriportPatient(data: MetriportPatientCreate): Promise<MetriportQueryResponse> {
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/patients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function startDocumentQuery(patientId: string, facilityId?: string): Promise<MetriportQueryResponse> {
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/documents/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId, facility_id: facilityId }),
  });
}

export async function getMetriportDocuments(patientId: string, facilityId?: string): Promise<MetriportQueryResponse> {
  const qs = facilityId ? `?facility_id=${facilityId}` : "";
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/documents/${patientId}${qs}`);
}

export async function startConsolidatedQuery(
  patientId: string,
  resources?: string[],
): Promise<MetriportQueryResponse> {
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/consolidated/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId, resources }),
  });
}

export async function onboardMetriportPatient(data: MetriportPatientCreate): Promise<MetriportQueryResponse> {
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/onboard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getMetriportFacilities(): Promise<MetriportQueryResponse> {
  return fetchWithRetry<MetriportQueryResponse>(`${API_BASE_URL}/metriport/facilities`);
}

// ============================================================================
// ROI Dashboard
// ============================================================================

export interface ROISummaryParams {
  trial_id?: string;
  conversion_rate?: number;
  screening_cost_per_patient?: number;
  estimated_value_per_enrollment?: number;
  time_bucket?: "day" | "week";
}

export interface ScreeningOverview {
  total_screenings: number;
  total_patients_screened: number;
  unique_trials_screened: number;
  total_eligible: number;
  total_ineligible: number;
  total_unknown: number;
  overall_pass_rate: number;
}

export interface TrialEligibilitySummary {
  trial_id: string;
  trial_name: string | null;
  total_screened: number;
  eligible_count: number;
  ineligible_count: number;
  unknown_count: number;
  pass_rate: number;
}

export interface SiteTrialBreakdown {
  site_id: string;
  site_name: string | null;
  trial_id: string;
  trial_name: string | null;
  eligible_count: number;
}

export interface DualEnrollmentCandidate {
  patient_id: string;
  eligible_trial_ids: string[];
  eligible_trial_names: string[];
  trial_count: number;
}

export interface TimeSeriesBucket {
  period: string;
  screenings: number;
  eligible: number;
  match_rate: number;
}

export interface ProjectedEnrollment {
  eligible_patients: number;
  conversion_rate: number;
  projected_enrollments: number;
}

export interface CostAnalysis {
  patients_screened: number;
  screening_cost_per_patient: number;
  total_screening_cost: number;
  projected_enrollments: number;
  estimated_value_per_enrollment: number;
  projected_enrollment_value: number;
  roi_ratio: number | null;
}

export interface ROISummaryResponse {
  generated_at: string;
  screening_overview: ScreeningOverview;
  eligibility_by_trial: TrialEligibilitySummary[];
  site_breakdown: SiteTrialBreakdown[];
  dual_enrollment_candidates: DualEnrollmentCandidate[];
  dual_enrollment_count: number;
  projected_enrollment: ProjectedEnrollment;
  cost_analysis: CostAnalysis;
  time_series: TimeSeriesBucket[];
}

export async function getROISummary(params?: ROISummaryParams): Promise<ROISummaryResponse> {
  const query = new URLSearchParams();
  if (params?.trial_id) query.set("trial_id", params.trial_id);
  if (params?.conversion_rate !== undefined) query.set("conversion_rate", String(params.conversion_rate));
  if (params?.screening_cost_per_patient !== undefined) query.set("screening_cost_per_patient", String(params.screening_cost_per_patient));
  if (params?.estimated_value_per_enrollment !== undefined) query.set("estimated_value_per_enrollment", String(params.estimated_value_per_enrollment));
  if (params?.time_bucket) query.set("time_bucket", params.time_bucket);
  const qs = query.toString();
  return fetchWithRetry<ROISummaryResponse>(`${API_BASE_URL}/dashboard/roi-summary${qs ? `?${qs}` : ""}`);
}

// ============================================================================
// Bulk Screening
// ============================================================================

export interface BulkScreeningRequest {
  patient_ids: string[];
  trial_ids: string[];
  min_match_score?: number;
  include_details?: boolean;
}

export interface BulkPatientResult {
  patient_id: string;
  eligible: boolean;
  match_score: number;
  inclusion_met: string[];
  inclusion_total: number;
  exclusion_triggered: string[];
  exclusion_total: number;
  missing_data: string[];
  safety_blocked: boolean;
  criteria_details: CriterionResultDetail[] | null;
}

export interface BulkTrialResult {
  trial_id: string;
  trial_name: string;
  nct_number: string | null;
  total_screened: number;
  eligible_count: number;
  ineligible_count: number;
  pass_rate: number;
  candidates: BulkPatientResult[];
}

export interface BulkScreeningSummary {
  total_patients: number;
  total_trials: number;
  total_pairs_screened: number;
  total_eligible: number;
  overall_pass_rate: number;
  screening_duration_ms: number;
  trials_not_found: string[];
}

export interface BulkScreeningResponse {
  summary: BulkScreeningSummary;
  results: BulkTrialResult[];
  requires_clinician_review: boolean;
  cds_disclaimer: string;
}

export interface ScreeningResultItem {
  id: string;
  patient_id: string;
  trial_id: string;
  trial_name: string | null;
  screening_date: string;
  overall_status: string;
  match_score: number | null;
  inclusion_met: number | null;
  inclusion_total: number | null;
  exclusion_triggered: number | null;
  exclusion_total: number | null;
  criterion_results: Record<string, unknown> | null;
  safety_blocked: boolean | null;
  triggered_by: string;
  notes: string | null;
  created_at: string;
}

export interface ScreeningResultListResponse {
  results: ScreeningResultItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface ScreeningResultListParams {
  patient_id?: string;
  trial_id?: string;
  status?: string;
  triggered_by?: string;
  offset?: number;
  limit?: number;
}

export async function runBulkScreening(
  body: BulkScreeningRequest
): Promise<BulkScreeningResponse> {
  return fetchWithRetry<BulkScreeningResponse>(`${API_BASE_URL}/trials/bulk-screen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getScreeningResults(
  params?: ScreeningResultListParams
): Promise<ScreeningResultListResponse> {
  const query = new URLSearchParams();
  if (params?.patient_id) query.set("patient_id", params.patient_id);
  if (params?.trial_id) query.set("trial_id", params.trial_id);
  if (params?.status) query.set("overall_status", params.status);
  if (params?.triggered_by) query.set("triggered_by", params.triggered_by);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchWithRetry<ScreeningResultListResponse>(
    `${API_BASE_URL}/screening-results${qs ? `?${qs}` : ""}`
  );
}

// ============================================================================
// Medidata Rave Integration
// ============================================================================

export interface RaveConnectionTestRequest {
  rave_url: string;
  username: string;
  password: string;
  environment?: string;
}

export interface RaveConnectionTestResponse {
  connected: boolean;
  latency_ms: number;
  rave_version: string | null;
  studies_count: number;
  error: string | null;
}

export interface RaveStudy {
  study_oid: string;
  study_name: string;
  environment: string;
  status: string;
  subject_count: number;
  site_count: number;
}

export interface RaveStudyListResponse {
  studies: RaveStudy[];
  total: number;
}

export interface RaveStudyImportResponse {
  success: boolean;
  trial_id: string | null;
  study_oid: string;
  study_name: string;
  criteria_found: number;
  mapping_preview: { rave_field: string; mapped_to: string }[];
  error: string | null;
}

export interface RaveScreeningPushRequest {
  trial_id: string;
  patient_ids?: string[];
}

export interface RaveScreeningPushResult {
  patient_id: string;
  status: "pushed" | "failed" | "skipped";
  rave_subject_id: string | null;
  error: string | null;
}

export interface RaveScreeningPushResponse {
  total: number;
  pushed: number;
  failed: number;
  skipped: number;
  results: RaveScreeningPushResult[];
}

export interface RaveEnrollmentSyncResponse {
  synced: number;
  pending: number;
  failed: number;
  events: RaveSyncEvent[];
}

export interface RaveSyncEvent {
  patient_id: string;
  rave_subject_id: string;
  status: string;
  previous_status: string | null;
  synced_at: string;
  error: string | null;
}

export interface RaveIntegrationStatus {
  connected: boolean;
  configured: boolean;
  rave_url: string | null;
  last_sync_at: string | null;
  synced_count: number;
  pending_count: number;
  failed_count: number;
}

export async function testRaveConnection(
  data: RaveConnectionTestRequest
): Promise<RaveConnectionTestResponse> {
  return fetchWithRetry<RaveConnectionTestResponse>(
    `${API_BASE_URL}/medidata-rave/connection/test`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
}

export async function getRaveStudies(): Promise<RaveStudyListResponse> {
  return fetchWithRetry<RaveStudyListResponse>(
    `${API_BASE_URL}/medidata-rave/studies`
  );
}

export async function importRaveStudy(
  studyOid: string
): Promise<RaveStudyImportResponse> {
  return fetchWithRetry<RaveStudyImportResponse>(
    `${API_BASE_URL}/medidata-rave/studies/${studyOid}/import`,
    { method: "POST" }
  );
}

export async function pushScreeningToRave(
  data: RaveScreeningPushRequest
): Promise<RaveScreeningPushResponse> {
  return fetchWithRetry<RaveScreeningPushResponse>(
    `${API_BASE_URL}/medidata-rave/screening/push`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
}

export async function syncRaveEnrollment(): Promise<RaveEnrollmentSyncResponse> {
  return fetchWithRetry<RaveEnrollmentSyncResponse>(
    `${API_BASE_URL}/medidata-rave/enrollment/sync`,
    { method: "POST" }
  );
}

export async function getRaveStatus(): Promise<RaveIntegrationStatus> {
  return fetchWithRetry<RaveIntegrationStatus>(
    `${API_BASE_URL}/medidata-rave/status`
  );
}

// ============================================================================
// Veeva Vault CDMS Integration
// ============================================================================

export interface VeevaConnectionTestRequest {
  vault_url: string;
  username: string;
  password: string;
}

export interface VeevaConnectionTestResponse {
  connected: boolean;
  latency_ms: number;
  vault_version: string | null;
  studies_count: number;
  session_valid: boolean;
  error: string | null;
}

export interface VeevaStudy {
  study_name: string;
  title: string;
  phase: string;
  status: string;
  subject_count: number;
}

export interface VeevaStudyListResponse {
  studies: VeevaStudy[];
  total: number;
}

export interface VeevaStudyImportResponse {
  success: boolean;
  trial_id: string | null;
  study_name: string;
  criteria_found: number;
  mapping_preview: { vault_field: string; mapped_to: string }[];
  error: string | null;
}

export interface VeevaScreeningPushRequest {
  trial_id: string;
  patient_ids?: string[];
}

export interface VeevaScreeningPushResult {
  patient_id: string;
  status: "pushed" | "failed" | "skipped";
  vault_subject_id: string | null;
  error: string | null;
}

export interface VeevaScreeningPushResponse {
  total: number;
  pushed: number;
  failed: number;
  skipped: number;
  results: VeevaScreeningPushResult[];
}

export interface VeevaEnrollmentSyncEvent {
  patient_id: string;
  vault_subject_id: string;
  status: string;
  previous_status: string | null;
  synced_at: string;
  error: string | null;
}

export interface VeevaEnrollmentSyncResponse {
  synced: number;
  pending: number;
  failed: number;
  events: VeevaEnrollmentSyncEvent[];
}

export interface VeevaIntegrationStatus {
  connected: boolean;
  configured: boolean;
  vault_url: string | null;
  last_sync_at: string | null;
  synced_count: number;
  pending_count: number;
  failed_count: number;
}

export async function testVeevaConnection(
  data: VeevaConnectionTestRequest
): Promise<VeevaConnectionTestResponse> {
  return fetchWithRetry<VeevaConnectionTestResponse>(
    `${API_BASE_URL}/veeva-vault/connection/test`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
}

export async function getVeevaStudies(): Promise<VeevaStudyListResponse> {
  return fetchWithRetry<VeevaStudyListResponse>(
    `${API_BASE_URL}/veeva-vault/studies`
  );
}

export async function importVeevaStudy(
  studyName: string
): Promise<VeevaStudyImportResponse> {
  return fetchWithRetry<VeevaStudyImportResponse>(
    `${API_BASE_URL}/veeva-vault/studies/${encodeURIComponent(studyName)}/import`,
    { method: "POST" }
  );
}

export async function pushScreeningToVeeva(
  data: VeevaScreeningPushRequest
): Promise<VeevaScreeningPushResponse> {
  return fetchWithRetry<VeevaScreeningPushResponse>(
    `${API_BASE_URL}/veeva-vault/screening/push`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
}

export async function syncVeevaEnrollment(): Promise<VeevaEnrollmentSyncResponse> {
  return fetchWithRetry<VeevaEnrollmentSyncResponse>(
    `${API_BASE_URL}/veeva-vault/enrollment/sync`,
    { method: "POST" }
  );
}

export async function getVeevaStatus(): Promise<VeevaIntegrationStatus> {
  return fetchWithRetry<VeevaIntegrationStatus>(
    `${API_BASE_URL}/veeva-vault/status`
  );
}
