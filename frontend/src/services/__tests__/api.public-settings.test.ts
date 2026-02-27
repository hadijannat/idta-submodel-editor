import { describe, expect, it, vi, afterEach } from 'vitest';

import { getPublicSettings } from '../api';

describe('getPublicSettings', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns the backend public settings contract including dpp flag', async () => {
    const payload = {
      mnestix_enabled: true,
      mnestix_url: 'http://localhost:3001',
      basyx_registry_url: 'http://localhost:4002',
      dataspace_enabled: true,
      dpp_enabled: true,
    };

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => payload,
      })
    );

    const result = await getPublicSettings();

    expect(result).toEqual(payload);
    expect(result.dpp_enabled).toBe(true);
  });
});
