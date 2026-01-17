/**
 * English translations for PassportMode.
 */

import type { PassportTranslations } from './types';

export const en: PassportTranslations = {
  toggle: {
    editor: 'Editor',
    passportView: 'Passport View',
    viewModeLabel: 'View mode',
  },

  loading: {
    ariaLabel: 'Loading passport card',
    loading: 'Loading...',
  },

  error: {
    title: 'Unable to display passport',
    description: 'An error occurred while rendering the passport card.',
    retry: 'Try again',
    editorHint: 'or switch to Editor mode to check the data',
  },

  nameplate: {
    title: 'Digital Nameplate',
    emptyMessage: 'No nameplate data entered yet.',
    emptyHint: 'Switch to Editor mode to fill in manufacturer and product information.',
    identifierMarker: 'Identifier marker',
    fields: {
      serialNumber: 'Serial Number',
      manufacturerProductType: 'Manufacturer Product Type',
      yearOfConstruction: 'Year of Construction',
      countryOfOrigin: 'Country of Origin',
      orderCode: 'Order Code',
      batchNumber: 'Batch Number',
      productArticleNumber: 'Product Article Number',
      hardwareVersion: 'Hardware Version',
      firmwareVersion: 'Firmware Version',
      softwareVersion: 'Software Version',
    },
  },

  pcf: {
    title: 'Product Carbon Footprint',
    emptyMessage: 'No carbon footprint data entered yet.',
    emptyHint: 'Switch to Editor mode to fill in PCF values.',
    totalCo2e: 'Total CO₂e',
    perUnit: 'per {{unit}}',
    derivedNote: 'Total derived from phase breakdown.',
    chartAriaLabel: 'Carbon footprint breakdown by lifecycle phase',
    chartAriaLabelWithBreakdown: 'Carbon footprint breakdown: {{breakdown}}',
    breakdownMissing: 'Breakdown not available in this dataset.',
    calculationMethod: 'Calculation Method',
    referenceUnit: 'Reference Unit',
    lifecyclePhase: 'Lifecycle Phase',
    unknownPhase: 'Unknown',
    phases: {
      A1: 'Raw Material Supply',
      A2: 'Transport',
      A3: 'Manufacturing',
      'A1-A3': 'Cradle to Gate',
      A4: 'Distribution',
      A5: 'Installation',
      B1: 'Use',
      B2: 'Maintenance',
      B3: 'Repair',
      B4: 'Replacement',
      B5: 'Refurbishment',
      B6: 'Operational Energy',
      B7: 'Operational Water',
      C1: 'Deconstruction',
      C2: 'Transport (EoL)',
      C3: 'Waste Processing',
      C4: 'Disposal',
      D: 'Benefits & Loads',
    },
  },

  generic: {
    emptyMessage: 'No data entered yet.',
    emptyHint: 'Switch to Editor mode to fill in the form fields.',
    templateLabel: 'Template:',
    itemsCount: '{{count}} items',
    itemLabel: 'Item {{index}}',
  },

  export: {
    button: 'Export',
    tooltip: 'Export card as PNG image',
    exporting: 'Exporting...',
    success: 'Card exported successfully',
    error: 'Export failed: {{message}}',
    unsupported: 'Export is not supported in this browser',
  },

  common: {
    co2e: 'CO₂e',
  },
};
