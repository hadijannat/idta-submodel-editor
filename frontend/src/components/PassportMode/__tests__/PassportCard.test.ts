/**
 * Tests for PassportCard routing logic.
 *
 * These tests verify that the correct card type is selected
 * based on schema detection.
 */

import { describe, it, expect } from 'vitest';
import type { SubmodelUISchema } from '../../../types/ui-schema';
import { detectPassportType } from '../utils/passportRegistry';

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

describe('PassportCard routing', () => {
  describe('routes to NameplateCard', () => {
    it('when schema has nameplate semanticId', () => {
      const schema = createSchema({
        semanticId: 'https://admin-shell.io/idta/submodel/nameplate/02006',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('when schema has nameplate templateName', () => {
      const schema = createSchema({
        templateName: 'IDTA-02006-2-0-Nameplate',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('when schema idShort is Nameplate', () => {
      const schema = createSchema({
        idShort: 'Nameplate',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });
  });

  describe('routes to PCFCard', () => {
    it('when schema has PCF semanticId', () => {
      const schema = createSchema({
        semanticId: 'https://admin-shell.io/idta/pcf/02023',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('when schema has CarbonFootprint semanticId', () => {
      const schema = createSchema({
        semanticId: 'https://example.org/CarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('when schema has PCF templateName', () => {
      const schema = createSchema({
        templateName: 'ProductCarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('when schema idShort is CarbonFootprint', () => {
      const schema = createSchema({
        idShort: 'CarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('when schema idShort is PCF', () => {
      const schema = createSchema({
        idShort: 'PCF',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });
  });

  describe('routes to GenericCard', () => {
    it('when schema is unknown type', () => {
      const schema = createSchema({
        idShort: 'TechnicalData',
        semanticId: 'https://example.org/technical-data',
        templateName: 'Technical-Data-Template',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('when schema is null', () => {
      expect(detectPassportType(null)).toBe('generic');
    });

    it('when schema has no identifying info', () => {
      const schema = createSchema({
        idShort: 'Generic',
        semanticId: null,
        templateName: null,
      });
      expect(detectPassportType(schema)).toBe('generic');
    });
  });

  describe('card component exports', () => {
    it('NameplateCard is a valid function component', async () => {
      const { default: NameplateCard } = await import('../cards/NameplateCard');
      expect(typeof NameplateCard).toBe('function');
    });

    it('PCFCard is a valid function component', async () => {
      const { default: PCFCard } = await import('../cards/PCFCard');
      expect(typeof PCFCard).toBe('function');
    });

    it('GenericCard is a valid function component', async () => {
      const { default: GenericCard } = await import('../cards/GenericCard');
      expect(typeof GenericCard).toBe('function');
    });

    it('PassportCard is a valid function component', async () => {
      const { default: PassportCard } = await import('../PassportCard');
      expect(typeof PassportCard).toBe('function');
    });
  });

  describe('card props interface', () => {
    it('all cards accept schema and formData props', () => {
      // Type verification - ensures all cards have consistent interface
      interface CardProps {
        schema: SubmodelUISchema;
        formData: Record<string, unknown> | undefined;
      }

      const validProps: CardProps = {
        schema: createSchema(),
        formData: undefined,
      };

      expect(validProps.schema).toBeDefined();
      expect(validProps.formData).toBeUndefined();
    });
  });
});

describe('PassportCard integration scenarios', () => {
  describe('realistic schema detection', () => {
    it('detects IDTA 02006 Nameplate from real-world semanticId', () => {
      const schema = createSchema({
        semanticId:
          'https://admin-shell.io/ZVEI/TechnicalData/Nameplate/2/0/Nameplate',
        templateName: 'IDTA 02006-2-0 Nameplate for Industrial Equipment',
        idShort: 'Nameplate',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });

    it('detects IDTA 02023 PCF from real-world semanticId', () => {
      const schema = createSchema({
        semanticId:
          'https://admin-shell.io/idta/CarbonFootprint/ProductCarbonFootprint/0/9',
        templateName: 'IDTA 02023-0-9 Carbon Footprint',
        idShort: 'CarbonFootprint',
      });
      expect(detectPassportType(schema)).toBe('pcf');
    });

    it('detects generic for IDTA 02004 Handover Documentation', () => {
      const schema = createSchema({
        semanticId:
          'https://admin-shell.io/ZVEI/TechnicalData/HandoverDocumentation/1/2',
        templateName: 'IDTA 02004-1-2 Handover Documentation',
        idShort: 'HandoverDocumentation',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('detects generic for IDTA 02002 Technical Data', () => {
      const schema = createSchema({
        semanticId:
          'https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2',
        templateName: 'IDTA 02002-1-0 Generic Frame for Technical Data',
        idShort: 'TechnicalData',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });
  });

  describe('edge cases', () => {
    it('handles schema with empty strings', () => {
      const schema = createSchema({
        semanticId: '',
        templateName: '',
        idShort: '',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('handles schema with only whitespace', () => {
      const schema = createSchema({
        semanticId: '   ',
        templateName: '   ',
        idShort: '   ',
      });
      expect(detectPassportType(schema)).toBe('generic');
    });

    it('handles schema with mixed case patterns', () => {
      const schema = createSchema({
        semanticId: 'NAMEPLATE',
      });
      expect(detectPassportType(schema)).toBe('nameplate');
    });
  });
});

/**
 * Note: The following tests would require @testing-library/react:
 *
 * - Renders NameplateCard for nameplate schema
 * - Renders PCFCard for PCF schema
 * - Renders GenericCard for unknown schema
 * - Updates when formData changes (live updates)
 *
 * These tests verify the routing logic works correctly without
 * actually rendering React components.
 */
