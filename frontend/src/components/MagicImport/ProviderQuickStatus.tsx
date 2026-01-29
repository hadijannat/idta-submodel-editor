/**
 * ProviderQuickStatus - Compact status indicator for Magic Import panel.
 *
 * Shows current LLM provider, model, and connection status.
 * Provides link to configure settings if not set up.
 */

import { useEffect, useState } from 'react';
import { getProviderQuickStatus, type ProviderQuickStatus as StatusType } from '../../services/settingsApi';
import { ProviderStatusBadge } from '../LLMSettings';
import './MagicImport.css';

interface ProviderQuickStatusProps {
  /** Callback when user clicks to configure/change provider */
  onConfigureClick?: () => void;
  /** Callback when user wants to change provider (opens selector) */
  onChangeProviderClick?: () => void;
}

export function ProviderQuickStatus({
  onConfigureClick,
  onChangeProviderClick,
}: ProviderQuickStatusProps) {
  const [status, setStatus] = useState<StatusType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const loadStatus = async () => {
      try {
        const data = await getProviderQuickStatus();
        if (mounted) {
          setStatus(data);
        }
      } catch {
        if (mounted) {
          setStatus({
            configured: false,
            provider: null,
            model: null,
            healthy: false,
            message: 'Could not check status',
          });
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadStatus();

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="llm-quick-status">
        <div className="llm-quick-status__info">
          <span className="llm-quick-status__provider">Checking provider...</span>
        </div>
      </div>
    );
  }

  // Not configured - show warning
  if (!status?.configured) {
    return (
      <div className="llm-quick-status llm-quick-status--warning">
        <div className="llm-quick-status__info">
          <ProviderStatusBadge status="unconfigured" compact />
          <span className="llm-quick-status__provider">No LLM provider configured</span>
        </div>
        {onConfigureClick && (
          <button
            type="button"
            className="llm-quick-status__link"
            onClick={onConfigureClick}
          >
            Configure Now →
          </button>
        )}
      </div>
    );
  }

  // Configured - show status
  const providerDisplay = status.provider
    ? status.provider.charAt(0).toUpperCase() + status.provider.slice(1)
    : 'Unknown';

  // Show privacy indicator for local provider
  const isLocal = status.provider === 'local';

  return (
    <div className={`llm-quick-status ${isLocal ? 'llm-quick-status--local' : ''}`}>
      <div className="llm-quick-status__info">
        <ProviderStatusBadge
          status={status.healthy ? 'connected' : 'error'}
          compact
        />
        <span className="llm-quick-status__provider">{providerDisplay}</span>
        {status.model && (
          <span className="llm-quick-status__model">· {status.model}</span>
        )}
        {/* Privacy indicator */}
        {isLocal && (
          <span className="llm-quick-status__privacy" title="Data stays on your machine">
            🔒
          </span>
        )}
      </div>
      <div className="llm-quick-status__actions">
        {(onChangeProviderClick || onConfigureClick) && (
          <button
            type="button"
            className="llm-quick-status__link"
            onClick={onChangeProviderClick || onConfigureClick}
          >
            Change →
          </button>
        )}
        {onConfigureClick && onChangeProviderClick && (
          <button
            type="button"
            className="llm-quick-status__link llm-quick-status__link--secondary"
            onClick={onConfigureClick}
            title="Configure API keys"
          >
            ⚙️
          </button>
        )}
      </div>
    </div>
  );
}

export default ProviderQuickStatus;
