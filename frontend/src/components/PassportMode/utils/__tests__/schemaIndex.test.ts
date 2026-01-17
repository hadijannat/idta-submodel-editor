/**
 * Comprehensive tests for schemaIndex utilities.
 */

import { describe, it, expect } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../../../types/ui-schema';
import type { SubmodelFormData, ElementFormData } from '../../../../types/aas-elements';
import {
  collectResolvedContexts,
  resolveSchemaElements,
  findMatchingElements,
} from '../schemaIndex';

/**
 * Helper to create base element with defaults.
 */
const baseElement = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'Element',
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..1]',
  category: null,
  ...overrides,
});

/**
 * Helper to create test schema.
 */
const makeSchema = (elements: UIElementSchema[]): SubmodelUISchema => ({
  templateName: 'Test',
  templatePath: null,
  submodelId: 'urn:test',
  idShort: 'Test',
  semanticId: null,
  description: null,
  administration: null,
  elements,
  supplementaryFiles: [],
});

describe('resolveSchemaElements', () => {
  describe('basic resolution', () => {
    it('resolves flat elements', () => {
      const schema = makeSchema([
        baseElement({ idShort: 'Prop1', modelType: 'Property' }),
        baseElement({ idShort: 'Prop2', modelType: 'Property' }),
      ]);

      const resolved = resolveSchemaElements(schema);

      expect(resolved.length).toBe(2);
      expect(resolved[0].path).toBe('elements.Prop1');
      expect(resolved[1].path).toBe('elements.Prop2');
    });

    it('includes schema and data in resolved elements', () => {
      const schema = makeSchema([
        baseElement({ idShort: 'TestProp', modelType: 'Property' }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          TestProp: { value: 'test value' },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      expect(resolved[0].schema.idShort).toBe('TestProp');
      expect((resolved[0].data as Record<string, unknown>).value).toBe('test value');
    });

    it('handles undefined formData', () => {
      const schema = makeSchema([
        baseElement({ idShort: 'TestProp', modelType: 'Property' }),
      ]);

      const resolved = resolveSchemaElements(schema, undefined);

      expect(resolved.length).toBe(1);
      expect(resolved[0].data).toBeUndefined();
    });
  });

  describe('nested collections', () => {
    it('resolves nested element paths', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'RootCollection',
          modelType: 'SubmodelElementCollection',
          elements: [
            baseElement({ idShort: 'ChildProp', modelType: 'Property' }),
          ],
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          RootCollection: {
            elements: {
              ChildProp: { value: 'abc' },
            },
          },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      expect(
        resolved.some((node) => node.path === 'elements.RootCollection')
      ).toBe(true);
      expect(
        resolved.some((node) => node.path === 'elements.RootCollection.elements.ChildProp')
      ).toBe(true);
    });

    it('resolves deeply nested collections', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'Level1',
          modelType: 'SubmodelElementCollection',
          elements: [
            baseElement({
              idShort: 'Level2',
              modelType: 'SubmodelElementCollection',
              elements: [
                baseElement({
                  idShort: 'Level3',
                  modelType: 'SubmodelElementCollection',
                  elements: [
                    baseElement({ idShort: 'DeepProp', modelType: 'Property' }),
                  ],
                }),
              ],
            }),
          ],
        }),
      ]);

      const resolved = resolveSchemaElements(schema);

      expect(
        resolved.some((node) => node.schema.idShort === 'DeepProp')
      ).toBe(true);
    });

    it('includes parent path in resolved elements', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'Parent',
          modelType: 'SubmodelElementCollection',
          elements: [
            baseElement({ idShort: 'Child', modelType: 'Property' }),
          ],
        }),
      ]);

      const resolved = resolveSchemaElements(schema);
      const childNode = resolved.find((n) => n.schema.idShort === 'Child');

      expect(childNode?.parentPath).toBe('elements.Parent.elements');
    });
  });

  describe('SubmodelElementList handling', () => {
    it('resolves list items with indices', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'ItemList',
          modelType: 'SubmodelElementList',
          itemTemplate: baseElement({ idShort: 'ItemTemplate', modelType: 'Property' }),
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          ItemList: {
            items: [{ value: 'item1' }, { value: 'item2' }],
          },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      expect(
        resolved.some((node) => node.path === 'elements.ItemList.items.0')
      ).toBe(true);
      expect(
        resolved.some((node) => node.path === 'elements.ItemList.items.1')
      ).toBe(true);
    });

    it('handles empty list', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'EmptyList',
          modelType: 'SubmodelElementList',
          itemTemplate: baseElement({ idShort: 'ItemTemplate', modelType: 'Property' }),
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          EmptyList: { items: [] },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      // Should only have the list itself, no items
      expect(resolved.length).toBe(1);
      expect(resolved[0].schema.idShort).toBe('EmptyList');
    });

    it('handles list items with collection template', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'ComplexList',
          modelType: 'SubmodelElementList',
          itemTemplate: baseElement({
            idShort: 'ComplexItem',
            modelType: 'SubmodelElementCollection',
            elements: [
              baseElement({ idShort: 'ItemProp', modelType: 'Property' }),
            ],
          }),
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          ComplexList: {
            items: [
              { elements: { ItemProp: { value: 'test' } } },
            ],
          },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      expect(
        resolved.some((node) =>
          node.path === 'elements.ComplexList.items.0.elements.ItemProp'
        )
      ).toBe(true);
    });
  });

  describe('Entity handling', () => {
    it('resolves entity statements', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'TestEntity',
          modelType: 'Entity',
          statements: [
            baseElement({ idShort: 'Statement1', modelType: 'Property' }),
            baseElement({ idShort: 'Statement2', modelType: 'Property' }),
          ],
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          TestEntity: {
            statements: {
              Statement1: { value: 'val1' },
              Statement2: { value: 'val2' },
            },
          },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      expect(
        resolved.some((node) =>
          node.path === 'elements.TestEntity.statements.Statement1'
        )
      ).toBe(true);
    });
  });

  describe('depth limiting', () => {
    it('respects max depth limit', () => {
      // Create deeply nested schema
      let deepElement: UIElementSchema = baseElement({ idShort: 'Deep', modelType: 'Property' });

      for (let i = 0; i < 15; i++) {
        deepElement = baseElement({
          idShort: `Level${i}`,
          modelType: 'SubmodelElementCollection',
          elements: [deepElement],
        });
      }

      const schema = makeSchema([deepElement]);
      const resolved = resolveSchemaElements(schema);

      // Should not have infinite elements due to depth limit
      expect(resolved.length).toBeLessThan(50);
    });
  });
});

