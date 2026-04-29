/**
 * LLMSettingsPanel - Main settings panel for configuring LLM providers.
 *
 * Provides:
 * - Provider selection (OpenAI, Anthropic, OpenRouter, Local)
 * - API key input with validation
 * - Model selection
 * - Advanced settings (confidence threshold, OCR)
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useLLMSettings, type ValidationStatus } from '../../hooks/useLLMSettings';
// Using ValidationStatus type for local state
import { PROVIDERS, type ProviderType } from '../../services/settingsApi';
import { ProviderStatusBadge, type StatusType } from './ProviderStatusBadge';
import './LLMSettings.css';

interface LLMSettingsPanelProps {
  onClose?: () => void;
  compact?: boolean;
}

export function LLMSettingsPanel({ onClose, compact = false }: LLMSettingsPanelProps) {
  const {
    settings,
    loading,
    error,
    saving,
    setProvider,
    setApiKey,
    setModel,
    validateCredentials,
    setConfidenceThreshold,
    setOcrEnabled,
    loadModels,
  } = useLLMSettings();

  const [selectedProviderOverride, setSelectedProviderOverride] = useState<ProviderType | null>(
    null
  );
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [localValidation, setLocalValidation] = useState<{
    status: ValidationStatus;
    message: string | null;
  }>({ status: 'idle', message: null });

  const selectedProvider = selectedProviderOverride ?? settings?.provider ?? null;
  const selectedProviderConfig = useMemo(
    () =>
      selectedProvider
        ? PROVIDERS.find((provider) => provider.id === selectedProvider)
        : undefined,
    [selectedProvider]
  );

  // Load models when provider changes
  useEffect(() => {
    if (!selectedProvider) return;

    let active = true;
    loadModels(selectedProvider).then((providerModels) => {
      if (active) {
        setModels(providerModels);
      }
    });

    return () => {
      active = false;
    };
  }, [selectedProvider, loadModels]);

  const handleProviderSelect = useCallback(
    async (provider: ProviderType) => {
      setSelectedProviderOverride(provider);
      setApiKeyInput('');
      setLocalValidation({ status: 'idle', message: null });

      // If provider is already configured, activate it
      if (settings?.providers[provider]?.configured) {
        await setProvider(provider);
      }
    },
    [settings, setProvider]
  );

  const handleValidateKey = useCallback(async () => {
    if (!selectedProvider || !apiKeyInput) return;

    setLocalValidation({ status: 'validating', message: null });

    try {
      const result = await validateCredentials(selectedProvider, apiKeyInput);
      setLocalValidation({
        status: result.valid ? 'valid' : 'invalid',
        message: result.message,
      });
    } catch (err) {
      setLocalValidation({
        status: 'invalid',
        message: err instanceof Error ? err.message : 'Validation failed',
      });
    }
  }, [selectedProvider, apiKeyInput, validateCredentials]);

  const handleSaveKey = useCallback(async () => {
    if (!selectedProvider || !apiKeyInput) return;

    try {
      await setApiKey(selectedProvider, apiKeyInput);
      setApiKeyInput('');
      setLocalValidation({ status: 'idle', message: null });
    } catch {
      // Error is handled by the hook
    }
  }, [selectedProvider, apiKeyInput, setApiKey]);

  const handleModelChange = useCallback(
    async (e: React.ChangeEvent<HTMLSelectElement>) => {
      await setModel(e.target.value);
    },
    [setModel]
  );

  const handleThresholdChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseFloat(e.target.value);
      if (!isNaN(value)) {
        await setConfidenceThreshold(value);
      }
    },
    [setConfidenceThreshold]
  );

  const handleOcrToggle = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      await setOcrEnabled(e.target.checked);
    },
    [setOcrEnabled]
  );

  const getProviderStatus = (provider: ProviderType): StatusType => {
    if (!settings) return 'unconfigured';
    const status = settings.providers[provider];
    if (!status?.configured) return 'unconfigured';
    if (status.healthy === null) return 'checking';
    return status.healthy ? 'connected' : 'error';
  };

  if (loading) {
    return (
      <div className="llm-settings-panel">
        <div className="llm-settings-panel__loading">
          <span className="spinner" />
          <p>Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`llm-settings-panel ${compact ? 'llm-settings-panel--compact' : ''}`}>
      {!compact && (
        <div className="llm-settings-panel__header">
          <h3>LLM Provider Configuration</h3>
          <p className="llm-settings-panel__subtitle">
            Configure the AI model used for PDF extraction
          </p>
          {onClose && (
            <button
              type="button"
              className="llm-settings-panel__close"
              onClick={onClose}
              aria-label="Close"
            >
              &times;
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="llm-settings-panel__error" role="alert">
          {error}
        </div>
      )}

      {/* Provider Selection */}
      <div className="llm-settings-panel__section">
        <h4>Provider</h4>
        <div className="llm-provider-grid">
          {PROVIDERS.map((provider) => {
            const isSelected = selectedProvider === provider.id;
            const isActive = settings?.provider === provider.id;
            const status = getProviderStatus(provider.id);

            return (
              <button
                key={provider.id}
                type="button"
                className={`llm-provider-card ${isSelected ? 'llm-provider-card--selected' : ''} ${
                  isActive ? 'llm-provider-card--active' : ''
                }`}
                onClick={() => handleProviderSelect(provider.id)}
              >
                <div className="llm-provider-card__header">
                  <span className="llm-provider-card__icon">{provider.icon}</span>
                  <span className="llm-provider-card__name">{provider.name}</span>
                  <ProviderStatusBadge status={status} compact />
                </div>
                <p className="llm-provider-card__description">{provider.description}</p>
                {isActive && (
                  <span className="llm-provider-card__active-badge">Active</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* API Key Input */}
      {selectedProvider && selectedProviderConfig?.requiresApiKey && (
        <div className="llm-settings-panel__section">
          <h4>API Key</h4>
          <div className="llm-api-key-input">
            <div className="llm-api-key-input__field">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={
                  settings?.api_key_masked
                    ? `Current: ${settings.api_key_masked}`
                    : 'Enter API key...'
                }
                className="llm-api-key-input__input"
              />
              <button
                type="button"
                className="llm-api-key-input__toggle"
                onClick={() => setShowApiKey(!showApiKey)}
                aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
              >
                {showApiKey ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>

            <div className="llm-api-key-input__actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleValidateKey}
                disabled={!apiKeyInput || localValidation.status === 'validating'}
              >
                {localValidation.status === 'validating' ? 'Validating...' : 'Validate'}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveKey}
                disabled={!apiKeyInput || saving || localValidation.status !== 'valid'}
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>

            {localValidation.message && (
              <div
                className={`llm-api-key-input__validation ${
                  localValidation.status === 'valid'
                    ? 'llm-api-key-input__validation--success'
                    : 'llm-api-key-input__validation--error'
                }`}
              >
                {localValidation.status === 'valid' ? '✓' : '✗'} {localValidation.message}
              </div>
            )}

            <p className="llm-api-key-input__help">
              Get your API key from{' '}
              <a
                href={selectedProviderConfig?.docsUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {selectedProviderConfig?.name}
              </a>
            </p>
          </div>
        </div>
      )}

      {/* Model Selection */}
      {selectedProvider && (
        <div className="llm-settings-panel__section">
          <h4>Model</h4>
          <select
            className="llm-model-select"
            value={
              // If selected provider is the active provider, use settings.model
              // Otherwise, use first model in list as default for the selected provider
              selectedProvider === settings?.provider
                ? settings?.model || ''
                : models[0] || ''
            }
            onChange={handleModelChange}
            disabled={saving}
          >
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
          <p className="llm-settings-panel__hint">
            Recommended: gpt-5.5 or claude-3.5-sonnet for best extraction quality
          </p>
        </div>
      )}

      {/* Advanced Settings */}
      {!compact && (
        <div className="llm-settings-panel__section">
          <button
            type="button"
            className="llm-settings-panel__advanced-toggle"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            Advanced Settings {showAdvanced ? '▲' : '▼'}
          </button>

          {showAdvanced && (
            <div className="llm-advanced-settings">
              <label className="llm-setting-row">
                <span>Confidence Threshold</span>
                <input
                  type="range"
                  min="0.5"
                  max="1"
                  step="0.05"
                  value={settings?.confidence_threshold ?? 0.8}
                  onChange={handleThresholdChange}
                  disabled={saving}
                />
                <span className="llm-setting-value">
                  {Math.round((settings?.confidence_threshold ?? 0.8) * 100)}%
                </span>
              </label>

              <label className="llm-setting-row">
                <span>Enable OCR</span>
                <input
                  type="checkbox"
                  checked={settings?.ocr_enabled ?? true}
                  onChange={handleOcrToggle}
                  disabled={saving}
                />
                <span className="llm-setting-hint">
                  Extract text from scanned documents
                </span>
              </label>
            </div>
          )}
        </div>
      )}

      {/* Current Status Summary */}
      {settings && (
        <div className="llm-settings-panel__status">
          <ProviderStatusBadge
            status={getProviderStatus(settings.provider)}
            message={
              settings.providers[settings.provider]?.configured
                ? `${settings.provider} · ${settings.model}`
                : 'Not configured'
            }
          />
        </div>
      )}
    </div>
  );
}

export default LLMSettingsPanel;
