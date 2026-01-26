/**
 * ConnectionStatus - Status badge for dataspace connection.
 *
 * Displays the current connection status with appropriate styling
 * and optional progress information.
 */

import type { DataspaceConnectionStatus } from '../../services/dataspaceApi';

interface ConnectionStatusProps {
  status: DataspaceConnectionStatus;
  progress?: number;
  progressMessage?: string | null;
  showProgress?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const STATUS_CONFIG: Record<
  DataspaceConnectionStatus,
  { label: string; color: 'gray' | 'blue' | 'green' | 'yellow' | 'red' }
> = {
  not_connected: { label: 'Not Connected', color: 'gray' },
  provisioning_secrets: { label: 'Provisioning Secrets', color: 'blue' },
  configuring_edc: { label: 'Configuring EDC', color: 'blue' },
  registering_connector: { label: 'Registering Connector', color: 'blue' },
  publishing_self_description: { label: 'Publishing Self-Description', color: 'blue' },
  connected: { label: 'Connected', color: 'green' },
  degraded: { label: 'Degraded', color: 'yellow' },
  disconnected: { label: 'Disconnected', color: 'gray' },
  failed: { label: 'Failed', color: 'red' },
};

export default function ConnectionStatus({
  status,
  progress,
  progressMessage,
  showProgress = false,
  size = 'md',
  className = '',
}: ConnectionStatusProps) {
  const config = STATUS_CONFIG[status] || { label: status, color: 'gray' };
  const isInProgress =
    status !== 'connected' &&
    status !== 'failed' &&
    status !== 'disconnected' &&
    status !== 'not_connected';

  const sizeClasses = {
    sm: 'dataspace-status--sm',
    md: 'dataspace-status--md',
    lg: 'dataspace-status--lg',
  };

  const colorClasses = {
    gray: 'dataspace-status--gray',
    blue: 'dataspace-status--blue',
    green: 'dataspace-status--green',
    yellow: 'dataspace-status--yellow',
    red: 'dataspace-status--red',
  };

  return (
    <div
      className={`dataspace-status ${sizeClasses[size]} ${colorClasses[config.color]} ${className}`}
    >
      <span className="dataspace-status__badge">
        {isInProgress && <span className="dataspace-status__pulse" />}
        <span className="dataspace-status__dot" />
        <span className="dataspace-status__label">{config.label}</span>
      </span>

      {showProgress && isInProgress && progress !== undefined && (
        <div className="dataspace-status__progress">
          <div className="dataspace-status__progress-bar">
            <div
              className="dataspace-status__progress-fill"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <span className="dataspace-status__progress-text">
            {Math.round(progress * 100)}%
          </span>
          {progressMessage && (
            <span className="dataspace-status__progress-message">{progressMessage}</span>
          )}
        </div>
      )}
    </div>
  );
}
