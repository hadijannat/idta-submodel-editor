/**
 * Tests for value extractor utilities.
 */

import { describe, it, expect } from 'vitest';
import type { SubmodelFormData } from '../../../../types/aas-elements';
import {
  getElementAtPath,
  extractPrimitive,
  extractLangString,
  extractCollection,
  extractList,
  isProvided,
  formatValue,
  extractNumber,
} from '../valueExtractors';

describe('getElementAtPath', () => {
  it('navigates dot-separated paths', () => {
    const formData: SubmodelFormData = {
      elements: {
        ManufacturerName: { value: 'Acme Corp' },
      },
    };
    const result = getElementAtPath(formData, 'elements.ManufacturerName');
    expect(result).toEqual({ value: 'Acme Corp' });
  });

  it('navigates deeply nested paths', () => {
    const formData: SubmodelFormData = {
      elements: {
        Parent: {
          elements: {
            Child: {
              value: 'nested value',
            },
          },
        },
      },
    };
    const result = getElementAtPath(formData, 'elements.Parent.elements.Child');
    expect(result).toEqual({ value: 'nested value' });
  });

  it('returns undefined for missing paths', () => {
    const formData: SubmodelFormData = {
      elements: {},
    };
    expect(getElementAtPath(formData, 'elements.Missing')).toBeUndefined();
  });

  it('returns undefined for null formData', () => {
    expect(getElementAtPath(undefined, 'elements.Test')).toBeUndefined();
  });

  it('handles partial path navigation', () => {
    const formData: SubmodelFormData = {
      elements: {
        First: { value: 'exists' },
      },
    };
    expect(getElementAtPath(formData, 'elements.First.Missing')).toBeUndefined();
  });
});

describe('extractPrimitive', () => {
  it('extracts string value', () => {
    const formData: SubmodelFormData = {
      elements: {
        Name: { value: 'Test String' },
      },
    };
    expect(extractPrimitive(formData, 'elements.Name.value')).toBe('Test String');
  });

  it('extracts number value', () => {
    const formData: SubmodelFormData = {
      elements: {
        Count: { value: 42 },
      },
    };
    expect(extractPrimitive(formData, 'elements.Count.value')).toBe(42);
  });

  it('extracts boolean value', () => {
    const formData: SubmodelFormData = {
      elements: {
        Active: { value: true },
      },
    };
    expect(extractPrimitive(formData, 'elements.Active.value')).toBe(true);
  });

  it('handles nested .value property', () => {
    const formData: SubmodelFormData = {
      elements: {
        Property: { value: 'nested' },
      },
    };
    expect(extractPrimitive(formData, 'elements.Property')).toBe('nested');
  });

  it('returns undefined for missing values', () => {
    const formData: SubmodelFormData = { elements: {} };
    expect(extractPrimitive(formData, 'elements.Missing')).toBeUndefined();
  });

  it('returns undefined for null formData', () => {
    expect(extractPrimitive(undefined, 'elements.Test')).toBeUndefined();
  });
});

describe('extractLangString', () => {
  it('extracts preferred language', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: {
            en: 'English description',
            de: 'German description',
          },
        },
      },
    };
    expect(extractLangString(formData, 'elements.Description', 'de')).toBe(
      'German description'
    );
  });

  it('falls back to English when preferred not available', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: {
            en: 'English description',
            fr: 'French description',
          },
        },
      },
    };
    expect(extractLangString(formData, 'elements.Description', 'de')).toBe(
      'English description'
    );
  });

  it('falls back to first available when English not available', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: {
            fr: 'French description',
            es: 'Spanish description',
          },
        },
      },
    };
    const result = extractLangString(formData, 'elements.Description', 'de');
    expect(['French description', 'Spanish description']).toContain(result);
  });

  it('handles direct lang map at path', () => {
    const formData: SubmodelFormData = {
      elements: {
        Name: {
          en: 'English name',
          de: 'German name',
        },
      },
    };
    expect(extractLangString(formData, 'elements.Name')).toBe('English name');
  });

  it('returns undefined for empty strings', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: {
            en: '   ',
            de: '',
          },
        },
      },
    };
    expect(extractLangString(formData, 'elements.Description')).toBeUndefined();
  });

  it('trims whitespace from values', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: {
            en: '  trimmed  ',
          },
        },
      },
    };
    expect(extractLangString(formData, 'elements.Description')).toBe('trimmed');
  });

  it('returns direct string value if not multilanguage', () => {
    const formData: SubmodelFormData = {
      elements: {
        Description: {
          value: 'simple string',
        },
      },
    };
    expect(extractLangString(formData, 'elements.Description')).toBe('simple string');
  });
});

describe('extractCollection', () => {
  it('extracts child elements from collection', () => {
    const formData: SubmodelFormData = {
      elements: {
        Parent: {
          elements: {
            Child1: { value: 'value1' },
            Child2: { value: 'value2' },
          },
        },
      },
    };
    const result = extractCollection(formData, 'elements.Parent');
    expect(result).toEqual({
      Child1: { value: 'value1' },
      Child2: { value: 'value2' },
    });
  });

  it('returns undefined for missing collections', () => {
    const formData: SubmodelFormData = { elements: {} };
    expect(extractCollection(formData, 'elements.Missing')).toBeUndefined();
  });

  it('handles element without .elements property', () => {
    const formData: SubmodelFormData = {
      elements: {
        Collection: {
          Field1: { value: 'v1' },
          Field2: { value: 'v2' },
        },
      },
    };
    const result = extractCollection(formData, 'elements.Collection');
    expect(result).toEqual({
      Field1: { value: 'v1' },
      Field2: { value: 'v2' },
    });
  });
});

