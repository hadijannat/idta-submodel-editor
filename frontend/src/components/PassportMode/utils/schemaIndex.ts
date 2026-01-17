/**
 * Schema Index - resolve schema elements to their form data paths.
 *
 * Provides helpers to match elements by semanticId/idShort and to
 * derive collection/list "contexts" for sibling value extraction.
 */

import type {
  ElementModelType,
  SubmodelUISchema,
  UIElementSchema,
} from '../../../types/ui-schema';
import type { ElementFormData, SubmodelFormData } from '../../../types/aas-elements';

export interface ResolvedElement {
  schema: UIElementSchema;
  data?: ElementFormData;
  path: string;
  parentPath: string | null;
}

export interface ResolvedContext {
  /** Path to the collection or list item */
  path: string;
  /** Direct child elements within the context */
  elements: ResolvedElement[];
}

export interface ElementMatcher {
  semanticIdPatterns?: RegExp[];
  idShortPatterns?: RegExp[];
  modelTypes?: ElementModelType[];
}

const MAX_SCHEMA_DEPTH = 8;

function getSemanticId(resolved: ResolvedElement): string | null {
  const dataSemantic =
    resolved.data && typeof resolved.data === 'object'
      ? (resolved.data.semanticId as string | null | undefined)
      : undefined;
  return dataSemantic ?? resolved.schema.semanticId ?? null;
}

function matchesPatterns(value: string | null, patterns?: RegExp[]): boolean {
  if (!value || !patterns || patterns.length === 0) return false;
  return patterns.some((pattern) => pattern.test(value));
}

/**
 * Find elements matching semanticId/idShort/modelType patterns.
 */
export function findMatchingElements(
  resolved: ResolvedElement[],
  matcher: ElementMatcher
): ResolvedElement[] {
  return resolved.filter((element) => {
    if (matcher.modelTypes && !matcher.modelTypes.includes(element.schema.modelType)) {
      return false;
    }

    const semanticId = getSemanticId(element);
    const matchesSemantic = matchesPatterns(semanticId, matcher.semanticIdPatterns);
    const matchesIdShort = matchesPatterns(element.schema.idShort, matcher.idShortPatterns);

    return matchesSemantic || matchesIdShort;
  });
}

/**
 * Resolve schema elements to concrete form data paths and data nodes.
 */
export function resolveSchemaElements(
  schema: SubmodelUISchema,
  formData?: SubmodelFormData
): ResolvedElement[] {
  const resolved: ResolvedElement[] = [];

  const walk = (
    elements: UIElementSchema[] | undefined,
    dataRecord: Record<string, ElementFormData> | undefined,
    basePath: string,
    parentPath: string | null,
    depth: number
  ) => {
    if (!elements || depth > MAX_SCHEMA_DEPTH) return;

    for (const element of elements) {
      const path = `${basePath}.${element.idShort}`;
      const data = dataRecord ? dataRecord[element.idShort] : undefined;

      resolved.push({ schema: element, data, path, parentPath });

      if (element.modelType === 'SubmodelElementCollection' && element.elements) {
        const childRecord =
          data && typeof data === 'object'
            ? (data.elements as Record<string, ElementFormData> | undefined)
            : undefined;
        walk(element.elements, childRecord, `${path}.elements`, `${path}.elements`, depth + 1);
      }

      if (element.modelType === 'SubmodelElementList') {
        const items =
          data && typeof data === 'object' && Array.isArray(data.items)
            ? (data.items as ElementFormData[])
            : [];
        const itemSchemas = element.items ?? [];
        const template = element.itemTemplate ?? null;

        items.forEach((itemData, index) => {
          const itemSchema = itemSchemas[index] ?? template;
          if (!itemSchema) return;
          const itemPath = `${path}.items.${index}`;
          resolved.push({
            schema: itemSchema,
            data: itemData,
            path: itemPath,
            parentPath: `${path}.items`,
          });

          if (itemSchema.modelType === 'SubmodelElementCollection' && itemSchema.elements) {
            const itemRecord =
              itemData && typeof itemData === 'object'
                ? (itemData.elements as Record<string, ElementFormData> | undefined)
                : undefined;
            walk(
              itemSchema.elements,
              itemRecord,
              `${itemPath}.elements`,
              `${itemPath}.elements`,
              depth + 1
            );
          }
        });
      }

      if (element.modelType === 'Entity' && element.statements) {
        const stmtRecord =
          data && typeof data === 'object'
            ? (data.statements as Record<string, ElementFormData> | undefined)
            : undefined;
        walk(
          element.statements,
          stmtRecord,
          `${path}.statements`,
          `${path}.statements`,
          depth + 1
        );
      }
    }
  };

  walk(schema.elements, formData?.elements, 'elements', 'elements', 0);

  return resolved;
}

