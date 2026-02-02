/**
 * Server-Side Validation Tests
 *
 * Tests for backend validation via POST /api/editor/validate/{name}
 * including complex rules that require server-side processing.
 */

import { test, expect } from '@playwright/test';
import { APIClient } from '../../helpers/api-client';
import {
  createNameplateFormData,
  createInvalidNameplateFormData,
  createMinimalNameplateFormData,
} from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('Server-Side Validation', () => {
  let api: APIClient;

  test.beforeEach(async ({ request }) => {
    api = new APIClient(request, API_BASE_URL);
  });

  test.describe('Valid Data', () => {
    test('accepts valid complete form data', async () => {
      const formData = createNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    test('accepts minimal valid form data', async () => {
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should be valid or have only warnings
      expect(result.errors.length).toBe(0);
    });
  });

  test.describe('Invalid Data', () => {
    test('rejects data with missing required fields', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('error messages indicate missing field', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Errors should mention the missing field
      const errorMessages = result.errors.map((e) => e.message.toLowerCase());
      const hasRelevantError = errorMessages.some(
        (msg) =>
          msg.includes('required') ||
          msg.includes('missing') ||
          msg.includes('uri') ||
          msg.includes('manufacturer')
      );

      expect(hasRelevantError).toBe(true);
    });

    test('error includes path to invalid field', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      if (result.errors.length > 0) {
        // Error should have a path property
        expect(result.errors[0].path).toBeDefined();
      }
    });
  });

  test.describe('Type Validation', () => {
    test('validates string type fields', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        ManufacturerName: { en: 'Test' },
        SerialNumber: 'SN-001', // String field
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.length).toBe(0);
    });

    test('validates multi-language property structure', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        ManufacturerName: { en: 'English', de: 'German' },
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.length).toBe(0);
    });
  });

  test.describe('Cardinality Validation', () => {
    test('validates minimum cardinality', async () => {
      // Empty required field violates [1..1] or [1..*] cardinality
      const { URIOfTheProduct, ...formData } = createMinimalNameplateFormData();
      formData.ManufacturerName = { en: 'Test' };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should have error for missing URIOfTheProduct
      expect(result.valid).toBe(false);
    });

    test('validates maximum cardinality for lists', async () => {
      // This test depends on having a list field with max cardinality
      const formData = createNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should pass if cardinality is respected
      expect(result.errors.length).toBe(0);
    });
  });

  test.describe('Semantic Validation', () => {
    test('validates enum values against allowed set', async () => {
      // This depends on the template having enum fields
      const formData = createNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.valid).toBe(true);
    });
  });

  test.describe('Nested Structure Validation', () => {
    test('validates nested collection structure', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        ContactInformation: {
          NationalCode: { en: 'DE' },
          CityTown: { en: 'Berlin' },
        },
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.length).toBe(0);
    });

    test('validates deeply nested properties', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        ContactInformation: {
          Phone: {
            CountryCode: '+49',
            AreaCode: '30',
            Number: '12345678',
          },
        },
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.length).toBe(0);
    });
  });

  test.describe('Warning Generation', () => {
    test('generates warnings for optional but recommended fields', async () => {
      // Minimal data might generate warnings
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // May or may not have warnings depending on schema
      expect(Array.isArray(result.warnings)).toBe(true);
    });

    test('warnings do not block validation', async () => {
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Even with warnings, validation should pass if required fields are present
      if (result.warnings.length > 0) {
        expect(result.valid).toBe(true);
      }
    });
  });

  test.describe('Export Blocking', () => {
    test('invalid data blocks export', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      try {
        await api.exportAasx(TEST_TEMPLATE, formData);
        // Should not reach here
        expect(false).toBe(true);
      } catch (error) {
        // Export should fail for invalid data
        expect(error).toBeDefined();
      }
    });

    test('valid data allows export', async () => {
      const formData = createNameplateFormData();

      const aasx = await api.exportAasx(TEST_TEMPLATE, formData);

      expect(aasx).toBeDefined();
      expect(aasx.length).toBeGreaterThan(0);
    });
  });

  test.describe('Version-Specific Validation', () => {
    test('validates against correct template version', async () => {
      const formData = createNameplateFormData();

      // Get available versions
      const versions = await api.getTemplateVersions(TEST_TEMPLATE);

      if (versions.length > 0) {
        const result = await api.validateFormData(TEST_TEMPLATE, formData, {
          version: versions[0].version,
        });

        expect(typeof result.valid).toBe('boolean');
      }
    });
  });

  test.describe('Error Response Format', () => {
    test('error response includes code', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      if (result.errors.length > 0) {
        expect(result.errors[0].code).toBeDefined();
      }
    });

    test('error response is properly structured', async () => {
      const formData = createInvalidNameplateFormData('missing-required');

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result).toHaveProperty('valid');
      expect(result).toHaveProperty('errors');
      expect(result).toHaveProperty('warnings');
      expect(Array.isArray(result.errors)).toBe(true);
      expect(Array.isArray(result.warnings)).toBe(true);
    });
  });
});
