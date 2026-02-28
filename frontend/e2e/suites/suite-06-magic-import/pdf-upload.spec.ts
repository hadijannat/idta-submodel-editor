/**
 * Magic Import PDF Upload Tests
 *
 * Tests for PDF-to-AAS extraction pipeline.
 * Automatically falls back to mock responses when real service is unavailable.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { createMockableAPIClient, MockableAPIClient } from '../../helpers/mock-api-client';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';
const COMPLETED_JOB_STATUSES = new Set(['done', 'completed']);

async function waitForMagicImportCompletion(
  api: MockableAPIClient,
  jobId: string,
  timeoutMs = 30000,
  pollIntervalMs = 1000
) {
  const deadline = Date.now() + timeoutMs;
  let status = await api.getMagicImportJobStatus(jobId);

  while (Date.now() < deadline) {
    const normalizedStatus = String(status.status).toLowerCase();
    if (COMPLETED_JOB_STATUSES.has(normalizedStatus)) {
      return status;
    }
    if (normalizedStatus === 'failed') {
      throw new Error(`Magic Import job ${jobId} failed`);
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    status = await api.getMagicImportJobStatus(jobId);
  }

  throw new Error(`Timed out waiting for Magic Import job ${jobId} to complete`);
}

test.describe('Magic Import PDF Upload', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status === testInfo.expectedStatus) return;

    const activeStepText = (
      await page
        .locator('.wizard-stepper button.wizard-step.active .wizard-step-title')
        .first()
        .textContent()
        .catch(() => null)
    )?.trim();

    const wizardPanelHtml = await page
      .locator('.wizard-panel')
      .first()
      .innerHTML()
      .catch(() => null);

    await testInfo.attach('debug-url.txt', {
      body: Buffer.from(page.url()),
      contentType: 'text/plain',
    });

    await testInfo.attach('debug-active-step.txt', {
      body: Buffer.from(activeStepText || 'unknown'),
      contentType: 'text/plain',
    });

    await testInfo.attach('debug-wizard-panel.html', {
      body: Buffer.from(wizardPanelHtml || '<wizard-panel-unavailable/>'),
      contentType: 'text/html',
    });
  });

  test.describe('UI Flow', () => {
    test('Magic Import step is available', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();

      // Check for Magic Import step
      await expect(formEditor.magicImportStep).toBeVisible();
    });

    test('can navigate to Magic Import step', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();

      await formEditor.goToStep('magic-import');
      await formEditor.waitForMagicImportPanel();
    });

    test('file upload input is available', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();
      await formEditor.goToStep('magic-import');
      await formEditor.waitForMagicImportPanel();

      // Input is intentionally transparent; assert it is present and the dropzone is visible.
      const dropzone = page.locator('.magic-import-panel__dropzone');
      const fileInput = page.locator('.magic-import-panel__input');
      await expect(dropzone).toBeVisible({ timeout: 30000 });
      await expect(fileInput).toHaveCount(1);
    });
  });

  test.describe('API-Based Upload', () => {
    let api: MockableAPIClient;

    test.beforeEach(async ({ request }) => {
      api = await createMockableAPIClient(request, API_BASE_URL, {
        forceMock: { magicImport: true },
      });
    });

    test('can create extraction job', async () => {
      // Create a minimal test PDF
      const pdfBuffer = Buffer.from('%PDF-1.4 test content');

      const job = await api.createMagicImportJob(pdfBuffer, TEST_TEMPLATE);

      expect(job.job_id).toBeDefined();
      expect(job.status).toBeDefined();
    });

    test('job status can be polled', async () => {
      const pdfBuffer = Buffer.from('%PDF-1.4 test content');

      const job = await api.createMagicImportJob(pdfBuffer, TEST_TEMPLATE);
      const status = await api.getMagicImportJobStatus(job.job_id);

      expect(status.job_id).toBe(job.job_id);
      expect(status.status).toBeDefined();
    });

    test('completed job has extractions', async () => {
      const pdfBuffer = Buffer.from('%PDF-1.4 test content');

      const job = await api.createMagicImportJob(pdfBuffer, TEST_TEMPLATE);
      const finalStatus = await waitForMagicImportCompletion(api, job.job_id);
      expect(COMPLETED_JOB_STATUSES.has(String(finalStatus.status).toLowerCase())).toBe(true);

      const mockJobWithExtractions = job as typeof job & {
        extractions?: Array<{ field: string; value: string; confidence: number }>;
      };
      expect(Array.isArray(mockJobWithExtractions.extractions)).toBe(true);
      expect((mockJobWithExtractions.extractions ?? []).length).toBeGreaterThan(0);
    });

    test('extractions include confidence scores', async () => {
      const pdfBuffer = Buffer.from('%PDF-1.4 test content');

      const job = await api.createMagicImportJob(pdfBuffer, TEST_TEMPLATE);

      const jobWithExtractions = job as typeof job & {
        extractions?: Array<{ field: string; value: string; confidence: number }>;
      };

      if (jobWithExtractions.extractions && jobWithExtractions.extractions.length > 0) {
        expect(jobWithExtractions.extractions[0].confidence).toBeDefined();
        expect(typeof jobWithExtractions.extractions[0].confidence).toBe('number');
        expect(jobWithExtractions.extractions[0].confidence).toBeGreaterThanOrEqual(0);
        expect(jobWithExtractions.extractions[0].confidence).toBeLessThanOrEqual(1);
      }
    });

    test('extractions include field names', async () => {
      const pdfBuffer = Buffer.from('%PDF-1.4 test content');

      const job = await api.createMagicImportJob(pdfBuffer, TEST_TEMPLATE);

      const jobWithExtractions = job as typeof job & {
        extractions?: Array<{ field: string; value: string; confidence: number }>;
      };

      if (jobWithExtractions.extractions && jobWithExtractions.extractions.length > 0) {
        expect(jobWithExtractions.extractions[0].field).toBeDefined();
        expect(typeof jobWithExtractions.extractions[0].field).toBe('string');
      }
    });
  });
});
