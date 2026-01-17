/**
 * ErrorBoundary - Graceful error handling for passport card components.
 *
 * Catches JavaScript errors in the card component tree and displays
 * a fallback UI instead of crashing the entire application.
 */

import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import { usePassportI18n } from './i18n';

interface ErrorBoundaryProps {
  /** Child components to protect */
  children: ReactNode;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
  /** Callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Default fallback UI when no custom fallback is provided.
 * Uses i18n hook for internationalized messages.
 */
function DefaultErrorFallback({ error, onRetry }: { error: Error | null; onRetry: () => void }) {
  const { t } = usePassportI18n();

  return (
    <div className="passport-error-boundary" role="alert">
      <div className="passport-error-content">
        <div className="passport-error-icon" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h3 className="passport-error-title">{t('error.title')}</h3>
        <p className="passport-error-message">
          {t('error.description')}
          {error?.message && (
            <span className="passport-error-details">
              {' '}({error.message})
            </span>
          )}
        </p>
        <div className="passport-error-actions">
          <button
            type="button"
            className="passport-error-retry"
            onClick={onRetry}
          >
            {t('error.retry')}
          </button>
          <span className="passport-error-hint">
            {t('error.editorHint')}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * ErrorBoundary component.
 *
 * Wraps passport card components to catch and handle rendering errors
 * gracefully, preventing crashes from propagating to the parent app.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error for debugging
    console.error('[PassportMode] Error caught by ErrorBoundary:', error);
    console.error('[PassportMode] Component stack:', errorInfo.componentStack);

    // Notify parent if callback provided
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (hasError) {
      if (fallback !== undefined) {
        return fallback;
      }
      return <DefaultErrorFallback error={error} onRetry={this.handleRetry} />;
    }

    return children;
  }
}

export default ErrorBoundary;
