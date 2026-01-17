/**
 * PassportMode i18n Type Definitions.
 *
 * Defines the structure of translation objects for type safety.
 * All translation keys are derived from this structure.
 */

/**
 * Full translation structure for PassportMode.
 */
export interface PassportTranslations {
  /** Toggle button labels */
  toggle: {
    /** Editor mode label */
    editor: string;
    /** Passport view mode label */
    passportView: string;
    /** Accessible label for view mode group */
    viewModeLabel: string;
  };

  /** Loading/skeleton states */
  loading: {
    /** Accessible label for loading state */
    ariaLabel: string;
    /** Loading text */
    loading: string;
  };

  /** Error boundary messages */
  error: {
    /** Error title */
    title: string;
    /** Error description */
    description: string;
    /** Retry button text */
    retry: string;
    /** Hint to switch to editor */
    editorHint: string;
  };

  /** Nameplate card translations */
  nameplate: {
    /** Card title */
    title: string;
    /** Empty state message */
    emptyMessage: string;
    /** Empty state hint */
    emptyHint: string;
    /** Identifier marker label */
    identifierMarker: string;
    /** Field labels */
    fields: {
      serialNumber: string;
      manufacturerProductType: string;
      yearOfConstruction: string;
      countryOfOrigin: string;
      orderCode: string;
      batchNumber: string;
      productArticleNumber: string;
      hardwareVersion: string;
      firmwareVersion: string;
      softwareVersion: string;
    };
  };

  /** PCF card translations */
  pcf: {
    /** Card title */
    title: string;
    /** Empty state message */
    emptyMessage: string;
    /** Empty state hint */
    emptyHint: string;
    /** Total CO2e label */
    totalCo2e: string;
    /** Per reference unit prefix */
    perUnit: string;
    /** Derivation note */
    derivedNote: string;
    /** Chart aria labels */
    chartAriaLabel: string;
    chartAriaLabelWithBreakdown: string;
    /** Breakdown missing message */
    breakdownMissing: string;
    /** Detail labels */
    calculationMethod: string;
    referenceUnit: string;
    /** Table headers */
    lifecyclePhase: string;
    /** Unknown phase label */
    unknownPhase: string;
    /** Lifecycle phase names */
    phases: {
      A1: string;
      A2: string;
      A3: string;
      'A1-A3': string;
      A4: string;
      A5: string;
      B1: string;
      B2: string;
      B3: string;
      B4: string;
      B5: string;
      B6: string;
      B7: string;
      C1: string;
      C2: string;
      C3: string;
      C4: string;
      D: string;
    };
  };

  /** Generic card translations */
  generic: {
    /** Empty state message */
    emptyMessage: string;
    /** Empty state hint */
    emptyHint: string;
    /** Template label */
    templateLabel: string;
    /** Items count ({{count}} items) */
    itemsCount: string;
    /** Item label (Item {{index}}) */
    itemLabel: string;
  };

  /** Export feature translations */
  export: {
    /** Export button label */
    button: string;
    /** Export button tooltip */
    tooltip: string;
    /** Exporting state */
    exporting: string;
    /** Success message */
    success: string;
    /** Error message */
    error: string;
    /** Unsupported browser message */
    unsupported: string;
  };

  /** Common/shared translations */
  common: {
    /** CO2 equivalent abbreviation */
    co2e: string;
  };
}

/**
 * All valid translation keys as dot-notation paths.
 *
 * This type ensures type safety when calling t() function.
 */
export type TranslationKey =
  // Toggle
  | 'toggle.editor'
  | 'toggle.passportView'
  | 'toggle.viewModeLabel'
  // Loading
  | 'loading.ariaLabel'
  | 'loading.loading'
  // Error
  | 'error.title'
  | 'error.description'
  | 'error.retry'
  | 'error.editorHint'
  // Nameplate
  | 'nameplate.title'
  | 'nameplate.emptyMessage'
  | 'nameplate.emptyHint'
  | 'nameplate.identifierMarker'
  | 'nameplate.fields.serialNumber'
  | 'nameplate.fields.manufacturerProductType'
  | 'nameplate.fields.yearOfConstruction'
  | 'nameplate.fields.countryOfOrigin'
  | 'nameplate.fields.orderCode'
  | 'nameplate.fields.batchNumber'
  | 'nameplate.fields.productArticleNumber'
  | 'nameplate.fields.hardwareVersion'
  | 'nameplate.fields.firmwareVersion'
  | 'nameplate.fields.softwareVersion'
  // PCF
  | 'pcf.title'
  | 'pcf.emptyMessage'
  | 'pcf.emptyHint'
  | 'pcf.totalCo2e'
  | 'pcf.perUnit'
  | 'pcf.derivedNote'
  | 'pcf.chartAriaLabel'
  | 'pcf.chartAriaLabelWithBreakdown'
  | 'pcf.breakdownMissing'
  | 'pcf.calculationMethod'
  | 'pcf.referenceUnit'
  | 'pcf.lifecyclePhase'
  | 'pcf.unknownPhase'
  | 'pcf.phases.A1'
  | 'pcf.phases.A2'
  | 'pcf.phases.A3'
  | 'pcf.phases.A1-A3'
  | 'pcf.phases.A4'
  | 'pcf.phases.A5'
  | 'pcf.phases.B1'
  | 'pcf.phases.B2'
  | 'pcf.phases.B3'
  | 'pcf.phases.B4'
  | 'pcf.phases.B5'
  | 'pcf.phases.B6'
  | 'pcf.phases.B7'
  | 'pcf.phases.C1'
  | 'pcf.phases.C2'
  | 'pcf.phases.C3'
  | 'pcf.phases.C4'
  | 'pcf.phases.D'
  // Generic
  | 'generic.emptyMessage'
  | 'generic.emptyHint'
  | 'generic.templateLabel'
  | 'generic.itemsCount'
  | 'generic.itemLabel'
  // Export
  | 'export.button'
  | 'export.tooltip'
  | 'export.exporting'
  | 'export.success'
  | 'export.error'
  | 'export.unsupported'
  // Common
  | 'common.co2e';
