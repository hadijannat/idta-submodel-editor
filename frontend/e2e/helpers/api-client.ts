/**
 * Typed API client for E2E test setup and assertions.
 *
 * Provides typed access to all backend API endpoints for test fixtures,
 * setup, teardown, and assertion verification.
 */

import type { APIRequestContext } from '@playwright/test';

// ============================================================================
// Types
// ============================================================================

export interface Template {
  name: string;
  title?: string;
  idta_number?: string;
  version?: string;
  status: 'published' | 'deprecated';
  description?: string;
  semantic_id?: string;
}

export interface TemplateListResponse {
  templates: Template[];
  total: number;
  cached: boolean;
}

export interface UISchemaElement {
  idShort: string;
  modelType: string;
  semanticId?: string;
  semanticLabel?: string;
  description?: string;
  cardinality?: string;
  valueType?: string;
  value?: unknown;
  elements?: UISchemaElement[];
  items?: UISchemaElement[];
}

export interface UISchema {
  submodelId: string;
  idShort: string;
  semanticId?: string;
  description?: string;
  templateName?: string;
  templatePath?: string;
  elements: UISchemaElement[];
}

export interface ValidationError {
  path: string;
  message: string;
  code: string;
}

export interface ValidationWarning {
  path: string;
  message: string;
  code: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ElementFormData {
  value?: unknown;
  semanticId?: string | null;
  valueId?: string | null;
  elements?: Record<string, ElementFormData>;
  items?: ElementFormData[];
  semanticIdListElement?: string | null;
  min?: unknown;
  max?: unknown;
  globalAssetId?: string;
  statements?: Record<string, ElementFormData>;
  contentType?: string;
  first?: string;
  second?: string;
  annotations?: ElementFormData[];
  [key: string]: unknown;
}

export interface SubmodelFormData {
  elements: Record<string, ElementFormData>;
  metadata?: Record<string, unknown>;
}

export interface SemanticSearchResult {
  irdi: string;
  preferredName: string;
  definition?: string;
  source: 'eclass' | 'iec_cdd';
}

export interface SemanticSearchResponse {
  results: SemanticSearchResult[];
  total: number;
  query: string;
}

export interface MagicImportJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  error?: string;
}

export interface MagicImportExtraction {
  field_path: string;
  extracted_value: string;
  confidence: number;
  evidence?: {
    page: number;
    bbox?: [number, number, number, number];
    text_snippet?: string;
  };
}

export interface MagicImportResult {
  job_id: string;
  extractions: MagicImportExtraction[];
  template_name: string;
  processing_time_ms: number;
}

