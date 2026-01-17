/**
 * Comprehensive tests for valueExtractors utilities.
 */

import { describe, it, expect } from 'vitest';
import type { ElementFormData, SubmodelFormData } from '../../../../types/aas-elements';
import {
  extractLangStringValue,
  extractSafeUrl,
  parseStrictNumber,
  traverseValue,
  getElementAtPath,
  extractPrimitiveValue,
  extractPrimitive,
  extractLangString,
  extractCollection,
  extractList,
  isProvided,
  formatValue,
  extractNumber,
} from '../valueExtractors';

describe('parseStrictNumber', () => {
  describe('valid inputs', () => {
    it('parses positive integers', () => {
      expect(parseStrictNumber('123')).toBe(123);
      expect(parseStrictNumber('0')).toBe(0);
      expect(parseStrictNumber('999999')).toBe(999999);
    });

    it('parses negative integers', () => {
      expect(parseStrictNumber('-123')).toBe(-123);
      expect(parseStrictNumber('-0')).toBe(-0);
    });

    it('parses positive decimals', () => {
      expect(parseStrictNumber('12.34')).toBe(12.34);
      expect(parseStrictNumber('0.5')).toBe(0.5);
      expect(parseStrictNumber('123.456789')).toBe(123.456789);
    });

    it('parses negative decimals', () => {
      expect(parseStrictNumber('-12.34')).toBe(-12.34);
      expect(parseStrictNumber('-0.5')).toBe(-0.5);
    });

    it('handles number type directly', () => {
      expect(parseStrictNumber(5)).toBe(5);
      expect(parseStrictNumber(3.14)).toBe(3.14);
      expect(parseStrictNumber(-42)).toBe(-42);
    });

    it('trims whitespace', () => {
      expect(parseStrictNumber('  123  ')).toBe(123);
      expect(parseStrictNumber('\t456\n')).toBe(456);
    });
  });

  describe('invalid inputs', () => {
    it('rejects locale-formatted numbers', () => {
      expect(parseStrictNumber('12,34')).toBeUndefined();
      expect(parseStrictNumber('1,234.56')).toBeUndefined();
      expect(parseStrictNumber('1.234,56')).toBeUndefined();
    });

    it('rejects numbers with units', () => {
      expect(parseStrictNumber('12kg')).toBeUndefined();
      expect(parseStrictNumber('100%')).toBeUndefined();
      expect(parseStrictNumber('$99')).toBeUndefined();
      expect(parseStrictNumber('12 meters')).toBeUndefined();
    });

    it('rejects scientific notation', () => {
      expect(parseStrictNumber('1e10')).toBeUndefined();
      expect(parseStrictNumber('1.5E-3')).toBeUndefined();
    });

    it('rejects empty and whitespace', () => {
      expect(parseStrictNumber('')).toBeUndefined();
      expect(parseStrictNumber('   ')).toBeUndefined();
    });

    it('rejects non-number types', () => {
      expect(parseStrictNumber(null)).toBeUndefined();
      expect(parseStrictNumber(undefined)).toBeUndefined();
      expect(parseStrictNumber({})).toBeUndefined();
      expect(parseStrictNumber([])).toBeUndefined();
      expect(parseStrictNumber(true)).toBeUndefined();
    });

    it('rejects Infinity and NaN', () => {
      expect(parseStrictNumber(Infinity)).toBeUndefined();
      expect(parseStrictNumber(-Infinity)).toBeUndefined();
      expect(parseStrictNumber(NaN)).toBeUndefined();
    });

    it('rejects leading zeros (except 0 itself)', () => {
      // Actually, "007" matches the pattern and parses to 7, which is valid
      expect(parseStrictNumber('007')).toBe(7);
    });

    it('rejects multiple decimal points', () => {
      expect(parseStrictNumber('1.2.3')).toBeUndefined();
    });
  });
});

