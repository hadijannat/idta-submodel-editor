import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useTools } from '../useTools';

describe('useTools wizard step integration', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('builds wizard steps from manifest metadata including dpp step', async () => {
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
        id: 'magic-import',
        name: 'Magic Import',
        description: 'Extract fields from PDF datasheets using LLM-powered extraction',
        version: '1.0.0',
        category: 'import',
        wizard_step: 4,
        feature_flag: 'magic_import_enabled',
        requires_auth: false,
        dependencies: [],
        enabled: false,
        initialized: false,
      },
      {
        id: 'export-panel',
        name: 'Export Panel',
        description: 'Export submodels to AASX, JSON, and PDF formats',
        version: '1.0.0',
        category: 'export',
        wizard_step: 6,
        feature_flag: null,
        requires_auth: false,
        dependencies: [],
        enabled: true,
        initialized: true,
      },
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

    const { result } = renderHook(() =>
      useTools({ fetchOnMount: false, enabledOnly: false })
    );

    await act(async () => {
      await result.current.refresh();
    });

    const stepIds = result.current.wizardSteps.map((step) => step.id);
    expect(stepIds).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(stepIds.indexOf(8)).toBeGreaterThan(stepIds.indexOf(7));

    const dppStep = result.current.wizardSteps.find((step) => step.id === 8);
    expect(dppStep?.toolId).toBe('dpp-builder');
    expect(dppStep?.enabled).toBe(true);

    const dataspaceStep = result.current.wizardSteps.find((step) => step.id === 7);
    expect(dataspaceStep?.enabled).toBe(false);
    expect(dataspaceStep?.disabledReason).toBe('Initialization failed: boom');
  });

  it('keeps static fallback steps when manifest loading fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    const { result } = renderHook(() =>
      useTools({ fetchOnMount: false, enabledOnly: false })
    );

    await act(async () => {
      await result.current.refresh();
    });

    const stepIds = result.current.wizardSteps.map((step) => step.id);
    expect(stepIds).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it('keeps hardcoded anchor steps even when manifest tries to override them', async () => {
    const manifest = [
      {
        id: 'custom-anchor-collision',
        name: 'Collision Tool',
        description: 'Should not replace the form editing anchor step',
        version: '1.0.0',
        category: 'core',
        wizard_step: 5,
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

    const { result } = renderHook(() =>
      useTools({ fetchOnMount: false, enabledOnly: false })
    );

    await act(async () => {
      await result.current.refresh();
    });

    const step5 = result.current.wizardSteps.find((step) => step.id === 5);
    expect(step5).toBeDefined();
    expect(step5?.title).toBe('Fill Required Fields');
    expect(step5?.toolId).toBeNull();
  });
});
