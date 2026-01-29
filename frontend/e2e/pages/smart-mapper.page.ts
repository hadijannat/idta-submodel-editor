/**
 * Page object for the Smart Mapper component.
 *
 * Encapsulates interactions with the CSV/XLSX import and mapping UI.
 */

import type { Locator, Page } from '@playwright/test';

export class SmartMapperPage {
  readonly page: Page;

  // Upload
  readonly fileInput: Locator;
  readonly uploadButton: Locator;
  readonly uploadProgress: Locator;

  // Column profiling
  readonly columnTable: Locator;
  readonly columnRows: Locator;

  // Mapping
  readonly mappingTable: Locator;
  readonly mappingRows: Locator;
  readonly autoMapButton: Locator;
  readonly clearMappingsButton: Locator;

  // Preview
  readonly previewPanel: Locator;
  readonly previewRows: Locator;

  // Actions
  readonly applyButton: Locator;
  readonly cancelButton: Locator;
  readonly saveRecipeButton: Locator;
  readonly loadRecipeButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Upload
    this.fileInput = page.locator('input[type="file"]');
    this.uploadButton = page.getByRole('button', { name: /upload|browse/i });
    this.uploadProgress = page.locator('.upload-progress, [data-testid="upload-progress"]');

    // Column profiling
    this.columnTable = page.locator('.column-table, [data-testid="column-table"]');
    this.columnRows = page.locator('.column-row, [data-testid="column-row"]');

    // Mapping
    this.mappingTable = page.locator('.mapping-table, [data-testid="mapping-table"]');
    this.mappingRows = page.locator('.mapping-row, [data-testid="mapping-row"]');
    this.autoMapButton = page.getByRole('button', { name: /auto.*map|suggest/i });
    this.clearMappingsButton = page.getByRole('button', { name: /clear/i });

    // Preview
    this.previewPanel = page.locator('.preview-panel, [data-testid="preview-panel"]');
    this.previewRows = page.locator('.preview-row, [data-testid="preview-row"]');

    // Actions
    this.applyButton = page.getByRole('button', { name: /apply/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });
    this.saveRecipeButton = page.getByRole('button', { name: /save.*recipe/i });
    this.loadRecipeButton = page.getByRole('button', { name: /load.*recipe/i });
  }

  /**
   * Upload a file for mapping.
   */
  async uploadFile(filePath: string): Promise<void> {
    await this.fileInput.setInputFiles(filePath);
    await this.page.waitForTimeout(1000); // Wait for processing
  }

  /**
   * Upload file content directly.
   */
  async uploadFileContent(
    content: string | Buffer,
    filename: string,
    mimeType: string
  ): Promise<void> {
    await this.fileInput.setInputFiles({
      name: filename,
      mimeType,
      buffer: Buffer.isBuffer(content) ? content : Buffer.from(content),
    });
    await this.page.waitForTimeout(1000);
  }

  /**
   * Get column names from the profiling table.
   */
  async getColumnNames(): Promise<string[]> {
    const names: string[] = [];
    const rows = await this.columnRows.all();

    for (const row of rows) {
      const nameCell = row.locator('.column-name, [data-testid="column-name"]');
      const text = await nameCell.textContent();
      if (text) names.push(text.trim());
    }

    return names;
  }

  /**
   * Click auto-map to generate mapping suggestions.
   */
  async autoMap(): Promise<void> {
    await this.autoMapButton.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Create a manual mapping by drag-and-drop or selection.
   */
  async createMapping(sourceColumn: string, targetPath: string): Promise<void> {
    // Find the source column row
    const sourceRow = this.columnRows.filter({ hasText: sourceColumn });

    // Find the target field
    const targetField = this.page.locator(`[data-path="${targetPath}"]`);

    // Drag from source to target
    if (await sourceRow.isVisible() && await targetField.isVisible()) {
      await sourceRow.dragTo(targetField);
    }
  }

  /**
   * Get current mappings.
   */
  async getMappings(): Promise<{ source: string; target: string }[]> {
    const mappings: { source: string; target: string }[] = [];
    const rows = await this.mappingRows.all();

    for (const row of rows) {
      const sourceCell = row.locator('.source-column');
      const targetCell = row.locator('.target-path');

      const source = await sourceCell.textContent();
      const target = await targetCell.textContent();

      if (source && target) {
        mappings.push({ source: source.trim(), target: target.trim() });
      }
    }

    return mappings;
  }

  /**
   * Apply mappings to the form.
   */
  async applyMappings(): Promise<void> {
    await this.applyButton.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Clear all mappings.
   */
  async clearMappings(): Promise<void> {
    await this.clearMappingsButton.click();
    await this.page.waitForTimeout(300);
  }

  /**
   * Save current mappings as a recipe.
   */
  async saveRecipe(name: string): Promise<void> {
    await this.saveRecipeButton.click();

    const nameInput = this.page.getByLabel(/recipe name/i);
    await nameInput.fill(name);

    const confirmButton = this.page.getByRole('button', { name: /save|confirm/i });
    await confirmButton.click();
  }

  /**
   * Load a saved recipe.
   */
  async loadRecipe(name: string): Promise<void> {
    await this.loadRecipeButton.click();

    const recipeItem = this.page.locator('.recipe-item', { hasText: name });
    await recipeItem.click();
  }

  /**
   * Check if preview panel is visible.
   */
  async isPreviewVisible(): Promise<boolean> {
    return await this.previewPanel.isVisible();
  }

  /**
   * Get preview row count.
   */
  async getPreviewRowCount(): Promise<number> {
    return await this.previewRows.count();
  }
}
