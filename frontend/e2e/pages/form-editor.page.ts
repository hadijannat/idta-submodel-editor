/**
 * Page object for the Form Editor component.
 *
 * Encapsulates interactions with the main AAS form editor including
 * property fields, collections, lists, and export functionality.
 */

import { expect, type Locator, type Page } from '@playwright/test';

export class FormEditorPage {
  readonly page: Page;
  private recentPageErrors: string[] = [];
  private static magicImportWarmupAttempted = false;

  // Main sections
  readonly formContainer: Locator;
  readonly stepperSidebar: Locator;
  readonly exportPanel: Locator;

  // Stepper steps
  readonly configureInstanceStep: Locator;
  readonly magicImportStep: Locator;
  readonly fillFieldsStep: Locator;
  readonly exportStep: Locator;

  // Form controls
  readonly saveButton: Locator;
  readonly resetButton: Locator;
  readonly validateButton: Locator;

  // Export controls
  readonly exportAasxButton: Locator;
  readonly exportJsonButton: Locator;
  readonly exportPdfButton: Locator;
  readonly exportFormatSelect: Locator;

  // Validation
  readonly validationErrorBanner: Locator;
  readonly validationWarningBanner: Locator;

  constructor(page: Page) {
    this.page = page;

    this.page.on('pageerror', (error) => {
      const summary = error.stack || error.message;
      this.trackPageError(summary);
    });

    // Main sections - using actual class names from App.tsx
    // The form container is the main content area (.app-main) - use getByRole for specificity
    this.formContainer = page.getByRole('main');
    this.stepperSidebar = page.locator('.wizard-stepper');
    this.exportPanel = page.locator('.app-export-sidebar');

    // Stepper steps - scoped to stepperSidebar to avoid collisions with nested wizards
    this.configureInstanceStep = this.stepperSidebar.locator('button.wizard-step', { hasText: /Configure Instance/i });
    this.magicImportStep = this.stepperSidebar.locator('button.wizard-step', { hasText: /Magic Import/i });
    this.fillFieldsStep = this.stepperSidebar.locator('button.wizard-step', { hasText: /Fill.*Fields/i });
    this.exportStep = this.stepperSidebar.locator('button.wizard-step', { hasText: /Export/i });

    // Form controls - use specific classes to avoid matching wizard steps or other buttons
    this.saveButton = page.locator('button.btn-save, button.btn-primary:has-text("Save")').first();
    this.resetButton = page.locator('button.btn-reset, button.btn-secondary:has-text("Reset")').first();
    this.validateButton = page.locator('button.btn-validate');

    // Export controls
    this.exportAasxButton = page.getByRole('button', { name: /export.*aasx/i });
    this.exportJsonButton = page.getByRole('button', { name: /export.*json/i });
    this.exportPdfButton = page.getByRole('button', { name: /export.*pdf/i });
    this.exportFormatSelect = page.getByRole('combobox', { name: /format/i });

    // Validation - from App.tsx review-summary section
    this.validationErrorBanner = page.locator('.issue-badge-error').first();
    this.validationWarningBanner = page.locator('.issue-badge-warning').first();
  }

  // --------------------------------------------------------------------------
  // Navigation
  // --------------------------------------------------------------------------

  /**
   * Wait for the form to be ready.
   */
  async waitForFormReady(timeout: number = 30000): Promise<void> {
    await this.formContainer.waitFor({ state: 'visible', timeout });
  }

  /**
   * Navigate to a specific step.
   */
  async goToStep(
    step: 'configure' | 'magic-import' | 'fill-fields' | 'export'
  ): Promise<void> {
    let stepButton: Locator;
    let expectedStepTitle: RegExp;

    switch (step) {
      case 'configure':
        stepButton = this.configureInstanceStep;
        expectedStepTitle = /Configure Instance/i;
        break;
      case 'magic-import':
        stepButton = this.magicImportStep;
        expectedStepTitle = /Magic Import/i;
        break;
      case 'fill-fields':
        stepButton = this.fillFieldsStep;
        expectedStepTitle = /Fill.*Fields/i;
        break;
      case 'export':
        stepButton = this.exportStep;
        expectedStepTitle = /Export/i;
        break;
    }

    await expect(stepButton).toBeVisible();
    await expect(stepButton).toBeEnabled();

    if (step === 'magic-import') {
      await this.warmMagicImportModules();
    }

    const activeStepTitleBeforeClick = (
      await this.stepperSidebar
        .locator('button.wizard-step.active')
        .first()
        .textContent()
        .catch(() => null)
    )
      ?.replace(/\s+/g, ' ')
      .trim();
    if (!activeStepTitleBeforeClick || !expectedStepTitle.test(activeStepTitleBeforeClick)) {
      await stepButton.click();
    }

    await expect
      .poll(
        async () => {
          const activeStep = this.stepperSidebar
            .locator('button.wizard-step.active')
            .first();
          const activeText = (await activeStep.textContent().catch(() => null)) ?? '';
          return activeText.replace(/\s+/g, ' ').trim();
        },
        {
          timeout: 20000,
          message: `Expected step "${step}" to become active`,
        }
      )
      .toMatch(expectedStepTitle);
  }

