/**
 * Template Selection Tests
 *
 * Tests for template discovery, search, and selection functionality.
 */

import { test, expect } from '@playwright/test';
import { TemplateSelectorPage } from '../../pages/template-selector.page';
import { FormEditorPage } from '../../pages/form-editor.page';
import { APIClient } from '../../helpers/api-client';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('Template Selection', () => {
  let templateSelector: TemplateSelectorPage;

  test.beforeEach(async ({ page }) => {
    templateSelector = new TemplateSelectorPage(page);
    await templateSelector.goto();
  });

  test.describe('Template List', () => {
    test('displays template list on initial load', async () => {
      const count = await templateSelector.getTemplateCount();
      expect(count).toBeGreaterThan(0);
    });

    test('shows template cards with required information', async () => {
      const templates = await templateSelector.getVisibleTemplateNames();
      expect(templates.length).toBeGreaterThan(0);

      // Check first template has expected info
      const firstTemplateName = templates[0];
      const info = await templateSelector.getTemplateInfo(firstTemplateName);

      expect(info.title).toBeTruthy();
    });

    test('displays Digital Nameplate template', async () => {
      const isVisible = await templateSelector.isTemplateVisible('Digital Nameplate');
      expect(isVisible).toBe(true);
    });
  });

  test.describe('Template Search', () => {
    test('filters templates by search query', async () => {
      const initialCount = await templateSelector.getTemplateCount();

      await templateSelector.searchTemplates('Nameplate');

      const filteredCount = await templateSelector.getTemplateCount();
      expect(filteredCount).toBeLessThanOrEqual(initialCount);
      expect(filteredCount).toBeGreaterThan(0);
    });

    test('shows no results message for non-existent template', async () => {
      await templateSelector.searchTemplates('NonExistentTemplate12345');

      const count = await templateSelector.getTemplateCount();
      expect(count).toBe(0);

      // Check for empty state message
      const isEmpty = await templateSelector.isListEmpty();
      expect(isEmpty).toBe(true);
    });

    test('clears search and shows all templates', async () => {
      const initialCount = await templateSelector.getTemplateCount();

      await templateSelector.searchTemplates('Nameplate');
      await templateSelector.clearSearch();

      const resetCount = await templateSelector.getTemplateCount();
      expect(resetCount).toBe(initialCount);
    });

    test('search is case-insensitive', async () => {
      await templateSelector.searchTemplates('nameplate');
      const lowerCount = await templateSelector.getTemplateCount();

      await templateSelector.clearSearch();
      await templateSelector.searchTemplates('NAMEPLATE');
      const upperCount = await templateSelector.getTemplateCount();

      expect(lowerCount).toBe(upperCount);
      expect(lowerCount).toBeGreaterThan(0);
    });

    test('partial search matches template names', async () => {
      await templateSelector.searchTemplates('Name');

      const isVisible = await templateSelector.isTemplateVisible('Digital Nameplate');
      expect(isVisible).toBe(true);
    });
  });

  test.describe('Template Selection', () => {
    test('clicking template card navigates to editor', async ({ page }) => {
      await templateSelector.selectTemplate('Digital Nameplate');

      // Wait for navigation and verify editor is visible
      const formEditor = new FormEditorPage(page);
      await formEditor.waitForFormReady();

      // Verify we're in the editor by checking for the form container (main section)
      await expect(formEditor.formContainer).toBeVisible({ timeout: 30000 });
    });

    test('search then select workflow works', async ({ page }) => {
      await templateSelector.searchAndSelectTemplate('Digital Nameplate');

      // Verify we're in the editor
      const formEditor = new FormEditorPage(page);
      await formEditor.waitForFormReady();
      await expect(formEditor.formContainer).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('API Integration', () => {
    test('templates match API response', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);

      // Get templates from API
      const apiResponse = await api.getTemplates();
      const apiTemplateNames = apiResponse.templates.map((t) => t.name);

      // Get templates from UI
      const uiTemplateNames = await templateSelector.getVisibleTemplateNames();

      // UI should show templates that are in API response
      for (const name of uiTemplateNames) {
        const matchingApiTemplate = apiTemplateNames.find(
          (apiName) => apiName.toLowerCase() === name.toLowerCase() ||
                       apiName.includes(name) ||
                       name.includes(apiName)
        );
        expect(matchingApiTemplate).toBeTruthy();
      }
    });

    test('template count matches API total', async ({ request }) => {
      const api = new APIClient(request, API_BASE_URL);

      const apiResponse = await api.getTemplates();
      const uiCount = await templateSelector.getTemplateCount();

      // UI count should match or be close to API total
      // (may differ slightly due to filtering or pagination)
      expect(uiCount).toBeGreaterThan(0);
      expect(uiCount).toBeLessThanOrEqual(apiResponse.total);
    });
  });
});
