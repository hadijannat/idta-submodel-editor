/**
 * PCF Panel utility functions.
 *
 * Helpers for identifying PCF templates and locating PCF-specific fields.
 */

import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import type { ElementFormData } from '../../types/aas-elements';
import type { PCFActivity } from '../../types/pcf';
import { PCF_SEMANTIC_IDS } from '../../types/pcf';

const ACTIVITY_REQUIRED_FIELDS = new Set([
  'activityname',
  'activityquantity',
  'activityunit',
]);

const ACTIVITY_FIELD_ALIASES: Record<string, string[]> = {
  name: ['activityname', 'name'],
  category: ['activitycategory', 'category', 'scope'],
  quantity: ['activityquantity', 'quantity', 'amount'],
  unit: ['activityunit', 'unit'],
  factor_value: ['emissionfactorvalue', 'factorvalue', 'emissionfactor'],
  factor_unit: ['emissionfactorunit', 'factorunit'],
  factor_source: ['emissionfactorsource', 'factorsource', 'source'],
  factor_region: ['emissionfactorregion', 'factorregion', 'region'],
  factor_year: ['emissionfactoryear', 'factoryear', 'year'],
  co2e_kg: ['activityco2ekg', 'co2ekg', 'co2e', 'co2eq'],
};

const parseEnvList = (value?: string): string[] => {
  if (!value) return [];
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
};

const CONFIG_ACTIVITY_LIST_SEMANTIC_IDS = parseEnvList(
  import.meta.env.VITE_PCF_ACTIVITY_LIST_SEMANTIC_IDS
);
const CONFIG_ACTIVITY_LIST_IDSHORTS = parseEnvList(
  import.meta.env.VITE_PCF_ACTIVITY_LIST_IDSHORTS
);

const normalizeIdShort = (value: string): string =>
  value.replace(/[^a-z0-9]/gi, '').toLowerCase();

const PRODUCT_FOOTPRINT_LIST_IDSHORT = 'productcarbonfootprints';
const PRODUCT_FOOTPRINT_ITEM_IDSHORT = 'productcarbonfootprint';
const PRODUCT_FOOTPRINT_SEMANTIC_TOKEN = 'ProductCarbonFootprint';

export interface PCFInstanceContainer {
  kind: 'list' | 'collection';
  path: string;
  itemSchema: UIElementSchema;
}

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

const findFieldPathByMatcher = (
  elements: UIElementSchema[],
  matcher: (element: UIElementSchema) => boolean,
  path: string = ''
): string | null => {
  for (const element of elements) {
    const currentPath = path ? `${path}.${element.idShort}` : element.idShort;

    if (matcher(element)) {
      return currentPath;
    }

    if (element.elements && element.elements.length > 0) {
      const found = findFieldPathByMatcher(element.elements, matcher, currentPath);
      if (found) return found;
    }

    if (element.statements && element.statements.length > 0) {
      const found = findFieldPathByMatcher(element.statements, matcher, currentPath);
      if (found) return found;
    }

    if (element.itemTemplate) {
      if (matcher(element.itemTemplate)) {
        return `${currentPath}[0]`;
      }
      if (element.itemTemplate.elements) {
        const found = findFieldPathByMatcher(
          element.itemTemplate.elements,
          matcher,
          `${currentPath}[0]`
        );
        if (found) return found;
      }
    }
  }

  return null;
};

export function findFieldPathInElementsBySemanticId(
  elements: UIElementSchema[],
  targetSemanticId: string
): string | null {
  if (!elements.length) return null;
  return findFieldPathByMatcher(elements, (element) => {
    const semanticId = element.semanticId ?? '';
    return semanticId.includes(targetSemanticId);
  });
}

export function findFieldPathInElementsByIdShort(
  elements: UIElementSchema[],
  idShorts: string[]
): string | null {
  if (!elements.length || idShorts.length === 0) return null;
  const normalizedTargets = new Set(idShorts.map(normalizeIdShort));
  return findFieldPathByMatcher(elements, (element) =>
    normalizedTargets.has(normalizeIdShort(element.idShort))
  );
}

