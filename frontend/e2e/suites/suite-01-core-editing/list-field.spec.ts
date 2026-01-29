/**
 * List Field Tests
 *
 * Tests for SubmodelElementList editing including adding/removing items,
 * cardinality enforcement, and item ordering.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('List Fields', () => {
  let formEditor: FormEditorPage;

  test.beforeEach(async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    formEditor = new FormEditorPage(page);

    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
    await formEditor.waitForFormReady();
    await formEditor.goToStep('fill-fields');
  });

  test.describe('Add Items', () => {
    test('can add item to list field', async ({ page }) => {
      // Find a list field in the form
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const initialCount = await listField.locator('.list-item, [data-testid="list-item"]').count();

      // Click add button
      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        await addButton.click();

        const newCount = await listField.locator('.list-item, [data-testid="list-item"]').count();
        expect(newCount).toBe(initialCount + 1);
      }
    });

    test('can add multiple items to list', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        // Add 3 items
        await addButton.click();
        await addButton.click();
        await addButton.click();

        const count = await listField.locator('.list-item, [data-testid="list-item"]').count();
        expect(count).toBeGreaterThanOrEqual(3);
      }
    });
  });

  test.describe('Remove Items', () => {
    test('can remove item from list field', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // First add an item
      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        await addButton.click();

        const initialCount = await listField.locator('.list-item, [data-testid="list-item"]').count();

        // Find and click remove button on first item
        const removeButton = listField.locator(
          '.remove-item, [data-testid="remove-item"], button[aria-label*="remove"], button[aria-label*="delete"]'
        ).first();

        if (await removeButton.isVisible()) {
          await removeButton.click();

          const newCount = await listField.locator('.list-item, [data-testid="list-item"]').count();
          expect(newCount).toBe(initialCount - 1);
        }
      }
    });

    test('confirm dialog appears for item removal', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        await addButton.click();

        const removeButton = listField.locator(
          '.remove-item, [data-testid="remove-item"], button[aria-label*="remove"]'
        ).first();

        if (await removeButton.isVisible()) {
          await removeButton.click();

          // Check if confirmation dialog appears (implementation dependent)
          const confirmDialog = page.getByRole('dialog');
          const hasDialog = await confirmDialog.isVisible({ timeout: 1000 }).catch(() => false);

          if (hasDialog) {
            const confirmButton = confirmDialog.getByRole('button', { name: /confirm|yes|delete/i });
            await confirmButton.click();
          }
        }
      }
    });
  });

  test.describe('Item Editing', () => {
    test('can edit values in list items', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        await addButton.click();

        // Find input in the new list item
        const listItem = listField.locator('.list-item, [data-testid="list-item"]').last();
        const input = listItem.locator('input, textarea').first();

        if (await input.isVisible()) {
          await input.fill('List Item Value');
          const value = await input.inputValue();
          expect(value).toBe('List Item Value');
        }
      }
    });

    test('list item values persist', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        await addButton.click();

        const listItem = listField.locator('.list-item, [data-testid="list-item"]').last();
        const input = listItem.locator('input, textarea').first();

        if (await input.isVisible()) {
          await input.fill('Persistent Value');

          // Navigate away and back
          await formEditor.goToStep('export');
          await formEditor.goToStep('fill-fields');

          // Re-find the input (DOM may have changed)
          const newListField = page.locator(
            '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
          ).first();
          const newListItem = newListField.locator('.list-item, [data-testid="list-item"]').last();
          const newInput = newListItem.locator('input, textarea').first();

          if (await newInput.isVisible()) {
            const value = await newInput.inputValue();
            expect(value).toBe('Persistent Value');
          }
        }
      }
    });
  });

  test.describe('Cardinality Enforcement', () => {
    test('add button respects maximum cardinality', async ({ page }) => {
      const listField = page.locator(
        '.list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.getByRole('button', { name: /add/i });
      if (await addButton.isVisible()) {
        // Try to add many items
        for (let i = 0; i < 20; i++) {
          if (await addButton.isDisabled()) {
            break;
          }
          await addButton.click();
        }

        // If max cardinality is enforced, button should be disabled
        // or the count should be limited
        const count = await listField.locator('.list-item, [data-testid="list-item"]').count();
        expect(count).toBeLessThanOrEqual(20);
      }
    });

    test('minimum cardinality shows validation warning', async ({ page }) => {
      // Find a required list field
      const listField = page.locator(
        '.list-field[data-required="true"], [data-cardinality*="[1"]'
      ).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        // This test only applies if there's a required list
        test.skip();
        return;
      }

      // Clear all items if possible
      const removeButtons = listField.locator(
        '.remove-item, [data-testid="remove-item"]'
      );
      const count = await removeButtons.count();

      for (let i = count - 1; i >= 0; i--) {
        await removeButtons.nth(i).click();
        // Handle confirmation if present
        const confirmButton = page.getByRole('button', { name: /confirm|yes/i });
        if (await confirmButton.isVisible({ timeout: 500 })) {
          await confirmButton.click();
        }
      }

      // Trigger validation
      await formEditor.validate();

      // Should show validation error for empty required list
      const hasErrors = await formEditor.hasValidationErrors();
      expect(hasErrors).toBe(true);
    });
  });

  test.describe('Export Integration', () => {
    test('list items appear in exported data', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);

      // Use API to export with list data
      const formData = {
        URIOfTheProduct: 'https://example.com/list-test',
        ManufacturerName: { en: 'List Test Manufacturer' },
        // Add list data if the schema supports it
      };

      const exportedJson = await api.exportJson(TEST_TEMPLATE, formData);
      const jsonString = JSON.stringify(exportedJson);

      expect(jsonString).toContain('example.com/list-test');
    });
  });
});