/**
 * Collect "contexts" (sibling groups) from collections and list items.
 */
export function collectResolvedContexts(
  schema: SubmodelUISchema,
  formData?: SubmodelFormData
): ResolvedContext[] {
  const contexts: ResolvedContext[] = [];

  const walk = (
    elements: UIElementSchema[] | undefined,
    dataRecord: Record<string, ElementFormData> | undefined,
    basePath: string,
    depth: number
  ) => {
    if (!elements || depth > MAX_SCHEMA_DEPTH) return;

    for (const element of elements) {
      const path = `${basePath}.${element.idShort}`;
      const data = dataRecord ? dataRecord[element.idShort] : undefined;

      if (element.modelType === 'SubmodelElementCollection' && element.elements) {
        const childRecord =
          data && typeof data === 'object'
            ? (data.elements as Record<string, ElementFormData> | undefined)
            : undefined;
        const directChildren = element.elements.map((child) => ({
          schema: child,
          data: childRecord ? childRecord[child.idShort] : undefined,
          path: `${path}.elements.${child.idShort}`,
          parentPath: `${path}.elements`,
        }));
        contexts.push({ path, elements: directChildren });
        walk(element.elements, childRecord, `${path}.elements`, depth + 1);
      }

      if (element.modelType === 'SubmodelElementList') {
        const items =
          data && typeof data === 'object' && Array.isArray(data.items)
            ? (data.items as ElementFormData[])
            : [];
        const itemSchemas = element.items ?? [];
        const template = element.itemTemplate ?? null;

        items.forEach((itemData, index) => {
          const itemSchema = itemSchemas[index] ?? template;
          if (!itemSchema) return;
          const itemPath = `${path}.items.${index}`;

          if (itemSchema.modelType === 'SubmodelElementCollection' && itemSchema.elements) {
            const itemRecord =
              itemData && typeof itemData === 'object'
                ? (itemData.elements as Record<string, ElementFormData> | undefined)
                : undefined;
            const directChildren = itemSchema.elements.map((child) => ({
              schema: child,
              data: itemRecord ? itemRecord[child.idShort] : undefined,
              path: `${itemPath}.elements.${child.idShort}`,
              parentPath: `${itemPath}.elements`,
            }));
            contexts.push({ path: itemPath, elements: directChildren });
            walk(itemSchema.elements, itemRecord, `${itemPath}.elements`, depth + 1);
          } else {
            contexts.push({
              path: itemPath,
              elements: [
                {
                  schema: itemSchema,
                  data: itemData,
                  path: itemPath,
                  parentPath: `${path}.items`,
                },
              ],
            });
          }
        });
      }

      if (element.modelType === 'Entity' && element.statements) {
        const stmtRecord =
          data && typeof data === 'object'
            ? (data.statements as Record<string, ElementFormData> | undefined)
            : undefined;
        const directChildren = element.statements.map((child) => ({
          schema: child,
          data: stmtRecord ? stmtRecord[child.idShort] : undefined,
          path: `${path}.statements.${child.idShort}`,
          parentPath: `${path}.statements`,
        }));
        contexts.push({ path, elements: directChildren });
        walk(element.statements, stmtRecord, `${path}.statements`, depth + 1);
      }
    }
  };

  walk(schema.elements, formData?.elements, 'elements', 0);

  return contexts;
}
