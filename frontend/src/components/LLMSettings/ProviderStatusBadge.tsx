/**
 * ProviderStatusBadge - Visual indicator for LLM provider connection status.
 */

import './LLMSettings.css';

export type StatusType = 'connected' | 'checking' | 'error' | 'unconfigured';

interface ProviderStatusBadgeProps {
  status: StatusType;
  message?: string;
  compact?: boolean;
}

export function ProviderStatusBadge({
  status,
  message,
  compact = false,
}: ProviderStatusBadgeProps) {
  const statusConfig = {
    connected: {
      color: 'green',
      label: 'Connected',
      icon: '●',
    },
    checking: {
      color: 'yellow',
      label: 'Checking...',
      icon: '○',
    },
    error: {
      color: 'red',
      label: 'Error',
      icon: '●',
    },
    unconfigured: {
      color: 'gray',
      label: 'Not configured',
      icon: '○',
    },
  };

  const config = statusConfig[status];

  if (compact) {
    return (
      <span
        className={`llm-status-badge llm-status-badge--compact llm-status-badge--${config.color}`}
        title={message || config.label}
      >
        <span className="llm-status-badge__dot">{config.icon}</span>
      </span>
    );
  }

  return (
    <span className={`llm-status-badge llm-status-badge--${config.color}`}>
      <span className="llm-status-badge__dot">{config.icon}</span>
      <span className="llm-status-badge__text">{message || config.label}</span>
    </span>
  );
}

export default ProviderStatusBadge;
