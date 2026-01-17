/**
 * PCF Panel utility functions.
 *
 * Helpers for identifying PCF templates and locating PCF-specific fields.
 */

import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import { PCF_SEMANTIC_IDS } from '../../types/pcf';

/**
 * Check if a template schema is a Carbon Footprint template.
 *
 * Checks the template's semanticId against known PCF semantic IDs.
 */
export function isPCFTemplate(schema: SubmodelUISchema | null): boolean {
  if (!schema) return false;

  const semanticId = schema.semanticId;
  if (!semanticId) return false;

  // Check if semanticId contains CarbonFootprint identifier
  const pcfIdentifiers = [
    'CarbonFootprint',
    PCF_SEMANTIC_IDS.CarbonFootprint,
    '0173-1#01-AHE712#001', // Carbon Footprint submodel
    '/idta/CarbonFootprint/',
  ];

  return pcfIdentifiers.some(
    (id) =>
      semanticId.includes(id) || semanticId.toLowerCase().includes('carbon')
  );
}

/**
 * Find a field path by its semantic ID in the schema.
 *
 * Returns the dot-separated path to the field (e.g., "PCFGoodsAddressHandover.PcfCO2eq").
 */
export function findFieldBySemanticId(
  schema: SubmodelUISchema | null,
  targetSemanticId: string
): string | null {
  if (!schema) return null;

  const findInElements = (
    elements: UIElementSchema[],
    path: string
  ): string | null => {
    for (const element of elements) {
      const currentPath = path ? `${path}.${element.idShort}` : element.idShort;

      // Check if this element has the target semantic ID
      const elemSemanticId = element.semanticId;
      if (elemSemanticId && elemSemanticId.includes(targetSemanticId)) {
        return currentPath;
      }

      // Recurse into nested elements
      if (element.elements && element.elements.length > 0) {
        const found = findInElements(element.elements, currentPath);
        if (found) return found;
      }

      // Recurse into statements (Entity)
      if (element.statements && element.statements.length > 0) {
        const found = findInElements(element.statements, currentPath);
        if (found) return found;
      }

      // Check item template for lists
      if (element.itemTemplate) {
        const template = element.itemTemplate;
        const templateSemanticId = template.semanticId;
        if (templateSemanticId?.includes(targetSemanticId)) {
          return `${currentPath}[0]`;
        }
        if (template.elements) {
          const found = findInElements(
            template.elements,
            `${currentPath}[0].${template.idShort || ''}`
          );
          if (found) return found;
        }
      }
    }
    return null;
  };

  return findInElements(schema.elements, '');
}

/**
 * Find the path to the PcfCO2eq field in form data.
 *
 * Searches by semantic ID first, falls back to idShort matching.
 */
export function findPcfCO2eqPath(
  schema: SubmodelUISchema | null
): string | null {
  if (!schema) return null;

  // Try to find by semantic ID first
  const bySemanticId = findFieldBySemanticId(schema, PCF_SEMANTIC_IDS.PcfCO2eq);
  if (bySemanticId) return bySemanticId;

  // Fall back to searching by idShort
  const findByIdShort = (
    elements: UIElementSchema[],
    path: string
  ): string | null => {
    for (const element of elements) {
      const currentPath = path ? `${path}.${element.idShort}` : element.idShort;

      if (element.idShort === 'PcfCO2eq' || element.idShort === 'PCFCo2eq') {
        return currentPath;
      }

      if (element.elements) {
        const found = findByIdShort(element.elements, currentPath);
        if (found) return found;
      }

      if (element.statements) {
        const found = findByIdShort(element.statements, currentPath);
        if (found) return found;
      }
    }
    return null;
  };

  return findByIdShort(schema.elements, '');
}

/**
 * Convert a dot-path string to form setValue path.
 *
 * Example: "PCFGoodsAddressHandover.PcfCO2eq" → "elements.PCFGoodsAddressHandover.elements.PcfCO2eq.value"
 */
export function pathToFormPath(dotPath: string): string {
  const parts = dotPath.split('.');
  const formParts: string[] = ['elements'];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    // Handle array notation
    if (part.includes('[')) {
      const [name, indexStr] = part.split('[');
      const index = indexStr.replace(']', '');
      formParts.push(name, 'items', index);
    } else {
      formParts.push(part);
      // Add 'elements' between nested collections, but not for the last part
      if (i < parts.length - 1) {
        formParts.push('elements');
      }
    }
  }

  // The final value is in the 'value' property
  formParts.push('value');

  return formParts.join('.');
}

/**
 * Generate a unique ID for an activity.
 */
export function generateActivityId(): string {
  return `act-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
