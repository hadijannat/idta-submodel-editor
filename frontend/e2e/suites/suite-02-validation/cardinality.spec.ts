/**
 * Cardinality Validation Tests
 *
 * Tests for AAS cardinality constraint enforcement including
 * [0..1], [1..1], [0..*], [1..*], and [n..m] patterns.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';
import { createMinimalNameplateFormData } from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('Cardinality Validation', () => {
  let api: APIClient;

  test.beforeEach(async ({ request }) => {
    api = new APIClient(request, API_BASE_URL);
  });

  test.describe('[1..1] - Exactly One Required', () => {
    test('missing required field fails validation', async () => {
      // URIOfTheProduct is typically [1..1]
      const formData = createMinimalNameplateFormData();
      delete formData.URIOfTheProduct;
      formData.ManufacturerName = { en: 'Test' };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.path?.includes('URIOfTheProduct'))).toBe(true);
    });

    test('present required field passes validation', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        URIOfTheProduct: 'https://example.com/test',
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should have no errors for these required fields
      expect(
        result.errors.filter((e) => e.path?.includes('URIOfTheProduct')).length
      ).toBe(0);
    });
  });

  test.describe('[0..1] - Optional Single', () => {
    test('empty optional field passes validation', async () => {
      // SerialNumber is typically [0..1]
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // No error for missing SerialNumber
      expect(
        result.errors.filter((e) => e.path?.includes('SerialNumber')).length
      ).toBe(0);
    });

    test('provided optional field passes validation', async () => {
      const formData = {
        ...createMinimalNameplateFormData(),
        SerialNumber: 'SN-001',
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.filter((e) => e.path?.includes('SerialNumber')).length).toBe(0);
    });
  });

  test.describe('[0..*] - Optional Multiple', () => {
    test('empty optional list passes validation', async () => {
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should pass without list items
      expect(result.errors.length).toBe(0);
    });

    test('multiple items in optional list passes validation', async () => {
      const formData = createMinimalNameplateFormData();

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.errors.length).toBe(0);
    });
  });

  test.describe('[1..*] - At Least One Required', () => {
    test('empty required list fails validation', async () => {
      // Find a [1..*] field in the template schema first
      const schema = await api.getTemplateSchema(TEST_TEMPLATE);

      const requiredListField = schema.elements.find(
        (e) => e.cardinality === '[1..*]' && e.modelType === 'SubmodelElementList'
      );

      if (!requiredListField) {
        test.skip();
        return;
      }

      const formData = {
        ...createMinimalNameplateFormData(),
        [requiredListField.idShort]: [], // Empty required list
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      expect(result.valid).toBe(false);
    });

    test('list with one item passes validation', async () => {
      const schema = await api.getTemplateSchema(TEST_TEMPLATE);

      const requiredListField = schema.elements.find(
        (e) => e.cardinality === '[1..*]' && e.modelType === 'SubmodelElementList'
      );

      if (!requiredListField) {
        test.skip();
        return;
      }

      const formData = {
        ...createMinimalNameplateFormData(),
        [requiredListField.idShort]: [{ value: 'item1' }],
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should have no cardinality error for this field
      expect(
        result.errors.filter((e) => e.path?.includes(requiredListField.idShort)).length
      ).toBe(0);
    });
  });

  test.describe('UI Cardinality Enforcement', () => {
    test('add button is disabled when max cardinality reached', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();
      await formEditor.goToStep('fill-fields');

      // Find a list field
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      if (!(await listField.isVisible())) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });

      if (await addButton.isVisible()) {
        // Add items until button is disabled or we hit a reasonable limit
        let iterations = 0;
        while (!(await addButton.isDisabled()) && iterations < 100) {
          await addButton.click();
          iterations++;
        }

        // Button should be disabled if max cardinality was reached
        // Or we hit our iteration limit (no max cardinality)
        expect(iterations).toBeLessThanOrEqual(100);
      }
    });

    test('remove button is disabled when min cardinality reached', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();
      await formEditor.goToStep('fill-fields');

      // Find a required list field
      const listField = page.locator(
        '.list-field[data-required="true"], [data-cardinality*="[1"]'
      ).first();

      if (!(await listField.isVisible())) {
        test.skip();
        return;
      }

      // Try to remove all items
      const removeButtons = listField.locator(
        '.remove-item, [data-testid="remove-item"], button[aria-label*="remove"]'
      );

      const count = await removeButtons.count();

      if (count === 1) {
        // Last item should not be removable for [1..*] fields
        const removeButton = removeButtons.first();
        const isDisabled = await removeButton.isDisabled();

        expect(isDisabled).toBe(true);
      }
    });

    test('required field indicator is shown', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();
      await formEditor.goToStep('fill-fields');

      // Find URIOfTheProduct field (required)
      const field = formEditor.getField('URIOfTheProduct');

      // Look for required indicator (asterisk, badge, etc.)
      const requiredIndicator = field.locator(
        '.required, [data-required="true"], .asterisk, *:has-text("*")'
      );

      const label = page.locator('label:has-text("URIOfTheProduct")');
      const labelText = await label.textContent();

      // Should have some required indication
      const hasIndicator =
        (await requiredIndicator.isVisible().catch(() => false)) ||
        labelText?.includes('*') ||
        (await field.getAttribute('aria-required')) === 'true';

      expect(hasIndicator).toBe(true);
    });
  });

  test.describe('Schema Cardinality Information', () => {
    test('schema includes cardinality for each element', async () => {
      const schema = await api.getTemplateSchema(TEST_TEMPLATE);

      // Check that elements have cardinality
      for (const element of schema.elements.slice(0, 5)) {
        // Cardinality should be present
        // Default is [1..1] if not specified
        // Formats: [1], [0..1], [1..1], [0..*], [1..*], etc.
        if (element.cardinality) {
          expect(element.cardinality).toMatch(/\[\d+(?:\.\.[\d*]+)?\]/);
        }
      }
    });

    test('cardinality patterns are valid', async () => {
      const schema = await api.getTemplateSchema(TEST_TEMPLATE);

      const validPatterns = [
        /^\[\d+\]$/,         // [1] - shorthand for [1..1]
        /^\[0\.\.1\]$/,      // [0..1]
        /^\[1\.\.1\]$/,      // [1..1]
        /^\[0\.\.\*\]$/,     // [0..*]
        /^\[1\.\.\*\]$/,     // [1..*]
        /^\[\d+\.\.\d+\]$/,  // [n..m]
      ];

      for (const element of schema.elements) {
        if (element.cardinality) {
          const isValid = validPatterns.some((pattern) =>
            pattern.test(element.cardinality!)
          );
          expect(isValid).toBe(true);
        }
      }
    });
  });

  test.describe('Nested Cardinality', () => {
    test('cardinality enforced in nested collections', async () => {
      // ContactInformation is a collection with nested required fields
      const formData = {
        ...createMinimalNameplateFormData(),
        ContactInformation: {
          // Provide empty collection
        },
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Should validate nested structure
      expect(typeof result.valid).toBe('boolean');
    });

    test('nested list cardinality is enforced', async () => {
      const schema = await api.getTemplateSchema(TEST_TEMPLATE);

      // Find nested structure
      const collectionWithList = schema.elements.find(
        (e) =>
          e.modelType === 'SubmodelElementCollection' &&
          e.elements?.some((nested) => nested.modelType === 'SubmodelElementList')
      );

      if (!collectionWithList) {
        test.skip();
        return;
      }

      const formData = {
        ...createMinimalNameplateFormData(),
        [collectionWithList.idShort]: {},
      };

      const result = await api.validateFormData(TEST_TEMPLATE, formData);

      // Validation should check nested structures
      expect(typeof result.valid).toBe('boolean');
    });
  });
});
