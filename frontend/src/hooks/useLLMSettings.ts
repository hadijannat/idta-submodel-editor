/**
 * Hook for managing LLM provider settings state.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  LLMSettings,
  ProviderType,
  ProviderValidationResponse,
} from '../services/settingsApi';
import {
  getLLMSettings,
  updateLLMSettings,
  validateProvider,
  getProviderModels,
} from '../services/settingsApi';

export type ValidationStatus = 'idle' | 'validating' | 'valid' | 'invalid';

export interface UseLLMSettingsReturn {
  // State
  settings: LLMSettings | null;
  loading: boolean;
  error: string | null;
  validationStatus: ValidationStatus;
  validationMessage: string | null;
  saving: boolean;

  // Actions
  refresh: () => Promise<void>;
  setProvider: (provider: ProviderType) => Promise<void>;
  setApiKey: (provider: ProviderType, apiKey: string) => Promise<void>;
  setModel: (model: string) => Promise<void>;
  validateCredentials: (
    provider: ProviderType,
    apiKey?: string
  ) => Promise<ProviderValidationResponse>;
  setConfidenceThreshold: (threshold: number) => Promise<void>;
  setOcrEnabled: (enabled: boolean) => Promise<void>;
  loadModels: (provider: ProviderType) => Promise<string[]>;
}

export function useLLMSettings(): UseLLMSettingsReturn {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationStatus, setValidationStatus] = useState<ValidationStatus>('idle');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Load settings on mount
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getLLMSettings();
      setSettings(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Set active provider
  const setProvider = useCallback(async (provider: ProviderType) => {
    setSaving(true);
    setError(null);

    try {
      const updated = await updateLLMSettings({ provider });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update provider');
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  // Set API key for a provider
  const setApiKey = useCallback(
    async (provider: ProviderType, apiKey: string) => {
      setSaving(true);
      setError(null);
      setValidationStatus('validating');

      try {
        // Validate first
        const validation = await validateProvider({ provider, api_key: apiKey });
        setValidationMessage(validation.message);

        if (!validation.valid) {
          setValidationStatus('invalid');
          throw new Error(validation.message);
        }

        setValidationStatus('valid');

        // Get default model for this provider to include with the save
        const modelsResponse = await getProviderModels(provider);
        const defaultModel = modelsResponse.default_model || modelsResponse.models[0];

        // Save with provider, API key, AND default model
        const updated = await updateLLMSettings({
          provider,
          api_key: apiKey,
          model: defaultModel,
        });
        setSettings(updated);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save API key');
        throw err;
      } finally {
        setSaving(false);
      }
    },
    []
  );

  // Set model
  const setModel = useCallback(async (model: string) => {
    setSaving(true);
    setError(null);

    try {
      const updated = await updateLLMSettings({ model });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update model');
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  // Validate credentials without saving
  const validateCredentials = useCallback(
    async (
      provider: ProviderType,
      apiKey?: string
    ): Promise<ProviderValidationResponse> => {
      setValidationStatus('validating');
      setValidationMessage(null);

      try {
        const result = await validateProvider({
          provider,
          api_key: apiKey,
        });

        setValidationStatus(result.valid ? 'valid' : 'invalid');
        setValidationMessage(result.message);

        return result;
      } catch (err) {
        setValidationStatus('invalid');
        const message = err instanceof Error ? err.message : 'Validation failed';
        setValidationMessage(message);
        throw err;
      }
    },
    []
  );

  // Set confidence threshold
  const setConfidenceThreshold = useCallback(async (threshold: number) => {
    setSaving(true);
    setError(null);

    try {
      const updated = await updateLLMSettings({ confidence_threshold: threshold });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update threshold');
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  // Set OCR enabled
  const setOcrEnabled = useCallback(async (enabled: boolean) => {
    setSaving(true);
    setError(null);

    try {
      const updated = await updateLLMSettings({ ocr_enabled: enabled });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update OCR setting');
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  // Load models for a provider
  const loadModels = useCallback(async (provider: ProviderType): Promise<string[]> => {
    try {
      const response = await getProviderModels(provider);
      return response.models;
    } catch {
      return [];
    }
  }, []);

  return {
    settings,
    loading,
    error,
    validationStatus,
    validationMessage,
    saving,
    refresh,
    setProvider,
    setApiKey,
    setModel,
    validateCredentials,
    setConfidenceThreshold,
    setOcrEnabled,
    loadModels,
  };
}
