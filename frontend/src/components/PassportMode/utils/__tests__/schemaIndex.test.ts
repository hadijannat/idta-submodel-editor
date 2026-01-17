import { describe, it, expect } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../../../types/ui-schema';
import type { SubmodelFormData } from '../../../../types/aas-elements';
import { collectResolvedContexts, resolveSchemaElements } from '../schemaIndex';

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

describe('schemaIndex', () => {
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
      resolved.some((node) => node.path === 'elements.RootCollection.elements.ChildProp')
    ).toBe(true);
  });

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
});
