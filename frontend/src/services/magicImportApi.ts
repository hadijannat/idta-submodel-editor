/**
 * API client for Magic Import service.
 */

import { API_BASE_URL, ApiError } from './api';

/**
 * Job status enum matching backend.
 */
export type JobStatus =
  | 'uploaded'
  | 'indexing'
  | 'ocr'
  | 'extracting'
  | 'localizing'
  | 'scoring'
  | 'validating'
  | 'done'
  | 'failed';

/**
 * Extraction status enum matching backend.
 */
export type ExtractionStatus = 'filled' | 'empty' | 'needs_review' | 'conflict';

/**
 * Bounding box with normalized coordinates.
 */
export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/**
 * Evidence reference to PDF source.
 */
export interface EvidenceRef {
  page: number;
  quote: string;
  boxes: BBox[];
  method: 'TEXT' | 'OCR';
  locator_score: number;
  snippet_hash?: string | null;
  char_start?: number | null;
  char_end?: number | null;
}

/**
 * Confidence breakdown.
 */
export interface ConfidenceBreakdown {
  llm: number;
  localizer: number;
  ocr: number;
  rules: number;
}

/**
 * Confidence reason codes.
 */
export type ConfidenceReasonCode =
  | 'multiple_candidates'
  | 'ocr_quality_low'
  | 'unit_ambiguity'
  | 'type_mismatch'
  | 'no_evidence_found'
  | 'low_llm_confidence'
  | 'value_outside_evidence'
  | 'semantic_constraint_violation';

/**
 * Structured reason explaining a confidence factor.
 */
export interface ConfidenceReason {
  code: ConfidenceReasonCode;
  message: string;
  severity: 'info' | 'warning' | 'error';
  detail?: Record<string, unknown>;
}

/**
 * Extracted field value.
 */
export interface FieldExtraction {
  path: string;
  value_type?: string | null;
  value_raw: string;
  value_normalized: string | number | boolean | null;
  status: ExtractionStatus;
  confidence: number;
  confidence_breakdown: ConfidenceBreakdown | null;
  confidence_reasons: ConfidenceReason[];
  evidence: EvidenceRef | null;
  needs_review: boolean;
  user_edited: boolean;
  user_approved: boolean;
}

/**
 * PDF index info summary.
 */
export interface PDFIndexInfo {
  total_pages: number;
  pages_with_text: number;
  pages_needing_ocr: number;
  total_words: number;
  language_detected: string | null;
}

/**
 * Document classification results.
 */
export interface DocumentClassification {
  doc_type: 'text' | 'scanned' | 'mixed';
  language: string | null;
  has_tables: boolean;
  quality_score: number;
  avg_ocr_confidence: number | null;
  text_density: number;
}

/**
 * Magic Import job.
 */
export interface MagicImportJob {
  job_id: string;
  status: JobStatus;
  template_name: string;
  template_status: 'published' | 'deprecated';
  template_version: string | null;
  pdf_filename: string;
  pdf_size_bytes: number;
  created_at: string;
  updated_at: string;
  progress: number;
  progress_message: string | null;
  error_message: string | null;
  pdf_info: PDFIndexInfo | null;
  doc_classification: DocumentClassification | null;
}

/**
 * Unmapped finding - value found in document that doesn't map to template.
 */
export interface UnmappedFinding {
  value: string;
  evidence: EvidenceRef;
  suggested_paths: string[];
  confidence: number;
  source: 'table' | 'text' | 'key_value';
  context?: string | null;
}

/**
 * Validation error for a specific field.
 */
export interface ValidationError {
  path: string;
  message: string;
  code: string;
}

/**
 * Validation result from template schema validation.
 */
