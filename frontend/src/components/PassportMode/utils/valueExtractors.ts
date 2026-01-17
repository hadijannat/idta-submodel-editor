/**
 * Value Extractors - Safe form data extraction utilities.
 *
 * These utilities extract values from nested form data structures
 * with type-safe handling of undefined paths and multilanguage values.
 */

import type { ElementFormData, SubmodelFormData, MultiLanguageValue } from '../../../types/aas-elements';

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
 * Extract a primitive value (string, number, boolean) from a path.
 * Handles both direct values and nested .value properties.
 */
export function extractPrimitive(
  formData: SubmodelFormData | undefined,
  path: string
): string | number | boolean | undefined {
  const element = getElementAtPath(formData, path);
  if (element === undefined || element === null) return undefined;

  // Direct primitive
  if (typeof element === 'string' || typeof element === 'number' || typeof element === 'boolean') {
    return element;
  }

  // Object with .value property
  if (typeof element === 'object' && 'value' in element) {
    const val = element.value;
    if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
      return val;
    }
  }

  return undefined;
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

  // Check if element itself is a lang map
  if (isMultiLanguageValue(element)) {
    return pickLanguage(element, preferredLang);
  }

  // Check .value property
  if (typeof element === 'object' && 'value' in element) {
    const val = element.value;

    // Direct string value
    if (typeof val === 'string') {
      return val || undefined;
    }

    // Multilanguage value object
    if (isMultiLanguageValue(val)) {
      return pickLanguage(val, preferredLang);
    }
  }

  // Fallback: check if the element has lang keys directly
  if (typeof element === 'object') {
    const obj = element as Record<string, unknown>;
    if (obj.en || obj.de || Object.keys(obj).some((k) => k.length === 2)) {
      return pickLanguage(obj as MultiLanguageValue, preferredLang);
    }
  }

  return undefined;
}

/**
 * Pick best available language from a multilanguage value.
 */
function pickLanguage(value: MultiLanguageValue, preferredLang: string): string | undefined {
  // Try preferred language
  const preferred = value[preferredLang as keyof MultiLanguageValue];
  if (preferred && typeof preferred === 'string' && preferred.trim()) {
    return preferred.trim();
  }

  // Try English as fallback
  const english = value.en;
  if (english && typeof english === 'string' && english.trim()) {
    return english.trim();
  }

  // Return first non-empty value
  for (const val of Object.values(value)) {
    if (typeof val === 'string' && val.trim()) {
      return val.trim();
    }
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
      /^n\/a$/i,
      /^-$/,
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
 * Format a value for display.
 * Handles numbers, booleans, dates, and strings.
 */
export function formatValue(value: unknown): string {
  if (value === undefined || value === null) return '';

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  if (typeof value === 'number') {
    // Format large numbers with separators
    if (Math.abs(value) >= 1000) {
      return value.toLocaleString();
    }
    // Keep reasonable precision for decimals
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

  if (typeof primitive === 'number' && !isNaN(primitive)) {
    return primitive;
  }

  if (typeof primitive === 'string') {
    const num = parseFloat(primitive);
    if (!isNaN(num)) {
      return num;
    }
  }

  return undefined;
}
