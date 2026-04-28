import { afterEach, describe, expect, it, vi } from 'vitest';

import { getToolLaunchBlocker, toolRegistry } from '../index';

describe('toolRegistry static initialization', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('registers export panel tool for wizard gating', () => {
    const tool = toolRegistry.getTool('export-panel');

    expect(tool).toBeDefined();
    expect(tool?.metadata.enabled).toBe(true);
    expect(tool?.metadata.wizardStep).toBe(6);
  });

  it('registers only standalone frontend-backed tools as launchable utilities', () => {
    const templateOps = toolRegistry.getTool('template-ops');
    const pcfTools = toolRegistry.getTool('pcf-tools');
    const utilityIds = toolRegistry.getUtilityTools().map((entry) => entry.metadata.id);

    expect(templateOps).toBeDefined();
    expect(templateOps?.metadata.enabled).toBe(true);
    expect(pcfTools).toBeDefined();
    expect(toolRegistry.hasComponent('template-ops')).toBe(true);
    expect(toolRegistry.hasComponent('pcf-tools')).toBe(true);
    expect(utilityIds).toEqual(expect.arrayContaining(['template-ops', 'pcf-tools']));
    expect(utilityIds).not.toContain('semantic');
  });

  it('includes dpp-builder in static fallback manifest', () => {
    const tool = toolRegistry.getTool('dpp-builder');

    expect(tool).toBeDefined();
    expect(tool?.metadata.wizardStep).toBe(8);
    expect(tool?.metadata.featureFlag).toBe('dpp_enabled');
    expect(toolRegistry.hasComponent('dpp-builder')).toBe(true);
  });

  it('blocks launch for enabled tools that failed initialization', async () => {
    const manifest = [
      {
        id: 'dataspace-connector',
        name: 'Dataspace Connector',
        description: 'Publish submodels to Manufacturing-X/Catena-X dataspaces',
        version: '1.0.0',
        category: 'integration',
        wizard_step: 7,
        feature_flag: 'dataspace_enabled',
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: false,
        disabled_reason: 'Initialization failed: boom',
        ui_entry: 'wizard',
        frontend_component: 'dataspace-connector',
        standalone: true,
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => manifest,
      })
    );

    await toolRegistry.loadServerManifest(true);
    const tool = toolRegistry.getTool('dataspace-connector');

    expect(getToolLaunchBlocker(tool)).toBe('Initialization failed: boom');
  });

  it('merges server manifest and keeps wizard order', async () => {
    const manifest = [
      {
        id: 'smart-mapper',
        name: 'Smart Mapper',
        description: 'Import and map CSV/XLSX data to template fields',
        version: '1.0.0',
        category: 'import',
        wizard_step: 3,
        feature_flag: null,
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
      },
      {
        id: 'dpp-builder',
        name: 'DPP Builder',
        description: 'Assemble Digital Product Passports for EU ESPR compliance',
        version: '1.0.0',
        category: 'export',
        wizard_step: 8,
        feature_flag: 'dpp_enabled',
        requires_auth: false,
        dependencies: ['export-panel'],
        enabled: true,
        initialized: true,
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => manifest,
      })
    );

    await toolRegistry.loadServerManifest(true);
    const wizardIds = toolRegistry.getWizardTools(true).map((entry) => entry.metadata.id);

    expect(wizardIds).toContain('dpp-builder');
    expect(toolRegistry.getTool('dpp-builder')?.metadata.enabled).toBe(true);
    expect(wizardIds.indexOf('smart-mapper')).toBeLessThan(
      wizardIds.indexOf('dpp-builder')
    );
  });

  it('falls back to static manifest when server manifest fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));

    await expect(toolRegistry.loadServerManifest(true)).resolves.toBeUndefined();
    expect(toolRegistry.getTool('export-panel')).toBeDefined();
  });

  it('uses deterministic tie-break ordering for tools on the same wizard step', async () => {
    const manifest = [
      {
        id: 'zeta-tool',
        name: 'Zeta Tool',
        description: 'A test tool',
        version: '1.0.0',
        category: 'core',
        wizard_step: 9,
        feature_flag: null,
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
      },
      {
        id: 'alpha-tool',
        name: 'Alpha Tool',
        description: 'A test tool',
        version: '1.0.0',
        category: 'core',
        wizard_step: 9,
        feature_flag: null,
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => manifest,
      })
    );

    await toolRegistry.loadServerManifest(true);

    const stepNineIds = toolRegistry
      .getWizardTools(true)
      .filter((entry) => entry.metadata.wizardStep === 9)
      .map((entry) => entry.metadata.id);

    expect(stepNineIds).toEqual(['alpha-tool', 'zeta-tool']);
  });

  it('does not expose field-action or API-only backend tools as sidebar utilities', async () => {
    const manifest = [
      {
        id: 'semantic',
        name: 'Semantic Lookup',
        description: 'Search semantic dictionaries',
        version: '1.0.0',
        category: 'core',
        wizard_step: null,
        feature_flag: 'semantic_enabled',
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
        ui_entry: 'field_action',
        frontend_component: null,
        standalone: false,
      },
      {
        id: 'pcf-tools',
        name: 'PCF Tools',
        description: 'PCF utilities',
        version: '1.0.0',
        category: 'analytics',
        wizard_step: null,
        feature_flag: null,
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
        ui_entry: 'utility',
        frontend_component: 'pcf-tools',
        standalone: true,
      },
      {
        id: 'opcua-bridge',
        name: 'OPC UA Bridge',
        description: 'OPC UA bridge API',
        version: '1.0.0',
        category: 'integration',
        wizard_step: null,
        feature_flag: 'opcua_bridge_enabled',
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
        ui_entry: 'api_only',
        frontend_component: null,
        standalone: false,
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => manifest,
      })
    );

    await toolRegistry.loadServerManifest(true);
    const utilityIds = toolRegistry.getUtilityTools().map((entry) => entry.metadata.id);

    expect(utilityIds).toContain('pcf-tools');
    expect(utilityIds).not.toContain('semantic');
    expect(utilityIds).not.toContain('opcua-bridge');
  });
});
