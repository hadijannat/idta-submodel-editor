import { describe, expect, it } from 'vitest';

import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import { getListItemBounds } from '../../types/aas-elements';
import { findExampleFields } from '../exampleValues';
import {
  codeListOptions,
  elementLabel,
  exampleValue,
  fieldOptions,
  fieldPlaceholder,
  formatHintWarning,
  isStrictEnumeration,
  isTemplateExample,
  requirementError,
  splitNotes,
  toIdShortPath,
} from '../fieldRequirements';

const element = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'Field',
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..1]',
  category: null,
  valueType: 'xs:string',
  inputType: 'text',
  ...overrides,
});

const countryHint = {
  id: 'iso3166-1-alpha2',
  label: 'ISO 3166-1 alpha-2',
  description: 'Two-letter country code',
  pattern: '^[A-Z]{2}$',
  example: 'DE',
  options: 'country',
  transform: 'uppercase' as const,
};

describe('toIdShortPath', () => {
  it('drops structural segments and list indexes', () => {
    expect(toIdShortPath('elements.ManufacturerName.value')).toBe('ManufacturerName');
    expect(toIdShortPath('elements.Markings.items.0.elements.MarkingName')).toBe(
      'Markings.MarkingName'
    );
    expect(toIdShortPath('elements.Entity.statements.Part.value')).toBe('Entity.Part');
  });
});

describe('splitNotes', () => {
  it('separates the description from its notes', () => {
    expect(
      splitNotes(
        'date of issue Note: format by lexical representation: CCYY-MM-DD Note: to be specified to the day'
      )
    ).toEqual({
      body: 'date of issue',
      notes: ['format by lexical representation: CCYY-MM-DD', 'to be specified to the day'],
    });
  });

  it('keeps constraints labelled and handles text without notes', () => {
    expect(splitNotes('Constraint: at least one entry').notes).toEqual([
      'Constraint: at least one entry',
    ]);
    expect(splitNotes('plain text')).toEqual({ body: 'plain text', notes: [] });
    expect(splitNotes(null)).toEqual({ body: '', notes: [] });
  });
});

describe('labels, options and placeholders', () => {
  it('prefers the label provided by the backend', () => {
    expect(elementLabel(element({ label: 'Country Of Origin', idShort: 'CountryOfOrigin' }))).toBe(
      'Country Of Origin'
    );
    expect(elementLabel(element({ semanticLabel: 'Semantic' }))).toBe('Semantic');
    expect(elementLabel(element({}))).toBe('Field');
  });

  it('offers the template enumeration before code lists', () => {
    const strict = element({
      allowedValues: [{ value: 'pass' }, { value: 'fail' }],
      allowedValuesStrict: true,
    });
    expect(fieldOptions(strict).map((option) => option.value)).toEqual(['pass', 'fail']);
    expect(isStrictEnumeration(strict)).toBe(true);
    expect(isStrictEnumeration(element({ allowedValues: [{ value: 'a' }] }))).toBe(false);
  });

  it('provides ISO code lists for format hints', () => {
    const countries = codeListOptions('country');
    expect(countries.length).toBeGreaterThan(200);
    expect(countries.find((option) => option.value === 'DE')?.label).toBe('Germany');
    expect(fieldOptions(element({ formatHint: countryHint })).length).toBe(countries.length);
    expect(codeListOptions('unknown')).toEqual([]);
  });

  it('uses template examples as placeholder', () => {
    expect(fieldPlaceholder(element({ exampleValues: ['FM-ABC-1234'] }), 'Type')).toBe(
      'e.g. FM-ABC-1234'
    );
    expect(fieldPlaceholder(element({ formatHint: countryHint }), 'Country')).toBe('e.g. DE');
    expect(fieldPlaceholder(element({}), 'Serial Number')).toBe('Enter Serial Number');
    expect(exampleValue(element({}))).toBeNull();
  });
});

describe('formatHintWarning', () => {
  it('accepts conforming values and flags others', () => {
    expect(formatHintWarning(countryHint, 'DE')).toBeNull();
    expect(formatHintWarning(countryHint, '')).toBeNull();
    expect(formatHintWarning(countryHint, 'Germany')).toContain('ISO 3166-1 alpha-2');
    expect(formatHintWarning(countryHint, 'XX')).toContain('not an assigned');
    expect(formatHintWarning(null, 'anything')).toBeNull();
  });

  it('ignores an invalid pattern', () => {
    expect(formatHintWarning({ ...countryHint, pattern: '[', options: null }, 'x')).toBeNull();
  });
});