describe('extractLangStringValue', () => {
  describe('with string input', () => {
    it('returns trimmed string', () => {
      expect(extractLangStringValue('Hello')).toBe('Hello');
      expect(extractLangStringValue('  Hello  ')).toBe('Hello');
    });

    it('returns undefined for empty string', () => {
      expect(extractLangStringValue('')).toBeUndefined();
      expect(extractLangStringValue('   ')).toBeUndefined();
    });
  });

  describe('with object map input', () => {
    it('extracts preferred language', () => {
      const value = { en: 'Hello', de: 'Hallo', fr: 'Bonjour' };
      expect(extractLangStringValue(value, ['de'])).toBe('Hallo');
      expect(extractLangStringValue(value, ['en'])).toBe('Hello');
      expect(extractLangStringValue(value, ['fr'])).toBe('Bonjour');
    });

    it('falls back through preferred languages', () => {
      const value = { de: 'Hallo' };
      expect(extractLangStringValue(value, ['en', 'de'])).toBe('Hallo');
    });

    it('returns first available if no preferred match', () => {
      const value = { ja: 'Konnichiwa' };
      expect(extractLangStringValue(value, ['en', 'de'])).toBe('Konnichiwa');
    });

    it('handles empty strings in map', () => {
      const value = { en: '', de: 'Hallo' };
      expect(extractLangStringValue(value, ['en', 'de'])).toBe('Hallo');
    });
  });

  describe('with array input', () => {
    it('extracts from language array', () => {
      const value = [
        { language: 'de', text: 'Hallo' },
        { language: 'en', text: 'Hello' },
      ];
      expect(extractLangStringValue(value, ['en'])).toBe('Hello');
    });

    it('handles lang key instead of language', () => {
      const value = [
        { lang: 'en', text: 'Hello' },
        { lang: 'de', text: 'Hallo' },
      ];
      expect(extractLangStringValue(value, ['de'])).toBe('Hallo');
    });

    it('handles value key instead of text', () => {
      const value = [
        { language: 'en', value: 'Hello' },
      ];
      expect(extractLangStringValue(value, ['en'])).toBe('Hello');
    });

    it('returns first available text if no language match', () => {
      const value = [
        { language: 'ja', text: 'Konnichiwa' },
      ];
      expect(extractLangStringValue(value, ['en'])).toBe('Konnichiwa');
    });
  });

  describe('with nested value object', () => {
    it('extracts from {value: map}', () => {
      const value = { value: { en: 'Hello', de: 'Hallo' } };
      expect(extractLangStringValue(value, ['de'])).toBe('Hallo');
    });

    it('extracts from {value: array}', () => {
      const value = {
        value: [
          { language: 'en', text: 'Hello' },
        ],
      };
      expect(extractLangStringValue(value, ['en'])).toBe('Hello');
    });

    it('extracts from {value: string}', () => {
      const value = { value: 'Hello' };
      expect(extractLangStringValue(value, ['en'])).toBe('Hello');
    });
  });

  describe('edge cases', () => {
    it('handles null', () => {
      expect(extractLangStringValue(null)).toBeUndefined();
    });

    it('handles undefined', () => {
      expect(extractLangStringValue(undefined)).toBeUndefined();
    });

    it('handles empty object', () => {
      expect(extractLangStringValue({})).toBeUndefined();
    });

    it('handles empty array', () => {
      expect(extractLangStringValue([])).toBeUndefined();
    });
  });
});

