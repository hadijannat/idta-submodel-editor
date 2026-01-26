/**
 * SelfDescription - Connector self-description viewer component.
 *
 * Displays connector information including BPN, endpoints, and capabilities
 * in an IDS/Gaia-X style format.
 */

import { useEffect, useState, useCallback } from 'react';
import { getSelfDescription, type SelfDescription as SelfDescriptionData } from '../../services/dataspaceApi';
import './DataspaceConnector.css';

interface SelfDescriptionProps {
  /**
   * Connection ID to show self-description for.
   */
  connectionId: string;
  /**
   * Called when an error occurs.
   */
  onError?: (error: string) => void;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

function getEnvironmentLabel(env: string): string {
  const labels: Record<string, string> = {
    sandbox: 'Local Sandbox',
    'catena-x-test': 'Catena-X Test',
    'catena-x-prod': 'Catena-X Production',
    'manufacturing-x': 'Manufacturing-X',
  };
  return labels[env] || env;
}

function getEdcModeLabel(mode: string): string {
  const labels: Record<string, string> = {
    'tractus-x': 'Tractus-X EDC',
    'aas-extension': 'AAS Extension EDC',
  };
  return labels[mode] || mode;
}

export function SelfDescription({ connectionId, onError }: SelfDescriptionProps) {
  const [data, setData] = useState<SelfDescriptionData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  const loadSelfDescription = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getSelfDescription(connectionId);
      setData(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load self-description';
      setError(message);
      onError?.(message);
    } finally {
      setIsLoading(false);
    }
  }, [connectionId, onError]);

  useEffect(() => {
    loadSelfDescription();
  }, [loadSelfDescription]);

  if (isLoading) {
    return (
      <div className="self-description-loading">
        <span className="spinner" /> Loading self-description...
      </div>
    );
  }

  if (error) {
    return (
      <div className="self-description-error">
        <span className="error-icon">!</span>
        {error}
        <button className="retry-btn" onClick={loadSelfDescription}>
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="self-description">
      {/* Header */}
      <div className="self-description-header">
        <div className="connector-title">
          <h3>{data.title}</h3>
          {data.description && <p className="connector-description">{data.description}</p>}
        </div>
        <button className="refresh-btn" onClick={loadSelfDescription} title="Refresh">
          ↻
        </button>
      </div>

      {/* Identity Section */}
      <div className="self-description-section">
        <h4>Identity</h4>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Connector ID</span>
            <span className="info-value monospace">{data.connector_id}</span>
          </div>
          {data.bpn && (
            <div className="info-item">
              <span className="info-label">Business Partner Number</span>
              <span className="info-value monospace bpn-badge">{data.bpn}</span>
            </div>
          )}
          <div className="info-item">
            <span className="info-label">Environment</span>
            <span className="info-value">
              <span className={`env-badge env-${data.environment}`}>
                {getEnvironmentLabel(data.environment)}
              </span>
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">EDC Mode</span>
            <span className="info-value">{getEdcModeLabel(data.edc_mode)}</span>
          </div>
          <div className="info-item">
            <span className="info-label">Security Profile</span>
            <span className="info-value monospace">{data.security_profile}</span>
          </div>
          {data.maintainer && (
            <div className="info-item">
              <span className="info-label">Maintainer</span>
              <span className="info-value">{data.maintainer}</span>
            </div>
          )}
          <div className="info-item">
            <span className="info-label">Created</span>
            <span className="info-value">{formatDate(data.created_at)}</span>
          </div>
        </div>
      </div>

      {/* Endpoints Section */}
      {data.endpoints.length > 0 && (
        <div className="self-description-section">
          <h4>Endpoints</h4>
          <div className="endpoints-list">
            {data.endpoints.map((endpoint, idx) => (
              <div key={idx} className="endpoint-item">
                <div className="endpoint-header">
                  <span className="endpoint-name">{endpoint.name}</span>
                  <span className={`endpoint-protocol protocol-${endpoint.protocol.toLowerCase().replace(/[^a-z]/g, '')}`}>
                    {endpoint.protocol}
                  </span>
                  {endpoint.healthy !== null && (
                    <span className={`endpoint-health ${endpoint.healthy ? 'healthy' : 'unhealthy'}`}>
                      {endpoint.healthy ? '●' : '○'}
                    </span>
                  )}
                </div>
                <div className="endpoint-url monospace">{endpoint.url}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Capabilities Section */}
      {data.capabilities.length > 0 && (
        <div className="self-description-section">
          <h4>Capabilities</h4>
          <div className="capabilities-list">
            {data.capabilities.map((cap, idx) => (
              <div
                key={idx}
                className={`capability-item ${cap.enabled ? 'enabled' : 'disabled'}`}
              >
                <span className="capability-status">{cap.enabled ? '✓' : '○'}</span>
                <span className="capability-name">{cap.name}</span>
                {cap.version && <span className="capability-version">v{cap.version}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw JSON-LD Section */}
      {data.raw_jsonld && (
        <div className="self-description-section">
          <button
            className="json-toggle"
            onClick={() => setShowRawJson(!showRawJson)}
          >
            {showRawJson ? '▼' : '▶'} Raw JSON-LD
          </button>
          {showRawJson && (
            <pre className="json-viewer">
              {JSON.stringify(data.raw_jsonld, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default SelfDescription;
