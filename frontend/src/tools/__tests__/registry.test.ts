import { afterEach, describe, expect, it, vi } from 'vitest';

import { toolRegistry } from '../index';

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

  it('registers utility tools even without UI components', () => {
    const tool = toolRegistry.getTool('template-ops');

    expect(tool).toBeDefined();
    expect(tool?.metadata.enabled).toBe(true);
  });

  it('includes dpp-builder in static fallback manifest', () => {
    const tool = toolRegistry.getTool('dpp-builder');

    expect(tool).toBeDefined();
    expect(tool?.metadata.wizardStep).toBe(8);
    expect(tool?.metadata.featureFlag).toBe('dpp_enabled');
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
});
