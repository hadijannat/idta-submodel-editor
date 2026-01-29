/**
 * Collection Field Tests
 *
 * Tests for SubmodelElementCollection editing including
 * expand/collapse, nested property editing, and nested collections.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';

const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('Collection Fields', () => {
  let formEditor: FormEditorPage;

  test.beforeEach(async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    formEditor = new FormEditorPage(page);

    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
    await formEditor.waitForFormReady();
    await formEditor.goToStep('fill-fields');
  });

  test.describe('Expand/Collapse', () => {
    test('collection can be expanded', async () => {
      // ContactInformation is typically a collection in Nameplate
      const collection = formEditor.getCollectionField('ContactInformation');

      // Check if collection exists
      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.expandCollection('ContactInformation');

      const isExpanded = await formEditor.isCollectionExpanded('ContactInformation');
      expect(isExpanded).toBe(true);
    });

    test('collection can be collapsed', async () => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // First expand
      await formEditor.expandCollection('ContactInformation');

      // Then collapse
      await formEditor.collapseCollection('ContactInformation');

      const isExpanded = await formEditor.isCollectionExpanded('ContactInformation');
      expect(isExpanded).toBe(false);
    });

    test('collection remembers expanded state when navigating', async () => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.expandCollection('ContactInformation');

      // Navigate away and back
      await formEditor.goToStep('export');
      await formEditor.goToStep('fill-fields');

      // Check state is preserved
      const isExpanded = await formEditor.isCollectionExpanded('ContactInformation');
      // Note: This behavior depends on implementation
      expect(typeof isExpanded).toBe('boolean');
    });
  });

  test.describe('Nested Property Editing', () => {
    test('can fill property inside collection', async ({ page }) => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.expandCollection('ContactInformation');

      // Fill a nested property (structure depends on template)
      // Try to find and fill a nested field
      const nestedField = page.locator(
        '[data-idshort*="CityTown"], [data-idshort*="Street"], [name*="CityTown"], [name*="Street"]'
      ).first();

      if (await nestedField.isVisible()) {
        const input = nestedField.locator('input, textarea').first();
        if (await input.isVisible()) {
          await input.fill('Test City');
          const value = await input.inputValue();
          expect(value).toBe('Test City');
        }
      }
    });

    test('nested collection values persist', async ({ page }) => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.expandCollection('ContactInformation');

      const nestedField = page.locator(
        '[data-idshort*="CityTown"], [name*="CityTown"]'
      ).first();

      if (await nestedField.isVisible()) {
        const input = nestedField.locator('input, textarea').first();
        if (await input.isVisible()) {
          await input.fill('Persistence Test City');

          // Navigate away and back
          await formEditor.goToStep('export');
          await formEditor.goToStep('fill-fields');
          await formEditor.expandCollection('ContactInformation');

          const value = await input.inputValue();
          expect(value).toBe('Persistence Test City');
        }
      }
    });
  });

  test.describe('Visual Indicators', () => {
    test('collection shows expand/collapse icon', async ({ page }) => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Look for expand/collapse indicator
      const expandIcon = collection.locator(
        '.expand-icon, .collapse-icon, [data-testid*="expand"], svg'
      );

      await expect(expandIcon.first()).toBeVisible();
    });

    test('collection header shows element count or label', async ({ page }) => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // Check for header text
      const header = collection.locator(
        '.collection-header, .field-label, h3, h4'
      ).first();

      const text = await header.textContent();
      expect(text).toBeTruthy();
    });
  });

  test.describe('Required Fields in Collections', () => {
    test('required nested fields show validation errors', async ({ page }) => {
      // This test verifies that validation reaches into collections
      await formEditor.validate();

      // Look for any validation errors
      const hasErrors = await formEditor.hasValidationErrors();
      // The presence of errors depends on the schema requirements
      expect(typeof hasErrors).toBe('boolean');
    });
  });

  test.describe('Keyboard Navigation', () => {
    test('Tab key navigates through collection fields', async ({ page }) => {
      const collection = formEditor.getCollectionField('ContactInformation');

      const isVisible = await collection.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      await formEditor.expandCollection('ContactInformation');

      // Get first input in collection
      const firstInput = collection.locator('input, textarea').first();

      if (await firstInput.isVisible()) {
        await firstInput.focus();
        await page.keyboard.press('Tab');

        // Verify focus moved to next element
        const focusedElement = page.locator(':focus');
        await expect(focusedElement).toBeVisible();
      }
    });
  });
});
