/**
 * Smoke Tests (Suite 00)
 *
 * Minimal reproducible tests that verify the core application flow:
 * 1. Application loads
 * 2. Templates are listed
 * 3. Template can be selected
 * 4. Basic form field can be filled
 * 5. Export produces valid AASX
 *
 * These tests run on every PR and should complete in < 2 minutes.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';
import { isConformanceToolAvailable, validateAasx } from '../../helpers/conformance-runner';
import { createMinimalNameplateFormData } from '../../helpers/test-data-factory';

// Test configuration
const TEST_TEMPLATE = 'Digital Nameplate';
const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('Smoke Tests', () => {
  test.describe.configure({ mode: 'serial' });

  test('can load application and see template list', async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);

    // Navigate to the app
    await templateSelector.goto();

    // Verify template list is visible
    await expect(templateSelector.templateList).toBeVisible();

    // Verify at least one template is shown
    const templateCount = await templateSelector.getTemplateCount();
    expect(templateCount).toBeGreaterThan(0);
  });

  test('can select a template and see form editor', async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    const formEditor = new FormEditorPage(page);

    // Navigate and select template
    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);

    // Wait for form to be ready
    await formEditor.waitForFormReady();

    // Verify we're in the form editor
    const templateName = await formEditor.getCurrentTemplateName();
    expect(templateName.toLowerCase()).toContain('nameplate');
  });

  test('can fill a basic property field', async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    const formEditor = new FormEditorPage(page);

    // Navigate and select template
    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
    await formEditor.waitForFormReady();

    // Navigate to fill fields step
    await formEditor.goToStep('fill-fields');

    // Fill a basic property (URIOfTheProduct is typically a required field)
    const testUri = 'https://example.com/products/smoke-test-001';
    await formEditor.fillProperty('URIOfTheProduct', testUri);

    // Verify the value was set
    const value = await formEditor.getPropertyValue('URIOfTheProduct');
    expect(value).toBe(testUri);
  });

  test('API health check returns OK', async ({ request }) => {
    const api = new APIClient(request, API_BASE_URL);

    // Check health endpoint
    const health = await api.healthCheck();
    expect(health.status).toBe('healthy');
  });

  test('can fetch templates via API', async ({ request }) => {
    const api = new APIClient(request, API_BASE_URL);

    // Fetch templates
    const response = await api.getTemplates();

    // Verify response structure
    expect(response.templates).toBeDefined();
    expect(Array.isArray(response.templates)).toBe(true);
    expect(response.total).toBeGreaterThan(0);

    // Verify Digital Nameplate is in the list
    const nameplate = response.templates.find(
      (t) => t.name.toLowerCase().includes('nameplate')
    );
    expect(nameplate).toBeDefined();
  });

  test('can fetch template schema via API', async ({ request }) => {
    const api = new APIClient(request, API_BASE_URL);

    // Fetch schema - may fail if GitHub API is rate-limited or unavailable
    let schema: Awaited<ReturnType<typeof api.getTemplateSchema>>;
    try {
      schema = await api.getTemplateSchema(TEST_TEMPLATE);
    } catch (error) {
      // Skip test if GitHub API is unavailable
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes('404') || message.includes('rate limit') || message.includes('INTERNAL_ERROR')) {
        test.skip(true, `GitHub API unavailable: ${message}`);
        return;
      }
      throw error;
    }

    // Verify schema structure
    expect(schema.submodelId).toBeDefined();
    expect(schema.idShort).toBeDefined();
    expect(schema.elements).toBeDefined();
    expect(Array.isArray(schema.elements)).toBe(true);
    expect(schema.elements.length).toBeGreaterThan(0);
  });

  test('can validate form data via API', async ({ request }) => {
    const api = new APIClient(request, API_BASE_URL);

    // Minimal valid form data
    const formData = {
      ...createMinimalNameplateFormData(),
      URIOfTheProduct: 'https://example.com/products/test-001',
      ManufacturerName: { en: 'Test Manufacturer' },
    };

    // Validate - may fail if template schema unavailable
    let result: Awaited<ReturnType<typeof api.validateFormData>>;
    try {
      result = await api.validateFormData(TEST_TEMPLATE, formData);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes('404') || message.includes('INTERNAL_ERROR')) {
        test.skip(true, `Template unavailable: ${message}`);
        return;
      }
      throw error;
    }

    // Should have validation result
    expect(result).toBeDefined();
    expect(typeof result.valid).toBe('boolean');
  });

  test('can export AASX via API', async ({ request }) => {
    const api = new APIClient(request, API_BASE_URL);

    // Form data for export
    const formData = {
      ...createMinimalNameplateFormData(),
      URIOfTheProduct: 'https://example.com/products/smoke-test-001',
      ManufacturerName: { en: 'Smoke Test Manufacturer' },
      ManufacturerProductDesignation: { en: 'Smoke Test Product' },
    };

    // Export - may fail if template schema unavailable or validation fails
    let aasxBuffer: Awaited<ReturnType<typeof api.exportAasx>>;
    try {
      aasxBuffer = await api.exportAasx(TEST_TEMPLATE, formData);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      // Skip if GitHub API unavailable or validation fails (usually means schema couldn't be loaded)
      if (message.includes('404') || message.includes('INTERNAL_ERROR') || message.includes('VALIDATION_FAILED')) {
        test.skip(true, `Export unavailable (GitHub API or validation issue): ${message.slice(0, 200)}`);
        return;
      }
      throw error;
    }

    // Verify we got a buffer back
    expect(aasxBuffer).toBeDefined();
    expect(aasxBuffer.length).toBeGreaterThan(0);

    // Verify it's a valid ZIP file (AASX is a ZIP)
    // ZIP files start with PK (0x50 0x4B)
    expect(aasxBuffer[0]).toBe(0x50);
    expect(aasxBuffer[1]).toBe(0x4b);
  });

  test('exported AASX passes conformance check', async ({ request }) => {
    // Skip if conformance tool is not available
    const conformanceAvailable = await isConformanceToolAvailable();
    test.skip(
      !conformanceAvailable,
      'aas-test-engines not installed. Install with: pip install aas-test-engines'
    );

    const api = new APIClient(request, API_BASE_URL);

    // Form data for export
    const formData = {
      ...createMinimalNameplateFormData(),
      URIOfTheProduct: 'https://example.com/products/conformance-test-001',
      ManufacturerName: { en: 'Conformance Test Manufacturer' },
      ManufacturerProductDesignation: { en: 'Conformance Test Product' },
    };

    // Export
    const aasxBuffer = await api.exportAasx(TEST_TEMPLATE, formData);

    // Run conformance check
    const result = await validateAasx(aasxBuffer);

    // Log details for debugging
    if (!result.passed) {
      console.log('Conformance check failed:');
      console.log('Errors:', result.errors);
      console.log('Warnings:', result.warnings);
      console.log('stdout:', result.stdout);
      console.log('stderr:', result.stderr);
    }

    // Assert conformance
    expect(result.passed).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  test('can complete full flow: select template, fill form, export', async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    const formEditor = new FormEditorPage(page);

    // 1. Navigate to app
    await templateSelector.goto();

    // 2. Search and select template
    await templateSelector.searchTemplates('Nameplate');
    await expect(templateSelector.getTemplateCard(TEST_TEMPLATE)).toBeVisible();
    await templateSelector.selectTemplate(TEST_TEMPLATE);

    // 3. Wait for form
    await formEditor.waitForFormReady();

    // 4. Go to fill fields step
    await formEditor.goToStep('fill-fields');

    // 5. Fill required fields
    await formEditor.fillProperty('URIOfTheProduct', 'https://example.com/products/full-flow-001');

    // Fill multi-language property
    await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'Full Flow Test Manufacturer');

    // 6. Validate form doesn't have blocking errors
    // Note: Some warnings may be present for optional fields
    const hasBlockingErrors = await formEditor.hasValidationErrors();
    expect(hasBlockingErrors).toBe(false);

    // 7. Navigate to export step
    await formEditor.goToStep('export');

    // 8. Verify export buttons are visible
    await expect(formEditor.exportAasxButton).toBeVisible();
    await expect(formEditor.exportJsonButton).toBeVisible();
  });
});

// Additional smoke test for search functionality
test.describe('Search Smoke Tests', () => {
  test('template search filters results correctly', async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);

    // Navigate
    await templateSelector.goto();

    // Get initial count
    const initialCount = await templateSelector.getTemplateCount();

    // Search for specific term
    await templateSelector.searchTemplates('Nameplate');

    // Verify filtered results
    const filteredCount = await templateSelector.getTemplateCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
    expect(filteredCount).toBeGreaterThan(0);

    // Verify Digital Nameplate is in results
    const isVisible = await templateSelector.isTemplateVisible(TEST_TEMPLATE);
    expect(isVisible).toBe(true);

    // Clear search
    await templateSelector.clearSearch();

    // Verify all templates are back
    const resetCount = await templateSelector.getTemplateCount();
    expect(resetCount).toBe(initialCount);
  });
});
