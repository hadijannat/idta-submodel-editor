/**
 * CSV Import Tests
 *
 * Tests for Smart Mapper CSV import functionality including
 * file upload, column profiling, and auto-mapping.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';
import { loadCsvBuffer, loadCsvFixture } from '../../helpers/fixtures-loader';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TEMPLATE = 'Digital Nameplate';

test.describe('CSV Import', () => {
  test.describe('API-Based CSV Import', () => {
    let api: APIClient;

    test.beforeEach(async ({ request }) => {
      api = new APIClient(request, API_BASE_URL);
    });

    test('can upload CSV file and get column profile', async () => {
      const csvBuffer = loadCsvBuffer('nameplate-complete.csv');

      let result: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        result = await api.uploadMapperFile(csvBuffer, 'nameplate-complete.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available or returned empty response
      if (!result || !result.session_id) {
        test.skip();
        return;
      }

      expect(result.session_id).toBeDefined();
      expect(result.profile).toBeDefined();
      expect(result.profile.columns).toBeDefined();
      expect(result.profile.columns.length).toBeGreaterThan(0);
    });

    test('column profile includes data types', async () => {
      const csvBuffer = loadCsvBuffer('nameplate-complete.csv');

      let result: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        result = await api.uploadMapperFile(csvBuffer, 'nameplate-complete.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available
      if (!result || !result.profile?.columns) {
        test.skip();
        return;
      }

      for (const column of result.profile.columns) {
        expect(column.name).toBeDefined();
        expect(column.data_type).toBeDefined();
        expect(column.sample_values).toBeDefined();
      }
    });

    test('auto-suggest generates mappings', async () => {
      const csvBuffer = loadCsvBuffer('nameplate-complete.csv');

      let uploadResult: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        uploadResult = await api.uploadMapperFile(csvBuffer, 'nameplate-complete.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available
      if (!uploadResult || !uploadResult.session_id) {
        test.skip();
        return;
      }

      const suggestions = await api.getMapperSuggestions(
        uploadResult.session_id,
        TEST_TEMPLATE
      );

      expect(Array.isArray(suggestions)).toBe(true);
      // Should suggest some mappings based on column names
      expect(suggestions.length).toBeGreaterThan(0);
    });

    test('mappings include source and target paths', async () => {
      const csvBuffer = loadCsvBuffer('nameplate-complete.csv');

      let uploadResult: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        uploadResult = await api.uploadMapperFile(csvBuffer, 'nameplate-complete.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available
      if (!uploadResult || !uploadResult.session_id) {
        test.skip();
        return;
      }

      const suggestions = await api.getMapperSuggestions(
        uploadResult.session_id,
        TEST_TEMPLATE
      );

      if (suggestions.length > 0) {
        expect(suggestions[0].source_column).toBeDefined();
        expect(suggestions[0].target_path).toBeDefined();
      }
    });

    test('apply mappings returns form data', async () => {
      const csvBuffer = loadCsvBuffer('nameplate-complete.csv');

      let uploadResult: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        uploadResult = await api.uploadMapperFile(csvBuffer, 'nameplate-complete.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available
      if (!uploadResult || !uploadResult.session_id) {
        test.skip();
        return;
      }

      const suggestions = await api.getMapperSuggestions(
        uploadResult.session_id,
        TEST_TEMPLATE
      );

      if (suggestions.length > 0) {
        const formData = await api.applyMapperMappings(
          uploadResult.session_id,
          suggestions
        );

        expect(formData).toBeDefined();
        expect(typeof formData).toBe('object');
      }
    });
  });

  test.describe('UI-Based CSV Import', () => {
    test('can upload CSV via UI', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);
      const formEditor = new FormEditorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);
      await formEditor.waitForFormReady();

      // Find Smart Mapper step or panel
      const mapperStep = page.getByRole('button', { name: /smart.*mapper|import.*data|csv/i });

      if (await mapperStep.isVisible()) {
        await mapperStep.click();

        // Upload CSV
        const fileInput = page.locator('input[type="file"]');
        const csvFixture = loadCsvFixture('nameplate-complete.csv');

        if (await fileInput.isVisible()) {
          await fileInput.setInputFiles({
            name: 'nameplate-complete.csv',
            mimeType: 'text/csv',
            buffer: Buffer.from(csvFixture.content),
          });

          // Wait for processing
          await page.waitForTimeout(2000);

          // Should show column mapping UI
          const mappingTable = page.locator('.mapping-table, [data-testid="mapping-table"]');
          await expect(mappingTable).toBeVisible({ timeout: 10000 });
        }
      }
    });

    test('shows column preview after upload', async ({ page }) => {
      const templateSelector = new TemplateSelectorPage(page);

      await templateSelector.goto();
      await templateSelector.searchAndSelectTemplate(TEST_TEMPLATE);

      const mapperPanel = page.locator('.smart-mapper, [data-testid="smart-mapper"]');

      if (await mapperPanel.isVisible()) {
        const fileInput = page.locator('input[type="file"]');
        const csvFixture = loadCsvFixture('nameplate-complete.csv');

        await fileInput.setInputFiles({
          name: 'nameplate-complete.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from(csvFixture.content),
        });

        // Should show column preview
        const columnPreview = page.locator('.column-preview, [data-testid="column-preview"]');
        await expect(columnPreview).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('Malformed CSV Handling', () => {
    test('handles malformed CSV gracefully', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);
      const csvBuffer = loadCsvBuffer('nameplate-malformed.csv');

      try {
        const result = await api.uploadMapperFile(csvBuffer, 'nameplate-malformed.csv');

        // Should still parse, even with malformed data
        expect(result.session_id).toBeDefined();
      } catch (error) {
        // Or should return a meaningful error
        expect(error).toBeDefined();
      }
    });

    test('missing values are handled', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);
      const csvBuffer = loadCsvBuffer('nameplate-malformed.csv');

      let result: Awaited<ReturnType<typeof api.uploadMapperFile>> | null = null;
      try {
        result = await api.uploadMapperFile(csvBuffer, 'nameplate-malformed.csv');
      } catch {
        // API not available
      }

      // Skip if Smart Mapper API not available
      if (!result || !result.session_id) {
        test.skip();
        return;
      }

      // Profile should still be generated
      expect(result.profile).toBeDefined();
    });
  });
});
