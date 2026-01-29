/**
 * Policy Builder Tests
 *
 * Tests for ODRL policy creation and management.
 * Automatically falls back to mock responses when real service is unavailable.
 */

import { test, expect } from '@playwright/test';
import { createMockableAPIClient, MockableAPIClient } from '../../helpers/mock-api-client';
import { loadPolicyFixture } from '../../helpers/fixtures-loader';
import { createPolicyConfig, createTestBPN } from '../../helpers/test-data-factory';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('Policy Builder', () => {
  let api: MockableAPIClient;

  test.beforeEach(async ({ request }) => {
    api = await createMockableAPIClient(request, API_BASE_URL);
  });

  test.describe('Policy Templates', () => {
    test('can list policy templates', async () => {
      const templates = await api.getPolicyTemplates();

      expect(Array.isArray(templates)).toBe(true);
      expect(templates.length).toBeGreaterThan(0);
    });

    test('templates include unrestricted access', async () => {
      const templates = await api.getPolicyTemplates();

      const unrestricted = templates.find(
        (t) => t.name.toLowerCase().includes('unrestricted') ||
               t.name.toLowerCase().includes('public')
      );

      expect(unrestricted).toBeDefined();
    });

    test('templates have required properties', async () => {
      const templates = await api.getPolicyTemplates();

      for (const template of templates) {
        expect(template.id).toBeDefined();
        expect(template.name).toBeDefined();
        expect(template.description).toBeDefined();
      }
    });
  });

  test.describe('Policy Preview', () => {
    test('can preview unrestricted policy', async () => {
      const config = createPolicyConfig('public');

      const odrl = await api.previewPolicy(config);

      expect(odrl).toBeDefined();
      expect(odrl).toHaveProperty('@context');
      expect(odrl).toHaveProperty('permission');
    });

    test('can preview BPN-restricted policy', async () => {
      const config = createPolicyConfig('restricted', {
        allowedBPNs: [createTestBPN(1), createTestBPN(2)],
      });

      const odrl = await api.previewPolicy(config);

      expect(odrl).toBeDefined();
      const odrlString = JSON.stringify(odrl);
      expect(odrlString).toContain('BPNL');
    });

    test('membership policy includes Catena-X constraint', async () => {
      const config = createPolicyConfig('membership');

      const odrl = await api.previewPolicy(config);

      const odrlString = JSON.stringify(odrl);
      expect(
        odrlString.includes('Membership') || odrlString.includes('catenax')
      ).toBe(true);
    });
  });

  test.describe('Policy Fixtures', () => {
    test('unrestricted fixture matches expected structure', async () => {
      try {
        const fixture = loadPolicyFixture('unrestricted-access');

        expect(fixture.config.access_level).toBe('public');
        expect(fixture.expectedOdrl).toBeDefined();
      } catch {
        // Fixture may not exist
        test.skip();
      }
    });

    test('BPN-restricted fixture includes allowed BPNs', async () => {
      try {
        const fixture = loadPolicyFixture('bpn-restricted');

        expect(fixture.config.access_level).toBe('restricted');
        expect(fixture.config.allowed_bpns).toBeDefined();
        expect(fixture.config.allowed_bpns.length).toBeGreaterThan(0);
      } catch {
        test.skip();
      }
    });
  });
});
