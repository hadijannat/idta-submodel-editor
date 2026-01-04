/**
 * API client for the IDTA Submodel Editor backend.
 */

import type {
  SubmodelUISchema,
  TemplateInfo,
  TemplateListResponse,
  TemplateVersionInfo,
  ValidationResult,
} from '../types/ui-schema';
import type { SubmodelFormData, UploadResponse } from '../types/aas-elements';

/**
 * API configuration.
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Custom error class for API errors.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Base fetch wrapper with error handling.
 */
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let details;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError(
      `API request failed: ${response.statusText}`,
      response.status,
      details
    );
  }

  // Handle empty responses
  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }

  return response as unknown as T;
}

/**
 * Download a file from an API response.
 */
async function downloadFile(
  endpoint: string,
  options: RequestInit = {},
  filename?: string
): Promise<void> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(
      `Download failed: ${response.statusText}`,
      response.status
    );
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);

  // Extract filename from Content-Disposition header if not provided
  let downloadFilename = filename;
  if (!downloadFilename) {
    const contentDisposition = response.headers.get('Content-Disposition');
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^"]+)"?/);
      if (match) {
        downloadFilename = match[1];
      }
    }
  }

  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = downloadFilename || 'download';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

// ============================================================================
// Template API
// ============================================================================

/**
 * List all available templates.
 */
export async function listTemplates(
  search?: string,
  idtaNumber?: string
): Promise<TemplateListResponse> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (idtaNumber) params.set('idta_number', idtaNumber);

  const query = params.toString();
  return apiFetch<TemplateListResponse>(
    `/api/templates${query ? `?${query}` : ''}`
  );
}

/**
 * Get information about a specific template.
 */
export async function getTemplateInfo(
  templateName: string
): Promise<TemplateInfo> {
  return apiFetch<TemplateInfo>(`/api/templates/${encodeURIComponent(templateName)}`);
}

/**
 * Get available versions for a template.
 */
export async function getTemplateVersions(
  templateName: string
): Promise<TemplateVersionInfo[]> {
  return apiFetch<TemplateVersionInfo[]>(
    `/api/templates/${encodeURIComponent(templateName)}/versions`
  );
}

/**
 * Refresh the template cache.
 */
export async function refreshTemplateCache(): Promise<{ cleared: number }> {
  return apiFetch<{ cleared: number }>('/api/templates/refresh', {
    method: 'POST',
  });
}

// ============================================================================
// Editor API
// ============================================================================

/**
 * Get the UI schema for a template.
 */
export async function getTemplateSchema(
  templateName: string
): Promise<SubmodelUISchema> {
  return apiFetch<SubmodelUISchema>(
    `/api/editor/templates/${encodeURIComponent(templateName)}/schema`
  );
}

/**
 * Validate form data against template schema.
 */
export async function validateFormData(
  templateName: string,
  formData: SubmodelFormData
): Promise<ValidationResult> {
  return apiFetch<ValidationResult>(
    `/api/editor/validate/${encodeURIComponent(templateName)}`,
    {
      method: 'POST',
      body: JSON.stringify(formData),
    }
  );
}

/**
 * Upload an AASX file for editing.
 */
export async function uploadAasx(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/editor/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(
      `Upload failed: ${response.statusText}`,
      response.status
    );
  }

  return response.json();
}

// ============================================================================
// Export API
// ============================================================================

/**
 * Export a filled submodel as AASX.
 */
export async function exportAsAasx(
  templateName: string,
  formData: SubmodelFormData,
  filename?: string
): Promise<void> {
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?format=aasx`,
    {
      method: 'POST',
      body: JSON.stringify(formData),
    },
    filename || `${templateName}.aasx`
  );
}

/**
 * Export a filled submodel as JSON.
 */
export async function exportAsJson(
  templateName: string,
  formData: SubmodelFormData,
  filename?: string
): Promise<void> {
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?format=json`,
    {
      method: 'POST',
      body: JSON.stringify(formData),
    },
    filename || `${templateName}.json`
  );
}

/**
 * Export a filled submodel as PDF.
 */
export async function exportAsPdf(
  templateName: string,
  formData: SubmodelFormData,
  filename?: string
): Promise<void> {
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?format=pdf`,
    {
      method: 'POST',
      body: JSON.stringify(formData),
    },
    filename || `${templateName}.pdf`
  );
}

/**
 * Verify export without downloading the file.
 */
export async function verifyExport(
  templateName: string,
  formData: SubmodelFormData,
  format: 'aasx' | 'json' | 'pdf' = 'aasx'
): Promise<void> {
  const url = `${API_BASE_URL}/api/export/${encodeURIComponent(
    templateName
  )}?format=${format}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(formData),
  });

  if (!response.ok) {
    let details;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError(
      `Verification failed: ${response.statusText}`,
      response.status,
      details
    );
  }

  // Drain response without triggering download.
  try {
    await response.arrayBuffer();
  } catch {
    // Ignore body consumption errors; verification already succeeded.
  }
}

/**
 * Get template preview without form data.
 */
export async function getTemplatePreview(
  templateName: string
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(
    `/api/export/${encodeURIComponent(templateName)}/preview`
  );
}

// ============================================================================
// Health API
// ============================================================================

/**
 * Check API health status.
 */
export async function checkHealth(): Promise<{
  status: string;
  version: string;
}> {
  return apiFetch<{ status: string; version: string }>('/health');
}
