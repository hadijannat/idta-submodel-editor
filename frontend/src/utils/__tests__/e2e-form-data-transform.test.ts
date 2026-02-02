/**
 * Unit tests for E2E API client transformation functions.
 *
 * Tests the toSubmodelFormData() and toElementFormData() functions that
 * transform simplified test data into the format expected by the backend API.
 * These functions are used in E2E tests at frontend/e2e/helpers/api-client.ts
 */

import { describe, it, expect } from 'vitest';
import {
  isPlainObject,
  isLanguageMap,
  looksLikeElementFormData,
  toElementFormData,
  toSubmodelFormData,
} from '../../../e2e/helpers/api-client';

describe('E2E API Client: isPlainObject', () => {
  it('returns true for plain objects', () => {
    expect(isPlainObject({})).toBe(true);
    expect(isPlainObject({ a: 1 })).toBe(true);
  });

  it('returns false for arrays', () => {
    expect(isPlainObject([])).toBe(false);
    expect(isPlainObject([1, 2, 3])).toBe(false);
  });

  it('returns false for null and primitives', () => {
    expect(isPlainObject(null)).toBe(false);
    expect(isPlainObject(undefined)).toBe(false);
    expect(isPlainObject('string')).toBe(false);
    expect(isPlainObject(123)).toBe(false);
    expect(isPlainObject(true)).toBe(false);
  });
});

describe('E2E API Client: isLanguageMap', () => {
  it('returns true for valid language maps', () => {
    expect(isLanguageMap({ en: 'Hello' })).toBe(true);
    expect(isLanguageMap({ en: 'Hello', de: 'Hallo' })).toBe(true);
    expect(isLanguageMap({ en: 'Hello', de: 'Hallo', fr: 'Bonjour' })).toBe(true);
  });

  it('returns false for empty objects', () => {
    expect(isLanguageMap({})).toBe(false);
  });

  it('returns false for objects with non-language keys', () => {
    expect(isLanguageMap({ foo: 'bar' })).toBe(false);
    expect(isLanguageMap({ en: 'Hello', foo: 'bar' })).toBe(false);
  });

  it('returns false for objects with non-string values', () => {
    expect(isLanguageMap({ en: 123 })).toBe(false);
    expect(isLanguageMap({ en: { nested: 'value' } })).toBe(false);
  });

  it('allows null and undefined values', () => {
    expect(isLanguageMap({ en: null })).toBe(true);
    expect(isLanguageMap({ en: undefined })).toBe(true);
  });
});

describe('E2E API Client: looksLikeElementFormData', () => {
  it('returns true for objects with ElementFormData keys', () => {
    expect(looksLikeElementFormData({ value: 'test' })).toBe(true);
    expect(looksLikeElementFormData({ elements: {} })).toBe(true);
    expect(looksLikeElementFormData({ items: [] })).toBe(true);
    expect(looksLikeElementFormData({ semanticId: 'urn:example' })).toBe(true);
  });

  it('returns false for objects without ElementFormData keys', () => {
    expect(looksLikeElementFormData({})).toBe(false);
    expect(looksLikeElementFormData({ foo: 'bar' })).toBe(false);
    expect(looksLikeElementFormData({ en: 'Hello', de: 'Hallo' })).toBe(false);
  });
});

