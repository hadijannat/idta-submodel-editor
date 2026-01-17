/**
 * Value Extractors - Safe form data extraction utilities.
 *
 * These utilities extract values from nested form data structures
 * with strict parsing, recursion guards, and multilingual handling.
 */

import type {
  ElementFormData,
  SubmodelFormData,
  MultiLanguageValue,
} from '../../../types/aas-elements';

export type PrimitiveValue = string | number | boolean;

interface LangStringEntry {
  language?: string;
  lang?: string;
  text?: string;
  value?: string;
}

const DEFAULT_MAX_DEPTH = 6;
const STRICT_NUMBER_PATTERN = /^-?\d+(\.\d+)?$/;
const SAFE_PROTOCOLS = new Set(['http:', 'https:']);

/**
 * Navigate to an element at a dot-separated path.
 * Example: getElementAtPath(formData, 'elements.ManufacturerName')
 */
export function getElementAtPath(
  formData: SubmodelFormData | undefined,
  path: string
): ElementFormData | undefined {
  if (!formData) return undefined;

  const parts = path.split('.');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = formData;

  for (const part of parts) {
    if (current === undefined || current === null) return undefined;
    current = current[part];
  }

  return current as ElementFormData | undefined;
}

/**
 * Extract a primitive from a raw value or ElementFormData object.
 */
export function extractPrimitiveValue(value: unknown): PrimitiveValue | undefined {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }

  if (value && typeof value === 'object' && 'value' in value) {
    const inner = (value as { value?: unknown }).value;
    if (
      typeof inner === 'string' ||
      typeof inner === 'number' ||
      typeof inner === 'boolean'
    ) {
      return inner;
    }
  }

  return undefined;
}

/**
 * Extract a primitive value (string, number, boolean) from a path.
 * Handles both direct values and nested .value properties.
 */
export function extractPrimitive(
  formData: SubmodelFormData | undefined,
  path: string
): string | number | boolean | undefined {
  const element = getElementAtPath(formData, path);
  if (element === undefined || element === null) return undefined;

  return extractPrimitiveValue(element);
}

/**
 * Check if a MultiLanguageProperty value object has language strings.
 */
function isMultiLanguageValue(value: unknown): value is MultiLanguageValue {
  if (!value || typeof value !== 'object') return false;
  const keys = Object.keys(value);
  // Check if keys look like language codes (2-3 chars)
  return keys.some((k) => /^[a-z]{2,3}(-[A-Z]{2,3})?$/i.test(k));
}

function isLangStringArray(value: unknown): value is LangStringEntry[] {
  if (!Array.isArray(value)) return false;
  return value.some(
    (entry) =>
      entry &&
      typeof entry === 'object' &&
      ('language' in entry || 'lang' in entry || 'text' in entry || 'value' in entry)
  );
}

/**
 * Extract a multilanguage string from a path.
 * Tries preferred language first, then falls back to en, then first available.
 */
export function extractLangString(
  formData: SubmodelFormData | undefined,
  path: string,
  preferredLang: string = 'en'
): string | undefined {
  const element = getElementAtPath(formData, path);
  if (element === undefined || element === null) return undefined;

  return extractLangStringValue(element, [preferredLang, 'en']);
}

/**
 * Pick best available language from a multilanguage value.
 */