describe('collectResolvedContexts', () => {
  it('collects contexts for collections', () => {
    const schema = makeSchema([
      baseElement({
        idShort: 'ProductCarbonFootprint',
        modelType: 'SubmodelElementCollection',
        elements: [
          baseElement({ idShort: 'PCFLifeCyclePhase', modelType: 'Property' }),
          baseElement({ idShort: 'PCFCO2eq', modelType: 'Property' }),
        ],
      }),
    ]);

    const formData: SubmodelFormData = {
      elements: {
        ProductCarbonFootprint: {
          elements: {
            PCFLifeCyclePhase: { value: 'A1' },
            PCFCO2eq: { value: '1.2' },
          },
        },
      },
    };

    const contexts = collectResolvedContexts(schema, formData);

    expect(contexts.length).toBeGreaterThan(0);
    const context = contexts.find(
      (ctx) => ctx.path === 'elements.ProductCarbonFootprint'
    );
    expect(context?.elements.length).toBe(2);
  });

  it('collects contexts for nested collections', () => {
    const schema = makeSchema([
      baseElement({
        idShort: 'Outer',
        modelType: 'SubmodelElementCollection',
        elements: [
          baseElement({
            idShort: 'Inner',
            modelType: 'SubmodelElementCollection',
            elements: [
              baseElement({ idShort: 'Prop', modelType: 'Property' }),
            ],
          }),
        ],
      }),
    ]);

    const formData: SubmodelFormData = {
      elements: {
        Outer: {
          elements: {
            Inner: {
              elements: {
                Prop: { value: 'test' },
              },
            },
          },
        },
      },
    };

    const contexts = collectResolvedContexts(schema, formData);

    // Should have contexts for both Outer and Inner
    expect(contexts.some((ctx) => ctx.path === 'elements.Outer')).toBe(true);
    expect(
      contexts.some((ctx) => ctx.path === 'elements.Outer.elements.Inner')
    ).toBe(true);
  });

  it('collects contexts for list items', () => {
    const schema = makeSchema([
      baseElement({
        idShort: 'PhaseList',
        modelType: 'SubmodelElementList',
        itemTemplate: baseElement({
          idShort: 'Phase',
          modelType: 'SubmodelElementCollection',
          elements: [
            baseElement({ idShort: 'Name', modelType: 'Property' }),
            baseElement({ idShort: 'Value', modelType: 'Property' }),
          ],
        }),
      }),
    ]);

    const formData: SubmodelFormData = {
      elements: {
        PhaseList: {
          items: [
            { elements: { Name: { value: 'A1' }, Value: { value: '10' } } },
            { elements: { Name: { value: 'A2' }, Value: { value: '20' } } },
          ],
        },
      },
    };

    const contexts = collectResolvedContexts(schema, formData);

    // Should have contexts for each list item
    expect(
      contexts.some((ctx) => ctx.path === 'elements.PhaseList.items.0')
    ).toBe(true);
    expect(
      contexts.some((ctx) => ctx.path === 'elements.PhaseList.items.1')
    ).toBe(true);
  });

  it('handles empty schema', () => {
    const schema = makeSchema([]);
    const contexts = collectResolvedContexts(schema);

    expect(contexts).toEqual([]);
  });

  it('handles undefined formData', () => {
    const schema = makeSchema([
      baseElement({
        idShort: 'Collection',
        modelType: 'SubmodelElementCollection',
        elements: [
          baseElement({ idShort: 'Prop', modelType: 'Property' }),
        ],
      }),
    ]);

    const contexts = collectResolvedContexts(schema, undefined);

    // Should still create contexts based on schema
    expect(contexts.length).toBe(1);
    expect(contexts[0].path).toBe('elements.Collection');
  });
});

