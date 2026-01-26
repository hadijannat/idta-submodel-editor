import { describe, expect, it } from 'vitest';

import { toolRegistry } from '../index';

describe('toolRegistry static initialization', () => {
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
});