describe('extractList', () => {
  it('extracts array items from list', () => {
    const formData: SubmodelFormData = {
      elements: {
        MyList: {
          items: [{ value: 'item1' }, { value: 'item2' }],
        },
      },
    };
    const result = extractList(formData, 'elements.MyList');
    expect(result).toEqual([{ value: 'item1' }, { value: 'item2' }]);
  });

  it('returns undefined for missing lists', () => {
    const formData: SubmodelFormData = { elements: {} };
    expect(extractList(formData, 'elements.Missing')).toBeUndefined();
  });

  it('handles direct array value', () => {
    const formData = {
      elements: {
        DirectArray: [{ value: 'a' }, { value: 'b' }],
      },
    } as unknown as SubmodelFormData;
    const result = extractList(formData, 'elements.DirectArray');
    expect(result).toEqual([{ value: 'a' }, { value: 'b' }]);
  });
});

describe('isProvided', () => {
  it('returns false for undefined', () => {
    expect(isProvided(undefined)).toBe(false);
  });

  it('returns false for null', () => {
    expect(isProvided(null)).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isProvided('')).toBe(false);
  });

  it('returns false for whitespace-only string', () => {
    expect(isProvided('   ')).toBe(false);
  });

  it('returns false for placeholder patterns', () => {
    expect(isProvided('Enter value')).toBe(false);
    expect(isProvided('Type here')).toBe(false);
    expect(isProvided('Select option')).toBe(false);
    expect(isProvided('[Not provided]')).toBe(false);
    expect(isProvided('placeholder')).toBe(false);
    expect(isProvided('N/A')).toBe(false);
    expect(isProvided('-')).toBe(false);
    expect(isProvided('...')).toBe(false);
  });

  it('returns true for actual string values', () => {
    expect(isProvided('Actual value')).toBe(true);
    expect(isProvided('Product Name')).toBe(true);
    expect(isProvided('12345')).toBe(true);
  });

  it('returns true for non-NaN numbers', () => {
    expect(isProvided(0)).toBe(true);
    expect(isProvided(42)).toBe(true);
    expect(isProvided(-5)).toBe(true);
    expect(isProvided(3.14)).toBe(true);
  });

  it('returns false for NaN', () => {
    expect(isProvided(NaN)).toBe(false);
  });

  it('returns true for booleans', () => {
    expect(isProvided(true)).toBe(true);
    expect(isProvided(false)).toBe(true);
  });

  it('returns true for non-empty arrays', () => {
    expect(isProvided([1, 2, 3])).toBe(true);
  });

  it('returns false for empty arrays', () => {
    expect(isProvided([])).toBe(false);
  });

  it('returns true for non-empty objects', () => {
    expect(isProvided({ key: 'value' })).toBe(true);
  });

  it('returns false for empty objects', () => {
    expect(isProvided({})).toBe(false);
  });
});

describe('formatValue', () => {
  it('formats boolean true as "Yes"', () => {
    expect(formatValue(true)).toBe('Yes');
  });

  it('formats boolean false as "No"', () => {
    expect(formatValue(false)).toBe('No');
  });

  it('formats large numbers with separators', () => {
    const result = formatValue(1234567);
    expect(result).toMatch(/1[,.]?234[,.]?567/);
  });

  it('formats small decimals with appropriate precision', () => {
    expect(formatValue(3.14159)).toBe('3.1416');
  });

  it('formats integers without decimals', () => {
    expect(formatValue(42)).toBe('42');
  });

  it('trims string values', () => {
    expect(formatValue('  trimmed  ')).toBe('trimmed');
  });

  it('returns empty string for undefined', () => {
    expect(formatValue(undefined)).toBe('');
  });

  it('returns empty string for null', () => {
    expect(formatValue(null)).toBe('');
  });

  it('removes trailing zeros from decimals', () => {
    expect(formatValue(3.5)).toBe('3.5');
    expect(formatValue(3.0)).toBe('3');
  });
});

describe('extractNumber', () => {
  it('extracts numeric value from path', () => {
    const formData: SubmodelFormData = {
      elements: {
        Count: { value: 42 },
      },
    };
    expect(extractNumber(formData, 'elements.Count.value')).toBe(42);
  });

  it('parses numeric string', () => {
    const formData: SubmodelFormData = {
      elements: {
        Price: { value: '19.99' },
      },
    };
    expect(extractNumber(formData, 'elements.Price.value')).toBe(19.99);
  });

  it('returns undefined for non-numeric string', () => {
    const formData: SubmodelFormData = {
      elements: {
        Name: { value: 'not a number' },
      },
    };
    expect(extractNumber(formData, 'elements.Name.value')).toBeUndefined();
  });

  it('returns undefined for NaN', () => {
    const formData: SubmodelFormData = {
      elements: {
        Invalid: { value: NaN },
      },
    };
    expect(extractNumber(formData, 'elements.Invalid.value')).toBeUndefined();
  });

  it('returns undefined for missing path', () => {
    const formData: SubmodelFormData = { elements: {} };
    expect(extractNumber(formData, 'elements.Missing')).toBeUndefined();
  });

  it('handles zero correctly', () => {
    const formData: SubmodelFormData = {
      elements: {
        Zero: { value: 0 },
      },
    };
    expect(extractNumber(formData, 'elements.Zero.value')).toBe(0);
  });

  it('handles negative numbers', () => {
    const formData: SubmodelFormData = {
      elements: {
        Negative: { value: -10.5 },
      },
    };
    expect(extractNumber(formData, 'elements.Negative.value')).toBe(-10.5);
  });
});
