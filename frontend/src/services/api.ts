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
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
export async function apiFetch<T>(
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
  idtaNumber?: string,
  status?: 'published' | 'deprecated' | 'all'
): Promise<TemplateListResponse> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (idtaNumber) params.set('idta_number', idtaNumber);
  if (status) params.set('status', status);

  const query = params.toString();
  return apiFetch<TemplateListResponse>(
    `/api/templates${query ? `?${query}` : ''}`
  );
}

/**
 * Get information about a specific template.
 */
export async function getTemplateInfo(
  templateName: string,
  status?: 'published' | 'deprecated' | 'all'
): Promise<TemplateInfo> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const query = params.toString();
  return apiFetch<TemplateInfo>(
    `/api/templates/${encodeURIComponent(templateName)}${
      query ? `?${query}` : ''
    }`
  );
}

/**
 * Get available versions for a template.
 */
export async function getTemplateVersions(
  templateName: string,
  status?: 'published' | 'deprecated'
): Promise<TemplateVersionInfo[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const query = params.toString();
  return apiFetch<TemplateVersionInfo[]>(
    `/api/templates/${encodeURIComponent(templateName)}/versions${
      query ? `?${query}` : ''
    }`
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
  templateName: string,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<SubmodelUISchema> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  const query = params.toString();
  return apiFetch<SubmodelUISchema>(
    `/api/editor/templates/${encodeURIComponent(templateName)}/schema${
      query ? `?${query}` : ''
    }`
  );
}

/**
 * Validate form data against template schema.
 */
export async function validateFormData(
  templateName: string,
  formData: SubmodelFormData,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<ValidationResult> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  const query = params.toString();
  return apiFetch<ValidationResult>(
    `/api/editor/validate/${encodeURIComponent(templateName)}${
      query ? `?${query}` : ''
    }`,
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
  filename?: string,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<void> {
  const params = new URLSearchParams({ format: 'aasx' });
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?${params.toString()}`,
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
  filename?: string,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<void> {
  const params = new URLSearchParams({ format: 'json' });
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?${params.toString()}`,
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
  filename?: string,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<void> {
  const params = new URLSearchParams({ format: 'pdf' });
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  await downloadFile(
    `/api/export/${encodeURIComponent(templateName)}?${params.toString()}`,
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
  format: 'aasx' | 'json' | 'pdf' = 'aasx',
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<void> {
  const params = new URLSearchParams({ format });
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  const url = `${API_BASE_URL}/api/export/${encodeURIComponent(
    templateName
  )}?${params.toString()}`;

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
  templateName: string,
  status?: 'published' | 'deprecated',
  version?: string | null
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (version) params.set('version', version);
  const query = params.toString();
  return apiFetch<Record<string, unknown>>(
    `/api/export/${encodeURIComponent(templateName)}/preview${
      query ? `?${query}` : ''
    }`
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

// ============================================================================
// Settings API
// ============================================================================

/**
 * Public settings from backend.
 */
export interface PublicSettings {
  mnestix_enabled: boolean;
  mnestix_url: string | null;
  basyx_registry_url: string | null;
  dataspace_enabled: boolean;
}

/**
 * Get public settings from the backend.
 */
export async function getPublicSettings(): Promise<PublicSettings> {
  return apiFetch<PublicSettings>('/api/settings');
}

// ============================================================================
// Tools API
// ============================================================================

/**
 * Tool metadata from the backend API.
 */
export interface ToolMetadataResponse {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  wizard_step: number | null;
  feature_flag: string | null;
  requires_auth: boolean;
  dependencies: string[];
  enabled: boolean;
  initialized: boolean;
}

/**
 * Tool health status.
 */
export interface ToolHealthResponse {
  tool_id: string;
  healthy: boolean;
  message: string | null;
}

/**
 * Health status for all tools.
 */
export interface ToolsHealthResponse {
  tools: Record<string, ToolHealthResponse>;
  all_healthy: boolean;
}

/**
 * Dependency check result.
 */
export interface ToolDependencyResponse {
  id: string;
  status: string;
  message: string | null;
}

/**
 * Full capability report for a tool.
 */
export interface ToolCapabilityReportResponse {
  tool_id: string;
  enabled: boolean;
  initialized: boolean;
  healthy: boolean;
  health_message: string | null;
  dependencies: ToolDependencyResponse[];
  capabilities: Record<string, unknown>;
  all_dependencies_satisfied: boolean;
}

/**
 * List all registered tools.
 *
 * @param enabledOnly - If true, only return enabled tools
 * @param category - Filter by category (core, import, export, integration, analytics)
 */
export async function getTools(
  enabledOnly = false,
  category?: string
): Promise<ToolMetadataResponse[]> {
  const params = new URLSearchParams();
  if (enabledOnly) params.set('enabled_only', 'true');
  if (category) params.set('category', category);
  const query = params.toString();
  return apiFetch<ToolMetadataResponse[]>(
    `/api/tools${query ? `?${query}` : ''}`
  );
}

/**
 * Get the full tool manifest for frontend consumption.
 *
 * Returns all tools with their metadata and runtime status.
 */
export async function getToolManifest(): Promise<ToolMetadataResponse[]> {
  return apiFetch<ToolMetadataResponse[]>('/api/tools/manifest');
}

/**
 * Check health of all enabled tools.
 */
export async function getToolsHealth(): Promise<ToolsHealthResponse> {
  return apiFetch<ToolsHealthResponse>('/api/tools/health');
}

/**
 * Get detailed information about a specific tool.
 *
 * @param toolId - The tool's unique identifier
 */
export async function getToolById(
  toolId: string
): Promise<ToolCapabilityReportResponse> {
  return apiFetch<ToolCapabilityReportResponse>(
    `/api/tools/${encodeURIComponent(toolId)}`
  );
}

/**
 * Check health of a specific tool.
 *
 * @param toolId - The tool's unique identifier
 */
export async function getToolHealth(toolId: string): Promise<ToolHealthResponse> {
  return apiFetch<ToolHealthResponse>(
    `/api/tools/${encodeURIComponent(toolId)}/health`
  );
}

/**
 * Get capabilities provided by a specific tool.
 *
 * @param toolId - The tool's unique identifier
 */
export async function getToolCapabilities(
  toolId: string
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(
    `/api/tools/${encodeURIComponent(toolId)}/capabilities`
  );
}

// ============================================================================
// Template Ops API
// ============================================================================

/**
 * Element change in a diff.
 */
export interface ElementChange {
  path: string;
  change_type: 'added' | 'removed' | 'modified' | 'moved' | 'renamed';
  old_value: string | null;
  new_value: string | null;
  details: Record<string, unknown> | null;
}

/**
 * Cardinality change in a diff.
 */
export interface CardinalityChange {
  path: string;
  old_cardinality: string;
  new_cardinality: string;
  breaking: boolean;
}

/**
 * Semantic change in a diff.
 */
export interface SemanticChange {
  path: string;
  old_semantic_id: string | null;
  new_semantic_id: string | null;
}

/**
 * Result of template diff operation.
 */
export interface TemplateDiffResult {
  source_template: string;
  source_version: string | null;
  target_template: string;
  target_version: string | null;
  elements_added: string[];
  elements_removed: string[];
  elements_modified: ElementChange[];
  cardinality_changes: CardinalityChange[];
  semantic_changes: SemanticChange[];
  is_breaking: boolean;
  summary: string;
}

/**
 * Migration mapping item.
 */
export interface MigrationMappingItem {
  source_path: string;
  target_path: string;
  confidence: number;
  match_reason: 'exact' | 'semantic' | 'fuzzy' | 'manual';
  transform: string | null;
}

/**
 * Migration plan between template versions.
 */
export interface MigrationPlan {
  source_template: string;
  source_version: string | null;
  target_template: string;
  target_version: string | null;
  auto_mappings: MigrationMappingItem[];
  unmapped_source: string[];
  unmapped_target: string[];
  mapping_coverage: number;
  warnings: string[];
}

/**
 * Validation diagnostic item.
 */
export interface ValidationDiagnostic {
  path: string;
  severity: 'error' | 'warning' | 'info';
  code: string;
  message: string;
  suggestion: string | null;
}

/**
 * Validation diagnostics for a template.
 */
export interface ValidationDiagnostics {
  template_name: string;
  template_version: string | null;
  valid: boolean;
  errors: ValidationDiagnostic[];
  warnings: ValidationDiagnostic[];
  info: ValidationDiagnostic[];
  element_count: number;
  semantic_coverage: number;
  conformance_level: string | null;
}

/**
 * Diff two template versions.
 */
export async function diffTemplates(
  sourceTemplate: string,
  targetTemplate: string,
  options?: {
    sourceVersion?: string;
    sourceStatus?: 'published' | 'deprecated' | 'local';
    targetVersion?: string;
    targetStatus?: 'published' | 'deprecated' | 'local';
    includeSemanticChanges?: boolean;
  }
): Promise<TemplateDiffResult> {
  return apiFetch<TemplateDiffResult>('/api/template-ops/diff', {
    method: 'POST',
    body: JSON.stringify({
      source_template: sourceTemplate,
      source_version: options?.sourceVersion,
      source_status: options?.sourceStatus || 'published',
      target_template: targetTemplate,
      target_version: options?.targetVersion,
      target_status: options?.targetStatus || 'published',
      include_semantic_changes: options?.includeSemanticChanges ?? true,
    }),
  });
}

/**
 * Generate migration plan between template versions.
 */
export async function generateMigrationPlan(
  sourceTemplate: string,
  targetTemplate: string,
  options?: {
    sourceVersion?: string;
    sourceStatus?: 'published' | 'deprecated' | 'local';
    targetVersion?: string;
    targetStatus?: 'published' | 'deprecated' | 'local';
    useSemantics?: boolean;
    minConfidence?: number;
  }
): Promise<MigrationPlan> {
  return apiFetch<MigrationPlan>('/api/template-ops/migrate', {
    method: 'POST',
    body: JSON.stringify({
      source_template: sourceTemplate,
      source_version: options?.sourceVersion,
      source_status: options?.sourceStatus || 'published',
      target_template: targetTemplate,
      target_version: options?.targetVersion,
      target_status: options?.targetStatus || 'published',
      use_semantics: options?.useSemantics ?? true,
      min_confidence: options?.minConfidence ?? 0.5,
    }),
  });
}

/**
 * Run comprehensive validation on a template.
 */
export async function validateTemplate(
  templateName: string,
  options?: {
    templateVersion?: string;
    templateStatus?: 'published' | 'deprecated' | 'local';
    checkSemanticIds?: boolean;
    checkCardinality?: boolean;
    checkValueTypes?: boolean;
    checkConformance?: boolean;
  }
): Promise<ValidationDiagnostics> {
  return apiFetch<ValidationDiagnostics>('/api/template-ops/validate', {
    method: 'POST',
    body: JSON.stringify({
      template_name: templateName,
      template_version: options?.templateVersion,
      template_status: options?.templateStatus || 'published',
      check_semantic_ids: options?.checkSemanticIds ?? true,
      check_cardinality: options?.checkCardinality ?? true,
      check_value_types: options?.checkValueTypes ?? true,
      check_conformance: options?.checkConformance ?? true,
    }),
  });
}
