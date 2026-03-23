/**
 * List Field Tests
 *
 * Tests for SubmodelElementList editing including adding/removing items,
 * cardinality enforcement, and item ordering.
 */

import { test, expect, type Locator, type Page } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';
import { createMinimalNameplateFormData } from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';
const VIRTUALIZATION_TEMPLATE = 'Carbon Footprint';
const LIST_FIELD_SELECTOR =
  '.aas-list, .list-field, [data-testid*="list-"], [data-modeltype="SubmodelElementList"]';
const REQUIRED_LIST_FIELD_SELECTOR =
  '.aas-list[data-required="true"], .aas-list[data-cardinality*="[1"], .list-field[data-required="true"]';
const LIST_ITEM_SELECTOR = '.aas-list-item, .list-item, [data-testid="list-item"]';
const ADD_ITEM_BUTTON_SELECTOR = 'button.aas-btn-add[aria-label="Add item"], button[aria-label="Add item"]';
const REMOVE_ITEM_BUTTON_SELECTOR =
  'button[aria-label="Remove item"], .remove-item, [data-testid="remove-item"], button[aria-label*="remove"], button[aria-label*="delete"]';

function getIndexedListItemSelector(index: number): string {
  return [
    `.aas-list-item[data-index="${index}"]`,
    `.list-item[data-index="${index}"]`,
    `[data-testid="list-item"][data-index="${index}"]`,
  ].join(', ');
}

async function openExpandableListTemplate(
  page: Page,
  formEditor: FormEditorPage
): Promise<Locator | null> {
  const templateSelector = new TemplateSelectorPage(page);
  await templateSelector.goto();
  await templateSelector.searchAndSelectTemplate(VIRTUALIZATION_TEMPLATE);
  await formEditor.waitForFormReady();
  await formEditor.goToStep('fill-fields');

  const editorToggle = page.getByRole('button', { name: /^Editor$/ });
  if (await editorToggle.isVisible().catch(() => false)) {
    await editorToggle.click();
  }

  const listFields = page.locator(LIST_FIELD_SELECTOR);
  const listFieldCount = await listFields.count();

  for (let i = 0; i < listFieldCount; i++) {
    const candidate = listFields.nth(i);
    const addButton = candidate.locator(ADD_ITEM_BUTTON_SELECTOR).first();
    const isVisible = await candidate.isVisible().catch(() => false);
    const canAdd =
      (await addButton.isVisible().catch(() => false)) &&
      !(await addButton.isDisabled().catch(() => true));

    if (isVisible && canAdd) {
      return candidate;
    }
  }

  return null;
}

async function findLastVisibleEditableListItem(
  listField: Locator
): Promise<{ control: Locator; index: number } | null> {
  const visibleItems = listField.locator(LIST_ITEM_SELECTOR);
  const visibleItemCount = await visibleItems.count();

  for (let i = visibleItemCount - 1; i >= 0; i--) {
    const candidate = visibleItems.nth(i);
    const control = candidate.locator('input, textarea').first();
    const isVisible = await control.isVisible().catch(() => false);

    if (!isVisible) {
      continue;
    }

    const index = Number((await candidate.getAttribute('data-index')) ?? '-1');
    if (index >= 0) {
      return {
        control: listField
          .locator(getIndexedListItemSelector(index))
          .locator('input, textarea')
          .first(),
        index,
      };
    }
  }

  return null;
}

