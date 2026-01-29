/**
 * Mock Services for E2E Tests
 *
 * Provides API mocking for tests that would otherwise require external services
 * (Magic Import, Dataspace, Semantic Search, etc.).
 *
 * Two mocking strategies:
 * 1. Page-level: Uses page.route() to intercept browser fetch calls (for UI tests)
 * 2. API-level: Returns mock data directly from API client methods (for API tests)
 *
 * Usage:
 *   import { mockSemanticSearch, createMockAPIClient } from './mock-services';
 *
 *   // For UI tests
 *   test.beforeEach(async ({ page }) => {
 *     await mockSemanticSearch(page);
 *   });
 *
 *   // For API tests - use mock data functions directly
 */

import type { Page, APIRequestContext } from '@playwright/test';
import type {
  SemanticSearchResponse,
  MagicImportJob,
  DataspaceConnection,
  PolicyTemplate,
} from './api-client';

// ============================================================================
// Service Availability Checks
// ============================================================================

/**
 * Check if a service endpoint is available via GET.
 */
export async function isServiceAvailableGet(
  request: APIRequestContext,
  url: string,
  timeout = 5000
): Promise<boolean> {
  try {
    const response = await request.get(url, { timeout });
    return response.ok();
  } catch {
    return false;
  }
}

/**
 * Check if a service endpoint is available via POST.
 */
export async function isServiceAvailablePost(
  request: APIRequestContext,
  url: string,
  timeout = 5000
): Promise<boolean> {
  try {
    const response = await request.post(url, { timeout, data: {} });
    return response.ok();
  } catch {
    return false;
  }
}

/**
 * Check if semantic search service is available.
 * Uses /api/semantic/providers endpoint since there's no dedicated health endpoint.
 */
export async function isSemanticServiceAvailable(
  request: APIRequestContext,
  baseURL: string = process.env.VITE_API_URL || 'http://localhost:8000'
): Promise<boolean> {
  return isServiceAvailableGet(request, `${baseURL}/api/semantic/providers`);
}

/**
 * Check if magic import service is available.
 * Uses POST /api/magic-import/health as per backend router.
 */
export async function isMagicImportServiceAvailable(
  request: APIRequestContext,
  baseURL: string = process.env.VITE_API_URL || 'http://localhost:8000'
): Promise<boolean> {
  return isServiceAvailablePost(request, `${baseURL}/api/magic-import/health`);
}

/**
 * Check if dataspace service is available.
 * Uses GET /api/dataspace/health as per backend router.
 */
export async function isDataspaceServiceAvailable(
  request: APIRequestContext,
  baseURL: string = process.env.VITE_API_URL || 'http://localhost:8000'
): Promise<boolean> {
  return isServiceAvailableGet(request, `${baseURL}/api/dataspace/health`);
}

// ============================================================================
// Semantic Search Mocks
// ============================================================================

/**
 * Mock data for ECLASS semantic search.
 */
const MOCK_ECLASS_RESULTS = {
  'temperature sensor': [
    {
      irdi: '0173-1#02-AAH123#001',
      preferredName: 'Temperature sensor',
      definition: 'A device that measures temperature',
      source: 'eclass',
      score: 0.95,
    },
    {
      irdi: '0173-1#02-AAH124#001',
      preferredName: 'Temperature transmitter',
      definition: 'A device that transmits temperature readings',
      source: 'eclass',
      score: 0.85,
    },
  ],
  manufacturer: [
    {
      irdi: '0173-1#02-AAO677#002',
      preferredName: 'Manufacturer name',
      definition: 'Legally valid designation of the natural or judicial body',
      source: 'eclass',
      score: 0.98,
    },
  ],
  'serial number': [
    {
      irdi: '0173-1#02-AAM556#002',
      preferredName: 'Serial number',
      definition: 'Unique combination of numbers and letters used to identify the device',
      source: 'eclass',
      score: 0.97,
    },
  ],
  product: [
    {
      irdi: '0173-1#02-AAY813#001',
      preferredName: 'Product designation',
      definition: 'Short description of the product',
      source: 'eclass',
      score: 0.92,
    },
    {
      irdi: '0173-1#02-AAO736#002',
      preferredName: 'Product type',
      definition: 'Designation of the product type',
      source: 'eclass',
      score: 0.88,
    },
  ],
  sensor: [
    {
      irdi: '0173-1#02-AAH123#001',
      preferredName: 'Temperature sensor',
      definition: 'A device that measures temperature',
      source: 'eclass',
      score: 0.90,
    },
    {
      irdi: '0173-1#02-AAI456#001',
      preferredName: 'Pressure sensor',
      definition: 'A device that measures pressure',
      source: 'eclass',
      score: 0.88,
    },
    {
      irdi: '0173-1#02-AAJ789#001',
      preferredName: 'Position sensor',
      definition: 'A device that detects position',
      source: 'eclass',
      score: 0.85,
    },
  ],
};

