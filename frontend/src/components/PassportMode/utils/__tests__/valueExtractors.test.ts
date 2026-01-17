import { describe, it, expect } from 'vitest';
import {
  extractLangStringValue,
  extractSafeUrl,
  parseStrictNumber,
  traverseValue,
} from '../valueExtractors';

describe('valueExtractors', () => {
  it('parses strict numeric strings only', () => {
    expect(parseStrictNumber('12.34')).toBe(12.34);
    expect(parseStrictNumber('12,34')).toBeUndefined();
    expect(parseStrictNumber('12kg')).toBeUndefined();
    expect(parseStrictNumber(5)).toBe(5);
  });

  it('extracts multilingual values from maps and arrays', () => {
    expect(extractLangStringValue({ en: 'Hello', de: 'Hallo' }, ['de'])).toBe('Hallo');
    expect(
      extractLangStringValue(
        [
          { language: 'de', text: 'Hallo' },
          { language: 'en', text: 'Hello' },
        ],
        ['en']
      )
    ).toBe('Hello');
  });

  it('extracts safe urls only', () => {
    expect(extractSafeUrl('https://example.com')).toBe('https://example.com/');
    expect(extractSafeUrl('http://example.com')).toBe('http://example.com/');
    expect(extractSafeUrl('ftp://example.com')).toBeUndefined();
  });

  it('traverses values with cycle guards', () => {
    const obj: Record<string, unknown> = { a: 1 };
    obj.self = obj;
    let count = 0;
    traverseValue(obj, () => {
      count += 1;
    });
    expect(count).toBeGreaterThan(0);
  });
});
