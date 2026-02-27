/**
 * TypeScript interfaces for the tool registry.
 *
 * These interfaces define the structure of tool metadata and props
 * for dynamic tool loading and rendering.
 */

import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../types/ui-schema';
import type { SubmodelFormData } from '../types/aas-elements';
import type { ComponentType } from 'react';

/**
 * Tool category for grouping in the UI.
 */
export type ToolCategory = 'core' | 'import' | 'export' | 'integration' | 'analytics';

/**
 * Tool metadata from the backend API.
 */
export interface ToolMetadata {
  /** Unique identifier for the tool (e.g., "magic-import") */
  id: string;
  /** Human-readable display name */
  name: string;
  /** Brief description of the tool's purpose */
  description: string;
  /** Semantic version of the tool */
  version: string;
  /** Classification for grouping tools in the UI */
  category: ToolCategory;
  /** Position in the wizard flow (null for utility tools) */
  wizardStep: number | null;
  /** Config key that enables/disables this tool */
  featureFlag: string | null;
  /** Whether authentication is required to use this tool */
  requiresAuth: boolean;
  /** List of other tool IDs that must be available */
  dependencies: string[];
  /** Whether the tool is currently enabled */
  enabled: boolean;
  /** Whether the tool has been initialized */
  initialized: boolean;
  /** Manifest schema version from backend */
  schemaVersion?: string | null;
  /** Why the tool is unavailable/disabled */
  disabledReason?: string | null;
}

/**
 * Health status for a tool.
 */
export interface ToolHealth {
  toolId: string;
  healthy: boolean;
  message: string | null;
}

/**
 * Health status for all tools.
 */
export interface ToolsHealth {
  tools: Record<string, ToolHealth>;
  allHealthy: boolean;
}

/**
 * Dependency check result.
 */
export interface ToolDependency {
  id: string;
  status: 'satisfied' | 'missing' | 'disabled' | 'unhealthy';
  message: string | null;
}

/**
 * Full capability report for a tool.
 */
export interface ToolCapabilityReport {
  toolId: string;
  enabled: boolean;
  initialized: boolean;
  healthy: boolean;
  healthMessage: string | null;
  dependencies: ToolDependency[];
  capabilities: Record<string, unknown>;
  allDependenciesSatisfied: boolean;
}

/**
 * Props passed to tool components by the wizard.
 */
export interface ToolComponentProps {
  /** Name of the selected template */
  templateName: string;
  /** Template publication status */
  templateStatus: 'published' | 'deprecated' | 'local';
  /** Selected template version (null for latest) */
  templateVersion: string | null;
  /** React Hook Form instance for form data */
  form: UseFormReturn<SubmodelFormData>;
  /** Parsed UI schema for the template */
  schema: SubmodelUISchema | null;
  /** Callback when the tool step is complete */
  onComplete?: () => void;
  /** Callback to navigate to a different step */
  onNavigate?: (step: number) => void;
}

/**
 * Tool component type for lazy loading.
 */
export type ToolComponent = ComponentType<ToolComponentProps>;

/**
 * Registry entry combining metadata with component.
 */
export interface ToolRegistryEntry {
  /** Tool metadata from backend */
  metadata: ToolMetadata;
  /** Lazy-loaded React component */
  component: React.LazyExoticComponent<ToolComponent>;
  /** Whether the component has been loaded */
  loaded: boolean;
}

/**
 * Tool manifest entry (backend API response).
 */
export interface ToolManifestEntry {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  wizard_step: number | null;
  feature_flag: string | null;
  requires_auth: boolean;
  dependencies: string[];
  enabled: boolean;
  initialized: boolean;
  schema_version?: string | null;
  disabled_reason?: string | null;
}

/**
 * Convert backend manifest entry to frontend ToolMetadata.
 */
export function toToolMetadata(entry: ToolManifestEntry): ToolMetadata {
  return {
    id: entry.id,
    name: entry.name,
    description: entry.description,
    version: entry.version,
    category: entry.category as ToolCategory,
    wizardStep: entry.wizard_step,
    featureFlag: entry.feature_flag,
    requiresAuth: entry.requires_auth,
    dependencies: entry.dependencies,
    enabled: entry.enabled,
    initialized: entry.initialized,
    schemaVersion: entry.schema_version ?? null,
    disabledReason: entry.disabled_reason ?? null,
  };
}