describe('findMatchingElements', () => {
  const createResolvedElements = (formData?: SubmodelFormData) => {
    const schema = makeSchema([
      baseElement({
        idShort: 'ManufacturerName',
        modelType: 'MultiLanguageProperty',
        semanticId: '0112/2///61987#ABA565#009',
      }),
      baseElement({
        idShort: 'SerialNumber',
        modelType: 'Property',
        semanticId: '0112/2///61987#ABA951#009',
      }),
      baseElement({
        idShort: 'ProductType',
        modelType: 'Property',
        semanticId: '0112/2///61987#ABA300#008',
      }),
      baseElement({
        idShort: 'PCFCO2eq',
        modelType: 'Property',
        semanticId: '0173-1#02-ABG855#001',
      }),
    ]);

    return resolveSchemaElements(schema, formData);
  };

  describe('semanticId matching', () => {
    it('matches by semanticId pattern', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        semanticIdPatterns: [/ABA565/i],
      });

      expect(matches.length).toBe(1);
      expect(matches[0].schema.idShort).toBe('ManufacturerName');
    });

    it('matches multiple semanticId patterns', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        semanticIdPatterns: [/ABA565/i, /ABA951/i],
      });

      expect(matches.length).toBe(2);
    });
  });

  describe('idShort matching', () => {
    it('matches by idShort pattern', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        idShortPatterns: [/SerialNumber/i],
      });

      expect(matches.length).toBe(1);
      expect(matches[0].schema.idShort).toBe('SerialNumber');
    });

    it('handles case-insensitive matching', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        idShortPatterns: [/serialnumber/i],
      });

      expect(matches.length).toBe(1);
    });
  });

  describe('modelType filtering', () => {
    it('filters by modelType', () => {
      const resolved = createResolvedElements();
      // modelTypes acts as a filter, but you still need a pattern to match
      // This test verifies that modelTypes restricts results to the correct type
      const matches = findMatchingElements(resolved, {
        idShortPatterns: [/ManufacturerName/i],
        modelTypes: ['MultiLanguageProperty'],
      });

      expect(matches.length).toBe(1);
      expect(matches[0].schema.idShort).toBe('ManufacturerName');
    });

    it('combines modelType with idShort pattern', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        idShortPatterns: [/PCFCO2eq/i],
        modelTypes: ['Property'],
      });

      expect(matches.length).toBe(1);
    });

    it('excludes non-matching modelTypes', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        idShortPatterns: [/ManufacturerName/i],
        modelTypes: ['Property'], // ManufacturerName is MultiLanguageProperty
      });

      expect(matches.length).toBe(0);
    });
  });

  describe('combined matching', () => {
    it('matches by semanticId OR idShort', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        semanticIdPatterns: [/doesnotexist/i],
        idShortPatterns: [/SerialNumber/i],
      });

      expect(matches.length).toBe(1);
    });
  });

  describe('edge cases', () => {
    it('returns empty array when no matches', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {
        semanticIdPatterns: [/nonexistent/i],
        idShortPatterns: [/nonexistent/i],
      });

      expect(matches).toEqual([]);
    });

    it('handles empty patterns', () => {
      const resolved = createResolvedElements();
      const matches = findMatchingElements(resolved, {});

      expect(matches).toEqual([]);
    });

    it('handles null semanticId in data', () => {
      const formData: SubmodelFormData = {
        elements: {
          ManufacturerName: { value: 'test', semanticId: null as unknown as string },
        },
      };

      const resolved = createResolvedElements(formData);
      const matches = findMatchingElements(resolved, {
        semanticIdPatterns: [/ABA565/i],
      });

      // Should fall back to schema semanticId
      expect(matches.length).toBe(1);
    });
  });
});