/**
 * Get mock semantic search results based on query.
 */
function getMockSemanticResults(query: string, limit: number) {
  const lowerQuery = query.toLowerCase();

  // Check for exact or partial matches
  for (const [key, results] of Object.entries(MOCK_ECLASS_RESULTS)) {
    if (lowerQuery.includes(key) || key.includes(lowerQuery)) {
      return results.slice(0, limit);
    }
  }

  // No matches found
  return [];
}

/**
 * Mock semantic search API endpoints.
 */
export async function mockSemanticSearch(page: Page): Promise<void> {
  await page.route('**/api/semantic/search**', async (route) => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get('q') || url.searchParams.get('query') || '';
    const limit = parseInt(url.searchParams.get('limit') || '10', 10);

    const results = getMockSemanticResults(query, limit);

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results,
        query,
        total: results.length,
        provider: 'eclass',
      }),
    });
  });

  await page.route('**/api/semantic/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'healthy', mocked: true }),
    });
  });
}

// ============================================================================
// Magic Import Mocks
// ============================================================================

/**
 * Mock Magic Import API endpoints.
 */
export async function mockMagicImport(page: Page): Promise<void> {
  // Mock job storage
  const jobs = new Map<string, {
    job_id: string;
    status: string;
    template: string;
    created_at: string;
    extractions: Array<{
      field: string;
      value: string;
      confidence: number;
      evidence?: { page: number; bbox: number[] };
    }>;
  }>();

  // Mock health endpoint
  await page.route('**/api/magic-import/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'healthy', mocked: true }),
    });
  });

  // Mock create job endpoint (POST /api/magic-import/jobs)
  await page.route('**/api/magic-import/jobs', async (route) => {
    // Only handle POST requests for job creation
    if (route.request().method() !== 'POST') {
      await route.fallback();
      return;
    }

    const jobId = `mock-job-${Date.now()}`;
    const job = {
      job_id: jobId,
      status: 'done',
      template: 'Digital Nameplate',
      created_at: new Date().toISOString(),
      extractions: [
        {
          field: 'ManufacturerName',
          value: 'ACME Corporation',
          confidence: 0.95,
          evidence: { page: 1, bbox: [100, 200, 300, 220] },
        },
        {
          field: 'ManufacturerProductDesignation',
          value: 'Industrial Sensor Model X',
          confidence: 0.92,
          evidence: { page: 1, bbox: [100, 240, 350, 260] },
        },
        {
          field: 'SerialNumber',
          value: 'SN-2024-001234',
          confidence: 0.98,
          evidence: { page: 1, bbox: [100, 280, 250, 300] },
        },
        {
          field: 'YearOfConstruction',
          value: '2024',
          confidence: 0.89,
          evidence: { page: 1, bbox: [100, 320, 180, 340] },
        },
        {
          field: 'URIOfTheProduct',
          value: 'https://acme.com/products/sensor-x',
          confidence: 0.75,
          evidence: { page: 2, bbox: [50, 100, 400, 120] },
        },
      ],
    };

    jobs.set(jobId, job);

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(job),
    });
  });

  // Mock job result endpoint (GET /api/magic-import/jobs/{id}/result)
  // Must be defined BEFORE the wildcard route to take precedence
  await page.route('**/api/magic-import/jobs/*/result', async (route) => {
    const url = route.request().url();
    const pathParts = url.split('/');
    const jobIdIndex = pathParts.findIndex(p => p === 'jobs') + 1;
    const jobId = pathParts[jobIdIndex];

    const job = jobId ? jobs.get(jobId) : undefined;
    const extractions = job?.extractions || [
      { field: 'ManufacturerName', value: 'Mock Manufacturer', confidence: 0.95 },
    ];

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: jobId,
        status: 'done',
        extractions,
      }),
    });
  });

  // Mock job PDF endpoint (GET /api/magic-import/jobs/{id}/pdf)
  await page.route('**/api/magic-import/jobs/*/pdf', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: Buffer.from('%PDF-1.4 Mock Job PDF'),
    });
  });

  // Mock job status endpoint (GET /api/magic-import/jobs/{id})
  // Note: This must come AFTER the more specific routes above
  await page.route('**/api/magic-import/jobs/*', async (route) => {
    const url = route.request().url();
    // Extract jobId - it's the segment after 'jobs'
    const pathParts = url.split('/');
    const jobsIndex = pathParts.findIndex(p => p === 'jobs');
    const jobId = jobsIndex >= 0 ? pathParts[jobsIndex + 1] : undefined;

    // Skip if this is a sub-path (result, pdf, etc.) - those have their own handlers
    if (jobId && (jobId === 'result' || jobId === 'pdf' || jobId === 'approve' || jobId === 'audit-report')) {
      await route.fallback();
      return;
    }

    if (jobId && jobs.has(jobId)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(jobs.get(jobId)),
      });
    } else {
      // Return a default done job for any ID
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: jobId,
          status: 'done',
          template: 'Digital Nameplate',
          extractions: [
            {
              field: 'ManufacturerName',
              value: 'Mock Manufacturer',
              confidence: 0.95,
            },
          ],
        }),
      });
    }
  });

  // Mock extraction review endpoint
  await page.route('**/api/magic-import/jobs/*/approve', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    });
  });

  // Mock audit report endpoint
  await page.route('**/api/magic-import/jobs/*/audit-report', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: Buffer.from('%PDF-1.4 Mock Audit Report'),
    });
  });
}

