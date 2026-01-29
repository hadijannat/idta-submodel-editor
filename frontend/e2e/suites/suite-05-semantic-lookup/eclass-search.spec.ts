/**
 * ECLASS Semantic Search Tests
 *
 * Tests for ECLASS dictionary lookup functionality.
 * Automatically falls back to mock responses when real service is unavailable.
 */

import { test, expect } from '@playwright/test';
import { createMockableAPIClient, MockableAPIClient } from '../../helpers/mock-api-client';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('ECLASS Semantic Search', () => {
  let api: MockableAPIClient;

  test.beforeEach(async ({ request }) => {
    api = await createMockableAPIClient(request, API_BASE_URL);
  });

  test('can search ECLASS dictionary', async () => {
    const response = await api.searchSemantic('temperature sensor', {
      provider: 'eclass',
      limit: 10,
    });

    expect(response).toBeDefined();
    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test('search results include IRDI', async () => {
    const response = await api.searchSemantic('manufacturer', {
      provider: 'eclass',
      limit: 5,
    });

    expect(response.results.length).toBeGreaterThan(0);
    expect(response.results[0].irdi).toBeDefined();
    // ECLASS IRDI format: 0173-1#XX-XXXXXX#XXX
    expect(response.results[0].irdi).toMatch(/0173-1#/);
  });

  test('search results include preferred name', async () => {
    const response = await api.searchSemantic('serial number', {
      provider: 'eclass',
      limit: 5,
    });

    expect(response.results.length).toBeGreaterThan(0);
    expect(response.results[0].preferredName).toBeDefined();
    expect(response.results[0].preferredName.length).toBeGreaterThan(0);
  });

  test('search results indicate source', async () => {
    const response = await api.searchSemantic('product', {
      provider: 'eclass',
      limit: 5,
    });

    expect(response.results.length).toBeGreaterThan(0);
    expect(response.results[0].source).toBe('eclass');
  });

  test('empty search returns empty results', async () => {
    const response = await api.searchSemantic('xyznonexistentterm123', {
      provider: 'eclass',
      limit: 5,
    });

    expect(response.results).toHaveLength(0);
  });

  test('limit parameter is respected', async () => {
    const response = await api.searchSemantic('sensor', {
      provider: 'eclass',
      limit: 3,
    });

    expect(response.results.length).toBeLessThanOrEqual(3);
  });
});
