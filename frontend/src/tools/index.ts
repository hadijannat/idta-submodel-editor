// Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
// SPDX-License-Identifier: MIT
/**
 * Tool registry with lazy loading for the IDTA Submodel Editor.
 *
 * This module provides:
 * - Lazy-loaded React components for each tool
 * - Integration with backend tool manifest
 * - Runtime tool discovery and status tracking
 */

import { lazy, type LazyExoticComponent, createElement } from 'react';
import type {
  ToolMetadata,
  ToolComponent,
  ToolRegistryEntry,
} from './types';
import { STATIC_TOOLS } from './manifest';
import { getToolManifest, type ToolMetadataResponse } from '../services/api';

/**
 * Lazy-loaded tool components.
 *
 * Maps tool IDs to their lazy-loaded React components.
 */
const TOOL_COMPONENTS: Record<string, LazyExoticComponent<ToolComponent>> = {
  'smart-mapper': lazy(() =>
    import('../components/SmartMapper/SmartMapperPage').then((m) => ({
      default: m.default as ToolComponent,
    }))
  ),
  'magic-import': lazy(() =>
    import('../components/MagicImport').then((m) => ({
      default: m.MagicImportPanel as ToolComponent,
    }))
  ),
  'dataspace-connector': lazy(() =>
    import('../components/DataspaceConnector').then((m) => ({
      default: m.DataspaceConnectorPanel as ToolComponent,
    }))
  ),
};

const createPlaceholderComponent = (
  toolId: string,
  toolName: string
): LazyExoticComponent<ToolComponent> =>
  lazy(async () => ({
    default: () =>
      createElement(
        'div',
        { className: 'wizard-panel' },
        createElement(
          'div',
          { className: 'app-welcome' },
          createElement('h2', null, toolName),
          createElement(
            'p',
            null,
            `No UI component is registered for tool "${toolId}" in this build.`
          )
        )
      ),
  }));

/**
 * Convert backend response to frontend ToolMetadata.
 */
function responseToMetadata(response: ToolMetadataResponse): ToolMetadata {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    version: response.version,
    category: response.category as ToolMetadata['category'],
    wizardStep: response.wizard_step,
    featureFlag: response.feature_flag,
    requiresAuth: response.requires_auth,
    dependencies: response.dependencies,
    enabled: response.enabled,
    initialized: response.initialized,
  };
}

/**
 * Tool registry for managing tool components and metadata.
 */
class ToolRegistryImpl {
  private tools: Map<string, ToolRegistryEntry> = new Map();
  private manifestLoaded = false;
  private loading = false;
  private loadPromise: Promise<void> | null = null;

  constructor() {
    // Initialize with static tool data
    this.initializeStaticTools();
  }

  /**
   * Initialize tools from static manifest.
   */
  private initializeStaticTools(): void {
    for (const [id, staticMeta] of Object.entries(STATIC_TOOLS)) {
      const component =
        TOOL_COMPONENTS[id] ?? createPlaceholderComponent(id, staticMeta.name);
      this.tools.set(id, {
        metadata: {
          ...staticMeta,
          enabled: true, // Assume enabled until we fetch from backend
          initialized: false,
        },
        component,
        loaded: false,
      });
    }
  }

  /**
   * Load tool manifest from the backend.
   *
   * Updates tool metadata with runtime status from the server.
   */
  async loadServerManifest(): Promise<void> {
    if (this.manifestLoaded) return;
    if (this.loading && this.loadPromise) {
      return this.loadPromise;
    }

    this.loading = true;
    this.loadPromise = this.doLoadManifest();

    try {
      await this.loadPromise;
    } finally {
      this.loading = false;
    }
  }

  private async doLoadManifest(): Promise<void> {
    try {
      const manifest = await getToolManifest();

      // Update existing tools with server metadata
      for (const entry of manifest) {
        const metadata = responseToMetadata(entry);
        const existing = this.tools.get(entry.id);

        if (existing) {
          // Update metadata but keep component reference
          this.tools.set(entry.id, {
            ...existing,
            metadata,
          });
        } else {
          const component =
            TOOL_COMPONENTS[entry.id] ?? createPlaceholderComponent(entry.id, metadata.name);
          this.tools.set(entry.id, {
            metadata,
            component,
            loaded: false,
          });
        }
      }

      this.manifestLoaded = true;
    } catch (error) {
      console.warn('Failed to load tool manifest from server:', error);
      // Continue with static tools
    }
  }

  /**
   * Get a tool by ID.
   */
  getTool(id: string): ToolRegistryEntry | undefined {
    return this.tools.get(id);
  }

  /**
   * Get all registered tools.
   */
  getAllTools(): ToolRegistryEntry[] {
    return Array.from(this.tools.values());
  }

  /**
   * Get all enabled tools.
   */
  getEnabledTools(): ToolRegistryEntry[] {
    return this.getAllTools().filter((t) => t.metadata.enabled);
  }

  /**
   * Get tools that have wizard steps, sorted by step number.
   */
  getWizardTools(): ToolRegistryEntry[] {
    return this.getEnabledTools()
      .filter((t) => t.metadata.wizardStep !== null)
      .sort((a, b) => (a.metadata.wizardStep ?? 0) - (b.metadata.wizardStep ?? 0));
  }

  /**
   * Get utility tools (no wizard step).
   */
  getUtilityTools(): ToolRegistryEntry[] {
    return this.getEnabledTools().filter((t) => t.metadata.wizardStep === null);
  }

  /**
   * Get tools by category.
   */
  getToolsByCategory(category: ToolMetadata['category']): ToolRegistryEntry[] {
    return this.getEnabledTools().filter((t) => t.metadata.category === category);
  }

  /**
   * Check if the manifest has been loaded.
   */
  isManifestLoaded(): boolean {
    return this.manifestLoaded;
  }

  /**
   * Check if a tool component exists.
   */
  hasComponent(id: string): boolean {
    return TOOL_COMPONENTS[id] !== undefined;
  }

  /**
   * Register a new tool component dynamically.
   *
   * Used for plugin tools loaded at runtime.
   */
  registerComponent(
    id: string,
    component: LazyExoticComponent<ToolComponent>,
    metadata?: Partial<ToolMetadata>
  ): void {
    const existing = this.tools.get(id);
    const defaultMetadata: ToolMetadata = {
      id,
      name: id,
      description: '',
      version: '1.0.0',
      category: 'core',
      wizardStep: null,
      featureFlag: null,
      requiresAuth: false,
      dependencies: [],
      enabled: true,
      initialized: false,
    };

    this.tools.set(id, {
      metadata: {
        ...defaultMetadata,
        ...existing?.metadata,
        ...metadata,
      },
      component,
      loaded: false,
    });

    // Also add to components map
    TOOL_COMPONENTS[id] = component;
  }
}

/**
 * Global tool registry instance.
 */
export const toolRegistry = new ToolRegistryImpl();

// Re-export types
export type { ToolMetadata, ToolComponentProps, ToolRegistryEntry } from './types';
export { STATIC_TOOLS, getDefaultWizardSteps, WIZARD_STEPS } from './manifest';