export interface ValidationResult {
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

/**
 * Evidence quality for Q4 classification.
 */
export type EvidenceQuality =
  | 'table_structured'
  | 'table_key_value'
  | 'text_grounded'
  | 'text_inferred'
  | 'ocr_high'
  | 'ocr_low'
  | 'none';

/**
 * Field type category for Q10 classification.
 */
export type FieldTypeCategory =
  | 'identifier'
  | 'date_time'
  | 'numeric_unit'
  | 'numeric_pure'
  | 'enum_choice'
  | 'boolean'
  | 'text_short'
  | 'text_long'
  | 'contact'
  | 'reference';

/**
 * Per-field quality metrics.
 */
export interface FieldMetrics {
  path: string;
  field_type_category: FieldTypeCategory;
  is_required: boolean;
  confidence: number;
  evidence_ratio: number;
  evidence_quality: EvidenceQuality;
  source_table: boolean;
  source_text: boolean;
  source_ocr: boolean;
  grounding_verified: boolean;
  llm_provider?: string | null;
  llm_model?: string | null;
}

/**
 * Template mismatch metrics for Q6.
 */
export interface TemplateMismatchMetrics {
  keyword_match_ratio: number;
  extraction_yield: number;
  evidence_localization_rate: number;
  mismatch_score: number;
  mismatch_indicators: string[];
  recommended_action: 'proceed' | 'warn' | 'abort';
}

/**
 * Auto-apply thresholds for Q8.
 */
export interface AutoApplyThresholds {
  min_confidence: number;
  min_evidence_ratio: number;
  require_grounding: boolean;
  allowed_evidence_qualities: EvidenceQuality[];
  blocked_field_types: FieldTypeCategory[];
}

/**
 * Comprehensive quality metrics.
 */
export interface QualityMetrics {
  job_id: string;
  template_name: string;
  computed_at: string;
  overall_confidence: number;
  weighted_confidence: number;
  evidence_ratio: number;
  table_evidence_ratio: number;
  text_evidence_ratio: number;
  high_confidence_no_evidence_count: number;
  grounding_rate: number;
  required_field_total: number;
  required_field_extracted: number;
  required_field_coverage: number;
  optional_field_coverage: number;
  field_metrics: FieldMetrics[];
  error_rates_by_type: Record<string, number>;
  mismatch_metrics: TemplateMismatchMetrics | null;
  llm_provider: string;
  llm_model: string;
  llm_tokens_used?: number | null;
  auto_apply_eligible_count: number;
  auto_apply_thresholds_used?: AutoApplyThresholds | null;
  experiment_id?: string | null;
  experiment_variant?: string | null;
}

/**
 * User correction outcome for feedback loop.
 */
export interface ExtractionOutcome {
  job_id: string;
  recorded_at: string;
  field_path: string;
  original_value?: string | null;
  final_value?: string | null;
  original_confidence: number;
  action: 'accepted' | 'edited' | 'deleted' | 'rejected';
  edit_distance: number;
  had_evidence: boolean;
  evidence_quality: EvidenceQuality;
  field_type: FieldTypeCategory;
  was_required: boolean;
}

/**
 * Extraction result.
 */
export interface MagicImportResult {
  job_id: string;
  template_name: string;
  extractions: FieldExtraction[];
  fields_extracted: number;
  fields_needing_review: number;
  average_confidence: number;
  llm_provider: string;
  llm_model: string;
  processing_time_seconds: number;
  llm_tokens_used?: number | null;
  llm_prompt_tokens?: number | null;
  llm_completion_tokens?: number | null;
  llm_called?: boolean | null;
  mismatch_suspected?: boolean;
  mismatch_reasons?: string[];
  validation_result: ValidationResult | null;
  template_version_used: string | null;
  unmapped_findings: UnmappedFinding[];
  quality_metrics?: QualityMetrics | null;
}

/**
 * Create a new Magic Import job by uploading a PDF.
 */
export async function createMagicImportJob(
  file: File,
  templateName: string,
  templateStatus: 'published' | 'deprecated' = 'published',
  templateVersion?: string
): Promise<MagicImportJob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('template_name', templateName);
  formData.append('template_status', templateStatus);
  if (templateVersion) {
    formData.append('template_version', templateVersion);
  }

  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to create Magic Import job', response.status, details);
  }

  return response.json();
}

/**
 * Get job status.
 */
export async function getMagicImportJob(jobId: string): Promise<MagicImportJob> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}`);

  if (!response.ok) {
    throw new ApiError('Failed to get job', response.status);
  }

  return response.json();
}

/**
 * Get extraction results for a completed job.
 */
export async function getMagicImportResult(jobId: string): Promise<MagicImportResult> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}/result`);

  if (!response.ok) {
    throw new ApiError('Failed to get result', response.status);
  }

  return response.json();
}

/**
 * Get PDF URL for viewer.
 */
export function getMagicImportPdfUrl(jobId: string): string {
  return `${API_BASE_URL}/api/magic-import/jobs/${jobId}/pdf`;
}

/**
 * Delete a job.
 */
export async function deleteMagicImportJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new ApiError('Failed to delete job', response.status);
  }
}

/**
 * List recent jobs.
 */
export async function listMagicImportJobs(
  limit: number = 50,
  status?: JobStatus
): Promise<MagicImportJob[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) {
    params.append('status', status);
  }

  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs?${params}`);

  if (!response.ok) {
    throw new ApiError('Failed to list jobs', response.status);
  }

  return response.json();
}

/**
 * Poll job status until complete or failed.
 */
export async function pollJobStatus(
  jobId: string,
  onProgress: (job: MagicImportJob) => void,
  intervalMs: number = 1000,
  maxAttempts: number = 600
): Promise<MagicImportJob> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const job = await getMagicImportJob(jobId);
    onProgress(job);

    if (job.status === 'done' || job.status === 'failed') {
      return job;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Job polling timeout');
}

/**
 * Re-extract request.
 */
export interface ReExtractRequest {
  paths: string[];
  hint?: string;
}

/**
 * Re-extract specific fields from an existing job.
 */
export async function reExtractFields(
  jobId: string,
  paths: string[],
  hint?: string
): Promise<MagicImportResult> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}/reextract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ paths, hint }),
  });

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to re-extract fields', response.status, details);
  }

  return response.json();
}

/**
 * Get quality metrics for a job.
 */
export async function getQualityMetrics(jobId: string): Promise<QualityMetrics> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}/quality-metrics`);

  if (!response.ok) {
    throw new ApiError('Failed to get quality metrics', response.status);
  }

  return response.json();
}

/**
 * Record a user correction.
 */
export async function recordCorrection(
  jobId: string,
  path: string,
  finalValue: string | null,
  action: 'accepted' | 'edited' | 'deleted' | 'rejected'
): Promise<ExtractionOutcome> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/jobs/${jobId}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, final_value: finalValue, action }),
  });

  if (!response.ok) {
    throw new ApiError('Failed to record correction', response.status);
  }

  return response.json();
}