describe('requirementError', () => {
  it('enforces strict enumerations', () => {
    const schema = element({
      allowedValues: [{ value: 'pass' }, { value: 'fail' }],
      allowedValuesStrict: true,
    });
    expect(requirementError(schema, 'pass')).toBeNull();
    expect(requirementError(schema, 'maybe')).toContain('Must be one of: pass, fail');
    expect(requirementError(schema, '')).toBeNull();
  });

  it('treats non-strict value lists as suggestions', () => {
    const schema = element({ allowedValues: [{ value: 'office' }], allowedValuesStrict: false });
    expect(requirementError(schema, 'satellite')).toBeNull();
  });

  it('matches booleans against True/False enumerations', () => {
    const schema = element({
      valueType: 'xs:boolean',
      allowedValues: [{ value: 'True' }, { value: 'False' }],
      allowedValuesStrict: true,
    });
    expect(requirementError(schema, true)).toBeNull();
  });

  it('enforces patterns as full matches', () => {
    const schema = element({ pattern: '[A-Z]{2}\\d{4}' });
    expect(requirementError(schema, 'AB1234')).toBeNull();
    expect(requirementError(schema, 'AB12345')).toContain('pattern');
  });

  it('enforces allowed ranges and value type bounds', () => {
    const schema = element({
      valueType: 'xs:unsignedByte',
      allowedRange: { min: 0, max: 63 },
      constraints: { min: 0, max: 255 },
    });
    expect(requirementError(schema, 10)).toBeNull();
    expect(requirementError(schema, 64)).toBe('Must be at most 63');
    expect(requirementError(schema, -1)).toBe('Must be at least 0');
  });
});

describe('template example values', () => {
  const schema: SubmodelUISchema = {
    submodelId: 'urn:test',
    idShort: 'Nameplate',
    semanticId: null,
    description: null,
    administration: null,
    supplementaryFiles: [],
    elements: [
      element({ idShort: 'CountryOfOrigin', exampleValues: ['DE'], value: 'DE' }),
      element({
        idShort: 'ManufacturerName',
        modelType: 'MultiLanguageProperty',
        exampleValues: ['Muster AG'],
      }),
      element({
        idShort: 'Markings',
        modelType: 'SubmodelElementList',
        itemTemplate: element({
          idShort: 'MarkingsItem',
          modelType: 'SubmodelElementCollection',
          elements: [element({ idShort: 'MarkingName', exampleValues: ['CE'] })],
        }),
      }),
      element({
        idShort: 'Conformity',
        exampleValues: ['pass'],
        allowedValues: [{ value: 'pass' }, { value: 'fail' }],
      }),
    ],
  };

  it('recognises unchanged examples but not enumerations or trivial values', () => {
    expect(isTemplateExample(schema.elements[0], 'DE')).toBe(true);
    expect(isTemplateExample(schema.elements[0], 'FR')).toBe(false);
    expect(isTemplateExample(schema.elements[3], 'pass')).toBe(false);
    expect(isTemplateExample(element({ exampleValues: ['1'] }), 1)).toBe(false);
    expect(isTemplateExample(element({ exampleValues: ['true'] }), true)).toBe(false);
  });

  it('finds example values across nested elements and list items', () => {
    const found = findExampleFields(schema, {
      elements: {
        CountryOfOrigin: { value: 'DE' },
        ManufacturerName: { value: { de: 'Muster AG', en: 'ACME' } },
        Markings: {
          items: [
            { elements: { MarkingName: { value: 'CE' } } },
            { elements: { MarkingName: { value: 'UKCA' } } },
          ],
        },
        Conformity: { value: 'pass' },
      },
    });

    expect(found.map((field) => field.path)).toEqual([
      'elements.CountryOfOrigin.value',
      'elements.ManufacturerName.value.de',
      'elements.Markings.items.0.elements.MarkingName.value',
    ]);
    expect(findExampleFields(null, undefined)).toEqual([]);
  });
});

describe('getListItemBounds', () => {
  it('does not cap a list that occurs once at one item', () => {
    expect(
      getListItemBounds({ cardinality: '[0..1]', itemTemplate: { cardinality: '[1..*]' } })
    ).toEqual({ min: 0, max: undefined });
    expect(getListItemBounds({ cardinality: '[1]', itemTemplate: null })).toEqual({
      min: 1,
      max: undefined,
    });
  });

  it('uses a bound declared on the item', () => {
    expect(
      getListItemBounds({ cardinality: '[1]', itemTemplate: { cardinality: '[1..3]' } })
    ).toEqual({ min: 1, max: 3 });
  });

  it('keeps a multi-valued cardinality declared on the list', () => {
    expect(getListItemBounds({ cardinality: '[1..*]' })).toEqual({ min: 1 });
    expect(getListItemBounds({ cardinality: '[0..2]' })).toEqual({ min: 0, max: 2 });
  });
});
