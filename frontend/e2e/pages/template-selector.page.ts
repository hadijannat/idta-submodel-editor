/**
 * Page object for the Template Selector component.
 *
 * Encapsulates interactions with the template selection UI
 * including search, filtering, and template card selection.
 */

import type { Locator, Page } from '@playwright/test';

export class TemplateSelectorPage {
  readonly page: Page;

  // Search and filter controls
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly refreshButton: Locator;

  // Template list
  readonly templateList: Locator;
  readonly templateCards: Locator;
  readonly loadingIndicator: Locator;
  readonly emptyState: Locator;

  // Template card elements
  readonly templateCardTitle: (name: string) => Locator;
  readonly templateCardDescription: (name: string) => Locator;
  readonly templateCardVersion: (name: string) => Locator;
  readonly templateCardIdta: (name: string) => Locator;

  constructor(page: Page) {
    this.page = page;

    // Search and filter controls
    this.searchInput = page.getByLabel('Search templates');
    this.statusFilter = page.getByRole('combobox', { name: /status/i });
    this.refreshButton = page.getByRole('button', { name: /refresh/i });

    // Template list - using actual class names from TemplateSelector component
    this.templateList = page.locator('.template-list');
    this.templateCards = page.locator('.template-item');
    this.loadingIndicator = page.locator('.template-list-loading');
    this.emptyState = page.locator('.template-list-empty');

    // Template card elements (functions returning locators) - using actual class names
    this.templateCardTitle = (name: string) =>
      this.getTemplateCard(name).locator('.template-title, .template-item-header');
    this.templateCardDescription = (name: string) =>
      this.getTemplateCard(name).locator('.template-item-name');
    this.templateCardVersion = (name: string) =>
      this.getTemplateCard(name).locator('.template-version');
    this.templateCardIdta = (name: string) =>
      this.getTemplateCard(name).locator('.template-idta-number');
  }

  // --------------------------------------------------------------------------
  // Navigation
  // --------------------------------------------------------------------------

  /**
   * Navigate to the template selector page (home page).
   */
  async goto(): Promise<void> {
    await this.page.goto('/', { waitUntil: 'domcontentloaded' });
    // Wait for the React app to mount and template selector to appear
    await this.page.waitForSelector('.template-selector, .wizard-panel', { timeout: 30000 });
    await this.waitForTemplatesLoaded();
  }

  /**
   * Wait for templates to be loaded.
   */
  async waitForTemplatesLoaded(timeout: number = 30000): Promise<void> {
    // First, wait for loading to complete (if it appears)
    try {
      // Give a small buffer for loading to start
      await this.page.waitForTimeout(500);

      // If loading indicator is visible, wait for it to disappear
      if (await this.loadingIndicator.isVisible()) {
        await this.loadingIndicator.waitFor({ state: 'hidden', timeout });
      }
    } catch {
      // Loading may not appear if cached - that's okay
    }

    // Wait for either templates to appear or empty state
    await Promise.race([
      this.templateCards.first().waitFor({ state: 'visible', timeout }),
      this.emptyState.waitFor({ state: 'visible', timeout }),
    ]);
  }

  // --------------------------------------------------------------------------
  // Template Selection
  // --------------------------------------------------------------------------

  /**
   * Get a template card by name.
   */
  getTemplateCard(name: string): Locator {
    return this.page.locator('.template-item', { hasText: name });
  }

  /**
   * Select a template by name.
   */
  async selectTemplate(name: string): Promise<void> {
    const card = this.getTemplateCard(name);
    await card.waitFor({ state: 'visible', timeout: 20000 });
    await card.click();
  }

  /**
   * Select a template by searching first.
   */
  async searchAndSelectTemplate(name: string): Promise<void> {
    await this.searchTemplates(name);
    await this.selectTemplate(name);
  }

  /**
   * Get all visible template names.
   */
  async getVisibleTemplateNames(): Promise<string[]> {
    const cards = await this.templateCards.all();
    const names: string[] = [];

    for (const card of cards) {
      // Get the template name from the .template-item-name element
      const nameElement = card.locator('.template-item-name');
      const text = await nameElement.textContent();
      if (text) {
        names.push(text.trim());
      }
    }

    return names;
  }

  /**
   * Get the count of visible templates.
   */
  async getTemplateCount(): Promise<number> {
    return await this.templateCards.count();
  }

  // --------------------------------------------------------------------------
  // Search and Filtering
  // --------------------------------------------------------------------------

  /**
   * Search for templates.
   */
  async searchTemplates(query: string): Promise<void> {
    await this.searchInput.fill(query);
    // Wait for debounced search to complete
    await this.page.waitForTimeout(300);
    await this.waitForTemplatesLoaded();
  }

  /**
   * Clear the search input.
   */
  async clearSearch(): Promise<void> {
    await this.searchInput.clear();
    await this.page.waitForTimeout(300);
    await this.waitForTemplatesLoaded();
  }

  /**
   * Filter by template status.
   */
  async filterByStatus(status: 'published' | 'deprecated' | 'all'): Promise<void> {
    await this.statusFilter.selectOption(status);
    await this.waitForTemplatesLoaded();
  }

  /**
   * Refresh the template list.
   */
  async refreshTemplates(): Promise<void> {
    await this.refreshButton.click();
    await this.waitForTemplatesLoaded();
  }

  // --------------------------------------------------------------------------
  // Assertions Helpers
  // --------------------------------------------------------------------------

  /**
   * Check if a template is visible.
   */
  async isTemplateVisible(name: string): Promise<boolean> {
    const card = this.getTemplateCard(name);
    return await card.isVisible();
  }

  /**
   * Check if the template list is empty.
   */
  async isListEmpty(): Promise<boolean> {
    const count = await this.getTemplateCount();
    return count === 0;
  }

  /**
   * Get template card info.
   */
  async getTemplateInfo(name: string): Promise<{
    title: string;
    description?: string;
    version?: string;
    idtaNumber?: string;
  }> {
    const card = this.getTemplateCard(name);
    await card.waitFor({ state: 'visible' });

    const title = (await this.templateCardTitle(name).textContent()) ?? '';
    const description = await this.templateCardDescription(name).textContent();
    const version = await this.templateCardVersion(name).textContent();
    const idtaNumber = await this.templateCardIdta(name).textContent();

    return {
      title: title.trim(),
      description: description?.trim() ?? undefined,
      version: version?.trim() ?? undefined,
      idtaNumber: idtaNumber?.trim() ?? undefined,
    };
  }

  // --------------------------------------------------------------------------
  // Local Template Upload
  // --------------------------------------------------------------------------

  /**
   * Get the local template upload button.
   */
  get uploadButton(): Locator {
    return this.page.getByRole('button', { name: /upload|import/i });
  }

  /**
   * Get the file input for upload.
   */
  get fileInput(): Locator {
    return this.page.locator('input[type="file"]');
  }

  /**
   * Upload a local AASX template.
   */
  async uploadLocalTemplate(filePath: string): Promise<void> {
    // Click upload button to reveal file input
    const uploadButton = this.uploadButton;
    if (await uploadButton.isVisible()) {
      await uploadButton.click();
    }

    // Set the file
    await this.fileInput.setInputFiles(filePath);

    // Wait for upload to complete
    await this.page.waitForResponse((response) =>
      response.url().includes('/api/editor/templates/local') && response.status() === 200
    );
  }
}