describe('schemaIndex integration', () => {
  describe('PCF data extraction scenario', () => {
    it('extracts lifecycle phase data from PCF schema', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'ProductCarbonFootprints',
          modelType: 'SubmodelElementList',
          itemTemplate: baseElement({
            idShort: 'ProductCarbonFootprint',
            modelType: 'SubmodelElementCollection',
            elements: [
              baseElement({
                idShort: 'PCFLifeCyclePhase',
                modelType: 'Property',
                semanticId: '0173-1#02-ABG858#001',
              }),
              baseElement({
                idShort: 'PCFCO2eq',
                modelType: 'Property',
                semanticId: '0173-1#02-ABG855#001',
              }),
            ],
          }),
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          ProductCarbonFootprints: {
            items: [
              {
                elements: {
                  PCFLifeCyclePhase: { value: 'A1' },
                  PCFCO2eq: { value: '10.5' },
                },
              },
              {
                elements: {
                  PCFLifeCyclePhase: { value: 'A2' },
                  PCFCO2eq: { value: '5.2' },
                },
              },
            ],
          },
        },
      };

      const contexts = collectResolvedContexts(schema, formData);

      // Should have contexts for each PCF entry
      expect(contexts.length).toBe(2);

      // Each context should have phase and CO2 elements
      contexts.forEach((context) => {
        const phaseMatch = findMatchingElements(context.elements, {
          idShortPatterns: [/PCFLifeCyclePhase/i],
        });
        const co2Match = findMatchingElements(context.elements, {
          idShortPatterns: [/PCFCO2eq/i],
        });

        expect(phaseMatch.length).toBe(1);
        expect(co2Match.length).toBe(1);
      });
    });
  });

  describe('Nameplate data extraction scenario', () => {
    it('extracts manufacturer and product data from nameplate schema', () => {
      const schema = makeSchema([
        baseElement({
          idShort: 'ManufacturerName',
          modelType: 'MultiLanguageProperty',
          semanticId: '0112/2///61987#ABA565#009',
        }),
        baseElement({
          idShort: 'ManufacturerProductDesignation',
          modelType: 'MultiLanguageProperty',
          semanticId: '0112/2///61987#ABA567#009',
        }),
        baseElement({
          idShort: 'SerialNumber',
          modelType: 'Property',
          semanticId: '0112/2///61987#ABA951#009',
        }),
      ]);

      const formData: SubmodelFormData = {
        elements: {
          ManufacturerName: { value: { en: 'ACME Corp' } },
          ManufacturerProductDesignation: { value: { en: 'Widget Pro' } },
          SerialNumber: { value: 'SN-12345' },
        },
      };

      const resolved = resolveSchemaElements(schema, formData);

      const manufacturer = findMatchingElements(resolved, {
        semanticIdPatterns: [/ABA565/i],
      });
      const product = findMatchingElements(resolved, {
        semanticIdPatterns: [/ABA567/i],
      });
      const serial = findMatchingElements(resolved, {
        idShortPatterns: [/SerialNumber/i],
      });

      expect(manufacturer.length).toBe(1);
      expect(product.length).toBe(1);
      expect(serial.length).toBe(1);

      expect((manufacturer[0].data as ElementFormData).value).toEqual({ en: 'ACME Corp' });
    });
  });
});
