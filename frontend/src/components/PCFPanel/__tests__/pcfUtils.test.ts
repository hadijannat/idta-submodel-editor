/**
 * Tests for PCF utility functions.
 */

import { describe, it, expect } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../../types/ui-schema';
import {
  isPCFTemplate,
  findFieldBySemanticId,
  findPcfCO2eqPath,
  findPcfActivityList,
  pathToFormPath,
  pathToFormItemsPath,
  buildActivityListItems,
  generateActivityId,
} from '../pcfUtils';
import { PCF_SEMANTIC_IDS } from '../../../types/pcf';
import type { PCFActivity } from '../../../types/pcf';

// Helper to create a minimal schema
const createSchema = (
  semanticId: string | null,
  elements: UIElementSchema[] = []
): SubmodelUISchema => ({
  templateName: 'Test',
  templatePath: 'test.aasx',
  submodelId: 'urn:example',
  idShort: 'Test',
  semanticId,
  description: null,
  administration: null,
  elements,
  supplementaryFiles: [],
});

const createElement = (
  idShort: string,
  semanticId: string | null = null,
  elements: UIElementSchema[] | undefined = undefined
): UIElementSchema => ({
  idShort,
  modelType: elements ? 'SubmodelElementCollection' : 'Property',
  semanticId,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  valueType: 'xs:string',
  elements,
});

const createListElement = (
  idShort: string,
  itemElements: UIElementSchema[]
): UIElementSchema => ({
  idShort,
  modelType: 'SubmodelElementList',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..*]',
  category: null,
  itemTemplate: {
    idShort: 'ActivityItem',
    modelType: 'SubmodelElementCollection',
    semanticId: null,
    semanticLabel: null,
    description: null,
    qualifiers: [],
    cardinality: '[1]',
    category: null,
    elements: itemElements,
  },
});

describe('isPCFTemplate', () => {
  it('returns false for null schema', () => {
    expect(isPCFTemplate(null)).toBe(false);
  });

  it('returns false for schema without semanticId', () => {
    const schema = createSchema(null);
    expect(isPCFTemplate(schema)).toBe(false);
  });

  it('returns true for CarbonFootprint semantic ID', () => {
    const schema = createSchema(PCF_SEMANTIC_IDS.CarbonFootprint);
    expect(isPCFTemplate(schema)).toBe(true);
  });

  it('returns true for semantic ID containing "carbon"', () => {
    const schema = createSchema('https://example.org/carbon-footprint');
    expect(isPCFTemplate(schema)).toBe(true);
  });

  it('returns true for IRDI-based carbon footprint', () => {
    const schema = createSchema('0173-1#01-AHE712#001');
    expect(isPCFTemplate(schema)).toBe(true);
  });
});

describe('findFieldBySemanticId', () => {
  it('returns null for null schema', () => {
    expect(findFieldBySemanticId(null, 'some-id')).toBe(null);
  });

  it('finds top-level field by semantic ID', () => {
    const schema = createSchema('test', [
      createElement('PcfCO2eq', PCF_SEMANTIC_IDS.PcfCO2eq),
    ]);
    expect(findFieldBySemanticId(schema, PCF_SEMANTIC_IDS.PcfCO2eq)).toBe(
      'PcfCO2eq'
    );
  });

  it('finds nested field by semantic ID', () => {
    const schema = createSchema('test', [
      createElement('Parent', null, [
        createElement('PcfCO2eq', PCF_SEMANTIC_IDS.PcfCO2eq),
      ]),
    ]);
    expect(findFieldBySemanticId(schema, PCF_SEMANTIC_IDS.PcfCO2eq)).toBe(
      'Parent.PcfCO2eq'
    );
  });

  it('returns null when semantic ID not found', () => {
    const schema = createSchema('test', [createElement('Other', 'other-id')]);
    expect(findFieldBySemanticId(schema, PCF_SEMANTIC_IDS.PcfCO2eq)).toBe(null);
  });
});

