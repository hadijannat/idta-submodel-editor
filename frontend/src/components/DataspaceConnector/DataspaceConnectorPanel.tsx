/**
 * DataspaceConnectorPanel - Main panel for dataspace publishing wizard step.
 *
 * Orchestrates the dataspace connection, publication, and management flow.
 * This is the primary component used in the wizard step 7.
 */

import { useState, useCallback, useEffect } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import { useDataspace } from './useDataspace';
import { usePublications } from './usePublications';
import OnboardingWizard from './OnboardingWizard';
import ConnectionStatus from './ConnectionStatus';
import PublicationManager from './PublicationManager';
import CatalogBrowser from './CatalogBrowser';
import TransferHistory from './TransferHistory';
import AuditLogViewer from './AuditLogViewer';
import SelfDescription from './SelfDescription';
import {
  listConnections,
  type DataspaceConnection,
  type PolicyConfig,
} from '../../services/dataspaceApi';
import './DataspaceConnector.css';

interface DataspaceConnectorPanelProps {
  templateName: string;
  templateStatus: 'published' | 'deprecated';
  templateVersion?: string | null;
  form: UseFormReturn<SubmodelFormData>;
  schema?: SubmodelUISchema | null;
  onPublished?: () => void;
}

type PanelView = 'loading' | 'onboarding' | 'connected' | 'publishing';
type ConnectedTab = 'publish' | 'catalog' | 'transfers' | 'audit' | 'info';

const TAB_LABELS: Record<ConnectedTab, string> = {
  publish: 'Publish',
  catalog: 'Catalog',
  transfers: 'Transfers',
  audit: 'Audit Log',
  info: 'Connector Info',
};