describe('E2E API Client: toElementFormData', () => {
  it('transforms null/undefined to empty object', () => {
    expect(toElementFormData(null)).toEqual({});
    expect(toElementFormData(undefined)).toEqual({});
  });

  it('transforms primitive values to { value }', () => {
    expect(toElementFormData('https://example.com')).toEqual({
      value: 'https://example.com',
    });
    expect(toElementFormData(42)).toEqual({ value: 42 });
    expect(toElementFormData(true)).toEqual({ value: true });
  });

  it('transforms arrays to { items }', () => {
    expect(toElementFormData(['a', 'b'])).toEqual({
      items: [{ value: 'a' }, { value: 'b' }],
    });
  });

  it('preserves objects that already look like ElementFormData', () => {
    const existing = { value: 'test', semanticId: 'urn:example' };
    expect(toElementFormData(existing)).toEqual(existing);
  });

  it('transforms language maps to { value: languageMap }', () => {
    const langMap = { en: 'Hello', de: 'Hallo' };
    expect(toElementFormData(langMap)).toEqual({ value: langMap });
  });

  it('transforms empty objects to { elements: {} }', () => {
    expect(toElementFormData({})).toEqual({ elements: {} });
  });

  it('transforms nested objects to { elements }', () => {
    const input = {
      NationalCode: { en: 'DE' },
      CityTown: { en: 'Munich' },
    };
    expect(toElementFormData(input)).toEqual({
      elements: {
        NationalCode: { value: { en: 'DE' } },
        CityTown: { value: { en: 'Munich' } },
      },
    });
  });

  it('handles deeply nested structures', () => {
    const input = {
      ContactInformation: {
        NationalCode: { en: 'DE' },
        Street: { en: 'Main St' },
      },
    };
    expect(toElementFormData(input)).toEqual({
      elements: {
        ContactInformation: {
          elements: {
            NationalCode: { value: { en: 'DE' } },
            Street: { value: { en: 'Main St' } },
          },
        },
      },
    });
  });
});

describe('E2E API Client: toSubmodelFormData', () => {
  it('transforms simple form data correctly', () => {
    const input = { URIOfTheProduct: 'https://example.com' };
    const result = toSubmodelFormData(input);
    expect(result).toEqual({
      elements: {
        URIOfTheProduct: { value: 'https://example.com' },
      },
    });
  });

  it('transforms language maps correctly', () => {
    const input = { ManufacturerName: { en: 'Test', de: 'Test DE' } };
    const result = toSubmodelFormData(input);
    expect(result).toEqual({
      elements: {
        ManufacturerName: { value: { en: 'Test', de: 'Test DE' } },
      },
    });
  });

  it('transforms empty collections correctly', () => {
    const input = { AddressInformation: {} };
    const result = toSubmodelFormData(input);
    expect(result).toEqual({
      elements: {
        AddressInformation: { elements: {} },
      },
    });
  });

  it('transforms nested objects correctly', () => {
    const input = {
      ContactInformation: {
        NationalCode: { en: 'DE' },
      },
    };
    const result = toSubmodelFormData(input);
    expect(result).toEqual({
      elements: {
        ContactInformation: {
          elements: {
            NationalCode: { value: { en: 'DE' } },
          },
        },
      },
    });
  });

  it('preserves data already in SubmodelFormData format', () => {
    const existing = {
      elements: {
        URIOfTheProduct: { value: 'https://example.com' },
      },
    };
    const result = toSubmodelFormData(existing);
    expect(result).toBe(existing);
  });

  it('transforms complex Digital Nameplate data', () => {
    const input = {
      URIOfTheProduct: 'https://example.com/product/001',
      ManufacturerName: { en: 'ACME Corp', de: 'ACME GmbH' },
      ManufacturerProductDesignation: { en: 'Widget Pro' },
      AddressInformation: {},
      OrderCodeOfManufacturer: 'WIDGET-001',
    };

    const result = toSubmodelFormData(input);

    expect(result.elements.URIOfTheProduct).toEqual({
      value: 'https://example.com/product/001',
    });
    expect(result.elements.ManufacturerName).toEqual({
      value: { en: 'ACME Corp', de: 'ACME GmbH' },
    });
    expect(result.elements.ManufacturerProductDesignation).toEqual({
      value: { en: 'Widget Pro' },
    });
    expect(result.elements.AddressInformation).toEqual({ elements: {} });
    expect(result.elements.OrderCodeOfManufacturer).toEqual({
      value: 'WIDGET-001',
    });
  });

  it('handles array items', () => {
    const input = {
      Markings: [
        { MarkingName: 'CE' },
        { MarkingName: 'UL' },
      ],
    };
    const result = toSubmodelFormData(input);
    expect(result.elements.Markings).toEqual({
      items: [
        { elements: { MarkingName: { value: 'CE' } } },
        { elements: { MarkingName: { value: 'UL' } } },
      ],
    });
  });

  it('handles null and undefined form data gracefully', () => {
    expect(toSubmodelFormData(null as unknown as Record<string, unknown>)).toEqual({
      elements: {},
    });
    expect(toSubmodelFormData(undefined as unknown as Record<string, unknown>)).toEqual({
      elements: {},
    });
  });
});
