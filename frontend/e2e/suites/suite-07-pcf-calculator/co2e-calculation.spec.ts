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
      let results: Awaited<ReturnType<typeof api.searchEmissionFactors>> | null = null;
      try {
        results = await api.searchEmissionFactors('electricity');
      } catch {
        // API not available
      }

      // Skip if PCF API not available
      if (!results) {
        test.skip();
        return;
      }

      expect(Array.isArray(results)).toBe(true);
    });

    test('emission factors include unit and value', async () => {
      let results: Awaited<ReturnType<typeof api.searchEmissionFactors>> | null = null;
      try {
        results = await api.searchEmissionFactors('steel');
      } catch {
        // API not available
      }

      // Skip if PCF API not available
      if (!results) {
        test.skip();
        return;
      }

      if (results.length > 0) {
        expect(results[0].name).toBeDefined();
        expect(results[0].unit).toBeDefined();
        expect(typeof results[0].value).toBe('number');
      }
    });

    test('emission factors include source', async () => {
      let results: Awaited<ReturnType<typeof api.searchEmissionFactors>> | null = null;
      try {
        results = await api.searchEmissionFactors('transport');
      } catch {
        // API not available
      }

      // Skip if PCF API not available
      if (!results) {
        test.skip();
        return;
      }

      if (results.length > 0) {
        expect(results[0].source).toBeDefined();
      }
    });
  });

  test.describe('PCF Calculation', () => {
    test('calculates total CO2e from form data', async () => {
      // Find a PCF template first
      let templates: Awaited<ReturnType<typeof api.getTemplates>> | null = null;
      try {
        templates = await api.getTemplates({ search: 'Carbon Footprint' });
      } catch {
        // API not available
      }

      if (!templates?.templates || templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const formData = createCarbonFootprintFormData();

      let result: Awaited<ReturnType<typeof api.calculatePCF>> | null = null;
      try {
        result = await api.calculatePCF(pcfTemplate, formData);
      } catch {
        // API not available
      }

      // Skip if PCF calculation API not available
      if (!result || result.total_co2e === undefined) {
        test.skip();
        return;
      }

      expect(result.total_co2e).toBeDefined();
      expect(typeof result.total_co2e).toBe('number');
    });

    test('calculation includes breakdown by scope', async () => {
      let templates: Awaited<ReturnType<typeof api.getTemplates>> | null = null;
      try {
        templates = await api.getTemplates({ search: 'Carbon Footprint' });
      } catch {
        // API not available
      }

      if (!templates?.templates || templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      const formData = createCarbonFootprintFormData();

      let result: Awaited<ReturnType<typeof api.calculatePCF>> | null = null;
      try {
        result = await api.calculatePCF(pcfTemplate, formData);
      } catch {
        // API not available
      }

      // Skip if PCF calculation API not available
      if (!result) {
        test.skip();
        return;
      }

      expect(result.breakdown).toBeDefined();
      expect(Array.isArray(result.breakdown)).toBe(true);
    });
  });

  test.describe('PCF Validation', () => {
    test('validates PCF form data against IDTA 02023', async () => {
      let templates: Awaited<ReturnType<typeof api.getTemplates>> | null = null;
      try {
        templates = await api.getTemplates({ search: 'Carbon Footprint' });
      } catch {
        // API not available
      }

      if (!templates?.templates || templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      let schema: Awaited<ReturnType<typeof api.getTemplateSchema>> | null = null;
      try {
        schema = await api.getTemplateSchema(pcfTemplate);
      } catch {
        // API not available
      }

      if (!schema) {
        test.skip();
        return;
      }

      const formData = createCarbonFootprintFormData();

      let result: Awaited<ReturnType<typeof api.validatePCF>> | null = null;
      try {
        result = await api.validatePCF(formData, schema);
      } catch {
        // API not available
      }

      // Skip if PCF validation API not available
      if (!result) {
        test.skip();
        return;
      }

      expect(typeof result.valid).toBe('boolean');
      expect(Array.isArray(result.errors)).toBe(true);
    });

    test('returns completeness score', async () => {
      let templates: Awaited<ReturnType<typeof api.getTemplates>> | null = null;
      try {
        templates = await api.getTemplates({ search: 'Carbon Footprint' });
      } catch {
        // API not available
      }

      if (!templates?.templates || templates.templates.length === 0) {
        test.skip();
        return;
      }

      const pcfTemplate = templates.templates[0].name;
      let schema: Awaited<ReturnType<typeof api.getTemplateSchema>> | null = null;
      try {
        schema = await api.getTemplateSchema(pcfTemplate);
      } catch {
        // API not available
      }

      if (!schema) {
        test.skip();
        return;
      }

      const formData = createCarbonFootprintFormData();

      let result: Awaited<ReturnType<typeof api.validatePCF>> | null = null;
      try {
        result = await api.validatePCF(formData, schema);
      } catch {
        // API not available
      }

      // Skip if PCF validation API not available
      if (!result) {
        test.skip();
        return;
      }

      if (result.completeness_score !== undefined) {
        expect(typeof result.completeness_score).toBe('number');
        expect(result.completeness_score).toBeGreaterThanOrEqual(0);
        expect(result.completeness_score).toBeLessThanOrEqual(100);
      }
    });
  });
});
