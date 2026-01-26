/**
 * PolicyPreview - Live ODRL JSON preview with validation warnings.
 *
 * Shows the generated ODRL policy JSON and displays any validation
 * errors or warnings from the backend policy preview API.
 */

import React, { useEffect, useState, useCallback } from 'react';
import type { PolicyConfig } from '../../services/dataspaceApi';
import { previewPolicy } from '../../services/dataspaceApi';

interface PolicyPreviewProps {
  /** Policy configuration to preview */
  config: PolicyConfig;
  /** Whether to auto-update preview */
  autoUpdate?: boolean;
  /** Debounce delay in ms */
  debounceMs?: number;
}

interface PreviewState {
  odrl: Record<string, unknown> | null;
  valid: boolean;
  validationErrors: string[];
  loading: boolean;
  error: string | null;
}

/**
 * PolicyPreview component
 */
export const PolicyPreview: React.FC<PolicyPreviewProps> = ({
  config,
  autoUpdate = true,
  debounceMs = 500,
}) => {
  const [state, setState] = useState<PreviewState>({
    odrl: null,
    valid: true,
    validationErrors: [],
    loading: false,
    error: null,
  });
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Fetch preview from API
  const fetchPreview = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const result = await previewPolicy(config);
      setState({
        odrl: result.odrl,
        valid: result.valid,
        validationErrors: result.validation_errors || [],
        loading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to preview policy',
      }));
    }
  }, [config]);

  // Auto-update with debounce
  useEffect(() => {
    if (!autoUpdate) return;

    const timer = setTimeout(() => {
      fetchPreview();
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [config, autoUpdate, debounceMs, fetchPreview]);

  // Copy to clipboard
  const handleCopy = useCallback(async () => {
    if (!state.odrl) return;

    try {
      await navigator.clipboard.writeText(JSON.stringify(state.odrl, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = JSON.stringify(state.odrl, null, 2);
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [state.odrl]);

  // Format ODRL for display
  const formattedODRL = state.odrl
    ? JSON.stringify(state.odrl, null, expanded ? 2 : 1)
    : '// Policy preview will appear here';

  return (
    <div className="policy-preview">
      {/* Actions */}
      <div className="policy-preview__actions">
        <button
          type="button"
          className={`policy-preview__copy-btn ${copied ? 'policy-preview__copy-btn--success' : ''}`}
          onClick={handleCopy}
          disabled={!state.odrl}
        >
          {copied ? '\u2713 Copied' : 'Copy'}
        </button>
        <button
          type="button"
          className="policy-preview__expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Compact' : 'Expand'}
        </button>
        {!autoUpdate && (
          <button
            type="button"
            className="policy-preview__expand-btn"
            onClick={fetchPreview}
            disabled={state.loading}
          >
            Refresh
          </button>
        )}
      </div>

      {/* Loading State */}
      {state.loading && (
        <div className="policy-preview__loading">
          <div className="policy-preview__spinner" />
          Generating preview...
        </div>
      )}

      {/* Error State */}
      {state.error && (
        <div className="policy-preview__error">
          <span>Error:</span> {state.error}
        </div>
      )}

      {/* Validation Status */}
      {!state.loading && !state.error && (
        <>
          {state.valid ? (
            <div className="policy-preview__valid">
              <span>{'\u2713'}</span>
              Policy configuration is valid
            </div>
          ) : (
            <div className="policy-preview__warnings">
              {state.validationErrors.map((error, idx) => (
                <div key={idx} className="policy-preview__warning">
                  <span className="policy-preview__warning-icon">{'\u26A0'}</span>
                  {error}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ODRL Preview */}
      {!state.loading && (
        <pre className="policy-preview__code">
          {formattedODRL}
        </pre>
      )}
    </div>
  );
};

export default PolicyPreview;
