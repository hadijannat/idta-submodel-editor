/**
 * Static tool manifest for the IDTA Submodel Editor.
 *
 * This file provides fallback metadata for tools when the backend
 * is unavailable, and defines the mapping between tool IDs and
 * their React components.
 */

import type { ToolMetadata, ToolCategory } from './types';

/**
 * Static tool definitions.
 *
 * These are used as fallbacks and for component mapping.
 * Runtime metadata is fetched from /api/tools/manifest.
 */
export const STATIC_TOOLS: Record<string, Omit<ToolMetadata, 'enabled' | 'initialized'>> = {
  'smart-mapper': {
    id: 'smart-mapper',
    name: 'Smart Mapper',
    description: 'Import and map CSV/XLSX data to template fields',
    version: '1.0.0',
    category: 'import',
    wizardStep: 3,
    featureFlag: null,
    requiresAuth: false,
    dependencies: [],
  },
  'magic-import': {
    id: 'magic-import',
    name: 'Magic Import',
    description: 'Extract fields from PDF datasheets using LLM-powered extraction',
    version: '1.0.0',
    category: 'import',
    wizardStep: 4,
    featureFlag: 'magic_import_enabled',
    requiresAuth: false,
    dependencies: [],
  },
  'export-panel': {
    id: 'export-panel',
    name: 'Export Panel',
    description: 'Export submodels to AASX, JSON, and PDF formats',
    version: '1.0.0',
    category: 'export',
    wizardStep: 6,
    featureFlag: null,
    requiresAuth: false,
    dependencies: [],
  },
  'dataspace-connector': {
    id: 'dataspace-connector',
    name: 'Dataspace Connector',
    description: 'Publish submodels to Manufacturing-X/Catena-X dataspaces',
    version: '1.0.0',
    category: 'integration',
    wizardStep: 7,
    featureFlag: 'dataspace_enabled',
    requiresAuth: false,
    dependencies: [],
  },
  'dpp-builder': {
    id: 'dpp-builder',
    name: 'DPP Builder',
    description: 'Assemble Digital Product Passports for EU ESPR compliance',
    version: '1.0.0',
    category: 'export',
    wizardStep: 8,
    featureFlag: 'dpp_enabled',
    requiresAuth: false,
    dependencies: ['export-panel'],
  },
  'semantic': {
    id: 'semantic',
    name: 'Semantic Lookup',
    description: 'Search and resolve semantic dictionary entries (ECLASS, IEC CDD)',
    version: '1.0.0',
    category: 'core',
    wizardStep: null,
    featureFlag: 'semantic_enabled',
    requiresAuth: false,
    dependencies: [],
    uiEntry: 'field_action',
    frontendComponent: null,
    standalone: false,
    requiresTemplate: true,
  },
  'pcf-tools': {
    id: 'pcf-tools',
    name: 'PCF Tools',
    description: 'Carbon Footprint Calculator & Validator for IDTA 02023 compliance',
    version: '1.0.0',
    category: 'analytics',
    wizardStep: null,
    featureFlag: null,
    requiresAuth: false,
    dependencies: [],
    uiEntry: 'utility',
    frontendComponent: 'pcf-tools',
    standalone: true,
    requiresTemplate: true,
  },
  'template-ops': {
    id: 'template-ops',
    name: 'Template Operations',
    description: 'Import, diff, migrate, and validate submodel templates',
    version: '1.0.0',
    category: 'core',
    wizardStep: null,
    featureFlag: null,
    requiresAuth: false,
    dependencies: [],
    uiEntry: 'utility',
    frontendComponent: 'template-ops',
    standalone: true,
    requiresTemplate: false,
  },
};

/**
 * Wizard step definitions.
 *
 * Steps 1, 2, and 5 are hardcoded in the app (template selection,
 * configuration, and form editing). Tools fill in the other steps.
 */
export const WIZARD_STEPS = {
  TEMPLATE_SELECTION: 1,
  CONFIGURATION: 2,
  FORM_EDITING: 5,
} as const;

/**
 * Get the default wizard steps array.
 */
export function getDefaultWizardSteps() {
  return [
    {
      id: WIZARD_STEPS.TEMPLATE_SELECTION,
      title: 'Choose Template',
      description: 'Select an IDTA template',
      toolId: null,
    },
    {
      id: WIZARD_STEPS.CONFIGURATION,
      title: 'Configure Instance',
      description: 'Review identifiers and versioning',
      toolId: null,
    },
    {
      id: WIZARD_STEPS.FORM_EDITING,
      title: 'Fill Required Fields',
      description: 'Complete mandatory elements',
      toolId: null,
    },
  ];
}

/**
 * Get tools sorted by wizard step.
 */
export function getWizardTools(tools: ToolMetadata[]): ToolMetadata[] {
  return tools
    .filter((t) => t.wizardStep !== null)
    .sort((a, b) => (a.wizardStep ?? 0) - (b.wizardStep ?? 0));
}

/**
 * Get utility tools (no wizard step).
 */
export function getUtilityTools(tools: ToolMetadata[]): ToolMetadata[] {
  return tools.filter((t) => t.wizardStep === null);
}

/**
 * Get tools by category.
 */
export function getToolsByCategory(
  tools: ToolMetadata[],
  category: ToolCategory
): ToolMetadata[] {
  return tools.filter((t) => t.category === category);
}