export function findProductCarbonFootprintContainer(
  schema: SubmodelUISchema | null
): PCFInstanceContainer | null {
  if (!schema) return null;

  const matchesProductList = (element: UIElementSchema): boolean => {
    if (element.modelType !== 'SubmodelElementList') return false;
    const normalizedId = normalizeIdShort(element.idShort);
    const semanticId = element.semanticId ?? '';
    const listElementSemantic = element.semanticIdListElement ?? '';
    const itemSchema = getListItemSchema(element);
    const itemSemantic = itemSchema?.semanticId ?? '';

    return (
      normalizedId === PRODUCT_FOOTPRINT_LIST_IDSHORT ||
      semanticId.includes('ProductCarbonFootprints') ||
      listElementSemantic.includes(PRODUCT_FOOTPRINT_SEMANTIC_TOKEN) ||
      itemSemantic.includes(PRODUCT_FOOTPRINT_SEMANTIC_TOKEN)
    );
  };

  const matchesProductCollection = (element: UIElementSchema): boolean => {
    if (element.modelType !== 'SubmodelElementCollection') return false;
    const normalizedId = normalizeIdShort(element.idShort);
    const semanticId = element.semanticId ?? '';
    return (
      normalizedId === PRODUCT_FOOTPRINT_ITEM_IDSHORT ||
      semanticId.includes(PRODUCT_FOOTPRINT_SEMANTIC_TOKEN)
    );
  };

  const findList = (
    elements: UIElementSchema[],
    path: string
  ): PCFInstanceContainer | null => {
    for (const element of elements) {
      const currentPath = path ? `${path}.${element.idShort}` : element.idShort;
      if (matchesProductList(element)) {
        const itemSchema = getListItemSchema(element);
        if (itemSchema) {
          return { kind: 'list', path: currentPath, itemSchema };
        }
      }
      if (element.elements) {
        const found = findList(element.elements, currentPath);
        if (found) return found;
      }
      if (element.statements) {
        const found = findList(element.statements, currentPath);
        if (found) return found;
      }
      if (element.itemTemplate?.elements) {
        const found = findList(element.itemTemplate.elements, currentPath);
        if (found) return found;
      }
    }
    return null;
  };

  const findCollection = (
    elements: UIElementSchema[],
    path: string
  ): PCFInstanceContainer | null => {
    for (const element of elements) {
      const currentPath = path ? `${path}.${element.idShort}` : element.idShort;
      if (matchesProductCollection(element)) {
        return { kind: 'collection', path: currentPath, itemSchema: element };
      }
      if (element.elements) {
        const found = findCollection(element.elements, currentPath);
        if (found) return found;
      }
      if (element.statements) {
        const found = findCollection(element.statements, currentPath);
        if (found) return found;
      }
      if (element.itemTemplate?.elements) {
        const found = findCollection(element.itemTemplate.elements, currentPath);
        if (found) return found;
      }
    }
    return null;
  };

  const listMatch = findList(schema.elements, '');
  if (listMatch) return listMatch;
  return findCollection(schema.elements, '');
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

interface ActivityListMatch {
  path: string;
  itemSchema: UIElementSchema;
}

/**
 * Find the path to a PCF activity list element, if present.
 *
 * Requires the list item template to include canonical activity fields, or
 * matches configured semantic IDs/idShorts if provided.
 */
export function findPcfActivityList(
  schema: SubmodelUISchema | null
): ActivityListMatch | null {
  if (!schema) return null;

  const matchesConfiguredIds = (element: UIElementSchema): boolean => {
    if (CONFIG_ACTIVITY_LIST_SEMANTIC_IDS.length === 0 &&
        CONFIG_ACTIVITY_LIST_IDSHORTS.length === 0) {
      return false;
    }
    const semanticId = element.semanticId ?? '';
    const idShort = element.idShort ?? '';
    if (
      CONFIG_ACTIVITY_LIST_SEMANTIC_IDS.some((id) => semanticId.includes(id))
    ) {
      return true;
    }
    return CONFIG_ACTIVITY_LIST_IDSHORTS.some(
      (id) => idShort.toLowerCase() === id.toLowerCase()
    );
  };

  const matchesActivityStructure = (element: UIElementSchema): boolean => {
    if (element.modelType !== 'SubmodelElementList') return false;
    const itemSchema = getListItemSchema(element);
    if (!itemSchema || itemSchema.modelType !== 'SubmodelElementCollection') {
      return false;
    }
    const childIds = new Set(
      (itemSchema.elements || []).map((child) => normalizeIdShort(child.idShort))
    );
    return Array.from(ACTIVITY_REQUIRED_FIELDS).every((field) =>
      childIds.has(field)
    );
  };

  const findInElements = (
    elements: UIElementSchema[],
    path: string
  ): ActivityListMatch | null => {
    for (const element of elements) {
      const currentPath = path ? `${path}.${element.idShort}` : element.idShort;

      if (
        (CONFIG_ACTIVITY_LIST_SEMANTIC_IDS.length > 0 ||
          CONFIG_ACTIVITY_LIST_IDSHORTS.length > 0) &&
        element.modelType === 'SubmodelElementList' &&
        matchesConfiguredIds(element)
      ) {
        const itemSchema = getListItemSchema(element);
        if (itemSchema) {
          return { path: currentPath, itemSchema };
        }
      }

      if (
        CONFIG_ACTIVITY_LIST_SEMANTIC_IDS.length === 0 &&
        CONFIG_ACTIVITY_LIST_IDSHORTS.length === 0 &&
        matchesActivityStructure(element)
      ) {
        const itemSchema = getListItemSchema(element);
        if (itemSchema) {
          return { path: currentPath, itemSchema };
        }
      }

      if (element.elements && element.elements.length > 0) {
        const found = findInElements(element.elements, currentPath);
        if (found) return found;
      }

      if (element.statements && element.statements.length > 0) {
        const found = findInElements(element.statements, currentPath);
        if (found) return found;
      }

      if (element.itemTemplate?.elements) {
        const found = findInElements(element.itemTemplate.elements, currentPath);
        if (found) return found;
      }
    }
    return null;
  };

  return findInElements(schema.elements, '');
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
 * Convert a dot-path to the list items path for setValue.
 *
 * Example: "PCFActivities" → "elements.PCFActivities.items"
 */
export function pathToFormItemsPath(dotPath: string): string {
  const parts = dotPath.split('.');
  const formParts: string[] = ['elements'];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    if (part.includes('[')) {
      const [name, indexStr] = part.split('[');
      const index = indexStr.replace(']', '');
      formParts.push(name, 'items', index);
    } else {
      formParts.push(part);
      if (i < parts.length - 1) {
        formParts.push('elements');
      }
    }
  }

  formParts.push('items');

  return formParts.join('.');
}

/**
 * Build list items for a PCF activity list element based on activity data.
 */
export function buildActivityListItems(
  activities: PCFActivity[],
  itemSchema: UIElementSchema
): ElementFormData[] {
  return activities
    .map((activity) => buildActivityListItem(activity, itemSchema))
    .filter((item): item is ElementFormData => item !== null);
}

export const getListItemSchema = (
  listSchema: UIElementSchema
): UIElementSchema | null => {
  if (listSchema.itemTemplate) return listSchema.itemTemplate;
  if (listSchema.items && listSchema.items.length > 0) return listSchema.items[0];
  return null;
};

const buildActivityListItem = (
  activity: PCFActivity,
  itemSchema: UIElementSchema
): ElementFormData | null => {
  if (itemSchema.modelType !== 'SubmodelElementCollection') {
    return null;
  }

  const elements: Record<string, ElementFormData> = {};
  for (const child of itemSchema.elements || []) {
    const normalized = normalizeIdShort(child.idShort);
    const value = resolveActivityValue(normalized, activity);
    elements[child.idShort] = {
      value: value ?? '',
      semanticId: child.semanticId ?? null,
      valueId: child.valueId ?? null,
      semanticIdListElement: child.semanticIdListElement ?? null,
    };
  }

  return {
    elements,
    semanticId: itemSchema.semanticId ?? null,
    valueId: itemSchema.valueId ?? null,
    semanticIdListElement: itemSchema.semanticIdListElement ?? null,
  };
};

const resolveActivityValue = (
  normalizedIdShort: string,
  activity: PCFActivity
): unknown => {
  if (ACTIVITY_FIELD_ALIASES.name.includes(normalizedIdShort)) {
    return activity.name;
  }
  if (ACTIVITY_FIELD_ALIASES.category.includes(normalizedIdShort)) {
    return activity.category;
  }
  if (ACTIVITY_FIELD_ALIASES.quantity.includes(normalizedIdShort)) {
    return activity.quantity;
  }
  if (ACTIVITY_FIELD_ALIASES.unit.includes(normalizedIdShort)) {
    return activity.unit;
  }
  if (ACTIVITY_FIELD_ALIASES.factor_value.includes(normalizedIdShort)) {
    return activity.factor_value;
  }
  if (ACTIVITY_FIELD_ALIASES.factor_unit.includes(normalizedIdShort)) {
    return activity.factor_unit;
  }
  if (ACTIVITY_FIELD_ALIASES.factor_source.includes(normalizedIdShort)) {
    return activity.factor_source ?? '';
  }
  if (ACTIVITY_FIELD_ALIASES.factor_region.includes(normalizedIdShort)) {
    return activity.factor_region ?? '';
  }
  if (ACTIVITY_FIELD_ALIASES.factor_year.includes(normalizedIdShort)) {
    return activity.factor_year ?? '';
  }
  if (ACTIVITY_FIELD_ALIASES.co2e_kg.includes(normalizedIdShort)) {
    return activity.co2e_kg ?? '';
  }
  return undefined;
};

/**
 * Generate a unique ID for an activity.
 */
export function generateActivityId(): string {
  return `act-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
