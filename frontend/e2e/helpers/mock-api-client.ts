/**
 * Mock API Client Wrapper
 *
 * Provides a wrapper around the real API client that falls back to mock data
 * when services are unavailable. This allows tests to run without external
 * dependencies while still using the same API interface.
 *
 * Usage:
 *   const api = await createMockableAPIClient(request, baseURL);
 *   // Uses real API if available, mock data otherwise
 */

import type { APIRequestContext } from '@playwright/test';
import {
  APIClient,
  type SemanticSearchResponse,
  type MagicImportJob,
  type DataspaceConnection,
  type PolicyTemplate,
} from './api-client';
import {
  isSemanticServiceAvailable,
  isMagicImportServiceAvailable,
  isDataspaceServiceAvailable,
  getMockSemanticSearchResponse,
  getMockMagicImportJob,
  getMockDataspaceEnvironments,
  getMockDataspaceEdcModes,
  getMockDataspaceConnection,
  getMockDataspaceHealth,
  getMockPolicyTemplates,
  getMockPolicyPreview,
} from './mock-services';

export interface MockableAPIClientOptions {
  /** Force mock mode for specific services */
  forceMock?: {
    semantic?: boolean;
    magicImport?: boolean;
    dataspace?: boolean;
  };
}

/**
 * A wrapper around APIClient that can fall back to mock responses.
 */
export class MockableAPIClient extends APIClient {
  private useMockSemantic = false;
  private useMockMagicImport = false;
  private useMockDataspace = false;

  // Mock state for dataspace connections
  private mockConnections = new Map<string, DataspaceConnection>();

  constructor(
    request: APIRequestContext,
    baseURL: string,
    options?: MockableAPIClientOptions
  ) {
    super(request, baseURL);

    if (options?.forceMock?.semantic) this.useMockSemantic = true;
    if (options?.forceMock?.magicImport) this.useMockMagicImport = true;
    if (options?.forceMock?.dataspace) this.useMockDataspace = true;
  }

  /**
   * Initialize mock mode based on service availability.
   * Call this before using the client.
   */
  async initializeMockMode(request: APIRequestContext): Promise<{
    semantic: boolean;
    magicImport: boolean;
    dataspace: boolean;
  }> {
    // Check each service and enable mocks if unavailable
    // Pass baseURL to availability checks for consistency
    if (!this.useMockSemantic) {
      this.useMockSemantic = !(await isSemanticServiceAvailable(request, this.baseURL));
    }
    if (!this.useMockMagicImport) {
      this.useMockMagicImport = !(await isMagicImportServiceAvailable(request, this.baseURL));
    }
    if (!this.useMockDataspace) {
      this.useMockDataspace = !(await isDataspaceServiceAvailable(request, this.baseURL));
    }

    return {
      semantic: this.useMockSemantic,
      magicImport: this.useMockMagicImport,
      dataspace: this.useMockDataspace,
    };
  }

  // --------------------------------------------------------------------------
  // Semantic Search (with mock fallback)
  // --------------------------------------------------------------------------

  override async searchSemantic(
    query: string,
    options?: { provider?: 'eclass' | 'iec_cdd'; limit?: number }
  ): Promise<SemanticSearchResponse> {
    if (this.useMockSemantic) {
      return getMockSemanticSearchResponse(query, options);
    }
    return super.searchSemantic(query, options);
  }

  // --------------------------------------------------------------------------
  // Magic Import (with mock fallback)
  // --------------------------------------------------------------------------

  override async createMagicImportJob(
    pdfFile: Buffer,
    templateName: string,
    options?: { provider?: string; use_ocr?: boolean }
  ): Promise<MagicImportJob> {
    if (this.useMockMagicImport) {
      return getMockMagicImportJob(templateName);
    }
    return super.createMagicImportJob(pdfFile, templateName, options);
  }

  override async getMagicImportJobStatus(jobId: string): Promise<MagicImportJob> {
    if (this.useMockMagicImport) {
      return {
        job_id: jobId,
        status: 'done',
      };
    }
    return super.getMagicImportJobStatus(jobId);
  }

  // --------------------------------------------------------------------------
  // Dataspace (with mock fallback)
  // --------------------------------------------------------------------------

  override async getDataspaceEnvironments(): Promise<
    Array<{ id: string; name: string; description: string }>
  > {
    if (this.useMockDataspace) {
      return getMockDataspaceEnvironments();
    }
    return super.getDataspaceEnvironments();
  }

  override async getDataspaceEdcModes(): Promise<
    Array<{ id: string; name: string; description: string }>
  > {
    if (this.useMockDataspace) {
      return getMockDataspaceEdcModes();
    }
    return super.getDataspaceEdcModes();
  }

  override async createDataspaceConnection(
    environment: string,
    edcMode: string
  ): Promise<DataspaceConnection> {
    if (this.useMockDataspace) {
      const connection = getMockDataspaceConnection(environment, edcMode);
      this.mockConnections.set(connection.connection_id, connection);
      return connection;
    }
    return super.createDataspaceConnection(environment, edcMode);
  }

  override async getDataspaceConnections(): Promise<DataspaceConnection[]> {
    if (this.useMockDataspace) {
      return Array.from(this.mockConnections.values());
    }
    return super.getDataspaceConnections();
  }

  override async getDataspaceConnection(connectionId: string): Promise<DataspaceConnection> {
    if (this.useMockDataspace) {
      const connection = this.mockConnections.get(connectionId);
      if (!connection) {
        throw new Error(`Connection not found: ${connectionId}`);
      }
      return connection;
    }
    return super.getDataspaceConnection(connectionId);
  }

  override async deleteDataspaceConnection(connectionId: string): Promise<void> {
    if (this.useMockDataspace) {
      this.mockConnections.delete(connectionId);
      return;
    }
    return super.deleteDataspaceConnection(connectionId);
  }

  override async getDataspaceHealth(): Promise<{
    services: Array<{ name: string; status: string; latency_ms?: number }>;
  }> {
    if (this.useMockDataspace) {
      return getMockDataspaceHealth();
    }
    return super.getDataspaceHealth();
  }

  override async getPolicyTemplates(): Promise<PolicyTemplate[]> {
    if (this.useMockDataspace) {
      return getMockPolicyTemplates();
    }
    return super.getPolicyTemplates();
  }

  override async previewPolicy(config: object): Promise<object> {
    if (this.useMockDataspace) {
      return getMockPolicyPreview(config as { access_level: string; allowed_bpns?: string[] });
    }
    return super.previewPolicy(config);
  }
}

/**
 * Create a MockableAPIClient that automatically detects service availability
 * and falls back to mocks when needed.
 */
export async function createMockableAPIClient(
  request: APIRequestContext,
  baseURL: string = 'http://localhost:8000',
  options?: MockableAPIClientOptions
): Promise<MockableAPIClient> {
  const client = new MockableAPIClient(request, baseURL, options);
  const mockStatus = await client.initializeMockMode(request);

  if (mockStatus.semantic || mockStatus.magicImport || mockStatus.dataspace) {
    const mocked = [];
    if (mockStatus.semantic) mocked.push('semantic');
    if (mockStatus.magicImport) mocked.push('magic-import');
    if (mockStatus.dataspace) mocked.push('dataspace');
    console.log(`ℹ️  Using mocks for: ${mocked.join(', ')}`);
  }

  return client;
}
