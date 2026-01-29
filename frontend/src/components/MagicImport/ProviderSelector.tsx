/**
 * ProviderSelector - Enhanced provider selection dialog for Magic Import.
 *
 * Shows:
 * - Provider cards with availability status
 * - Privacy indicators (local vs cloud)
 * - Model recommendations for local provider
 * - Fallback warnings when switching providers
 */

import { useCallback, useEffect, useState } from 'react';
import {
  getProviderDetails,
  selectProvider,
  type ProviderDetailResponse,
  type ModelRecommendation,
  type ProviderType,
} from '../../services/settingsApi';
import { ProviderStatusBadge } from '../LLMSettings';
import './MagicImport.css';

interface ProviderSelectorProps {
  onClose: () => void;
  onProviderSelected?: (provider: string, model: string | null) => void;
  showOnlyAvailable?: boolean;
}

export function ProviderSelector({
  onClose,
  onProviderSelected,
  showOnlyAvailable = false,
}: ProviderSelectorProps) {
  const [details, setDetails] = useState<ProviderDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [showRecommendations, setShowRecommendations] = useState(false);

  // Load provider details on mount
  useEffect(() => {
    let mounted = true;

    const loadDetails = async () => {
      try {
        const data = await getProviderDetails();
        if (mounted) {
          setDetails(data);
          setSelectedProvider(data.active_provider);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load providers');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadDetails();

    return () => {
      mounted = false;
    };
  }, []);

  const handleProviderSelect = useCallback(
    async (provider: string) => {
      if (selecting) return;

      setSelecting(true);
      setError(null);

      try {
        const result = await selectProvider(provider as ProviderType, true);

        if (result.success) {
          setSelectedProvider(result.active_provider);

          if (result.fallback_used && result.fallback_reason) {
            // Show fallback warning but still proceed
            setError(`Note: ${result.fallback_reason}`);
          }

          onProviderSelected?.(result.active_provider || provider, result.model);
        } else {
          setError(result.fallback_reason || 'Provider unavailable');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Selection failed');
      } finally {
        setSelecting(false);
      }
    },
    [selecting, onProviderSelected]
  );

  const getProviderIcon = (name: string) => {
    switch (name) {
      case 'openai':
        return '🤖';
      case 'anthropic':
        return '🧠';
      case 'openrouter':
        return '🌐';
      case 'local':
        return '💻';
      default:
        return '⚙️';
    }
  };

  const getProviderDisplayName = (name: string) => {
    switch (name) {
      case 'openai':
        return 'OpenAI';
      case 'anthropic':
        return 'Anthropic';
      case 'openrouter':
        return 'OpenRouter';
      case 'local':
        return 'Local (Ollama)';
      default:
        return name;
    }
  };

  if (loading) {
    return (
      <div className="provider-selector">
        <div className="provider-selector__loading">
          <div className="spinner" />
          <p>Loading providers...</p>
        </div>
      </div>
    );
  }

  const providers = showOnlyAvailable
    ? details?.providers.filter((p) => p.available) || []
    : details?.providers || [];

  const localProvider = details?.providers.find((p) => p.name === 'local');
  const recommendations = details?.model_recommendations || {};

  return (
    <div className="provider-selector">
      <div className="provider-selector__header">
        <h3>Select AI Provider</h3>
        <p className="provider-selector__subtitle">
          Choose how your PDF data will be processed
        </p>
        <button
          type="button"
          className="provider-selector__close"
          onClick={onClose}
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      {error && (
        <div
          className={`provider-selector__message ${
            error.startsWith('Note:')
              ? 'provider-selector__message--warning'
              : 'provider-selector__message--error'
          }`}
        >
          {error}
        </div>
      )}

      <div className="provider-selector__grid">
        {providers.map((provider) => {
          const isSelected = selectedProvider === provider.name;
          const isLocal = provider.is_local;

          return (
            <button
              key={provider.name}
              type="button"
              className={`provider-card ${isSelected ? 'provider-card--selected' : ''} ${
                !provider.available ? 'provider-card--disabled' : ''
              } ${isLocal ? 'provider-card--local' : ''}`}
              onClick={() => provider.available && handleProviderSelect(provider.name)}
              disabled={!provider.available || selecting}
            >
              <div className="provider-card__header">
                <span className="provider-card__icon">{getProviderIcon(provider.name)}</span>
                <span className="provider-card__name">
                  {getProviderDisplayName(provider.name)}
                </span>
                <ProviderStatusBadge
                  status={provider.available ? 'connected' : 'unconfigured'}
                  compact
                />
              </div>

              {/* Privacy indicator */}
              <div
                className={`provider-card__privacy ${
                  isLocal ? 'provider-card__privacy--local' : 'provider-card__privacy--cloud'
                }`}
              >
                <span className="provider-card__privacy-icon">
                  {isLocal ? '🔒' : '☁️'}
                </span>
                <span className="provider-card__privacy-text">{provider.privacy_note}</span>
              </div>

              {/* Model info */}
              {provider.model && (
                <div className="provider-card__model">Model: {provider.model}</div>
              )}

              {/* Error message */}
              {provider.error && !provider.available && (
                <div className="provider-card__error">{provider.error}</div>
              )}

              {/* Selected indicator */}
              {isSelected && <span className="provider-card__checkmark">✓</span>}
            </button>
          );
        })}
      </div>

      {/* Model recommendations for local provider */}
      {Object.keys(recommendations).length > 0 && (
        <div className="provider-selector__recommendations">
          <button
            type="button"
            className="provider-selector__recommendations-toggle"
            onClick={() => setShowRecommendations(!showRecommendations)}
          >
            {showRecommendations ? '▼' : '▶'} Model Recommendations for Local Provider
          </button>

          {showRecommendations && (
            <div className="model-recommendations">
              {localProvider && !localProvider.available && (
                <div className="provider-selector__message provider-selector__message--warning">
                  Local provider is unavailable. Start Ollama to detect installed models.
                </div>
              )}
              {Object.entries(recommendations).map(([useCase, models]) => (
                <div key={useCase} className="model-recommendations__group">
                  <h5 className="model-recommendations__title">
                    {useCase === 'extraction'
                      ? '🎯 Recommended for Extraction'
                      : useCase === 'fast'
                      ? '⚡ Fast (Lower Memory)'
                      : '🏆 High Quality (More Memory)'}
                  </h5>
                  <div className="model-recommendations__list">
                    {models.map((model: ModelRecommendation) => (
                      <div
                        key={model.model_id}
                        className={`model-recommendation ${
                          model.is_available
                            ? 'model-recommendation--available'
                            : 'model-recommendation--unavailable'
                        }`}
                      >
                        <div className="model-recommendation__header">
                          <span className="model-recommendation__name">
                            {model.display_name}
                          </span>
                          <span
                            className={`model-recommendation__badge model-recommendation__badge--${model.quality_tier}`}
                          >
                            {model.quality_tier}
                          </span>
                          {model.is_available && (
                            <span className="model-recommendation__installed">✓ Installed</span>
                          )}
                        </div>
                        <p className="model-recommendation__description">{model.description}</p>
                        <div className="model-recommendation__specs">
                          <span>Parameters: {model.parameters}</span>
                          <span>RAM: {model.min_memory_gb}GB min</span>
                          {model.quantization && <span>Quant: {model.quantization}</span>}
                        </div>
                        {!model.is_available && (
                          <div className="model-recommendation__install-hint">
                            Run: <code>ollama pull {model.model_id}</code>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="provider-selector__footer">
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onClose}
          disabled={!selectedProvider}
        >
          Use {selectedProvider ? getProviderDisplayName(selectedProvider) : 'Provider'}
        </button>
      </div>
    </div>
  );
}

export default ProviderSelector;