export interface DataspaceConnection {
  connection_id: string;
  environment: string;
  edc_mode: string;
  status:
    | 'not_connected'
    | 'provisioning_secrets'
    | 'configuring_edc'
    | 'registering_connector'
    | 'publishing_self_description'
    | 'connected'
    | 'degraded'
    | 'disconnected'
    | 'failed';
  progress?: number;
  progress_message?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface DataspacePublication {
  id: string;
  connection_id: string;
  template_name: string;
  submodel_id: string;
  status: 'pending' | 'published' | 'failed';
  published_at?: string;
}

export interface PolicyTemplate {
  id: string;
  name: string;
  description: string;
  odrl: object;
}

export interface MapperProfile {
  columns: {
    name: string;
    sample_values: string[];
    data_type: string;
  }[];
}

export interface MapperMapping {
  source_column: string;
  target_path: string;
  transformation?: string;
}

export interface MapperRecipe {
  id: string;
  name: string;
  template_name: string;
  mappings: MapperMapping[];
}

export interface PCFEmissionFactor {
  id: string;
  name: string;
  unit: string;
  value: number;
  source: string;
}

export interface PCFCalculationResult {
  total_co2e: number;
  breakdown: {
    scope: string;
    value: number;
    unit: string;
  }[];
}

const LANGUAGE_CODES = new Set([
  'en',
  'de',
  'fr',
  'es',
  'it',
  'zh',
  'ja',
  'ko',
  'pt',
]);

const ELEMENT_FORM_KEYS = new Set([
  'value',
  'semanticId',
  'valueId',
  'elements',
  'items',
  'semanticIdListElement',
  'min',
  'max',
  'globalAssetId',
  'statements',
  'contentType',
  'first',
  'second',
  'annotations',
]);

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isLanguageMap(value: Record<string, unknown>): boolean {
  const keys = Object.keys(value);
  if (keys.length === 0) return false;
  return keys.every((key) => LANGUAGE_CODES.has(key)) &&
    Object.values(value).every(
      (val) => typeof val === 'string' || val === null || val === undefined
    );
}

export function looksLikeElementFormData(value: Record<string, unknown>): boolean {
  return Object.keys(value).some((key) => ELEMENT_FORM_KEYS.has(key));
}

export function toElementFormData(value: unknown): ElementFormData {
  if (value === null || value === undefined) {
    return {};
  }
  if (Array.isArray(value)) {
    return { items: value.map((item) => toElementFormData(item)) };
  }
  if (isPlainObject(value)) {
    // Check if it already looks like ElementFormData first
    if (looksLikeElementFormData(value)) {
      return value as ElementFormData;
    }
    // Empty object = intentionally empty collection
    // Must check before isLanguageMap since empty objects fail that check
    if (Object.keys(value).length === 0) {
      return { elements: {} };
    }
    // Language maps (e.g., { en: 'hello', de: 'hallo' }) should be treated as values
    if (isLanguageMap(value)) {
      return { value };
    }
    // Otherwise, recursively transform nested objects
    const elements: Record<string, ElementFormData> = {};
    for (const [key, nested] of Object.entries(value)) {
      elements[key] = toElementFormData(nested);
    }
    return { elements };
  }
  return { value };
}

export function toSubmodelFormData(formData: Record<string, unknown>): SubmodelFormData {
  if (isPlainObject(formData) && 'elements' in formData) {
    return formData as SubmodelFormData;
  }
  const elements: Record<string, ElementFormData> = {};
  for (const [key, value] of Object.entries(formData || {})) {
    elements[key] = toElementFormData(value);
  }
  return { elements };
}

/**
 * Checks if an HTTP status code indicates a transient error that should be retried.
 */
function isRetryableStatus(status: number): boolean {
  return status === 429 || (status >= 500 && status < 600);
}

/**
 * Sleep for a specified number of milliseconds.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================
// API Client
// ============================================================================

export class APIClient {
  protected baseURL: string;
  protected request: APIRequestContext;

  constructor(request: APIRequestContext, baseURL: string = 'http://localhost:8000') {
    this.request = request;
    this.baseURL = baseURL;
  }

  // --------------------------------------------------------------------------
  // Health Check
  // --------------------------------------------------------------------------

  async healthCheck(): Promise<{ status: string }> {
    const response = await this.request.get(`${this.baseURL}/health`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Templates
  // --------------------------------------------------------------------------

  async getTemplates(options?: {
    search?: string;
    idta_number?: string;
    status?: 'published' | 'deprecated' | 'all';
  }): Promise<TemplateListResponse> {
    const params = new URLSearchParams();
    if (options?.search) params.set('search', options.search);
    if (options?.idta_number) params.set('idta_number', options.idta_number);
    if (options?.status) params.set('status', options.status);

    const url = `${this.baseURL}/api/templates${params.toString() ? '?' + params.toString() : ''}`;
    const response = await this.request.get(url);
    return response.json();
  }

  async getTemplate(name: string): Promise<Template> {
    const response = await this.request.get(`${this.baseURL}/api/templates/${encodeURIComponent(name)}`);
    return response.json();
  }

  async getTemplateVersions(name: string): Promise<{ version: string; date: string }[]> {
    const response = await this.request.get(
      `${this.baseURL}/api/templates/${encodeURIComponent(name)}/versions`
    );
    return response.json();
  }

  async refreshTemplateCache(): Promise<{ cleared: number }> {
    const response = await this.request.post(`${this.baseURL}/api/templates/refresh`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Editor / Schema
  // --------------------------------------------------------------------------

  async getTemplateSchema(name: string, options?: {
    status?: 'published' | 'deprecated';
    version?: string;
  }): Promise<UISchema> {
    const params = new URLSearchParams();
    if (options?.status) params.set('status', options.status);
    if (options?.version) params.set('version', options.version);

    const url = `${this.baseURL}/api/editor/templates/${encodeURIComponent(name)}/schema${
      params.toString() ? '?' + params.toString() : ''
    }`;
    const response = await this.request.get(url);
    return response.json();
  }

  async getConceptDescription(
    templateName: string,
    semanticId: string
  ): Promise<object> {
    const params = new URLSearchParams({ semantic_id: semanticId });
    const response = await this.request.get(
      `${this.baseURL}/api/editor/templates/${encodeURIComponent(templateName)}/concept-description?${params}`
    );
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Validation
  // --------------------------------------------------------------------------

  async validateFormData(
    templateName: string,
    formData: Record<string, unknown>,
    options?: { status?: 'published' | 'deprecated'; version?: string }
  ): Promise<ValidationResult> {
    const maxRetries = 3;
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const params = new URLSearchParams();
        if (options?.status) params.set('status', options.status);
        if (options?.version) params.set('version', options.version);

        const payload = toSubmodelFormData(formData);
        const response = await this.request.post(
          `${this.baseURL}/api/editor/validate/${encodeURIComponent(templateName)}${
            params.toString() ? '?' + params.toString() : ''
          }`,
          { data: payload }
        );

        if (!response.ok()) {
          const body = await response.text();
          // Retry on rate limit or server errors
          if (isRetryableStatus(response.status())) {
            lastError = new Error(`HTTP ${response.status()}: ${body}`);
            await sleep(1000 * attempt);
            continue;
          }
          throw new Error(`Validation request failed: ${body}`);
        }

        return response.json();
      } catch (error) {
        lastError = error as Error;
        if (attempt < maxRetries) {
          await sleep(1000 * attempt);
        }
      }
    }

    throw lastError;
  }

  // --------------------------------------------------------------------------
  // Export
  // --------------------------------------------------------------------------

  async exportAasx(
    templateName: string,
    formData: Record<string, unknown>,
    options?: { status?: 'published' | 'deprecated'; version?: string }
  ): Promise<Buffer> {
    const maxRetries = 3;
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const params = new URLSearchParams({ format: 'aasx' });
        if (options?.status) params.set('status', options.status);
        if (options?.version) params.set('version', options.version);

        const payload = toSubmodelFormData(formData);
        const response = await this.request.post(
          `${this.baseURL}/api/export/${encodeURIComponent(templateName)}?${params}`,
          { data: payload }
        );

        // Check for error response
        if (!response.ok()) {
          const body = await response.text();
          // Retry on rate limit or server errors
          if (isRetryableStatus(response.status())) {
            lastError = new Error(`Export failed with status ${response.status()}: ${body}`);
            await sleep(1000 * attempt);
            continue;
          }
          throw new Error(`Export failed with status ${response.status()}: ${body}`);
        }

        return Buffer.from(await response.body());
      } catch (error) {
        lastError = error as Error;
        if (attempt < maxRetries) {
          await sleep(1000 * attempt);
        }
      }
    }

    throw lastError!;
  }

  async exportJson(
    templateName: string,
    formData: Record<string, unknown>,
    options?: { status?: 'published' | 'deprecated'; version?: string }
  ): Promise<object> {
    const maxRetries = 3;
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const params = new URLSearchParams({ format: 'json' });
        if (options?.status) params.set('status', options.status);
        if (options?.version) params.set('version', options.version);

        const payload = toSubmodelFormData(formData);
        const response = await this.request.post(
          `${this.baseURL}/api/export/${encodeURIComponent(templateName)}?${params}`,
          { data: payload }
        );

        if (!response.ok()) {
          const body = await response.text();
          // Retry on rate limit or server errors
          if (isRetryableStatus(response.status())) {
            lastError = new Error(`Export failed with status ${response.status()}: ${body}`);
            await sleep(1000 * attempt);
            continue;
          }
          throw new Error(`Export failed with status ${response.status()}: ${body}`);
        }

        return response.json();
      } catch (error) {
        lastError = error as Error;
        if (attempt < maxRetries) {
          await sleep(1000 * attempt);
        }
      }
    }

    throw lastError!;
  }

  async exportPdf(
    templateName: string,
    formData: Record<string, unknown>,
    options?: {
      status?: 'published' | 'deprecated';
      version?: string;
      include_conformance?: boolean;
    }
  ): Promise<Buffer> {
    const params = new URLSearchParams({ format: 'pdf' });
    if (options?.status) params.set('status', options.status);
    if (options?.version) params.set('version', options.version);
    if (options?.include_conformance !== undefined) {
      params.set('include_conformance', String(options.include_conformance));
    }

    const payload = toSubmodelFormData(formData);
    const response = await this.request.post(
      `${this.baseURL}/api/export/${encodeURIComponent(templateName)}?${params}`,
      { data: payload }
    );
    return Buffer.from(await response.body());
  }

  // --------------------------------------------------------------------------
  // Semantic Lookup
  // --------------------------------------------------------------------------

  async searchSemantic(
    query: string,
    options?: { provider?: 'eclass' | 'iec_cdd'; limit?: number }
  ): Promise<SemanticSearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (options?.provider) params.set('provider', options.provider);
    if (options?.limit) params.set('limit', String(options.limit));

    const response = await this.request.get(`${this.baseURL}/api/semantic/search?${params}`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Smart Mapper
  // --------------------------------------------------------------------------

  async uploadMapperFile(
    file: Buffer,
    filename: string
  ): Promise<{ session_id: string; profile: MapperProfile }> {
    const response = await this.request.post(`${this.baseURL}/api/mapper/upload`, {
      multipart: {
        file: {
          name: filename,
          mimeType: filename.endsWith('.xlsx')
            ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            : 'text/csv',
          buffer: file,
        },
      },
    });
    return response.json();
  }

  async getMapperSuggestions(
    sessionId: string,
    templateName: string
  ): Promise<MapperMapping[]> {
    const response = await this.request.post(`${this.baseURL}/api/mapper/suggest`, {
      data: { session_id: sessionId, template_name: templateName },
    });
    return response.json();
  }

  async applyMapperMappings(
    sessionId: string,
    mappings: MapperMapping[]
  ): Promise<Record<string, unknown>> {
    const response = await this.request.post(`${this.baseURL}/api/mapper/apply`, {
      data: { session_id: sessionId, mappings },
    });
    return response.json();
  }

  async saveMapperRecipe(recipe: Omit<MapperRecipe, 'id'>): Promise<MapperRecipe> {
    const response = await this.request.post(`${this.baseURL}/api/mapper/recipes`, {
      data: recipe,
    });
    return response.json();
  }

  async getMapperRecipes(templateName?: string): Promise<MapperRecipe[]> {
    const params = templateName ? `?template_name=${encodeURIComponent(templateName)}` : '';
    const response = await this.request.get(`${this.baseURL}/api/mapper/recipes${params}`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Magic Import
  // --------------------------------------------------------------------------

  async createMagicImportJob(
    pdfFile: Buffer,
    templateName: string,
    options?: { provider?: string; use_ocr?: boolean }
  ): Promise<MagicImportJob> {
    const formData: Record<string, unknown> = {
      file: {
        name: 'document.pdf',
        mimeType: 'application/pdf',
        buffer: pdfFile,
      },
      template_name: templateName,
    };
    if (options?.provider) formData['provider'] = options.provider;
    if (options?.use_ocr !== undefined) formData['use_ocr'] = options.use_ocr;

    const response = await this.request.post(`${this.baseURL}/api/magic-import/jobs`, {
      multipart: formData as Record<string, unknown>,
    });
    return response.json();
  }

  async getMagicImportJobStatus(jobId: string): Promise<MagicImportJob> {
    const response = await this.request.get(`${this.baseURL}/api/magic-import/jobs/${jobId}`);
    return response.json();
  }

  async getMagicImportResult(jobId: string): Promise<MagicImportResult> {
    const response = await this.request.get(`${this.baseURL}/api/magic-import/jobs/${jobId}/result`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // PCF Calculator
  // --------------------------------------------------------------------------

  async searchEmissionFactors(query: string): Promise<PCFEmissionFactor[]> {
    const response = await this.request.get(
      `${this.baseURL}/api/pcf/emission-factors?q=${encodeURIComponent(query)}`
    );
    return response.json();
  }

  async calculatePCF(
    templateName: string,
    formData: Record<string, unknown>
  ): Promise<PCFCalculationResult> {
    const response = await this.request.post(`${this.baseURL}/api/pcf/calculate`, {
      data: { template_name: templateName, form_data: formData },
    });
    return response.json();
  }

  async validatePCF(
    formData: Record<string, unknown>,
    templateSchema: UISchema
  ): Promise<ValidationResult & { completeness_score?: number }> {
    const response = await this.request.post(`${this.baseURL}/api/pcf/validate`, {
      data: { form_data: formData, template_schema: templateSchema },
    });
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Dataspace
  // --------------------------------------------------------------------------

  async getDataspaceEnvironments(): Promise<{ id: string; name: string; description: string }[]> {
    const response = await this.request.get(`${this.baseURL}/api/dataspace/environments`);
    return response.json();
  }

  async getDataspaceEdcModes(): Promise<{ id: string; name: string; description: string }[]> {
    const response = await this.request.get(`${this.baseURL}/api/dataspace/edc-modes`);
    return response.json();
  }

  async createDataspaceConnection(
    environment: string,
    edcMode: string
  ): Promise<DataspaceConnection> {
    const response = await this.request.post(`${this.baseURL}/api/dataspace/connections`, {
      data: { environment, edc_mode: edcMode },
    });
    return response.json();
  }

  async getDataspaceConnections(): Promise<DataspaceConnection[]> {
    const response = await this.request.get(`${this.baseURL}/api/dataspace/connections`);
    return response.json();
  }

  async getDataspaceConnection(connectionId: string): Promise<DataspaceConnection> {
    const response = await this.request.get(
      `${this.baseURL}/api/dataspace/connections/${connectionId}`
    );
    return response.json();
  }

  async deleteDataspaceConnection(connectionId: string): Promise<void> {
    await this.request.delete(`${this.baseURL}/api/dataspace/connections/${connectionId}`);
  }

  async publishSubmodel(
    connectionId: string,
    templateName: string,
    formData: Record<string, unknown>,
    policyId?: string
  ): Promise<DataspacePublication> {
    const response = await this.request.post(`${this.baseURL}/api/dataspace/publications`, {
      data: {
        connection_id: connectionId,
        template_name: templateName,
        form_data: formData,
        policy_id: policyId,
      },
    });
    return response.json();
  }

  async getPublications(options?: {
    connection_id?: string;
    template_name?: string;
    status?: string;
  }): Promise<DataspacePublication[]> {
    const params = new URLSearchParams();
    if (options?.connection_id) params.set('connection_id', options.connection_id);
    if (options?.template_name) params.set('template_name', options.template_name);
    if (options?.status) params.set('status', options.status);

    const url = `${this.baseURL}/api/dataspace/publications${
      params.toString() ? '?' + params.toString() : ''
    }`;
    const response = await this.request.get(url);
    return response.json();
  }

  async unpublishSubmodel(publicationId: string): Promise<void> {
    await this.request.delete(`${this.baseURL}/api/dataspace/publications/${publicationId}`);
  }

  async getPolicyTemplates(): Promise<PolicyTemplate[]> {
    const response = await this.request.get(`${this.baseURL}/api/dataspace/policies/templates`);
    return response.json();
  }

  async previewPolicy(config: object): Promise<object> {
    const response = await this.request.post(`${this.baseURL}/api/dataspace/policies/preview`, {
      data: config,
    });
    return response.json();
  }

  async getDataspaceHealth(): Promise<{
    services: { name: string; status: string; latency_ms?: number }[];
  }> {
    const response = await this.request.get(`${this.baseURL}/api/dataspace/health`);
    return response.json();
  }

  // --------------------------------------------------------------------------
  // Template Operations
  // --------------------------------------------------------------------------

  async diffTemplates(
    sourceName: string,
    targetName: string
  ): Promise<{
    added: string[];
    removed: string[];
    modified: { path: string; source: unknown; target: unknown }[];
  }> {
    const response = await this.request.post(`${this.baseURL}/api/template-ops/diff`, {
      data: { source_template: sourceName, target_template: targetName },
    });
    return response.json();
  }

  async getMigrationSuggestions(
    sourceName: string,
    targetName: string,
    formData: Record<string, unknown>
  ): Promise<MapperMapping[]> {
    const response = await this.request.post(`${this.baseURL}/api/template-ops/migrate/suggest`, {
      data: {
        source_template: sourceName,
        target_template: targetName,
        form_data: formData,
      },
    });
    return response.json();
  }

  async applyMigration(
    mappings: MapperMapping[],
    formData: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const response = await this.request.post(`${this.baseURL}/api/template-ops/migrate/apply`, {
      data: { mappings, form_data: formData },
    });
    return response.json();
  }

  async importLocalTemplate(
    file: Buffer,
    filename: string,
    name?: string
  ): Promise<{ success: boolean; template?: Template; error?: string }> {
    const formData: Record<string, unknown> = {
      file: {
        name: filename,
        mimeType: 'application/asset-administration-shell-package+xml',
        buffer: file,
      },
    };

    const params = name ? `?name=${encodeURIComponent(name)}` : '';
    const response = await this.request.post(
      `${this.baseURL}/api/editor/templates/local${params}`,
      { multipart: formData }
    );
    return response.json();
  }
}
