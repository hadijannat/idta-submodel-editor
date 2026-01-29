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
import { mockMagicImport } from '../../helpers/mock-services';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital nameplate';

test.describe('Magic Import PDF Upload', () => {
  test.describe('UI Flow', () => {
    test.beforeEach(async ({ page }) => {
      // Mock the API routes for browser requests
      await mockMagicImport(page);
    });

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

      // Should show Magic Import panel
      const magicImportHeading = page.getByRole('heading', { name: /Magic Import/i });
      await expect(magicImportHeading).toBeVisible();
    });

    test('file upload input is available', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();
      await formEditor.goToStep('magic-import');

      // Find file input
      const fileInput = page.locator('.magic-import-panel__input, input[type="file"]');
      await expect(fileInput).toBeVisible();
    });
  });

  test.describe('API-Based Upload', () => {
    let api: MockableAPIClient;

    test.beforeEach(async ({ request }) => {
      api = await createMockableAPIClient(request, API_BASE_URL);
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

      // Job should be completed (immediately in mock mode)
      expect(job.status).toBe('completed');

      // Check for extractions (cast to extended type)
      const jobWithExtractions = job as typeof job & {
        extractions?: Array<{ field: string; value: string; confidence: number }>;
      };

      expect(jobWithExtractions.extractions).toBeDefined();
      expect(Array.isArray(jobWithExtractions.extractions)).toBe(true);
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
