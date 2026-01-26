/**
 * API client for Dataspace Connector service.
 *
 * Provides methods for managing dataspace connections, publications,
 * and policies for Manufacturing-X / Catena-X integration.
 */

import { API_BASE_URL, ApiError, apiFetch } from './api';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type DataspaceConnectionStatus =
  | 'not_connected'
  | 'provisioning_secrets'
  | 'configuring_edc'
  | 'registering_connector'
  | 'publishing_self_description'
  | 'connected'
  | 'degraded'
  | 'disconnected'
  | 'failed';

export type PublicationStatus =
  | 'pending'
  | 'registering'
  | 'publishing'
  | 'published'
  | 'updating'
  | 'unpublishing'
  | 'unpublished'
  | 'failed';

export type AccessType = 'public' | 'restricted' | 'membership';

export type ConstraintOperator =
  | 'eq'
  | 'neq'
  | 'lt'
  | 'gt'
  | 'lteq'
  | 'gteq'
  | 'in'
  | 'hasPart'
  | 'isPartOf'
  | 'isAllOf'
  | 'isAnyOf'
  | 'isNoneOf';

export type Environment =
  | 'sandbox'
  | 'catena-x-test'
  | 'catena-x-prod'
  | 'manufacturing-x';
export type EDCMode = 'tractus-x' | 'aas-extension';

// ---------------------------------------------------------------------------
// Base Types
// ---------------------------------------------------------------------------

export interface HealthCheckResult {
  component: string;
  healthy: boolean;
  latency_ms: number | null;
  message: string | null;
  checked_at: string;
}

export interface PolicyConstraint {
  left_operand: string;
  operator: ConstraintOperator;
  right_operand: string | string[];
}

export interface PolicyConfig {
  target_paths?: string[];
  allowed_partners?: string[];
  access_type?: AccessType;
  constraints?: PolicyConstraint[];
  valid_from?: string | null;
  valid_until?: string | null;
}

// ---------------------------------------------------------------------------
// Connection Types
// ---------------------------------------------------------------------------

