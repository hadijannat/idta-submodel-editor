/**
 * MnestixBrowser - Embeds the Mnestix AAS Browser in an iframe.
 *
 * Provides a full-page view of the Mnestix AAS browser with:
 * - Automatic configuration from backend settings
 * - Loading state with spinner
 * - Error handling for unavailable Mnestix
 * - Responsive sizing
 */

import { useState, useEffect, useCallback } from 'react';
import { getPublicSettings, type PublicSettings } from '../../services/api';
import './MnestixBrowser.css';

interface MnestixBrowserProps {
  /** Optional callback when the browser is closed */
  onClose?: () => void;
}

type BrowserState = 'loading' | 'ready' | 'error' | 'disabled';

export default function MnestixBrowser({ onClose }: MnestixBrowserProps) {
  const [state, setState] = useState<BrowserState>('loading');
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [iframeLoading, setIframeLoading] = useState(true);

  // Load settings on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const publicSettings = await getPublicSettings();
        setSettings(publicSettings);

        if (!publicSettings.mnestix_enabled) {
          setState('disabled');
          return;
        }

        if (!publicSettings.mnestix_url) {
          setError('Mnestix URL is not configured');
          setState('error');
          return;
        }

        setState('ready');
      } catch (err) {
        console.error('Failed to load Mnestix settings:', err);
        setError('Failed to load browser settings');
        setState('error');
      }
    };

    loadSettings();
  }, []);

  // Handle iframe load
  const handleIframeLoad = useCallback(() => {
    setIframeLoading(false);
  }, []);

  // Handle iframe error
  const handleIframeError = useCallback(() => {
    setIframeLoading(false);
    setError('Failed to load the AAS Browser');
    setState('error');
  }, []);

  // Build the Mnestix URL with registry parameter
  const buildMnestixUrl = useCallback(() => {
    if (!settings?.mnestix_url) return '';

    const url = new URL(settings.mnestix_url);

    // Add the AAS registry URL as a parameter if available
    if (settings.basyx_registry_url) {
      url.searchParams.set('aasRegistry', settings.basyx_registry_url);
    }

    return url.toString();
  }, [settings]);

  // Render loading state
  if (state === 'loading') {
    return (
      <div className="mnestix-browser">
        <div className="mnestix-browser__loading">
          <div className="mnestix-browser__spinner" />
          <p>Loading AAS Browser...</p>
        </div>
      </div>
    );
  }

  // Render disabled state
  if (state === 'disabled') {
    return (
      <div className="mnestix-browser">
        <div className="mnestix-browser__disabled">
          <span className="mnestix-browser__icon">&#128274;</span>
          <h3>AAS Browser Not Available</h3>
          <p>
            The Mnestix AAS Browser is not enabled in this deployment. Contact your
            administrator to enable it.
          </p>
          {onClose && (
            <button
              type="button"
              className="mnestix-browser__btn--secondary"
              onClick={onClose}
            >
              Go Back
            </button>
          )}
        </div>
      </div>
    );
  }

  // Render error state
  if (state === 'error') {
    return (
      <div className="mnestix-browser">
        <div className="mnestix-browser__error">
          <span className="mnestix-browser__icon">&#9888;</span>
          <h3>Failed to Load AAS Browser</h3>
          <p>{error || 'An unexpected error occurred'}</p>
          <div className="mnestix-browser__error-actions">
            <button
              type="button"
              className="mnestix-browser__btn--primary"
              onClick={() => window.location.reload()}
            >
              Retry
            </button>
            {onClose && (
              <button
                type="button"
                className="mnestix-browser__btn--secondary"
                onClick={onClose}
              >
                Go Back
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Render the iframe
  const mnestixUrl = buildMnestixUrl();

  return (
    <div className="mnestix-browser">
      <div className="mnestix-browser__header">
        <div className="mnestix-browser__title">
          <h2>AAS Browser</h2>
          <span className="mnestix-browser__subtitle">
            Powered by Mnestix
          </span>
        </div>
        <div className="mnestix-browser__actions">
          <a
            href={mnestixUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mnestix-browser__btn--link"
          >
            Open in New Tab
          </a>
          {onClose && (
            <button
              type="button"
              className="mnestix-browser__btn--secondary"
              onClick={onClose}
            >
              Close Browser
            </button>
          )}
        </div>
      </div>

      <div className="mnestix-browser__content">
        {iframeLoading && (
          <div className="mnestix-browser__iframe-loading">
            <div className="mnestix-browser__spinner" />
            <p>Connecting to AAS Browser...</p>
          </div>
        )}
        <iframe
          src={mnestixUrl}
          title="Mnestix AAS Browser"
          className={`mnestix-browser__iframe ${
            iframeLoading ? 'mnestix-browser__iframe--loading' : ''
          }`}
          onLoad={handleIframeLoad}
          onError={handleIframeError}
          allow="clipboard-read; clipboard-write"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
        />
      </div>
    </div>
  );
}
