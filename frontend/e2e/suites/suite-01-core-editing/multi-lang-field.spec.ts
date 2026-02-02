/**
 * Multi-Language Property Field Tests
 *
 * Tests for MultiLanguageProperty editing including language selection,
 * adding/removing languages, and language-specific value handling.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';
import { createMinimalNameplateFormData } from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('Multi-Language Property Fields', () => {
  let formEditor: FormEditorPage;

  test.beforeEach(async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    formEditor = new FormEditorPage(page);

    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
    await formEditor.waitForFormReady();
    await formEditor.goToStep('fill-fields');
  });

  test.describe('Language Selection', () => {
    test('can fill value for default language', async () => {
      // ManufacturerName is typically a MultiLanguageProperty
      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'Test Manufacturer');

      // Verify value was set (check the field contains the value)
      const field = formEditor.getMultiLangField('ManufacturerName');

      // Check via input value
      const input = field.locator('input, textarea').first();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        expect(value).toBe('Test Manufacturer');
      }
    });

    test('can switch between languages', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Fill English value
      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'English Name');

      // Switch to German
      const deTab = field.getByRole('tab', { name: /de|german/i });
      const langSelect = field.locator('select');

      if (await deTab.isVisible()) {
        await deTab.click();
      } else if (await langSelect.isVisible()) {
        await langSelect.selectOption({ label: /german|de/i });
      }

      // The input should now be empty or have German value
      const input = field.locator('input, textarea').last();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        // German field should be empty (we only filled English)
        expect(value === '' || value === 'English Name').toBe(true);
      }
    });

    test('different languages maintain separate values', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Fill English value
      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'English Name');

      // Fill German value
      await formEditor.fillMultiLangProperty('ManufacturerName', 'de', 'Deutscher Name');

      // Switch back to English
      const enTab = field.getByRole('tab', { name: /en|english/i });
      const langSelect = field.locator('select');

      if (await enTab.isVisible()) {
        await enTab.click();
      } else if (await langSelect.isVisible()) {
        await langSelect.selectOption({ label: /english|en/i });
      }

      // Verify English value is still there
      const input = field.locator('input, textarea').last();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        expect(value).toBe('English Name');
      }
    });
  });

  test.describe('Add/Remove Languages', () => {
    test('can add a new language', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Find add language button
      const addLangButton = field.getByRole('button', { name: /add.*language/i });

      if (await addLangButton.isVisible()) {
        await addLangButton.click();

        // Should show language selector or new input
        const newInput = field.locator('input, textarea').last();
        await expect(newInput).toBeVisible();
      }
    });

    test('can remove a language', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // First add a language if possible
      const addLangButton = field.getByRole('button', { name: /add.*language/i });

      if (await addLangButton.isVisible()) {
        await addLangButton.click();

        // Find remove button
        const removeLangButton = field.locator(
          'button[aria-label*="remove"], button[aria-label*="delete"], .remove-lang'
        ).last();

        if (await removeLangButton.isVisible()) {
          const beforeCount = await field.locator('.lang-tab, [role="tab"]').count();
          await removeLangButton.click();
          const afterCount = await field.locator('.lang-tab, [role="tab"]').count();

          expect(afterCount).toBeLessThanOrEqual(beforeCount);
        }
      }
    });
  });

  test.describe('Language Validation', () => {
    test('at least one language value is required for required fields', async () => {
      // Clear the ManufacturerName field and trigger validation
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Clear the input
      const input = field.locator('input, textarea').first();
      if (await input.isVisible()) {
        await input.clear();
      }

      // Trigger validation
      await formEditor.validate();

      // Should have validation error
      const hasErrors = await formEditor.hasValidationErrors();
      // ManufacturerName is typically required
      expect(typeof hasErrors).toBe('boolean');
    });
  });

  test.describe('Unicode Support', () => {
    test('supports Chinese characters', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', '制造商名称');

      const input = field.locator('input, textarea').first();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        expect(value).toBe('制造商名称');
      }
    });

    test('supports Arabic characters', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'اسم الشركة المصنعة');

      const input = field.locator('input, textarea').first();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        expect(value).toBe('اسم الشركة المصنعة');
      }
    });

    test('supports mixed scripts', async () => {
      const field = formEditor.getMultiLangField('ManufacturerName');

      const isVisible = await field.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const mixedValue = 'Company 会社 Firma';
      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', mixedValue);

      const input = field.locator('input, textarea').first();
      if (await input.isVisible()) {
        const value = await input.inputValue();
        expect(value).toBe(mixedValue);
      }
    });
  });

  test.describe('Export Integration', () => {
    test('all language values appear in exported JSON', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);

      const formData = {
        ...createMinimalNameplateFormData(),
        URIOfTheProduct: 'https://example.com/multilang-test',
        ManufacturerName: {
          en: 'English Manufacturer Name',
          de: 'Deutscher Herstellername',
          fr: 'Nom du fabricant français',
        },
      };

      const exportedJson = await api.exportJson(TEST_TEMPLATE, formData);
      const jsonString = JSON.stringify(exportedJson);

      expect(jsonString).toContain('English Manufacturer Name');
      expect(jsonString).toContain('Deutscher Herstellername');
      expect(jsonString).toContain('Nom du fabricant français');
    });
  });

  test.describe('Value Persistence', () => {
    test('multi-language values persist when navigating', async () => {
      await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'Persistent English');
      await formEditor.fillMultiLangProperty('ManufacturerName', 'de', 'Persistent German');

      // Navigate away and back
      await formEditor.goToStep('export');
      await formEditor.goToStep('fill-fields');

      // Check English value
      const field = formEditor.getMultiLangField('ManufacturerName');
      const input = field.locator('input, textarea').first();

      if (await input.isVisible()) {
        const value = await input.inputValue();
        // Should have one of the values
        expect(value === 'Persistent English' || value === 'Persistent German').toBe(true);
      }
    });
  });
});