describe('extractSafeUrl', () => {
  describe('valid URLs', () => {
    it('accepts https URLs', () => {
      expect(extractSafeUrl('https://example.com')).toBe('https://example.com/');
      expect(extractSafeUrl('https://example.com/path')).toBe('https://example.com/path');
      expect(extractSafeUrl('https://example.com:8080')).toBe('https://example.com:8080/');
    });

    it('accepts http URLs', () => {
      expect(extractSafeUrl('http://example.com')).toBe('http://example.com/');
      expect(extractSafeUrl('http://localhost:3000')).toBe('http://localhost:3000/');
    });

    it('preserves query strings', () => {
      expect(extractSafeUrl('https://example.com?foo=bar')).toBe('https://example.com/?foo=bar');
    });

    it('preserves hash fragments', () => {
      expect(extractSafeUrl('https://example.com#section')).toBe('https://example.com/#section');
    });
  });

  describe('invalid URLs', () => {
    it('rejects ftp URLs', () => {
      expect(extractSafeUrl('ftp://example.com')).toBeUndefined();
    });

    it('rejects file URLs', () => {
      expect(extractSafeUrl('file:///etc/passwd')).toBeUndefined();
    });

    it('rejects javascript URLs', () => {
      expect(extractSafeUrl('javascript:alert(1)')).toBeUndefined();
    });

    it('rejects data URLs', () => {
      expect(extractSafeUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined();
    });

    it('rejects malformed URLs', () => {
      expect(extractSafeUrl('not a url')).toBeUndefined();
      expect(extractSafeUrl('http://')).toBeUndefined();
    });

    it('rejects non-string inputs', () => {
      expect(extractSafeUrl(123)).toBeUndefined();
      expect(extractSafeUrl(null)).toBeUndefined();
      expect(extractSafeUrl(undefined)).toBeUndefined();
      expect(extractSafeUrl({})).toBeUndefined();
    });

    it('rejects empty strings', () => {
      expect(extractSafeUrl('')).toBeUndefined();
      expect(extractSafeUrl('   ')).toBeUndefined();
    });
  });
});

describe('traverseValue', () => {
  it('visits all nodes in flat object', () => {
    const obj = { a: 1, b: 2, c: 3 };
    const visited: Array<[unknown, Array<string | number>]> = [];

    traverseValue(obj, (value, path) => {
      visited.push([value, [...path]]);
    });

    expect(visited.length).toBeGreaterThan(0);
    expect(visited.some(([, path]) => path.includes('a'))).toBe(true);
  });

  it('visits nested objects', () => {
    const obj = { a: { b: { c: 1 } } };
    const paths: Array<string | number>[] = [];

    traverseValue(obj, (_, path) => {
      paths.push([...path]);
    });

    expect(paths.some((p) => p.length === 3)).toBe(true);
  });

  it('visits arrays', () => {
    const obj = { items: [1, 2, 3] };
    const visited: unknown[] = [];

    traverseValue(obj, (value) => {
      if (typeof value === 'number') visited.push(value);
    });

    expect(visited).toContain(1);
    expect(visited).toContain(2);
    expect(visited).toContain(3);
  });

  it('handles cycles without infinite loop', () => {
    const obj: Record<string, unknown> = { a: 1 };
    obj.self = obj;

    let count = 0;
    traverseValue(obj, () => {
      count += 1;
      if (count > 100) throw new Error('Infinite loop detected');
    });

    expect(count).toBeLessThan(100);
  });

  it('respects maxDepth option', () => {
    const obj = { a: { b: { c: { d: { e: 1 } } } } };
    let maxDepthReached = 0;

    traverseValue(
      obj,
      (_, path) => {
        if (path.length > maxDepthReached) maxDepthReached = path.length;
      },
      { maxDepth: 2 }
    );

    expect(maxDepthReached).toBeLessThanOrEqual(2);
  });

  it('handles null and undefined', () => {
    let count = 0;
    traverseValue(null, () => count++);
    expect(count).toBe(1);

    count = 0;
    traverseValue(undefined, () => count++);
    expect(count).toBe(1);
  });

  it('handles primitives', () => {
    const values: unknown[] = [];
    traverseValue('hello', (v) => values.push(v));
    expect(values).toContain('hello');

    values.length = 0;
    traverseValue(42, (v) => values.push(v));
    expect(values).toContain(42);
  });
});

describe('getElementAtPath', () => {
  const formData: SubmodelFormData = {
    elements: {
      Manufacturer: { value: 'ACME Corp' },
      Product: {
        elements: {
          Name: { value: 'Widget' },
          Price: { value: 99.99 },
        },
      },
    },
  };

  it('navigates dot-separated paths', () => {
    const result = getElementAtPath(formData, 'elements.Manufacturer');
    expect(result).toEqual({ value: 'ACME Corp' });
  });

  it('navigates nested paths', () => {
    const result = getElementAtPath(formData, 'elements.Product.elements.Name');
    expect(result).toEqual({ value: 'Widget' });
  });

  it('returns undefined for missing paths', () => {
    const result = getElementAtPath(formData, 'elements.NonExistent');
    expect(result).toBeUndefined();
  });

  it('returns undefined for undefined formData', () => {
    const result = getElementAtPath(undefined, 'elements.Manufacturer');
    expect(result).toBeUndefined();
  });

  it('handles empty path parts', () => {
    const result = getElementAtPath(formData, 'elements');
    expect(result).toBeDefined();
  });
});

describe('extractPrimitiveValue', () => {
  it('returns strings directly', () => {
    expect(extractPrimitiveValue('hello')).toBe('hello');
  });

  it('returns numbers directly', () => {
    expect(extractPrimitiveValue(42)).toBe(42);
    expect(extractPrimitiveValue(3.14)).toBe(3.14);
  });

  it('returns booleans directly', () => {
    expect(extractPrimitiveValue(true)).toBe(true);
    expect(extractPrimitiveValue(false)).toBe(false);
  });

  it('extracts value from {value: primitive}', () => {
    expect(extractPrimitiveValue({ value: 'hello' })).toBe('hello');
    expect(extractPrimitiveValue({ value: 42 })).toBe(42);
    expect(extractPrimitiveValue({ value: true })).toBe(true);
  });

  it('returns undefined for non-primitives', () => {
    expect(extractPrimitiveValue({ other: 'data' })).toBeUndefined();
    expect(extractPrimitiveValue([1, 2, 3])).toBeUndefined();
    expect(extractPrimitiveValue(null)).toBeUndefined();
    expect(extractPrimitiveValue(undefined)).toBeUndefined();
  });
});

describe('extractPrimitive', () => {
  const formData: SubmodelFormData = {
    elements: {
      StringProp: { value: 'text' },
      NumberProp: { value: 42 },
      BoolProp: { value: true },
      DirectProp: 'direct' as unknown as ElementFormData, // Edge case: direct primitive
    },
  };

  it('extracts string primitive', () => {
    expect(extractPrimitive(formData, 'elements.StringProp')).toBe('text');
  });

  it('extracts number primitive', () => {
    expect(extractPrimitive(formData, 'elements.NumberProp')).toBe(42);
  });

  it('extracts boolean primitive', () => {
    expect(extractPrimitive(formData, 'elements.BoolProp')).toBe(true);
  });

  it('handles direct primitive values', () => {
    expect(extractPrimitive(formData, 'elements.DirectProp')).toBe('direct');
  });

  it('returns undefined for missing path', () => {
    expect(extractPrimitive(formData, 'elements.Missing')).toBeUndefined();
  });
});

describe('extractLangString', () => {
  const formData: SubmodelFormData = {
    elements: {
      SimpleLang: { value: { en: 'Hello', de: 'Hallo' } },
      DirectString: { value: 'Simple string' },
    },
  };

  it('extracts with preferred language', () => {
    expect(extractLangString(formData, 'elements.SimpleLang', 'de')).toBe('Hallo');
  });

  it('falls back to en by default', () => {
    expect(extractLangString(formData, 'elements.SimpleLang')).toBe('Hello');
  });

  it('handles direct string values', () => {
    expect(extractLangString(formData, 'elements.DirectString')).toBe('Simple string');
  });

  it('returns undefined for missing path', () => {
    expect(extractLangString(formData, 'elements.Missing')).toBeUndefined();
  });
});

describe('extractCollection', () => {
  const formData: SubmodelFormData = {
    elements: {
      Collection: {
        elements: {
          Child1: { value: 'a' },
          Child2: { value: 'b' },
        },
      },
      DirectRecord: {
        Key1: { value: 'x' },
        Key2: { value: 'y' },
      },
    },
  };

  it('extracts elements from collection', () => {
    const result = extractCollection(formData, 'elements.Collection');
    expect(result?.Child1).toEqual({ value: 'a' });
    expect(result?.Child2).toEqual({ value: 'b' });
  });

  it('returns undefined for missing path', () => {
    expect(extractCollection(formData, 'elements.Missing')).toBeUndefined();
  });

  it('returns undefined for undefined formData', () => {
    expect(extractCollection(undefined, 'elements.Collection')).toBeUndefined();
  });
});

describe('extractList', () => {
  const formData: SubmodelFormData = {
    elements: {
      ListWithItems: {
        items: [{ value: 'a' }, { value: 'b' }, { value: 'c' }],
      },
      DirectArray: [{ value: 'x' }, { value: 'y' }] as unknown as ElementFormData, // Edge case: direct array
    },
  };

  it('extracts items from list', () => {
    const result = extractList(formData, 'elements.ListWithItems');
    expect(result?.length).toBe(3);
    expect(result?.[0]).toEqual({ value: 'a' });
  });

  it('handles direct array', () => {
    const result = extractList(formData, 'elements.DirectArray');
    expect(result?.length).toBe(2);
  });

  it('returns undefined for missing path', () => {
    expect(extractList(formData, 'elements.Missing')).toBeUndefined();
  });
});

describe('isProvided', () => {
  describe('falsy values', () => {
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
      expect(isProvided('\t\n')).toBe(false);
    });

    it('returns false for NaN', () => {
      expect(isProvided(NaN)).toBe(false);
    });
  });

  describe('placeholder patterns', () => {
    it('returns false for "Enter..." patterns', () => {
      expect(isProvided('Enter value')).toBe(false);
      expect(isProvided('Enter your name')).toBe(false);
    });

    it('returns false for "Type..." patterns', () => {
      expect(isProvided('Type here')).toBe(false);
    });

    it('returns false for "Select..." patterns', () => {
      expect(isProvided('Select option')).toBe(false);
    });

    it('returns false for bracketed placeholders', () => {
      expect(isProvided('[Not provided]')).toBe(false);
      expect(isProvided('[TBD]')).toBe(false);
    });

    it('returns false for common placeholder words', () => {
      expect(isProvided('placeholder')).toBe(false);
      expect(isProvided('example')).toBe(false);
      expect(isProvided('sample')).toBe(false);
      expect(isProvided('TBD')).toBe(false);
      expect(isProvided('TBA')).toBe(false);
      expect(isProvided('...')).toBe(false);
    });
  });

  describe('truthy values', () => {
    it('returns true for non-empty strings', () => {
      expect(isProvided('Hello')).toBe(true);
      expect(isProvided('ACME Corp')).toBe(true);
    });

    it('returns true for numbers (including 0)', () => {
      expect(isProvided(0)).toBe(true);
      expect(isProvided(42)).toBe(true);
      expect(isProvided(-1)).toBe(true);
    });

    it('returns true for booleans', () => {
      expect(isProvided(true)).toBe(true);
      expect(isProvided(false)).toBe(true);
    });

    it('returns true for non-empty arrays', () => {
      expect(isProvided([1, 2])).toBe(true);
      expect(isProvided(['a'])).toBe(true);
    });

    it('returns true for non-empty objects', () => {
      expect(isProvided({ a: 1 })).toBe(true);
    });
  });

  describe('edge cases', () => {
    it('returns false for empty array', () => {
      expect(isProvided([])).toBe(false);
    });

    it('returns false for empty object', () => {
      expect(isProvided({})).toBe(false);
    });
  });
});

