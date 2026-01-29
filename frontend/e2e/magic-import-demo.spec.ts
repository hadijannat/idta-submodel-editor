import { test, expect } from '@playwright/test';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';

const DEFAULT_BASE_URL = 'http://localhost:8080';
const DEFAULT_TEMPLATE = 'Digital Nameplate';
const DEFAULT_PDF = '@Downloads/Danfoss-APP-11-13-L.pdf';

const resolvePdfPath = (input: string): string => {
  if (input.startsWith('@Downloads/')) {
    return path.join(os.homedir(), 'Downloads', input.replace('@Downloads/', ''));
  }
  return input;
};

test('Magic Import demo walkthrough', async ({ page }) => {
  const baseUrl = process.env.DEMO_BASE_URL || DEFAULT_BASE_URL;
  const templateName = process.env.DEMO_TEMPLATE || DEFAULT_TEMPLATE;
  const pdfPath = resolvePdfPath(process.env.DEMO_PDF || DEFAULT_PDF);

  if (!fs.existsSync(pdfPath)) {
    throw new Error(`PDF not found at ${pdfPath}. Set DEMO_PDF to an existing file.`);
  }

  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  // Step 1: Choose template
  await page.getByLabel('Search templates').fill(templateName);
  const templateCard = page.locator('.template-item', { hasText: templateName });
  await expect(templateCard).toBeVisible({ timeout: 20000 });
  await templateCard.click();

  // Step 2: Configure instance (auto-advances on template selection)
  await expect(page.getByRole('heading', { name: /Configure Instance/i })).toBeVisible({
    timeout: 30000,
  });

  // Jump to Magic Import via sidebar stepper
  const magicImportStep = page.getByRole('button', { name: /Magic Import/i });
  await expect(magicImportStep).toBeEnabled({ timeout: 30000 });
  await magicImportStep.click();

  // Step 4: Magic Import upload
  await expect(page.getByRole('heading', { name: 'Magic Import' })).toBeVisible();
  const fileInput = page.locator('.magic-import-panel__input');
  await fileInput.setInputFiles(pdfPath);

  // Wait for processing to complete
  await expect(
    page.getByRole('heading', { name: /Magic Import - Review Extractions/i })
  ).toBeVisible({ timeout: 180000 });

  // Select first row to show provenance
  const firstRow = page.locator('.extraction-table__row').first();
  await expect(firstRow).toBeVisible({ timeout: 30000 });
  await firstRow.click();

  // Focus evidence if available
  const focusButton = page.getByRole('button', { name: /Focus evidence/i });
  if (await focusButton.isVisible()) {
    await focusButton.click();
  }

  // Approve all extractions
  const approveAll = page.getByRole('button', { name: /Approve All/i });
  if (await approveAll.isVisible()) {
    await approveAll.click();
    const approveAllItem = page.getByRole('button', { name: /All \(/i });
    await approveAllItem.click();
  }

  // Apply to form
  const applyButton = page.getByRole('button', { name: /Apply .* Fields to Form/i });
  await expect(applyButton).toBeEnabled({ timeout: 30000 });
  await applyButton.click();

  // Navigate to Fill Required Fields to show applied values
  const fillFieldsStep = page.getByRole('button', { name: /Fill Required Fields/i });
  if (await fillFieldsStep.isVisible()) {
    await fillFieldsStep.click();
    await expect(page.getByText(/Fill Required Fields/i)).toBeVisible();
  }
});
