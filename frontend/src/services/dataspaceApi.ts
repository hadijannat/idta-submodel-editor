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

export interface ConnectorEndpoint {
  name: string;
  url: string;
  protocol: string;
  healthy: boolean | null;
}

export interface ConnectorCapability {
  name: string;
  version: string | null;
  enabled: boolean;
}

export interface SelfDescription {
  connection_id: string;
  connector_id: string;
  bpn: string | null;
  environment: string;
  edc_mode: string;
  title: string;
  description: string | null;
  maintainer: string | null;
  endpoints: ConnectorEndpoint[];
  capabilities: ConnectorCapability[];
  security_profile: string;
  created_at: string;
  raw_jsonld: Record<string, unknown> | null;
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

/**
 * Get connector self-description for a connection.
 */
export async function getSelfDescription(
  connectionId: string
): Promise<SelfDescription> {
  return apiFetch<SelfDescription>(
    `/api/dataspace/connections/${encodeURIComponent(connectionId)}/self-description`
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

// ---------------------------------------------------------------------------
// Catalog Types
// ---------------------------------------------------------------------------

export type NegotiationStatus =
  | 'initial'
  | 'requesting'
  | 'offered'
  | 'agreeing'
  | 'agreed'
  | 'verifying'
  | 'verified'
  | 'finalized'
  | 'terminated'
  | 'error';

export interface CatalogProviderInfo {
  bpn: string;
  name: string | null;
  protocol_address: string;
  last_seen: string | null;
}

export interface CatalogOffer {
  offer_id: string;
  asset_id: string;
  provider_bpn: string;
  policy: Record<string, unknown>;
  properties: Record<string, unknown>;
  content_type: string | null;
  name: string | null;
  description: string | null;
}

export interface SearchCatalogRequest {
  connection_id: string;
  semantic_id?: string | null;
  provider_bpn?: string | null;
  limit?: number;
  offset?: number;
}

export interface SearchCatalogResponse {
  offers: CatalogOffer[];
  total: number;
  has_more: boolean;
}

export interface ListProvidersResponse {
  providers: CatalogProviderInfo[];
}

export interface NegotiateContractRequest {
  connection_id: string;
  provider_address: string;
  offer_id: string;
  asset_id: string;
  policy: Record<string, unknown>;
}

export interface NegotiationResponse {
  negotiation_id: string;
  state: NegotiationStatus;
  agreement_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Catalog API
// ---------------------------------------------------------------------------

/**
 * Search a provider's catalog for available offers.
 */
export async function searchCatalog(
  request: SearchCatalogRequest
): Promise<SearchCatalogResponse> {
  return apiFetch<SearchCatalogResponse>('/api/dataspace/catalog/search', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * List known catalog providers for a connection.
 */
export async function listCatalogProviders(
  connectionId: string
): Promise<ListProvidersResponse> {
  return apiFetch<ListProvidersResponse>(
    `/api/dataspace/catalog/${encodeURIComponent(connectionId)}/providers`
  );
}

/**
 * Add a provider to the known providers list.
 */
export async function addCatalogProvider(
  connectionId: string,
  bpn: string,
  protocolAddress: string,
  name?: string
): Promise<CatalogProviderInfo> {
  const params = new URLSearchParams({
    bpn,
    protocol_address: protocolAddress,
  });
  if (name) params.set('name', name);

  return apiFetch<CatalogProviderInfo>(
    `/api/dataspace/catalog/${encodeURIComponent(connectionId)}/providers?${params}`,
    { method: 'POST' }
  );
}

/**
 * Initiate a contract negotiation for a catalog offer.
 */
export async function initiateCatalogNegotiation(
  request: NegotiateContractRequest
): Promise<NegotiationResponse> {
  return apiFetch<NegotiationResponse>('/api/dataspace/catalog/negotiate', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get the current status of a contract negotiation.
 */
export async function getNegotiationStatus(
  negotiationId: string
): Promise<NegotiationResponse> {
  return apiFetch<NegotiationResponse>(
    `/api/dataspace/catalog/negotiations/${encodeURIComponent(negotiationId)}`
  );
}

/**
 * Poll negotiation status until finalized, terminated, error, or timeout.
 */
export async function pollNegotiationStatus(
  negotiationId: string,
  onProgress: (negotiation: NegotiationResponse) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 90 // 3 minutes with 2s interval
): Promise<NegotiationResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const negotiation = await getNegotiationStatus(negotiationId);
    onProgress(negotiation);

    // Terminal states
    if (
      negotiation.state === 'finalized' ||
      negotiation.state === 'terminated' ||
      negotiation.state === 'error'
    ) {
      return negotiation;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Negotiation polling timeout');
}

// ---------------------------------------------------------------------------
// Transfer Types
// ---------------------------------------------------------------------------

export type TransferStatus =
  | 'initial'
  | 'provisioning'
  | 'provisioned'
  | 'requesting'
  | 'started'
  | 'suspended'
  | 'completed'
  | 'terminated'
  | 'deprovisioning'
  | 'deprovisioned'
  | 'error';

export interface Transfer {
  transfer_id: string;
  connection_id: string;
  agreement_id: string;
  asset_id: string;
  provider_bpn: string;
  consumer_bpn: string | null;
  state: TransferStatus;
  transfer_type: string;
  data_destination: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface InitiateTransferRequest {
  connection_id: string;
  agreement_id: string;
  asset_id: string;
  provider_address: string;
  provider_bpn?: string | null;
  transfer_type?: string;
  data_destination?: string | null;
}

export interface TransferResponse {
  transfer: Transfer;
  message: string;
}

export interface ListTransfersResponse {
  transfers: Transfer[];
  total: number;
}

export interface TransferEDR {
  transfer_id: string;
  endpoint: string;
  auth_type: string;
  auth_token: string;
  expires_at: string | null;
}

export interface TransferEDRResponse {
  edr: TransferEDR;
  valid: boolean;
}

// ---------------------------------------------------------------------------
// Transfer API
// ---------------------------------------------------------------------------

/**
 * Initiate a data transfer after contract negotiation.
 */
export async function initiateTransfer(
  request: InitiateTransferRequest
): Promise<TransferResponse> {
  return apiFetch<TransferResponse>('/api/dataspace/transfers', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * List data transfers.
 */
export async function listTransfers(
  connectionId?: string,
  status?: TransferStatus,
  limit: number = 50
): Promise<ListTransfersResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (connectionId) params.set('connection_id', connectionId);
  if (status) params.set('status', status);

  return apiFetch<ListTransfersResponse>(
    `/api/dataspace/transfers?${params}`
  );
}

/**
 * Get details of a specific transfer.
 */
export async function getTransfer(transferId: string): Promise<Transfer> {
  return apiFetch<Transfer>(
    `/api/dataspace/transfers/${encodeURIComponent(transferId)}`
  );
}

/**
 * Get the EDR for accessing transferred data.
 */
export async function getTransferEDR(
  transferId: string
): Promise<TransferEDRResponse> {
  return apiFetch<TransferEDRResponse>(
    `/api/dataspace/transfers/${encodeURIComponent(transferId)}/edr`
  );
}

/**
 * Terminate an active transfer.
 */
export async function terminateTransfer(transferId: string): Promise<Transfer> {
  return apiFetch<Transfer>(
    `/api/dataspace/transfers/${encodeURIComponent(transferId)}/terminate`,
    { method: 'POST' }
  );
}

/**
 * Poll transfer status until completed, terminated, error, or timeout.
 */
export async function pollTransferStatus(
  transferId: string,
  onProgress: (transfer: Transfer) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 150 // 5 minutes with 2s interval
): Promise<Transfer> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const transfer = await getTransfer(transferId);
    onProgress(transfer);

    // Terminal states
    if (
      transfer.state === 'completed' ||
      transfer.state === 'terminated' ||
      transfer.state === 'error' ||
      transfer.state === 'deprovisioned'
    ) {
      return transfer;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Transfer polling timeout');
}

// ---------------------------------------------------------------------------
// Audit Log Types
// ---------------------------------------------------------------------------

export type AuditEventType =
  // Connection events
  | 'connection_created'
  | 'connection_connected'
  | 'connection_disconnected'
  | 'connection_failed'
  | 'connection_health_check'
  // Publication events
  | 'publication_started'
  | 'publication_completed'
  | 'publication_failed'
  | 'publication_updated'
  | 'publication_unpublished'
  // Catalog events
  | 'catalog_searched'
  | 'provider_added'
  // Negotiation events
  | 'negotiation_initiated'
  | 'negotiation_completed'
  | 'negotiation_failed'
  | 'negotiation_terminated'
  // Transfer events
  | 'transfer_initiated'
  | 'transfer_started'
  | 'transfer_completed'
  | 'transfer_failed'
  | 'transfer_terminated'
  // Policy events
  | 'policy_created'
  | 'policy_updated'
  | 'policy_deleted'
  // General events
  | 'error'
  | 'warning'
  | 'info';

export interface AuditEvent {
  entry_id: string;
  event_type: AuditEventType;
  timestamp: string;
  connection_id: string | null;
  resource_id: string | null;
  resource_type: string | null;
  actor: string | null;
  action: string;
  details: Record<string, unknown>;
  success: boolean;
  error_message: string | null;
}

export interface AuditFilters {
  connection_id?: string | null;
  event_type?: AuditEventType | null;
  resource_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  success?: boolean | null;
  limit?: number;
  offset?: number;
}

export interface ListAuditLogsResponse {
  entries: AuditEvent[];
  total: number;
  has_more: boolean;
}

// ---------------------------------------------------------------------------
// Audit Log API
// ---------------------------------------------------------------------------

/**
 * List audit log entries with optional filters.
 */
export async function listAuditLogs(
  filters?: AuditFilters
): Promise<ListAuditLogsResponse> {
  const params = new URLSearchParams();
  if (filters?.connection_id) params.set('connection_id', filters.connection_id);
  if (filters?.event_type) params.set('event_type', filters.event_type);
  if (filters?.resource_type) params.set('resource_type', filters.resource_type);
  if (filters?.start_date) params.set('start_date', filters.start_date);
  if (filters?.end_date) params.set('end_date', filters.end_date);
  if (filters?.success !== undefined && filters.success !== null) {
    params.set('success', String(filters.success));
  }
  if (filters?.limit) params.set('limit', String(filters.limit));
  if (filters?.offset) params.set('offset', String(filters.offset));

  const queryString = params.toString();
  return apiFetch<ListAuditLogsResponse>(
    `/api/dataspace/audit${queryString ? `?${queryString}` : ''}`
  );
}

/**
 * Get a specific audit log entry.
 */
export async function getAuditEntry(entryId: string): Promise<AuditEvent> {
  return apiFetch<AuditEvent>(
    `/api/dataspace/audit/${encodeURIComponent(entryId)}`
  );
}