function pickLanguage(value: MultiLanguageValue, preferredLangs: string[]): string | undefined {
  for (const lang of preferredLangs) {
    const candidate = value[lang as keyof MultiLanguageValue];
    if (candidate && typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
  }

  for (const val of Object.values(value)) {
    if (typeof val === 'string' && val.trim()) {
      return val.trim();
    }
  }

  return undefined;
}

/**
 * Extract a multilanguage string from raw values or ElementFormData.
 */
export function extractLangStringValue(
  value: unknown,
  preferredLangs: string[] = ['en']
): string | undefined {
  if (typeof value === 'string' && value.trim()) return value.trim();

  if (isMultiLanguageValue(value)) {
    return pickLanguage(value, preferredLangs);
  }

  if (isLangStringArray(value)) {
    for (const lang of preferredLangs) {
      const match = value.find(
        (entry) => entry.language === lang || entry.lang === lang
      );
      if (match && typeof match.text === 'string' && match.text.trim()) {
        return match.text.trim();
      }
      if (match && typeof match.value === 'string' && match.value.trim()) {
        return match.value.trim();
      }
    }

    for (const entry of value) {
      if (typeof entry.text === 'string' && entry.text.trim()) return entry.text.trim();
      if (typeof entry.value === 'string' && entry.value.trim()) return entry.value.trim();
    }
  }

  if (value && typeof value === 'object' && 'value' in value) {
    const inner = (value as { value?: unknown }).value;
    if (isMultiLanguageValue(inner)) {
      return pickLanguage(inner, preferredLangs);
    }
    if (isLangStringArray(inner)) {
      return extractLangStringValue(inner, preferredLangs);
    }
    if (typeof inner === 'string' && inner.trim()) return inner.trim();
  }

  return undefined;
}

/**
 * Extract child elements from a SubmodelElementCollection.
 * Returns a record of idShort -> ElementFormData
 */
export function extractCollection(
  formData: SubmodelFormData | undefined,
  path: string
): Record<string, ElementFormData> | undefined {
  const element = getElementAtPath(formData, path);
  if (element === undefined || element === null) return undefined;

  // Check for .elements property
  if (typeof element === 'object' && 'elements' in element && element.elements) {
    return element.elements as Record<string, ElementFormData>;
  }

  // The element itself might be the collection record
  if (typeof element === 'object' && !('value' in element)) {
    return element as Record<string, ElementFormData>;
  }

  return undefined;
}

/**
 * Extract list items from a SubmodelElementList.
 */
export function extractList(
  formData: SubmodelFormData | undefined,
  path: string
): ElementFormData[] | undefined {
  const element = getElementAtPath(formData, path);
  if (element === undefined || element === null) return undefined;

  // Check for .items property
  if (typeof element === 'object' && 'items' in element && Array.isArray(element.items)) {
    return element.items;
  }

  // The element itself might be an array
  if (Array.isArray(element)) {
    return element;
  }

  return undefined;
}

/**
 * Traverse an object graph safely with depth and cycle guards.
 */
export function traverseValue(
  value: unknown,
  visitor: (value: unknown, path: Array<string | number>) => void,
  options: { maxDepth?: number } = {}
) {
  const maxDepth = options.maxDepth ?? DEFAULT_MAX_DEPTH;
  const seen = new WeakSet<object>();

  const walk = (node: unknown, path: Array<string | number>, depth: number) => {
    if (depth > maxDepth) return;
    visitor(node, path);

    if (!node || typeof node !== 'object') return;
    if (seen.has(node as object)) return;
    seen.add(node as object);

    if (Array.isArray(node)) {
      node.forEach((item, index) => walk(item, [...path, index], depth + 1));
      return;
    }

    for (const [key, val] of Object.entries(node)) {
      walk(val, [...path, key], depth + 1);
    }
  };

  walk(value, [], 0);
}

/**
 * Check if a value is "provided" (not empty/placeholder).
 * Returns false for: undefined, null, empty string, whitespace only,
 * placeholder text like "Enter...", "[Not provided]"
 */
export function isProvided(value: unknown): boolean {
  if (value === undefined || value === null) return false;

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return false;

    // Common placeholder patterns
    const placeholders = [
      /^enter\s/i,
      /^type\s/i,
      /^select\s/i,
      /^\[.*\]$/,
      /^placeholder$/i,
      /^example$/i,
      /^sample$/i,
      /^tbd$/i,
      /^tba$/i,
      /^\.\.\.$/,
    ];

    return !placeholders.some((p) => p.test(trimmed));
  }

  if (typeof value === 'number') return !isNaN(value);
  if (typeof value === 'boolean') return true;

  // Objects/arrays are considered provided if they have content
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;

  return true;
}

/**
 * Strict numeric parsing (no locale commas, no trailing text).
 */
export function parseStrictNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (!STRICT_NUMBER_PATTERN.test(trimmed)) return undefined;
  const num = Number(trimmed);
  return Number.isFinite(num) ? num : undefined;
}

/**
 * Format a value for display.
 * Handles numbers, booleans, dates, and strings.
 */
export function formatValue(value: unknown): string {
  if (value === undefined || value === null) return '';

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '';
    if (Math.abs(value) >= 1000) {
      return value.toLocaleString();
    }
    if (!Number.isInteger(value)) {
      return value.toFixed(4).replace(/\.?0+$/, '');
    }
    return value.toString();
  }

  if (typeof value === 'string') {
    return value.trim();
  }

  return String(value);
}

/**
 * Extract a numeric value from a path.
 */
export function extractNumber(
  formData: SubmodelFormData | undefined,
  path: string
): number | undefined {
  const primitive = extractPrimitive(formData, path);

  return parseStrictNumber(primitive);
}

/**
 * Return a safe URL if the string is http(s).
 */
export function extractSafeUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  try {
    const url = new URL(trimmed);
    if (!SAFE_PROTOCOLS.has(url.protocol)) return undefined;
    return url.toString();
  } catch {
    return undefined;
  }
}
