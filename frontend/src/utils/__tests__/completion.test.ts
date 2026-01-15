import { describe, expect, it } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import { computeCompletion, hasValue } from '../completion';

const baseElement = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'base',
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  valueType: 'xs:string',
  ...overrides,
});

const baseSchema = (elements: UIElementSchema[]): SubmodelUISchema => ({
  templateName: null,
  templatePath: null,
  submodelId: 'urn:example',
  idShort: 'Example',
  semanticId: null,
  description: null,
  administration: null,
  elements,
  supplementaryFiles: [],
});

describe('completion helpers', () => {
  it('detects when values are present', () => {
    expect(hasValue('')).toBe(false);
    expect(hasValue('value')).toBe(true);
    expect(hasValue(0)).toBe(true);
    expect(hasValue(false)).toBe(true);
    expect(hasValue([])).toBe(false);
    expect(hasValue(['x'])).toBe(true);
  });

  it('counts required completion for simple properties', () => {
    const schema = baseSchema([
      baseElement({ idShort: 'required', cardinality: '[1]' }),
      baseElement({ idShort: 'optional', cardinality: '[0..1]' }),
    ]);
    const values: SubmodelFormData = {
      elements: {
        required: { value: 'ok' },
        optional: { value: '' },
      },
    };

    expect(computeCompletion(schema, values)).toEqual({ required: 1, completed: 1 });
  });

  it('counts nested collection requirements', () => {
    const schema = baseSchema([
      baseElement({
        idShort: 'group',
        modelType: 'SubmodelElementCollection',
        elements: [baseElement({ idShort: 'child', cardinality: '[1]' })],
      }),
    ]);
    const values: SubmodelFormData = {
      elements: {
        group: {
          elements: {
            child: { value: 'filled' },
          },
        },
      },
    };

    expect(computeCompletion(schema, values)).toEqual({ required: 1, completed: 1 });
  });

  it('marks required lists incomplete when empty', () => {
    const schema = baseSchema([
      baseElement({
        idShort: 'items',
        modelType: 'SubmodelElementList',
        cardinality: '[1..*]',
        itemTemplate: baseElement({ idShort: 'item', cardinality: '[1]' }),
      }),
    ]);
    const values: SubmodelFormData = {
      elements: {
        items: {
          items: [],
        },
      },
    };

    expect(computeCompletion(schema, values)).toEqual({ required: 1, completed: 0 });
  });
});