describe('findPcfCO2eqPath', () => {
  it('returns null for null schema', () => {
    expect(findPcfCO2eqPath(null)).toBe(null);
  });

  it('finds PcfCO2eq by semantic ID', () => {
    const schema = createSchema('test', [
      createElement('PcfCO2eq', PCF_SEMANTIC_IDS.PcfCO2eq),
    ]);
    expect(findPcfCO2eqPath(schema)).toBe('PcfCO2eq');
  });

  it('finds PcfCO2eq by idShort fallback', () => {
    const schema = createSchema('test', [createElement('PcfCO2eq', null)]);
    expect(findPcfCO2eqPath(schema)).toBe('PcfCO2eq');
  });

  it('finds PCFCo2eq alternate idShort', () => {
    const schema = createSchema('test', [createElement('PCFCo2eq', null)]);
    expect(findPcfCO2eqPath(schema)).toBe('PCFCo2eq');
  });
});

describe('pathToFormPath', () => {
  it('converts simple path to form path', () => {
    expect(pathToFormPath('PcfCO2eq')).toBe('elements.PcfCO2eq.value');
  });

  it('converts nested path with elements', () => {
    expect(pathToFormPath('Parent.PcfCO2eq')).toBe(
      'elements.Parent.elements.PcfCO2eq.value'
    );
  });

  it('handles deeply nested paths', () => {
    expect(pathToFormPath('A.B.C')).toBe('elements.A.elements.B.elements.C.value');
  });

  it('handles array notation in path', () => {
    // Array items have the form: elements.{list}.items.{index}.{field}
    expect(pathToFormPath('List[0].Field')).toBe(
      'elements.List.items.0.Field.value'
    );
  });
});

describe('pathToFormItemsPath', () => {
  it('converts list path to items path', () => {
    expect(pathToFormItemsPath('PCFActivities')).toBe(
      'elements.PCFActivities.items'
    );
  });

  it('converts nested list path to items path', () => {
    expect(pathToFormItemsPath('Parent.PCFActivities')).toBe(
      'elements.Parent.elements.PCFActivities.items'
    );
  });
});

describe('findPcfActivityList', () => {
  it('finds list element with required activity fields', () => {
    const listElement = createListElement('PCFActivities', [
      createElement('ActivityName'),
      createElement('ActivityQuantity'),
      createElement('ActivityUnit'),
    ]);
    const schema = createSchema('test', [listElement]);
    const result = findPcfActivityList(schema);
    expect(result?.path).toBe('PCFActivities');
  });
});

describe('buildActivityListItems', () => {
  it('maps activity values into list item elements', () => {
    const listElement = createListElement('PCFActivities', [
      createElement('ActivityName'),
      createElement('ActivityQuantity'),
      createElement('ActivityUnit'),
      createElement('EmissionFactorValue'),
    ]);
    const itemSchema = listElement.itemTemplate as UIElementSchema;
    const activity: PCFActivity = {
      id: 'act-1',
      name: 'Electricity',
      category: 'scope2',
      quantity: 100,
      unit: 'kWh',
      factor_value: 0.42,
      factor_unit: 'kg CO2e/kWh',
      factor_source: 'EPA',
      co2e_kg: 42,
    };

    const items = buildActivityListItems([activity], itemSchema);
    expect(items.length).toBe(1);
    expect(items[0].elements?.ActivityName?.value).toBe('Electricity');
    expect(items[0].elements?.ActivityQuantity?.value).toBe(100);
    expect(items[0].elements?.ActivityUnit?.value).toBe('kWh');
    expect(items[0].elements?.EmissionFactorValue?.value).toBe(0.42);
  });
});

describe('generateActivityId', () => {
  it('generates unique IDs', () => {
    const id1 = generateActivityId();
    const id2 = generateActivityId();
    expect(id1).not.toBe(id2);
  });

  it('generates IDs with expected prefix', () => {
    const id = generateActivityId();
    expect(id.startsWith('act-')).toBe(true);
  });
});