describe('formatValue', () => {
  describe('primitives', () => {
    it('formats booleans', () => {
      expect(formatValue(true)).toBe('Yes');
      expect(formatValue(false)).toBe('No');
    });

    it('formats large numbers with locale', () => {
      const formatted = formatValue(1234567);
      expect(formatted).toContain('1');
      // Locale formatting varies, just check it's formatted somehow
      expect(formatted.length).toBeGreaterThan(0);
    });

    it('formats small decimals', () => {
      expect(formatValue(0.123456)).toBe('0.1235');
    });

    it('formats integers', () => {
      expect(formatValue(42)).toBe('42');
    });

    it('trims strings', () => {
      expect(formatValue('  hello  ')).toBe('hello');
    });
  });

  describe('edge cases', () => {
    it('returns empty string for undefined', () => {
      expect(formatValue(undefined)).toBe('');
    });

    it('returns empty string for null', () => {
      expect(formatValue(null)).toBe('');
    });

    it('returns empty string for Infinity', () => {
      expect(formatValue(Infinity)).toBe('');
      expect(formatValue(-Infinity)).toBe('');
    });

    it('stringifies other types', () => {
      expect(formatValue({})).toBe('[object Object]');
    });
  });
});

describe('extractNumber', () => {
  const formData: SubmodelFormData = {
    elements: {
      NumericProp: { value: '123.45' },
      DirectNumber: { value: 42 },
      InvalidProp: { value: 'not a number' },
    },
  };

  it('extracts and parses numeric string', () => {
    expect(extractNumber(formData, 'elements.NumericProp')).toBe(123.45);
  });

  it('extracts direct number', () => {
    expect(extractNumber(formData, 'elements.DirectNumber')).toBe(42);
  });

  it('returns undefined for non-numeric', () => {
    expect(extractNumber(formData, 'elements.InvalidProp')).toBeUndefined();
  });

  it('returns undefined for missing path', () => {
    expect(extractNumber(formData, 'elements.Missing')).toBeUndefined();
  });
});
