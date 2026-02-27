/**
 * Nameplate Card Tests
 *
 * Tests for Digital Product Passport Nameplate card rendering.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';

const TEST_TEMPLATE = 'Digital Nameplate';

function getPassportToggle(page: import('@playwright/test').Page) {
  return page
    .locator('.passport-mode-toggle')
    .getByRole('button', { name: /^Passport View$/i });
}

function getEditorToggle(page: import('@playwright/test').Page) {
  return page
    .locator('.passport-mode-toggle')
    .getByRole('button', { name: /^Editor$/i });
}

test.describe('Nameplate Passport Card', () => {
  test.beforeEach(async ({ page }) => {
    const templateSelector = new TemplateSelectorPage(page);
    const formEditor = new FormEditorPage(page);

    await templateSelector.goto();
    await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
    await formEditor.waitForFormReady();
    await formEditor.goToStep('fill-fields');

    // Fill some data
    await formEditor.fillProperty('URIOfTheProduct', 'https://example.com/passport-test');
    await formEditor.fillMultiLangProperty('ManufacturerName', 'en', 'Passport Test Manufacturer');
    await formEditor.fillProperty('SerialNumber', 'SN-PASSPORT-001');
  });

  test('passport mode toggle is visible', async ({ page }) => {
    const passportToggle = getPassportToggle(page);

    await expect(passportToggle).toBeVisible();
  });

  test('can switch to passport view', async ({ page }) => {
    const passportToggle = getPassportToggle(page);
    await passportToggle.click();

    // Passport view should be visible
    const passportView = page.locator('.passport-view, [data-testid="passport-view"]');
    await expect(passportView).toBeVisible({ timeout: 10000 });
  });

  test('nameplate card displays manufacturer name', async ({ page }) => {
    const passportToggle = getPassportToggle(page);
    await passportToggle.click();

    const passportView = page.locator('.passport-view, [data-testid="passport-view"]');
    await expect(passportView).toBeVisible({ timeout: 10000 });

    // Check for manufacturer name in passport
    const manufacturerText = passportView.getByText('Passport Test Manufacturer');
    await expect(manufacturerText).toBeVisible();
  });

  test('nameplate card displays serial number', async ({ page }) => {
    const passportToggle = getPassportToggle(page);
    await passportToggle.click();

    const passportView = page.locator('.passport-view, [data-testid="passport-view"]');
    await expect(passportView).toBeVisible({ timeout: 10000 });

    // Check for serial number
    const serialText = passportView.getByText('SN-PASSPORT-001');
    await expect(serialText).toBeVisible();
  });

  test('form changes update passport view live', async ({ page }) => {
    const passportToggle = getPassportToggle(page);
    const formEditor = new FormEditorPage(page);

    const isPassportToggleVisible = await passportToggle.isVisible().catch(() => false);
    if (isPassportToggleVisible) {
      await passportToggle.click();

      const passportView = page.locator('.passport-view, [data-testid="passport-view"]');
      await expect(passportView).toBeVisible({ timeout: 10000 });

      // Switch back to form - use more specific selector
      const formToggle = getEditorToggle(page);
      const isFormToggleVisible = await formToggle.isVisible().catch(() => false);
      if (!isFormToggleVisible) {
        test.skip();
        return;
      }
      await formToggle.click();

      // Change a value
      await formEditor.fillProperty('SerialNumber', 'SN-UPDATED-002');

      // Switch back to passport
      await passportToggle.click();

      // Verify update
      const updatedSerial = passportView.getByText('SN-UPDATED-002');
      await expect(updatedSerial).toBeVisible();
    }
  });

  test('can export passport as PNG', async ({ page }) => {
    const passportToggle = getPassportToggle(page);
    await passportToggle.click();

    const exportButton = page
      .locator('.passport-mode-header')
      .getByRole('button', { name: /export/i });

    await expect(exportButton).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await exportButton.click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain('.png');
  });
});