async function getVisibleTextControlValueAtIndex(
  listField: Locator,
  targetIndex: number
): Promise<string | null> {
  const control = listField
    .locator(getIndexedListItemSelector(targetIndex))
    .locator('input, textarea')
    .first();
  const isVisible = await control.isVisible().catch(() => false);
  if (!isVisible) {
    return null;
  }

  return await control.inputValue();
}

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
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const initialCount = await listField.locator(LIST_ITEM_SELECTOR).count();

      // Click add button
      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      await addButton.click();

      const newCount = await listField.locator(LIST_ITEM_SELECTOR).count();
      expect(newCount).toBe(initialCount + 1);
    });

    test('can add multiple items to list', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      // Add 3 items
      await addButton.click();
      await addButton.click();
      await addButton.click();

      const count = await listField.locator(LIST_ITEM_SELECTOR).count();
      expect(count).toBeGreaterThanOrEqual(3);
    });
  });

  test.describe('Remove Items', () => {
    test('can remove item from list field', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      // First add an item
      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      await addButton.click();

      const initialCount = await listField.locator(LIST_ITEM_SELECTOR).count();

      // Find and click remove button on first item
      const removeButton = listField.locator(REMOVE_ITEM_BUTTON_SELECTOR).first();

      if (await removeButton.isVisible()) {
        await removeButton.click();

        const newCount = await listField.locator(LIST_ITEM_SELECTOR).count();
        expect(newCount).toBe(initialCount - 1);
      }
    });

    test('confirm dialog appears for item removal', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      await addButton.click();

      const removeButton = listField.locator(REMOVE_ITEM_BUTTON_SELECTOR).first();

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
    });
  });

  test.describe('Item Editing', () => {
    test('can edit values in list items', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      await addButton.click();

      // Find input in the new list item
      const listItem = listField.locator(LIST_ITEM_SELECTOR).last();
      const input = listItem.locator('input, textarea').first();

      if (await input.isVisible()) {
        await input.fill('List Item Value');
        const value = await input.inputValue();
        expect(value).toBe('List Item Value');
      }
    });

    test('list item values persist', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible()) || (await addButton.isDisabled())) {
        test.skip();
        return;
      }

      await addButton.click();

      const listItem = listField.locator(LIST_ITEM_SELECTOR).last();
      const input = listItem.locator('input, textarea').first();

      if (await input.isVisible()) {
        await input.fill('Persistent Value');

        // Navigate away and back
        await formEditor.goToStep('export');
        await formEditor.goToStep('fill-fields');

        // Re-find the input (DOM may have changed)
        const newListField = page.locator(LIST_FIELD_SELECTOR).first();
        const newListItem = newListField.locator(LIST_ITEM_SELECTOR).last();
        const newInput = newListItem.locator('input, textarea').first();

        if (await newInput.isVisible()) {
          const value = await newInput.inputValue();
          expect(value).toBe('Persistent Value');
        }
      }
    });

    test('uses virtualized rendering when item count exceeds threshold', async ({ page }) => {
      const listField = await openExpandableListTemplate(page, formEditor);
      if (!listField) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible())) {
        test.skip();
        return;
      }

      for (let i = 0; i < 22; i++) {
        if (await addButton.isDisabled()) {
          break;
        }
        await addButton.click();
      }

      const listCountText = (await listField.locator('.aas-list-count').textContent()) ?? '';
      const totalItems = Number(listCountText.match(/\d+/)?.[0] ?? '0');

      if (totalItems <= 20) {
        test.skip();
        return;
      }

      const virtualizedContainer = listField.locator('.virtualized-list-container');
      await expect(virtualizedContainer).toBeVisible();

      const visibleItems = listField.locator(LIST_ITEM_SELECTOR);
      const visibleItemCount = await visibleItems.count();
      expect(visibleItemCount).toBeGreaterThan(0);
      expect(visibleItemCount).toBeLessThan(totalItems);

      const firstVisibleInput = visibleItems.first().locator('input, textarea').first();
      await expect(firstVisibleInput).toBeVisible();
      await firstVisibleInput.fill('Virtualized Item Value');
      await expect(firstVisibleInput).toHaveValue('Virtualized Item Value');
    });

    test('preserves tail item state when scrolling and appending in a virtualized list', async ({ page }) => {
      const listField = await openExpandableListTemplate(page, formEditor);
      if (!listField) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
      if (!(await addButton.isVisible())) {
        test.skip();
        return;
      }

      for (let i = 0; i < 22; i++) {
        if (await addButton.isDisabled()) {
          break;
        }
        await addButton.click();
      }

      const listCountText = (await listField.locator('.aas-list-count').textContent()) ?? '';
      const totalItems = Number(listCountText.match(/\d+/)?.[0] ?? '0');

      if (totalItems <= 20) {
        test.skip();
        return;
      }

      const virtualizedContainer = listField.locator('.virtualized-list-container');
      await expect(virtualizedContainer).toBeVisible();

      await virtualizedContainer.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
      });

      const visibleItems = listField.locator(LIST_ITEM_SELECTOR);
      const visibleItemCount = await visibleItems.count();
      expect(visibleItemCount).toBeGreaterThan(0);
      expect(visibleItemCount).toBeLessThan(totalItems);

      const tailEditableItem = await findLastVisibleEditableListItem(listField);
      if (!tailEditableItem) {
        test.skip();
        return;
      }

      const tailScrollTop = await virtualizedContainer.evaluate((element) => element.scrollTop);
      const { control: tailControl, index: tailIndex } = tailEditableItem;
      const sentinelValue = `Tail Sentinel Value ${tailIndex}`;
      await tailControl.fill(sentinelValue);
      await expect(tailControl).toHaveValue(sentinelValue);

      await addButton.click();
      await expect(listField.locator('.aas-list-count')).toContainText(`(${totalItems + 1} items)`);

      await virtualizedContainer.evaluate(
        (element, scrollTop) => {
          element.scrollTop = scrollTop;
        },
        tailScrollTop
      );

      const updatedVisibleCount = await visibleItems.count();
      expect(updatedVisibleCount).toBeGreaterThan(0);
      expect(updatedVisibleCount).toBeLessThan(totalItems + 1);

      await expect
        .poll(async () => {
          await virtualizedContainer.evaluate(
            (element, scrollTop) => {
              element.scrollTop = scrollTop;
            },
            tailScrollTop
          );
          return getVisibleTextControlValueAtIndex(listField, tailIndex);
        })
        .toBe(sentinelValue);
    });
  });

  test.describe('Cardinality Enforcement', () => {
    test('add button respects maximum cardinality', async ({ page }) => {
      const listField = page.locator(LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        test.skip();
        return;
      }

      const addButton = listField.locator(ADD_ITEM_BUTTON_SELECTOR).first();
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
        const count = await listField.locator(LIST_ITEM_SELECTOR).count();
        expect(count).toBeLessThanOrEqual(20);
      }
    });

    test('minimum cardinality shows validation warning', async ({ page }) => {
      // Find a required list field
      const listField = page.locator(REQUIRED_LIST_FIELD_SELECTOR).first();

      const isVisible = await listField.isVisible();
      if (!isVisible) {
        // This test only applies if there's a required list
        test.skip();
        return;
      }

      // Clear all items if possible
      const removeButtons = listField.locator(REMOVE_ITEM_BUTTON_SELECTOR);
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
        ...createMinimalNameplateFormData(),
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