export interface DataspaceConnection {
  connection_id: string;
  status: DataspaceConnectionStatus;
  environment: Environment;
  edc_mode: EDCMode;
  bpn: string | null;
  basyx_url: string | null;
  dtr_url: string | null;
  edc_control_url: string | null;
  edc_data_url: string | null;
  progress: number;
  progress_message: string | null;
  error_message: string | null;
  last_health_check: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateConnectionRequest {
  environment: Environment;
  edc_mode?: EDCMode;
  bpn?: string | null;
  credentials?: Record<string, string> | null;
}

export interface CreateConnectionResponse {
  connection: DataspaceConnection;
  message: string;
}

export interface ConnectionStatusResponse {
  connection: DataspaceConnection;
  health_checks: HealthCheckResult[];
}

export interface ListConnectionsResponse {
  connections: DataspaceConnection[];
  total: number;
}

export interface DisconnectRequest {
  force?: boolean;
  unpublish_all?: boolean;
}

export interface DisconnectResponse {
  connection_id: string;
  status: DataspaceConnectionStatus;
  unpublished_count: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Publication Types
// ---------------------------------------------------------------------------

export interface SubmodelPublication {
  publication_id: string;
  connection_id: string;
  template_name: string;
  submodel_id: string;
  status: PublicationStatus;
  aas_endpoint: string | null;
  dtr_asset_id: string | null;
  edc_offer_id: string | null;
  policy_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublishSubmodelRequest {
  connection_id: string;
  template_name: string;
  template_status?: 'published' | 'deprecated';
  template_version?: string | null;
  form_data: Record<string, unknown>;
  aas_id?: string | null;
  submodel_id?: string | null;
  policy?: PolicyConfig | null;
}

export interface PublishSubmodelResponse {
  publication: SubmodelPublication;
  message: string;
}

export interface ListPublicationsResponse {
  publications: SubmodelPublication[];
  total: number;
}

export interface UnpublishRequest {
  remove_from_registry?: boolean;
  remove_from_edc?: boolean;
}

export interface UnpublishResponse {
  publication_id: string;
  status: PublicationStatus;
  message: string;
}

// ---------------------------------------------------------------------------
// Health Types
// ---------------------------------------------------------------------------

export interface HealthCheckResponse {
  connection_id: string;
  overall_healthy: boolean;
  status: DataspaceConnectionStatus;
  checks: HealthCheckResult[];
  checked_at: string;
}

// ---------------------------------------------------------------------------
// Environment/Mode Types
// ---------------------------------------------------------------------------

export interface EnvironmentInfo {
  id: Environment;
  name: string;
  description: string;
  requires_bpn: boolean;
  requires_credentials: boolean;
  is_default: boolean;
}

export interface EDCModeInfo {
  id: EDCMode;
  name: string;
  description: string;
  is_default: boolean;
}

export interface PolicyTemplate {
  id: string;
  name: string;
  description: string;
  access_type: AccessType;
}

// ---------------------------------------------------------------------------
// Connection API
// ---------------------------------------------------------------------------

/**
 * Create a new dataspace connection.
 */
export async function createConnection(
  request: CreateConnectionRequest
): Promise<CreateConnectionResponse> {
  return apiFetch<CreateConnectionResponse>('/api/dataspace/connections', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * List all dataspace connections.
 */
export async function listConnections(
  limit: number = 50
): Promise<ListConnectionsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetch<ListConnectionsResponse>(
    `/api/dataspace/connections?${params}`
  );
}

/**
 * Get a specific connection with health checks.
 */
export async function getConnection(
  connectionId: string
): Promise<ConnectionStatusResponse> {
  return apiFetch<ConnectionStatusResponse>(
    `/api/dataspace/connections/${encodeURIComponent(connectionId)}`
  );
}

/**
 * Delete a connection.
 */
export async function deleteConnection(
  connectionId: string,
  options?: DisconnectRequest
): Promise<DisconnectResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/dataspace/connections/${encodeURIComponent(connectionId)}`,
    {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: options ? JSON.stringify(options) : undefined,
    }
  );

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to delete connection', response.status, details);
  }

  return response.json();
}

/**
 * Reconnect a failed or disconnected connection.
 */
export async function reconnectConnection(
  connectionId: string
): Promise<CreateConnectionResponse> {
  return apiFetch<CreateConnectionResponse>(
    `/api/dataspace/connections/${encodeURIComponent(connectionId)}/reconnect`,
    { method: 'POST' }
  );
}

// ---------------------------------------------------------------------------
// Publication API
// ---------------------------------------------------------------------------

/**
 * Publish a submodel to a dataspace.
 */
export async function createPublication(
  request: PublishSubmodelRequest
): Promise<PublishSubmodelResponse> {
  return apiFetch<PublishSubmodelResponse>('/api/dataspace/publications', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * List publications.
 */
export async function listPublications(
  connectionId?: string,
  templateName?: string,
  status?: PublicationStatus,
  limit: number = 50
): Promise<ListPublicationsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (connectionId) params.set('connection_id', connectionId);
  if (templateName) params.set('template_name', templateName);
  if (status) params.set('status', status);

  return apiFetch<ListPublicationsResponse>(
    `/api/dataspace/publications?${params}`
  );
}

/**
 * Get a specific publication.
 */
export async function getPublication(
  publicationId: string
): Promise<SubmodelPublication> {
  return apiFetch<SubmodelPublication>(
    `/api/dataspace/publications/${encodeURIComponent(publicationId)}`
  );
}

/**
 * Update a publication.
 */
export async function updatePublication(
  publicationId: string,
  request: PublishSubmodelRequest
): Promise<SubmodelPublication> {
  return apiFetch<SubmodelPublication>(
    `/api/dataspace/publications/${encodeURIComponent(publicationId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(request),
    }
  );
}

/**
 * Unpublish a submodel.
 */
export async function deletePublication(
  publicationId: string,
  options?: UnpublishRequest
): Promise<UnpublishResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/dataspace/publications/${encodeURIComponent(publicationId)}`,
    {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: options ? JSON.stringify(options) : undefined,
    }
  );

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to unpublish', response.status, details);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Health & Discovery API
// ---------------------------------------------------------------------------

/**
 * Check health of dataspace components.
 */
export async function checkHealth(
  connectionId?: string
): Promise<HealthCheckResponse> {
  const params = connectionId
    ? new URLSearchParams({ connection_id: connectionId })
    : '';
  return apiFetch<HealthCheckResponse>(
    `/api/dataspace/health${params ? `?${params}` : ''}`
  );
}

/**
 * Get available dataspace environments.
 */
export async function getEnvironments(): Promise<EnvironmentInfo[]> {
  return apiFetch<EnvironmentInfo[]>('/api/dataspace/environments');
}

/**
 * Get available EDC modes.
 */
export async function getEDCModes(): Promise<EDCModeInfo[]> {
  return apiFetch<EDCModeInfo[]>('/api/dataspace/edc-modes');
}

/**
 * Get policy templates.
 */
export async function getPolicyTemplates(): Promise<PolicyTemplate[]> {
  return apiFetch<PolicyTemplate[]>('/api/dataspace/policies/templates');
}

/**
 * Preview a policy configuration.
 */
export async function previewPolicy(
  config: PolicyConfig
): Promise<{ odrl: Record<string, unknown>; valid: boolean; validation_errors: string[] }> {
  return apiFetch('/api/dataspace/policies/preview', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

// ---------------------------------------------------------------------------
// Polling Helper
// ---------------------------------------------------------------------------

/**
 * Poll connection status until connected, failed, or timeout.
 */
export async function pollConnectionStatus(
  connectionId: string,
  onProgress: (connection: DataspaceConnection) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 150 // 5 minutes with 2s interval
): Promise<DataspaceConnection> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await getConnection(connectionId);
    const connection = response.connection;
    onProgress(connection);

    // Terminal states
    if (
      connection.status === 'connected' ||
      connection.status === 'failed' ||
      connection.status === 'disconnected'
    ) {
      return connection;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Connection polling timeout');
}

/**
 * Poll publication status until published, failed, or timeout.
 */
export async function pollPublicationStatus(
  publicationId: string,
  onProgress: (publication: SubmodelPublication) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 60 // 2 minutes with 2s interval
): Promise<SubmodelPublication> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const publication = await getPublication(publicationId);
    onProgress(publication);

    // Terminal states
    if (
      publication.status === 'published' ||
      publication.status === 'failed' ||
      publication.status === 'unpublished'
    ) {
      return publication;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Publication polling timeout');
}
