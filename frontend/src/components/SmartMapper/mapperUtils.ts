/**
 * Smart Mapper utility functions
 */

import type { UIElementSchema } from '../../types/ui-schema';
import { isRequired } from '../../types/aas-elements';
import type { TargetField, PreviewEntry } from './types';

/**
 * Normalize text for comparison (lowercase, remove special chars)
 */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/**
 * Tokenize text into words for matching
 */
export function tokenize(text: string): string[] {
  if (!text) return [];
  return normalize(text).split(/\s+/).filter(Boolean);
}

/**
 * Score match between source column name and target field (Jaccard similarity)
 */
export function scoreMatch(source: string, target: TargetField): number {
  const sourceTokens = new Set(tokenize(source));
  if (!sourceTokens.size) return 0;
  const targetTokens = new Set(
    tokenize(`${target.idShortPath} ${target.label} ${target.semanticLabel ?? ''}`)
  );
  let intersection = 0;
  sourceTokens.forEach((token) => {
    if (targetTokens.has(token)) intersection += 1;
  });
  const union = new Set([...sourceTokens, ...targetTokens]).size;
  return union ? intersection / union : 0;
}

/**
 * Flatten schema elements into a list of mappable target fields
 */
export function flattenTargets(
  elements: UIElementSchema[],
  path: string[] = []
): TargetField[] {
  const targets: TargetField[] = [];

  const isLeaf = (element: UIElementSchema) =>
    element.modelType === 'Property' ||
    element.modelType === 'MultiLanguageProperty' ||
    element.modelType === 'Range' ||
    element.modelType === 'File' ||
    element.modelType === 'ReferenceElement';

  const pushLeaf = (
    element: UIElementSchema,
    pathSegments: string[],
    requiredOverride?: boolean
  ) => {
    const label = element.idShort || pathSegments[pathSegments.length - 1];
    targets.push({
      idShortPath: pathSegments.join('.'),
      label,
      elementType: element.modelType,
      valueType: element.valueType ?? null,
      required: requiredOverride ?? isRequired(element.cardinality),
      semanticLabel: element.semanticLabel ?? null,
      languages: element.supportedLanguages ?? undefined,
    });
  };

  for (const element of elements) {
    if (element.modelType === 'SubmodelElementList') {
      const listPath = [...path, `${element.idShort}[]`];
      const listRequired = isRequired(element.cardinality);
      const template = element.itemTemplate ?? element.items?.[0] ?? null;

      if (template) {
        if (isLeaf(template)) {
          const leafPath = [
            ...listPath,
            template.idShort ? template.idShort : 'value',
          ];
          pushLeaf(template, leafPath, listRequired);
        } else {
          const basePath = template.idShort ? [...listPath, template.idShort] : listPath;
          if (template.elements && template.elements.length) {
            targets.push(...flattenTargets(template.elements, basePath));
          }
          if (template.statements && template.statements.length) {
            targets.push(...flattenTargets(template.statements, basePath));
          }
        }
      }
      continue;
    }

    const nextPath = [...path, element.idShort];
    if (isLeaf(element)) {
      pushLeaf(element, nextPath);
    }

    if (element.elements && element.elements.length) {
      targets.push(...flattenTargets(element.elements, nextPath));
    }
    if (element.statements && element.statements.length) {
      targets.push(...flattenTargets(element.statements, nextPath));
    }
  }

  return targets;
}

/**
 * Deep merge form elements, with patch overriding base
 */
export function mergeElements(
  base: Record<string, unknown>,
  patch: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...base };
  Object.entries(patch).forEach(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const nextBase = (base[key] as Record<string, unknown>) ?? {};
      result[key] = mergeElements(nextBase, value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  });
  return result;
}

/**
 * Extract preview entries from mapped form data for dry-run display
 */
export function extractPreviewEntries(
  mappedFormData: Record<string, unknown> | null
): PreviewEntry[] {
  if (!mappedFormData) return [];
  const entries: PreviewEntry[] = [];
  const elements = (mappedFormData.elements ?? {}) as Record<string, unknown>;

  const extractValues = (
    obj: Record<string, unknown>,
    prefix: string
  ): void => {
    Object.entries(obj).forEach(([key, val]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      if (val && typeof val === 'object' && !Array.isArray(val)) {
        const valObj = val as Record<string, unknown>;
        // Check if this is a leaf element with 'value' key
        if ('value' in valObj) {
          const rawValue = valObj.value;
          if (rawValue && typeof rawValue === 'object' && !Array.isArray(rawValue)) {
            // MultiLanguageProperty: { en: "...", de: "..." }
            const langValues = Object.entries(rawValue as Record<string, string>)
              .map(([lang, text]) => `${lang}: ${text}`)
              .join(', ');
            entries.push({ path, value: langValues, type: 'MLP' });
          } else if (rawValue !== null && rawValue !== undefined) {
            entries.push({ path, value: String(rawValue), type: 'Property' });
          }
        } else {
          // Recurse into nested objects (SMC, etc.)
          extractValues(valObj, path);
        }
      }
    });
  };

  extractValues(elements, '');
  return entries;
}