  /**
   * Wait for Magic Import panel content to be rendered.
   * Accept either heading-first or panel-first render paths.
   */
  async waitForMagicImportPanel(timeout: number = 30000): Promise<void> {
    const magicImportHeading = this.page.getByRole('heading', {
      name: /^Magic Import/i,
    });
    const magicImportPanel = this.page.locator('.magic-import-panel');
    const loadingIndicator = this.page.getByText(/Loading Magic Import/i);

    const waitForPanel = async (waitTimeout: number) =>
      Promise.race([
        magicImportHeading.waitFor({ state: 'visible', timeout: waitTimeout }),
        magicImportPanel.waitFor({ state: 'visible', timeout: waitTimeout }),
      ]);

    const startedAt = Date.now();

    try {
      const firstWindow = Math.min(timeout, 10000);
      await Promise.race([
        waitForPanel(firstWindow),
        loadingIndicator.waitFor({ state: 'visible', timeout: firstWindow }),
      ]);

      if (
        !(await magicImportHeading.isVisible().catch(() => false)) &&
        !(await magicImportPanel.isVisible().catch(() => false))
      ) {
        const elapsed = Date.now() - startedAt;
        const remainingTimeout = Math.max(timeout - elapsed, 1000);
        await waitForPanel(remainingTimeout);
      }
    } catch {
      const activeStepText = (
        await this.stepperSidebar
          .locator('button.wizard-step.active .wizard-step-title')
          .first()
          .textContent()
          .catch(() => null)
      )?.trim();
      const rootSnippet = await this.page
        .locator('#root')
        .innerHTML()
        .then((html) => html.replace(/\s+/g, ' ').slice(0, 280))
        .catch(() => null);
      const pageErrors = this.recentPageErrors.length
        ? this.recentPageErrors.slice(-3).join(' | ')
        : 'none';

      throw new Error(
        `Magic Import panel did not become visible within ${timeout}ms (active step: ${activeStepText || 'unknown'}, recent page errors: ${pageErrors}, root snippet: ${rootSnippet || '<unavailable>'})`
      );
    }
  }

  private trackPageError(summary: string): void {
    this.recentPageErrors.push(summary);
    if (this.recentPageErrors.length > 10) {
      this.recentPageErrors = this.recentPageErrors.slice(-10);
    }
  }

  private async warmMagicImportModules(timeout: number = 5000): Promise<void> {
    if (FormEditorPage.magicImportWarmupAttempted) {
      return;
    }
    FormEditorPage.magicImportWarmupAttempted = true;

    const viteProbe = await this.page.request
      .get('/@vite/client', {
        failOnStatusCode: false,
        timeout: 2000,
      })
      .catch(() => null);

    if (!viteProbe?.ok()) {
      return;
    }

    const modulePaths = [
      '/src/components/MagicImport/index.tsx',
      '/src/components/MagicImport/MagicImportPanel.tsx',
      '/src/components/MagicImport/useMagicImport.ts',
    ];
    const deadline = Date.now() + timeout;
    let attempt = 0;

    while (Date.now() < deadline) {
      attempt += 1;
      const checks = await Promise.all(
        modulePaths.map(async (path) => {
          const response = await this.page.request
            .get(`${path}?e2eWarmup=${attempt}`, {
              failOnStatusCode: false,
              timeout: 2000,
            })
            .catch(() => null);
          if (!response?.ok()) {
            return false;
          }

          const contentType = response.headers()['content-type'] ?? '';
          return !contentType || contentType.includes('javascript');
        })
      );

      if (checks.every(Boolean)) {
        return;
      }

      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) {
        break;
      }
      await this.page.waitForTimeout(Math.min(300, remainingMs));
    }

