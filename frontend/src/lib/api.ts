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
  job_id: string;
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
  created_at: string;
  document_count: number;
  fact_count: number;
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