export default function DataspaceConnectorPanel({
  templateName,
  templateStatus,
  templateVersion,
  form,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  schema: _schema,
  onPublished,
}: DataspaceConnectorPanelProps) {
  const [view, setView] = useState<PanelView>('loading');
  const [activeTab, setActiveTab] = useState<ConnectedTab>('publish');
  const [existingConnection, setExistingConnection] = useState<DataspaceConnection | null>(
    null
  );

  const {
    connection,
    healthChecks,
    isConnecting,
    error: connectionError,
    disconnect,
    refreshStatus,
  } = useDataspace({
    onConnected: () => {
      setView('connected');
    },
  });

  const {
    isPublishing,
    error: publicationError,
    publish,
  } = usePublications();

  // Check for existing connections on mount
  useEffect(() => {
    const checkExistingConnections = async () => {
      try {
        const response = await listConnections(1);
        if (response.connections.length > 0) {
          const activeConnection = response.connections.find(
            (c) => c.status === 'connected'
          );
          if (activeConnection) {
            setExistingConnection(activeConnection);
            setView('connected');
            return;
          }
        }
        setView('onboarding');
      } catch (err) {
        console.error('Failed to check existing connections:', err);
        setView('onboarding');
      }
    };

    checkExistingConnections();
  }, []);

  // Get the active connection
  const activeConnection = connection || existingConnection;

  // Handle publish click
  const handlePublish = useCallback(async () => {
    if (!activeConnection) return;

    const formData = form.getValues();

    // Default policy for now
    const policy: PolicyConfig = {
      access_type: 'membership',
    };

    try {
      setView('publishing');
      await publish(
        activeConnection.connection_id,
        templateName,
        formData as unknown as Record<string, unknown>,
        {
          templateStatus,
          templateVersion,
          policy,
        }
      );
      onPublished?.();
      setView('connected');
    } catch {
      // Error is handled by the hook
      setView('connected');
    }
  }, [
    activeConnection,
    form,
    templateName,
    templateStatus,
    templateVersion,
    publish,
    onPublished,
  ]);

  // Handle disconnect
  const handleDisconnect = useCallback(async () => {
    if (
      window.confirm(
        'Are you sure you want to disconnect from the dataspace? Any unpublished changes will be lost.'
      )
    ) {
      await disconnect(false, true);
      setExistingConnection(null);
      setView('onboarding');
    }
  }, [disconnect]);

  // Handle reconnect
  const handleReconnect = useCallback(() => {
    setExistingConnection(null);
    setView('onboarding');
  }, []);

  // Render loading state
  if (view === 'loading') {
    return (
      <div className="dataspace-connector-panel">
        <div className="dataspace-connector-panel__loading">
          <div className="dataspace-connector-panel__spinner" />
          <p>Checking dataspace connection...</p>
        </div>
      </div>
    );
  }

  // Render onboarding wizard
  if (view === 'onboarding') {
    return (
      <div className="dataspace-connector-panel">
        <div className="dataspace-connector-panel__header">
          <h2>Dataspace Publishing</h2>
          <p className="dataspace-connector-panel__subtitle">
            Connect to a Manufacturing-X / Catena-X dataspace to publish your submodel.
          </p>
        </div>
        <OnboardingWizard
          form={form}
          onConnected={() => setView('connected')}
        />
      </div>
    );
  }

  // Render connected state
  if (view === 'connected' && activeConnection) {
    return (
      <div className="dataspace-connector-panel">
        {/* Compact header with connection status */}
        <div className="dataspace-connector-panel__header dataspace-connector-panel__header--connected">
          <div className="dataspace-connector-panel__header-main">
            <h2>Dataspace</h2>
            <ConnectionStatus status={activeConnection.status} size="sm" />
          </div>
          <div className="dataspace-connector-panel__header-info">
            <span className="dataspace-connector-panel__env-badge">
              {activeConnection.environment === 'sandbox' && 'Sandbox'}
              {activeConnection.environment === 'catena-x-test' && 'Catena-X Test'}
              {activeConnection.environment === 'catena-x-prod' && 'Catena-X Prod'}
              {activeConnection.environment === 'manufacturing-x' && 'Manufacturing-X'}
            </span>
            {activeConnection.bpn && (
              <span className="dataspace-connector-panel__bpn-badge">
                {activeConnection.bpn}
              </span>
            )}
          </div>
          <div className="dataspace-connector-panel__header-actions">
            <button
              type="button"
              className="dataspace-connector-panel__btn--icon"
              onClick={() => refreshStatus()}
              title="Refresh Status"
            >
              ↻
            </button>
            <button
              type="button"
              className="dataspace-connector-panel__btn--icon dataspace-connector-panel__btn--danger"
              onClick={handleDisconnect}
              title="Disconnect"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="dataspace-connector-panel__tabs">
          {(Object.keys(TAB_LABELS) as ConnectedTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={`dataspace-connector-panel__tab ${
                activeTab === tab ? 'dataspace-connector-panel__tab--active' : ''
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="dataspace-connector-panel__tab-content">
          {/* Publish Tab */}
          {activeTab === 'publish' && (
            <div className="dataspace-connector-panel__publish-tab">
              <div className="dataspace-connector-panel__publish-section">
                <h3>Publish Current Submodel</h3>
                <p className="dataspace-connector-panel__publish-desc">
                  Publish the filled {templateName} submodel to the dataspace. This will:
                </p>
                <ul className="dataspace-connector-panel__publish-steps">
                  <li>Create an AAS in the BaSyx repository</li>
                  <li>Register the Digital Twin in the DTR</li>
                  <li>Create an EDC asset with access policies</li>
                  <li>Make the submodel discoverable to dataspace participants</li>
                </ul>

                {connectionError && (
                  <div className="dataspace-connector-panel__error">
                    {connectionError}
                  </div>
                )}

                {publicationError && (
                  <div className="dataspace-connector-panel__error">
                    {publicationError}
                  </div>
                )}

                <button
                  type="button"
                  className="dataspace-connector-panel__btn--primary"
                  onClick={handlePublish}
                  disabled={isPublishing || isConnecting}
                >
                  {isPublishing ? 'Publishing...' : 'Publish to Dataspace'}
                </button>
              </div>

              <div className="dataspace-connector-panel__publications">
                <PublicationManager
                  connectionId={activeConnection.connection_id}
                  onPublish={handlePublish}
                />
              </div>
            </div>
          )}

          {/* Catalog Tab */}
          {activeTab === 'catalog' && (
            <CatalogBrowser
              connectionId={activeConnection.connection_id}
              onNegotiationComplete={(agreementId) => {
                console.log('Negotiation completed:', agreementId);
                // Switch to transfers tab to show the result
                setActiveTab('transfers');
              }}
            />
          )}

          {/* Transfers Tab */}
          {activeTab === 'transfers' && (
            <TransferHistory
              connectionId={activeConnection.connection_id}
            />
          )}

          {/* Audit Log Tab */}
          {activeTab === 'audit' && (
            <AuditLogViewer
              connectionId={activeConnection.connection_id}
            />
          )}

          {/* Connector Info Tab */}
          {activeTab === 'info' && (
            <div className="dataspace-connector-panel__info-tab">
              <SelfDescription
                connectionId={activeConnection.connection_id}
              />

              {/* Health checks section */}
              {healthChecks.length > 0 && (
                <div className="dataspace-connector-panel__health-section">
                  <h4>Component Health</h4>
                  <div className="dataspace-connector-panel__health-checks">
                    {healthChecks.map((check) => (
                      <div
                        key={check.component}
                        className={`dataspace-connector-panel__health-check ${
                          check.healthy
                            ? 'dataspace-connector-panel__health-check--healthy'
                            : 'dataspace-connector-panel__health-check--unhealthy'
                        }`}
                      >
                        <span className="dataspace-connector-panel__health-icon">
                          {check.healthy ? '\u2713' : '\u2717'}
                        </span>
                        <span className="dataspace-connector-panel__health-name">
                          {check.component}
                        </span>
                        {check.latency_ms && (
                          <span className="dataspace-connector-panel__health-latency">
                            {Math.round(check.latency_ms)}ms
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Render publishing state
  if (view === 'publishing') {
    return (
      <div className="dataspace-connector-panel">
        <div className="dataspace-connector-panel__publishing">
          <div className="dataspace-connector-panel__spinner" />
          <h3>Publishing Submodel</h3>
          <p>Creating AAS, registering with DTR, and configuring EDC...</p>
        </div>
      </div>
    );
  }

  // Fallback - show reconnect option
  return (
    <div className="dataspace-connector-panel">
      <div className="dataspace-connector-panel__disconnected">
        <span className="dataspace-connector-panel__disconnected-icon">&#9888;</span>
        <h3>Not Connected</h3>
        <p>
          No active dataspace connection. Connect to a dataspace to publish your
          submodel.
        </p>
        <button
          type="button"
          className="dataspace-connector-panel__btn--primary"
          onClick={handleReconnect}
        >
          Connect to Dataspace
        </button>
      </div>
    </div>
  );
}