    this.trackPageError(
      `Magic Import warm-up did not confirm module fetches within ${timeout}ms`
    );
  }

  // --------------------------------------------------------------------------
  // Field Interactions - Property Fields
  // --------------------------------------------------------------------------

  /**
   * Get a form field container by idShort path.
   * Returns the AAS renderer wrapper element with data-id-short attribute.
   * Use getFieldInput() to get the actual input element.
   */
  getField(idShortPath: string): Locator {
    // Use data-id-short attribute which is set on the renderer wrapper
    // This returns a single element, avoiding strict mode violations
    return this.page.locator(`[data-id-short="${idShortPath}"]`);
  }

  /**
   * Get the input element within a field.
   * Finds the actual input/textarea inside the field container.
   */
  getFieldInput(idShortPath: string): Locator {
    return this.getField(idShortPath).locator('.aas-input, input, textarea').first();
  }

  /**
   * Get a text input field.
   */
  getTextInput(idShortPath: string): Locator {
    return this.getField(idShortPath).locator('.aas-input, input[type="text"], textarea').first();
  }

  /**
   * Fill a text/string property field.
   */
  async fillProperty(idShortPath: string, value: string): Promise<void> {
    const input = this.getFieldInput(idShortPath);
    await input.fill(value);
  }

  /**
   * Fill a number property field.
   */
  async fillNumberProperty(idShortPath: string, value: number): Promise<void> {
    const input = this.getField(idShortPath).locator('.aas-input, input[type="number"], input[type="text"]').first();
    await input.fill(value.toString());
  }

  /**
   * Fill a date property field.
   */
  async fillDateProperty(idShortPath: string, date: string): Promise<void> {
    const input = this.getField(idShortPath).locator('.aas-input, input[type="date"], input[type="text"]').first();
    await input.fill(date);
  }

  /**
   * Fill a boolean property field.
   */
  async fillBooleanProperty(idShortPath: string, value: boolean): Promise<void> {
    const checkbox = this.getField(idShortPath).locator('input[type="checkbox"]').first();
    if (value) {
      await checkbox.check();
    } else {
      await checkbox.uncheck();
    }
  }

  /**
   * Select an enum value.
   */
  async selectEnumValue(idShortPath: string, value: string): Promise<void> {
    const select = this.getField(idShortPath).locator('select').first();
    await select.selectOption(value);
  }

  /**
   * Get the current value of a property field.
   */
  async getPropertyValue(idShortPath: string): Promise<string> {
    const input = this.getFieldInput(idShortPath);
    return await input.inputValue();
  }

  // --------------------------------------------------------------------------
  // Field Interactions - Multi-Language Property
  // --------------------------------------------------------------------------

  /**
   * Get a multi-language field by its label text.
   */
  getMultiLangField(labelText: string): Locator {
    return this.page.locator(`.aas-field-multilang:has(.aas-label:text("${labelText}"))`);
  }

  /**
   * Fill a multi-language property value for a specific language.
   * @param labelText - The label text of the field (e.g., "ManufacturerName")
   * @param language - Language code (e.g., "en", "de") - must be exact match
   * @param value - The value to fill
   */
  async fillMultiLangProperty(
    labelText: string,
    language: string,
    value: string
  ): Promise<void> {
    const field = this.getMultiLangField(labelText);
    await field.waitFor({ state: 'visible', timeout: 10000 });

    // Click the language tab - use aria-controls to precisely match language code
    // aria-controls format: "{path}-panel-{lang}"
    const langTab = field.locator(`[role="tab"][aria-controls$="-panel-${language}"]`);
    await langTab.click();

    // Wait for the panel to become visible (not hidden)
    // The active panel's textarea should now be visible
    const activePanel = field.locator('.aas-multilang-panel:not([hidden])');
    await activePanel.waitFor({ state: 'visible', timeout: 5000 });

    // Fill the textarea in the active panel
    const textarea = activePanel.locator('textarea.aas-textarea');
    await textarea.fill(value);
  }

  /**
   * Add a new language to a multi-language property.
   */
  async addLanguage(idShortPath: string, language: string): Promise<void> {
    const field = this.getMultiLangField(idShortPath);
    const addButton = field.getByRole('button', { name: /add.*language/i });
    await addButton.click();

    // Select the new language
    const langInput = this.page.getByRole('combobox', { name: /language/i }).last();
    await langInput.fill(language);
    await langInput.press('Enter');
  }

  // --------------------------------------------------------------------------
  // Field Interactions - Collection Fields
  // --------------------------------------------------------------------------

  /**
   * Get a collection field.
   */
  getCollectionField(idShortPath: string): Locator {
    return this.page.locator(
      `.aas-collection[data-id-short="${idShortPath}"], ` +
        `.aas-collection:has(.aas-collection-title:text("${idShortPath}"))`
    );
  }

  /**
   * Expand a collection by clicking its header.
   */
  async expandCollection(idShortPath: string): Promise<void> {
    const collection = this.getCollectionField(idShortPath);
    const header = collection.locator('.aas-collection-header');
    const content = collection.locator('.aas-collection-content');

    // Only click if not already expanded
    if (!(await content.isVisible())) {
      await header.click();
    }
  }

  /**
   * Collapse a collection by clicking its header.
   */
  async collapseCollection(idShortPath: string): Promise<void> {
    const collection = this.getCollectionField(idShortPath);
    const header = collection.locator('.aas-collection-header');
    const content = collection.locator('.aas-collection-content');

    // Only click if currently expanded
    if (await content.isVisible()) {
      await header.click();
    }
  }

  /**
   * Check if a collection is expanded.
   */
  async isCollectionExpanded(idShortPath: string): Promise<boolean> {
    const collection = this.getCollectionField(idShortPath);
    const content = collection.locator('.aas-collection-content.expanded');
    return await content.isVisible();
  }

  // --------------------------------------------------------------------------
  // Field Interactions - List Fields
  // --------------------------------------------------------------------------

  /**
   * Get a list field.
   */
  getListField(idShortPath: string): Locator {
    return this.page.locator(
      `.aas-list[data-id-short="${idShortPath}"], ` +
        `.aas-list:has(.aas-list-title:text("${idShortPath}"))`
    );
  }

  /**
   * Add an item to a list field.
   */
  async addListItem(idShortPath: string): Promise<void> {
    const list = this.getListField(idShortPath);
    const addButton = list.locator('.aas-btn-add');
    await addButton.click();
  }

  /**
   * Remove an item from a list field by index.
   */
  async removeListItem(idShortPath: string, index: number): Promise<void> {
    const list = this.getListField(idShortPath);
    const removeButtons = list.locator('.aas-list-item .aas-btn-danger');
    await removeButtons.nth(index).click();
  }

  /**
   * Get the number of items in a list field.
   */
  async getListItemCount(idShortPath: string): Promise<number> {
    const list = this.getListField(idShortPath);
    const items = list.locator('.aas-list-item');
    return await items.count();
  }

  // --------------------------------------------------------------------------
  // Field Interactions - File Fields
  // --------------------------------------------------------------------------

  /**
   * Get a file field.
   */
  getFileField(idShortPath: string): Locator {
    return this.getField(idShortPath).locator('.aas-field-file').first();
  }

  /**
   * Set a file URL.
   */
  async setFileUrl(idShortPath: string, url: string): Promise<void> {
    const field = this.getField(idShortPath);
    const urlInput = field.locator('.aas-input, input[type="url"], input[type="text"]').first();
    await urlInput.fill(url);
  }

  /**
   * Set file content type.
   */
  async setFileContentType(idShortPath: string, contentType: string): Promise<void> {
    const field = this.getField(idShortPath);
    const contentTypeInput = field.locator('input[name*="contentType"], select').first();

    if (await contentTypeInput.isVisible()) {
      if ((await contentTypeInput.evaluate((el) => el.tagName)) === 'SELECT') {
        await contentTypeInput.selectOption(contentType);
      } else {
        await contentTypeInput.fill(contentType);
      }
    }
  }

  // --------------------------------------------------------------------------
  // Field Interactions - Range Fields
  // --------------------------------------------------------------------------

  /**
   * Get a range field.
   */
  getRangeField(idShortPath: string): Locator {
    return this.getField(idShortPath).locator('.aas-field-range').first();
  }

  /**
   * Fill a range field.
   */
  async fillRangeProperty(
    idShortPath: string,
    min: string | number,
    max: string | number
  ): Promise<void> {
    const field = this.getField(idShortPath);
    const inputs = field.locator('.aas-input, input');
    const minInput = inputs.first();
    const maxInput = inputs.nth(1);

    await minInput.fill(min.toString());
    await maxInput.fill(max.toString());
  }

  // --------------------------------------------------------------------------
  // Field Interactions - Reference Fields
  // --------------------------------------------------------------------------

  /**
   * Get a reference field.
   */
  getReferenceField(idShortPath: string): Locator {
    return this.getField(idShortPath).locator('.aas-field-reference').first();
  }

  /**
   * Fill a reference field with a global reference.
   */
  async fillReferenceProperty(idShortPath: string, value: string): Promise<void> {
    const field = this.getField(idShortPath);
    const input = field.locator('.aas-input, input[type="text"]').first();
    await input.fill(value);
  }

  // --------------------------------------------------------------------------
  // Validation
  // --------------------------------------------------------------------------

  /**
   * Trigger validation.
   */
  async validate(): Promise<void> {
    await this.validateButton.click();
    await this.page.waitForTimeout(500); // Wait for validation to complete
  }

  /**
   * Check if the form has validation errors.
   */
  async hasValidationErrors(): Promise<boolean> {
    return await this.validationErrorBanner.isVisible();
  }

  /**
   * Check if the form has validation warnings.
   */
  async hasValidationWarnings(): Promise<boolean> {
    return await this.validationWarningBanner.isVisible();
  }

  /**
   * Get validation error messages.
   */
  async getValidationErrors(): Promise<string[]> {
    const errors = this.page.locator('.issue-item:has(.issue-badge-error)');
    const count = await errors.count();
    const messages: string[] = [];

    for (let i = 0; i < count; i++) {
      const text = await errors.nth(i).textContent();
      if (text) messages.push(text.trim());
    }

    return messages;
  }

  /**
   * Get field-level error for a specific field.
   * AAS fields show errors in .aas-error-message spans.
   */
  async getFieldError(idShortPath: string): Promise<string | null> {
    const field = this.getField(idShortPath);
    const error = field.locator('.aas-error-message').first();

    if (await error.isVisible()) {
      return await error.textContent();
    }

    return null;
  }

  /**
   * Check if a field has an error state (red border/styling).
   */
  async hasFieldError(idShortPath: string): Promise<boolean> {
    const field = this.getField(idShortPath);
    const errorInput = field.locator('.aas-input-error');
    return await errorInput.count() > 0;
  }

  // --------------------------------------------------------------------------
  // Export
  // --------------------------------------------------------------------------

  /**
   * Export to AASX format.
   */
  async exportAasx(): Promise<void> {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportAasxButton.click();
    const download = await downloadPromise;
    await download.saveAs(`/tmp/${download.suggestedFilename()}`);
  }

  /**
   * Export to JSON format.
   */
  async exportJson(): Promise<void> {
    const downloadPromise = this.page.waitForEvent('download');
    await this.exportJsonButton.click();
    const download = await downloadPromise;
    await download.saveAs(`/tmp/${download.suggestedFilename()}`);
  }

  /**
   * Export and get the download.
   */
  async exportAndGetDownload(
    format: 'aasx' | 'json' | 'pdf'
  ): Promise<{ filename: string; path: string }> {
    const downloadPromise = this.page.waitForEvent('download');

    switch (format) {
      case 'aasx':
        await this.exportAasxButton.click();
        break;
      case 'json':
        await this.exportJsonButton.click();
        break;
      case 'pdf':
        await this.exportPdfButton.click();
        break;
    }

    const download = await downloadPromise;
    const filename = download.suggestedFilename();
    const path = `/tmp/${filename}`;
    await download.saveAs(path);

    return { filename, path };
  }

  // --------------------------------------------------------------------------
  // Form State
  // --------------------------------------------------------------------------

  /**
   * Reset the form to initial values.
   */
  async resetForm(): Promise<void> {
    await this.resetButton.click();

    // Confirm reset if dialog appears
    const confirmButton = this.page.getByRole('button', { name: /confirm|yes/i });
    if (await confirmButton.isVisible({ timeout: 1000 })) {
      await confirmButton.click();
    }
  }

  /**
   * Check if the form has unsaved changes.
   */
  async hasUnsavedChanges(): Promise<boolean> {
    // Look for dirty state indicator
    const dirtyIndicator = this.page.locator(
      '.unsaved-changes, [data-testid="unsaved-changes"], .dirty-indicator'
    );
    return await dirtyIndicator.isVisible();
  }

  /**
   * Get the current template name from the UI.
   * In step 2 (Configure Instance), it's in .template-summary .template-summary-title
   * In step 5 (Fill Fields), it's in .submodel-header h2
   */
  async getCurrentTemplateName(): Promise<string> {
    // Try getting from template summary card (step 2)
    const summaryTitle = this.page.locator('.template-summary .template-summary-title').first();
    if (await summaryTitle.isVisible()) {
      const text = await summaryTitle.textContent();
      if (text) return text.trim();
    }

    // Try getting from submodel header (step 5)
    const submodelHeader = this.page.locator('.submodel-header h2');
    if (await submodelHeader.isVisible()) {
      const text = await submodelHeader.textContent();
      if (text) return text.trim();
    }

    // Try from wizard sidebar selected template
    const sidebarTitle = this.page.locator('.wizard-sidebar .template-summary-title').first();
    if (await sidebarTitle.isVisible()) {
      const text = await sidebarTitle.textContent();
      if (text) return text.trim();
    }

    // Fallback to any h2 in the wizard panel
    const panelHeader = this.page.locator('.wizard-panel h2').first();
    const text = await panelHeader.textContent();
    return text?.trim() ?? '';
  }
}
