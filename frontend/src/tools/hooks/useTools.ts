/**
 * React hook for accessing the tool registry.
 *
 * Provides tools metadata, loading state, and filtering utilities
 * for components that need to interact with tools.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { toolRegistry } from '../index';
import type { ToolMetadata, ToolRegistryEntry } from '../types';
import { getDefaultWizardSteps } from '../manifest';

interface UseToolsOptions {
  /** Whether to fetch the manifest from the server on mount */
  fetchOnMount?: boolean;
  /** Filter to only enabled tools */
  enabledOnly?: boolean;
}

interface UseToolsReturn {
  /** All registered tools */
  tools: ToolRegistryEntry[];
  /** Tools that have wizard steps, sorted by step */
  wizardTools: ToolRegistryEntry[];
  /** Utility tools (no wizard step) */
  utilityTools: ToolRegistryEntry[];
  /** Whether the manifest is being loaded */
  loading: boolean;
  /** Error message if loading failed */
  error: string | null;
  /** Whether the manifest has been loaded from the server */
  manifestLoaded: boolean;
  /** Refresh tools from the server */
  refresh: () => Promise<void>;
  /** Get a specific tool by ID */
  getTool: (id: string) => ToolRegistryEntry | undefined;
  /** Get tools by category */
  getByCategory: (category: ToolMetadata['category']) => ToolRegistryEntry[];
  /** Check if a tool is enabled */
  isToolEnabled: (id: string) => boolean;
  /** Get wizard steps with tool info */
  wizardSteps: WizardStep[];
}

export interface WizardStep {
  id: number;
  title: string;
  description: string;
  toolId: string | null;
  tool: ToolRegistryEntry | null;
  enabled: boolean;
}

const TOOL_STEP_LABEL_OVERRIDES: Record<
  string,
  { title: string; description: string }
> = {
  'export-panel': {
    title: 'Review & Export',
    description: 'Validate and export',
  },
  'dataspace-connector': {
    title: 'Dataspace Publishing',
    description: 'Publish to Manufacturing-X/Catena-X',
  },
};

const MAX_RUNTIME_WIZARD_STEP = 20;

function isValidRuntimeWizardStep(step: number): boolean {
  return Number.isInteger(step) && step >= 1 && step <= MAX_RUNTIME_WIZARD_STEP;
}

/**
 * Hook for accessing the tool registry.
 *
 * @param options - Configuration options
 * @returns Tool registry state and utilities
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { wizardTools, loading, getTool } = useTools();
 *
 *   if (loading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       {wizardTools.map(tool => (
 *         <div key={tool.metadata.id}>{tool.metadata.name}</div>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useTools(options: UseToolsOptions = {}): UseToolsReturn {
  const { fetchOnMount = true, enabledOnly = true } = options;

  const [loading, setLoading] = useState(!toolRegistry.isManifestLoaded());
  const [error, setError] = useState<string | null>(null);
  const [manifestLoaded, setManifestLoaded] = useState(toolRegistry.isManifestLoaded());
  const [version, setVersion] = useState(0); // Force re-render on refresh

  const loadManifest = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);

    try {
      await toolRegistry.loadServerManifest(force);
      setManifestLoaded(true);
      setVersion((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tools');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load manifest on mount if requested
  useEffect(() => {
    if (fetchOnMount && !toolRegistry.isManifestLoaded()) {
      loadManifest();
    }
  }, [fetchOnMount, loadManifest]);

  // Get all tools
  const tools = useMemo(() => {
    // Depend on version to re-compute after refresh
    void version;
    return enabledOnly
      ? toolRegistry.getEnabledTools()
      : toolRegistry.getAllTools();
  }, [enabledOnly, version]);

  // Get wizard tools
  const wizardTools = useMemo(() => {
    void version;
    return toolRegistry.getWizardTools();
  }, [version]);

  // Get utility tools
  const utilityTools = useMemo(() => {
    void version;
    return toolRegistry.getUtilityTools();
  }, [version]);

  // Build wizard steps with tool info
  const wizardSteps = useMemo((): WizardStep[] => {
    void version;
    const anchors = getDefaultWizardSteps();
    const stepMap = new Map<
      number,
      { id: number; title: string; description: string; toolId: string | null }
    >();

    for (const anchor of anchors) {
      stepMap.set(anchor.id, anchor);
    }

    const manifestSteps = toolRegistry.getWizardTools(true);
    for (const toolEntry of manifestSteps) {
      const wizardStep = toolEntry.metadata.wizardStep;
      if (wizardStep === null) continue;
      if (!isValidRuntimeWizardStep(wizardStep)) {
        continue;
      }
      if (stepMap.has(wizardStep)) {
        continue;
      }
      const labels =
        TOOL_STEP_LABEL_OVERRIDES[toolEntry.metadata.id] ?? {
          title: toolEntry.metadata.name,
          description: toolEntry.metadata.description,
        };
      stepMap.set(wizardStep, {
        id: wizardStep,
        title: labels.title,
        description: labels.description,
        toolId: toolEntry.metadata.id,
      });
    }

    return Array.from(stepMap.values())
      .sort((a, b) => a.id - b.id)
      .map((step) => {
        const tool = step.toolId ? toolRegistry.getTool(step.toolId) ?? null : null;
        const enabled = step.toolId === null || (tool?.metadata.enabled ?? false);

        return {
          id: step.id,
          title: step.title,
          description: step.description,
          toolId: step.toolId,
          tool,
          enabled,
        };
      });
  }, [version]);

  // Get tool by ID
  const getTool = useCallback((id: string) => {
    return toolRegistry.getTool(id);
  }, []);

  // Get tools by category
  const getByCategory = useCallback(
    (category: ToolMetadata['category']) => {
      return toolRegistry.getToolsByCategory(category);
    },
    []
  );

  // Check if tool is enabled
  const isToolEnabled = useCallback((id: string) => {
    const tool = toolRegistry.getTool(id);
    return tool?.metadata.enabled ?? false;
  }, []);

  // Refresh from server
  const refresh = useCallback(async () => {
    await loadManifest(true);
  }, [loadManifest]);

  return {
    tools,
    wizardTools,
    utilityTools,
    loading,
    error,
    manifestLoaded,
    refresh,
    getTool,
    getByCategory,
    isToolEnabled,
    wizardSteps,
  };
}

/**
 * Hook for getting a single tool by ID.
 *
 * @param toolId - The tool ID to get
 * @returns The tool entry or undefined
 */
export function useTool(toolId: string): ToolRegistryEntry | undefined {
  const { getTool, loading } = useTools({ fetchOnMount: true });

  return useMemo(() => {
    if (loading) return undefined;
    return getTool(toolId);
  }, [getTool, toolId, loading]);
}

/**
 * Hook for checking if a tool is available and enabled.
 *
 * @param toolId - The tool ID to check
 * @returns Whether the tool is available and enabled
 */
export function useToolEnabled(toolId: string): boolean {
  const { isToolEnabled, loading } = useTools({ fetchOnMount: true });

  return useMemo(() => {
    if (loading) return false;
    return isToolEnabled(toolId);
  }, [isToolEnabled, toolId, loading]);
}
