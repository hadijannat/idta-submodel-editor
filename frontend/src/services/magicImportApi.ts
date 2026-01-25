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
  | 'done'
  | 'failed';

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
 * Extracted field value.
 */
export interface FieldExtraction {
  path: string;
  value_type?: string | null;
  value_raw: string;
  value_normalized: string | number | boolean | null;
  confidence: number;
  confidence_breakdown: ConfidenceBreakdown | null;
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