// ============================================================================
// Dataspace Mocks
// ============================================================================

/**
 * Mock Dataspace API endpoints.
 */
export async function mockDataspace(page: Page): Promise<void> {
  // Mock connection storage
  const connections = new Map<string, {
    id: string;
    environment: string;
    edc_mode: string;
    status: string;
    created_at: string;
  }>();

  // Mock health endpoint
  await page.route('**/api/dataspace/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        mocked: true,
        services: [
          { name: 'BaSyx AAS Server', status: 'healthy', url: 'http://mock:4001' },
          { name: 'BaSyx Registry', status: 'healthy', url: 'http://mock:4002' },
          { name: 'EDC Control Plane', status: 'healthy', url: 'http://mock:19192' },
          { name: 'EDC Data Plane', status: 'healthy', url: 'http://mock:19291' },
          { name: 'Digital Twin Registry', status: 'healthy', url: 'http://mock:4003' },
          { name: 'Vault', status: 'healthy', url: 'http://mock:8200' },
        ],
      }),
    });
  });

  // Mock environments endpoint
  await page.route('**/api/dataspace/environments', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'sandbox',
          name: 'Sandbox Environment',
          description: 'Local development environment for testing',
        },
        {
          id: 'catena-x-test',
          name: 'Catena-X Test',
          description: 'Catena-X test network',
        },
        {
          id: 'catena-x-prod',
          name: 'Catena-X Production',
          description: 'Catena-X production network',
        },
      ]),
    });
  });

  // Mock EDC modes endpoint
  await page.route('**/api/dataspace/edc-modes', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'tractus-x',
          name: 'Tractus-X EDC',
          description: 'Eclipse Tractus-X EDC Connector',
        },
        {
          id: 'aas-extension',
          name: 'AAS Extension',
          description: 'EDC with AAS Extension for direct AAS integration',
        },
      ]),
    });
  });

  // Mock connections list endpoint
  await page.route('**/api/dataspace/connections', async (route, request) => {
    if (request.method() === 'POST') {
      // Create connection
      const body = request.postDataJSON();
      const id = `mock-conn-${Date.now()}`;
      const connection = {
        id,
        environment: body?.environment || 'sandbox',
        edc_mode: body?.edc_mode || 'tractus-x',
        status: 'connected',
        created_at: new Date().toISOString(),
      };

      connections.set(id, connection);

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(connection),
      });
    } else {
      // List connections
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(Array.from(connections.values())),
      });
    }
  });

  // Mock individual connection endpoint
  await page.route('**/api/dataspace/connections/*', async (route, request) => {
    const url = route.request().url();
    const connId = url.split('/').pop();

    if (request.method() === 'DELETE') {
      if (connId) {
        connections.delete(connId);
      }
      await route.fulfill({ status: 204 });
    } else {
      if (connId && connections.has(connId)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(connections.get(connId)),
        });
      } else {
        await route.fulfill({ status: 404 });
      }
    }
  });

  // Mock policy templates endpoint
  await page.route('**/api/dataspace/policies/templates', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'unrestricted',
          name: 'Unrestricted Access',
          description: 'No access restrictions',
        },
        {
          id: 'membership',
          name: 'Membership Required',
          description: 'Requires dataspace membership credential',
        },
        {
          id: 'bpn-restricted',
          name: 'BPN Restricted',
          description: 'Restricted to specific business partner numbers',
        },
      ]),
    });
  });

  // Mock publications endpoint
  await page.route('**/api/dataspace/publications', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

// ============================================================================
// Mock Data Functions (for direct use in API tests)
// ============================================================================

/**
 * Get mock semantic search results.
 * Use this in API tests to simulate responses.
 */
export function getMockSemanticSearchResponse(
  query: string,
  options?: { limit?: number }
): SemanticSearchResponse {
  const limit = options?.limit ?? 10;
  const results = getMockSemanticResults(query, limit);

  return {
    results: results.map((r) => ({
      irdi: r.irdi,
      preferredName: r.preferredName,
      definition: r.definition,
      source: r.source as 'eclass' | 'iec_cdd',
    })),
    query,
    total: results.length,
  };
}

/**
 * Get mock Magic Import job response.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getMockMagicImportJob(_template: string): MagicImportJob & {
  extractions: Array<{
    field: string;
    value: string;
    confidence: number;
  }>;
} {
  return {
    job_id: `mock-job-${Date.now()}`,
    status: 'done',
    extractions: [
      { field: 'ManufacturerName', value: 'ACME Corporation', confidence: 0.95 },
      { field: 'ManufacturerProductDesignation', value: 'Industrial Sensor Model X', confidence: 0.92 },
      { field: 'SerialNumber', value: 'SN-2024-001234', confidence: 0.98 },
      { field: 'YearOfConstruction', value: '2024', confidence: 0.89 },
      { field: 'URIOfTheProduct', value: 'https://acme.com/products/sensor-x', confidence: 0.75 },
    ],
  };
}

/**
 * Get mock dataspace environments.
 */
export function getMockDataspaceEnvironments(): Array<{ id: string; name: string; description: string }> {
  return [
    { id: 'sandbox', name: 'Sandbox Environment', description: 'Local development environment for testing' },
    { id: 'catena-x-test', name: 'Catena-X Test', description: 'Catena-X test network' },
    { id: 'catena-x-prod', name: 'Catena-X Production', description: 'Catena-X production network' },
  ];
}

/**
 * Get mock EDC modes.
 */
export function getMockDataspaceEdcModes(): Array<{ id: string; name: string; description: string }> {
  return [
    { id: 'tractus-x', name: 'Tractus-X EDC', description: 'Eclipse Tractus-X EDC Connector' },
    { id: 'aas-extension', name: 'AAS Extension', description: 'EDC with AAS Extension for direct AAS integration' },
  ];
}

/**
 * Get mock dataspace connection.
 */
export function getMockDataspaceConnection(
  environment: string,
  edcMode: string
): DataspaceConnection {
  return {
    id: `mock-conn-${Date.now()}`,
    environment,
    edc_mode: edcMode,
    status: 'connected',
    created_at: new Date().toISOString(),
  };
}

/**
 * Get mock dataspace health.
 */
export function getMockDataspaceHealth(): {
  services: Array<{ name: string; status: string; url?: string }>;
} {
  return {
    services: [
      { name: 'BaSyx AAS Server', status: 'healthy', url: 'http://mock:4001' },
      { name: 'BaSyx Registry', status: 'healthy', url: 'http://mock:4002' },
      { name: 'EDC Control Plane', status: 'healthy', url: 'http://mock:19192' },
      { name: 'EDC Data Plane', status: 'healthy', url: 'http://mock:19291' },
      { name: 'Digital Twin Registry', status: 'healthy', url: 'http://mock:4003' },
      { name: 'Vault', status: 'healthy', url: 'http://mock:8200' },
    ],
  };
}

/**
 * Get mock policy templates.
 */
export function getMockPolicyTemplates(): PolicyTemplate[] {
  return [
    {
      id: 'unrestricted',
      name: 'Unrestricted Access',
      description: 'No access restrictions',
      odrl: {
        '@context': 'http://www.w3.org/ns/odrl.jsonld',
        '@type': 'Set',
        permission: [{ target: 'urn:target', action: 'use' }],
      },
    },
    {
      id: 'membership',
      name: 'Membership Required',
      description: 'Requires dataspace membership credential',
      odrl: {
        '@context': 'http://www.w3.org/ns/odrl.jsonld',
        '@type': 'Set',
        permission: [{
          target: 'urn:target',
          action: 'use',
          constraint: { leftOperand: 'Membership', operator: 'eq', rightOperand: 'active' },
        }],
      },
    },
    {
      id: 'bpn-restricted',
      name: 'BPN Restricted',
      description: 'Restricted to specific business partner numbers',
      odrl: {
        '@context': 'http://www.w3.org/ns/odrl.jsonld',
        '@type': 'Set',
        permission: [{
          target: 'urn:target',
          action: 'use',
          constraint: { leftOperand: 'BusinessPartnerNumber', operator: 'isAnyOf', rightOperand: [] },
        }],
      },
    },
  ];
}

/**
 * Get mock policy preview.
 */
export function getMockPolicyPreview(config: {
  access_level: string;
  allowed_bpns?: string[];
}): object {
  const baseOdrl = {
    '@context': 'http://www.w3.org/ns/odrl.jsonld',
    '@type': 'Set',
    permission: [] as object[],
  };

  if (config.access_level === 'public') {
    baseOdrl.permission.push({ target: 'urn:target', action: 'use' });
  } else if (config.access_level === 'membership') {
    baseOdrl.permission.push({
      target: 'urn:target',
      action: 'use',
      constraint: { leftOperand: 'Membership', operator: 'eq', rightOperand: 'active' },
    });
  } else if (config.access_level === 'restricted' && config.allowed_bpns) {
    baseOdrl.permission.push({
      target: 'urn:target',
      action: 'use',
      constraint: {
        leftOperand: 'BusinessPartnerNumber',
        operator: 'isAnyOf',
        rightOperand: config.allowed_bpns,
      },
    });
  }

  return baseOdrl;
}

// ============================================================================
// Combined Setup
// ============================================================================

/**
 * Mock all external services.
 * Use this when running tests without any external dependencies.
 */
export async function mockAllServices(page: Page): Promise<void> {
  await mockSemanticSearch(page);
  await mockMagicImport(page);
  await mockDataspace(page);
}

/**
 * Setup mocks conditionally based on service availability.
 * Real services are used when available, mocks when not.
 */
export async function setupConditionalMocks(
  page: Page,
  request: APIRequestContext
): Promise<{ semantic: boolean; magicImport: boolean; dataspace: boolean }> {
  const results = {
    semantic: false,
    magicImport: false,
    dataspace: false,
  };

  // Check and mock semantic service
  if (!(await isSemanticServiceAvailable(request))) {
    await mockSemanticSearch(page);
    results.semantic = true;
  }

  // Check and mock magic import service
  if (!(await isMagicImportServiceAvailable(request))) {
    await mockMagicImport(page);
    results.magicImport = true;
  }

  // Check and mock dataspace service
  if (!(await isDataspaceServiceAvailable(request))) {
    await mockDataspace(page);
    results.dataspace = true;
  }

  return results;
}
