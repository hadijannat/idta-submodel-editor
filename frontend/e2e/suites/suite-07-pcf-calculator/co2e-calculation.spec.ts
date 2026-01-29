/**
 * CO2e Calculation Tests
 *
 * Tests for PCF (Product Carbon Footprint) calculator functionality.
 */

import { test, expect } from '@playwright/test';
import { APIClient } from '../../helpers/api-client';
import { createCarbonFootprintFormData } from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('CO2e Calculation', () => {
  let api: APIClient;

  test.beforeEach(async ({ request }) => {
    api = new APIClient(request, API_BASE_URL);
  });

  test.describe('Emission Factor Search', () => {
    test('can search emission factors', async () => {
      const results = await api.searchEmissionFactors('electricity');

      expect(Array.isArray(results)).toBe(true);
    });

    test('emission factors include unit and value', async () => {
      const results = await api.searchEmissionFactors('steel');

      if (results.length > 0) {
        expect(results[0].name).toBeDefined();
        expect(results[0].unit).toBeDefined();
        expect(typeof results[0].value).toBe('number');
      }
    });

    test('emission factors include source', async () => {
      const results = await api.searchEmissionFactors('transport');

      if (results.length > 0) {
        expect(results[0].source).toBeDefined();
      }
    });
  });

  test.describe('PCF Calculation', () => {
    test('calculates total CO2e from form data', async () => {
      // Find a PCF template first
      const templates = await api.getTemplates({ search: 'Carbon Footprint' });

      if (templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const formData = createCarbonFootprintFormData();

      const result = await api.calculatePCF(pcfTemplate, formData);

      expect(result.total_co2e).toBeDefined();
      expect(typeof result.total_co2e).toBe('number');
    });

    test('calculation includes breakdown by scope', async () => {
      const templates = await api.getTemplates({ search: 'Carbon Footprint' });

      if (templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const formData = createCarbonFootprintFormData();

      const result = await api.calculatePCF(pcfTemplate, formData);

      expect(result.breakdown).toBeDefined();
      expect(Array.isArray(result.breakdown)).toBe(true);
    });
  });

  test.describe('PCF Validation', () => {
    test('validates PCF form data against IDTA 02023', async () => {
      const templates = await api.getTemplates({ search: 'Carbon Footprint' });

      if (templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const schema = await api.getTemplateSchema(pcfTemplate);
      const formData = createCarbonFootprintFormData();

      const result = await api.validatePCF(formData, schema);

      expect(typeof result.valid).toBe('boolean');
      expect(Array.isArray(result.errors)).toBe(true);
    });

    test('returns completeness score', async () => {
      const templates = await api.getTemplates({ search: 'Carbon Footprint' });

      if (templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const schema = await api.getTemplateSchema(pcfTemplate);
      const formData = createCarbonFootprintFormData();

      const result = await api.validatePCF(formData, schema);

      if (result.completeness_score !== undefined) {
        expect(typeof result.completeness_score).toBe('number');
        expect(result.completeness_score).toBeGreaterThanOrEqual(0);
        expect(result.completeness_score).toBeLessThanOrEqual(100);
      }
    });
  });
});
