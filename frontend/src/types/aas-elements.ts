/**
 * Type definitions for AAS element form data.
 *
 * These types define the shape of data submitted from forms.
 */

/**
 * Form data for a single element.
 */
export interface ElementFormData {
  // Common value field
  value?: unknown;

  // For SubmodelElementCollection
  elements?: Record<string, ElementFormData>;

  // For SubmodelElementList
  items?: ElementFormData[];

  // For Range
  min?: unknown;
  max?: unknown;

  // For Entity
  globalAssetId?: string;
  statements?: Record<string, ElementFormData>;

  // For File
  contentType?: string;

  // For Relationship
  first?: string;
  second?: string;
  annotations?: ElementFormData[];

  // Allow additional properties
  [key: string]: unknown;
}

/**
 * Complete form submission data.
 */
export interface SubmodelFormData {
  elements: Record<string, ElementFormData>;
  metadata?: Record<string, unknown>;
}

/**
 * Export request payload.
 */
export interface ExportRequest {
  template_name: string;
  form_data: SubmodelFormData;
  format: 'aasx' | 'json' | 'pdf';
  filename?: string;
}

/**
 * Response from AASX upload.
 */
export interface UploadResponse {
  success: boolean;
  schema?: Record<string, unknown>;
  error?: string;
  filename?: string;
}

/**
 * Language codes used in the application.
 */
export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'de', name: 'Deutsch' },
  { code: 'fr', name: 'Français' },
  { code: 'es', name: 'Español' },
  { code: 'it', name: 'Italiano' },
  { code: 'zh', name: '中文' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' },
  { code: 'pt', name: 'Português' },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

/**
 * Multi-language value type.
 */
export type MultiLanguageValue = Partial<Record<LanguageCode, string>>;

/**
 * Helper to check if a cardinality indicates required.
 */
export function isRequired(cardinality: string): boolean {
  const normalized = normalizeCardinality(cardinality);
  return normalized === '[1]' || normalized === '[1..*]';
}

/**
 * Helper to check if a cardinality allows multiple items.
 */
export function allowsMultiple(cardinality: string): boolean {
  const normalized = normalizeCardinality(cardinality);
  return normalized.includes('*') || normalized.includes('..');
}

/**
 * Get minimum required items from cardinality.
 */
export function getMinItems(cardinality: string): number {
  const normalized = normalizeCardinality(cardinality);
  if (normalized === '[1..*]') return 1;
  if (normalized === '[0..*]' || normalized === '[0..1]') return 0;
  if (normalized === '[1]') return 1;
  return 0;
}

/**
 * Get maximum allowed items from cardinality.
 */
export function getMaxItems(cardinality: string): number | undefined {
  const normalized = normalizeCardinality(cardinality);
  if (normalized.includes('*')) return undefined;
  if (normalized === '[0..1]' || normalized === '[1]') return 1;
  return undefined;
}

/**
 * Normalize common cardinality encodings to bracket format.
 */
export function normalizeCardinality(cardinality: string): string {
  const trimmed = (cardinality || '').trim();
  const mapping: Record<string, string> = {
    ZeroToOne: '[0..1]',
    ZeroToMany: '[0..*]',
    OneToMany: '[1..*]',
    One: '[1]',
    Zero: '[0]',
  };

  if (mapping[trimmed]) return mapping[trimmed];
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) return trimmed;
  if (trimmed.includes('..')) return `[${trimmed}]`;
  if (/^\\d+$/.test(trimmed)) return `[${trimmed}]`;
  return trimmed;
}
