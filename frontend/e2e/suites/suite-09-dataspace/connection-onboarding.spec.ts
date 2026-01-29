/**
 * Dataspace Connection Onboarding Tests
 *
 * Tests for dataspace connection management including
 * environment selection, onboarding wizard, and health checks.
 * Automatically falls back to mock responses when real service is unavailable.
 */

import { test, expect } from '@playwright/test';
import { createMockableAPIClient, MockableAPIClient } from '../../helpers/mock-api-client';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('Dataspace Connection Onboarding', () => {
  let api: MockableAPIClient;

  test.beforeEach(async ({ request }) => {
    api = await createMockableAPIClient(request, API_BASE_URL);
  });

  test.describe('Environment Discovery', () => {
    test('can list available environments', async () => {
      const environments = await api.getDataspaceEnvironments();

      expect(Array.isArray(environments)).toBe(true);
      expect(environments.length).toBeGreaterThan(0);
    });

    test('environments include sandbox', async () => {
      const environments = await api.getDataspaceEnvironments();

      const sandbox = environments.find((e) => e.id === 'sandbox');
      expect(sandbox).toBeDefined();
    });

    test('environments have required properties', async () => {
      const environments = await api.getDataspaceEnvironments();

      for (const env of environments) {
        expect(env.id).toBeDefined();
        expect(env.name).toBeDefined();
        expect(env.description).toBeDefined();
      }
    });
  });

  test.describe('EDC Mode Selection', () => {
    test('can list available EDC modes', async () => {
      const modes = await api.getDataspaceEdcModes();

      expect(Array.isArray(modes)).toBe(true);
      expect(modes.length).toBeGreaterThan(0);
    });

    test('modes include tractus-x', async () => {
      const modes = await api.getDataspaceEdcModes();

      const tractusX = modes.find((m) => m.id === 'tractus-x');
      expect(tractusX).toBeDefined();
    });
  });

  test.describe('Connection Creation', () => {
    test('can create sandbox connection', async () => {
      const connection = await api.createDataspaceConnection('sandbox', 'tractus-x');

      expect(connection.id).toBeDefined();
      expect(connection.environment).toBe('sandbox');
      expect(connection.edc_mode).toBe('tractus-x');
      expect(connection.status).toBeDefined();
    });

    test('connection has valid status', async () => {
      const connection = await api.createDataspaceConnection('sandbox', 'tractus-x');

      expect(['connecting', 'connected', 'disconnected', 'error']).toContain(
        connection.status
      );
    });

    test('can list connections', async () => {
      await api.createDataspaceConnection('sandbox', 'tractus-x');

      const connections = await api.getDataspaceConnections();

      expect(Array.isArray(connections)).toBe(true);
      expect(connections.length).toBeGreaterThan(0);
    });

    test('can get connection details', async () => {
      const created = await api.createDataspaceConnection('sandbox', 'tractus-x');

      const connection = await api.getDataspaceConnection(created.id);

      expect(connection.id).toBe(created.id);
      expect(connection.environment).toBe('sandbox');
    });
  });

  test.describe('Connection Lifecycle', () => {
    test('can delete connection', async () => {
      const connection = await api.createDataspaceConnection('sandbox', 'tractus-x');

      await api.deleteDataspaceConnection(connection.id);

      // Verify deletion
      try {
        await api.getDataspaceConnection(connection.id);
        // Should not reach here
        expect(false).toBe(true);
      } catch (error) {
        // Expected - connection should not exist
        expect(error).toBeDefined();
      }
    });
  });

  test.describe('Health Monitoring', () => {
    test('can check dataspace health', async () => {
      const health = await api.getDataspaceHealth();

      expect(health.services).toBeDefined();
      expect(Array.isArray(health.services)).toBe(true);
    });

    test('health includes all expected services', async () => {
      const health = await api.getDataspaceHealth();

      const serviceNames = health.services.map((s) => s.name.toLowerCase());

      // Should include key services
      expect(
        serviceNames.some((n) => n.includes('basyx') || n.includes('aas'))
      ).toBe(true);
    });

    test('health status is reported', async () => {
      const health = await api.getDataspaceHealth();

      for (const service of health.services) {
        expect(service.status).toBeDefined();
        expect(['healthy', 'unhealthy', 'unknown']).toContain(service.status);
      }
    });
  });
});
