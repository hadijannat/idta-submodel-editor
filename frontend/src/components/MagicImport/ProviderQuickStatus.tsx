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
  onConfigureClick?: () => void;
}

export function ProviderQuickStatus({ onConfigureClick }: ProviderQuickStatusProps) {
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

  return (
    <div className="llm-quick-status">
      <div className="llm-quick-status__info">
        <ProviderStatusBadge
          status={status.healthy ? 'connected' : 'error'}
          compact
        />
        <span className="llm-quick-status__provider">{providerDisplay}</span>
        {status.model && (
          <span className="llm-quick-status__model">· {status.model}</span>
        )}
      </div>
      {onConfigureClick && (
        <button
          type="button"
          className="llm-quick-status__link"
          onClick={onConfigureClick}
        >
          Change Provider →
        </button>
      )}
    </div>
  );
}

export default ProviderQuickStatus;
