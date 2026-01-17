/**
 * Tests for passport registry detection utilities.
 */

import { describe, it, expect } from 'vitest';
import type { SubmodelUISchema } from '../../../../types/ui-schema';
import { detectPassportType, getCardTypeLabel } from '../passportRegistry';

/**
 * Helper to create a minimal schema for testing.
 */
const createSchema = (
  overrides: Partial<SubmodelUISchema> = {}
): SubmodelUISchema => ({
  submodelId: 'urn:example',
  idShort: 'Test',
  semanticId: null,
  description: null,
  administration: null,
  elements: [],
  supplementaryFiles: [],
  ...overrides,
});

describe('detectPassportType', () => {
  describe('nameplate detection', () => {
    it('returns nameplate for semanticId containing "02006"', () => {
      const schema = createSchema({
        semanticId: 'https://admin-shell.io/idta/submodel/nameplate/02006',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('returns nameplate for semanticId containing "nameplate"', () => {
      const schema = createSchema({
        semanticId: 'https://example.org/nameplate/v1',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('returns nameplate for ECLASS semantic ID', () => {
      const schema = createSchema({
        semanticId: '0173-1#01-AGZ672#001',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('returns nameplate for templateName containing "nameplate"', () => {
      const schema = createSchema({
        templateName: 'IDTA-02006-Nameplate',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('returns nameplate for templateName containing "02006"', () => {
      const schema = createSchema({
        templateName: 'IDTA-02006',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('returns nameplate for idShort "Nameplate"', () => {
      const schema = createSchema({
        idShort: 'Nameplate',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('is case-insensitive for nameplate detection', () => {
      const schema1 = createSchema({ semanticId: 'NAMEPLATE' });
      const schema2 = createSchema({ templateName: 'NamePlate' });
      expect(detectPassportType(schema1)).toBe('nameplate');
      expect(detectPassportType(schema2)).toBe('nameplate');
    });
  });

  describe('pcf detection', () => {
    it('returns pcf for semanticId containing "02023"', () => {
      const schema = createSchema({
        semanticId: 'https://admin-shell.io/idta/submodel/pcf/02023',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for semanticId containing "CarbonFootprint"', () => {
      const schema = createSchema({
        semanticId: 'https://example.org/CarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for semanticId containing "ProductCarbonFootprint"', () => {
      const schema = createSchema({
        semanticId: 'urn:ProductCarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for ECLASS PCF semantic ID', () => {
      const schema = createSchema({
        semanticId: '0173-1#01-AHE712#001',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for semanticId containing "PCF"', () => {
      const schema = createSchema({
        semanticId: 'https://example.org/PCF',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for templateName containing "carbon"', () => {
      const schema = createSchema({
        templateName: 'Product-Carbon-Footprint',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for templateName containing "footprint"', () => {
      const schema = createSchema({
        templateName: 'CarbonFootprint-Template',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for templateName containing "pcf"', () => {
      const schema = createSchema({
        templateName: 'PCF-Template',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for templateName containing "02023"', () => {
      const schema = createSchema({
        templateName: 'IDTA-02023',
        semanticId: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for idShort "CarbonFootprint"', () => {
      const schema = createSchema({
        idShort: 'CarbonFootprint',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for idShort "ProductCarbonFootprint"', () => {
      const schema = createSchema({
        idShort: 'ProductCarbonFootprint',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('returns pcf for idShort "PCF"', () => {
      const schema = createSchema({
        idShort: 'PCF',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('is case-insensitive for pcf detection', () => {
      const schema1 = createSchema({ semanticId: 'carbonfootprint' });
      const schema2 = createSchema({ templateName: 'CARBON' });
      expect(detectPassportType(schema1)).toBe('pcf');
      expect(detectPassportType(schema2)).toBe('pcf');
    });
  });

  describe('generic fallback', () => {
    it('returns generic for unknown schemas', () => {
      const schema = createSchema({
        idShort: 'SomeOtherSubmodel',
        semanticId: 'https://example.org/other',
        templateName: 'Other-Template',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('returns generic for null schema', () => {
      expect(detectPassportType(null)).toBe('generic');
    });

    it('returns generic for schema with no identifying info', () => {
      const schema = createSchema({
        idShort: 'Test',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('returns generic when semanticId, templateName, and idShort are empty strings', () => {
      const schema = createSchema({
        idShort: '',
        semanticId: '',
        templateName: '',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });
  });

  describe('detection priority', () => {
    it('semanticId takes priority over templateName', () => {
      const schema = createSchema({
        semanticId: 'https://example.org/02006', // nameplate
        templateName: 'PCF-Template', // pcf
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('templateName takes priority over idShort', () => {
      const schema = createSchema({
        semanticId: null,
        templateName: 'nameplate-template', // nameplate
        idShort: 'CarbonFootprint', // pcf
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('uses submodelId when semanticId is missing', () => {
      const schema = createSchema({
        semanticId: null,
        submodelId: 'https://admin-shell.io/idta/SubmodelTemplate/CarbonFootprint/0/9',
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });
  });
});

describe('getCardTypeLabel', () => {
  it('returns "Digital Nameplate" for nameplate type', () => {
    expect(getCardTypeLabel('nameplate')).toBe('Digital Nameplate');
  });

  it('returns "Product Carbon Footprint" for pcf type', () => {
    expect(getCardTypeLabel('pcf')).toBe('Product Carbon Footprint');
  });

  it('returns "Digital Passport" for generic type', () => {
    expect(getCardTypeLabel('generic')).toBe('Digital Passport');
  });
});
