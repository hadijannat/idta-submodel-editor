import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useLLMSettings } from '../useLLMSettings';
import * as settingsApi from '../../services/settingsApi';
import type { LLMSettings, ProviderValidationResponse } from '../../services/settingsApi';

vi.mock('../../services/settingsApi', () => ({
  getLLMSettings: vi.fn(),
  updateLLMSettings: vi.fn(),
  validateProvider: vi.fn(),
  getProviderModels: vi.fn(),
}));

const configuredStatus = {
  configured: true,
  healthy: true,
  latency_ms: 120,
};

const unconfiguredStatus = {
  configured: false,
  healthy: null,
  latency_ms: null,
};

const mockSettings: LLMSettings = {
  provider: 'openai',
  model: 'gpt-5.5',
  api_key_configured: true,
  api_key_masked: 'sk-...test',
  base_url: null,
  confidence_threshold: 0.8,
  ocr_enabled: true,
  providers: {
    openai: configuredStatus,
    anthropic: unconfiguredStatus,
    openrouter: unconfiguredStatus,
    local: unconfiguredStatus,
  },
};

describe('useLLMSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(settingsApi.getLLMSettings).mockResolvedValue(mockSettings);
  });

  it('forwards the selected OpenAI model when validating credentials', async () => {
    vi.mocked(settingsApi.validateProvider).mockResolvedValue({
      valid: true,
      message: 'OpenAI credentials valid for gpt-5.5',
      models: ['gpt-5.5'],
    });

    const { result } = renderHook(() => useLLMSettings());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    let validation: ProviderValidationResponse | undefined;
    await act(async () => {
      validation = await result.current.validateCredentials(
        'openai',
        'sk-test-key',
        'gpt-5.5'
      );
    });

    expect(validation?.valid).toBe(true);
    expect(settingsApi.validateProvider).toHaveBeenCalledWith({
      provider: 'openai',
      api_key: 'sk-test-key',
      model: 'gpt-5.5',
    });
    expect(result.current.validationStatus).toBe('valid');
  });

  it('validates and saves the provider default model when storing an API key', async () => {
    vi.mocked(settingsApi.getProviderModels).mockResolvedValue({
      provider: 'openai',
      models: ['gpt-5.5', 'gpt-5.5-pro'],
      default_model: 'gpt-5.5',
    });
    vi.mocked(settingsApi.validateProvider).mockResolvedValue({
      valid: true,
      message: 'OpenAI credentials valid for gpt-5.5',
      models: ['gpt-5.5', 'gpt-5.5-pro'],
    });
    vi.mocked(settingsApi.updateLLMSettings).mockResolvedValue(mockSettings);

    const { result } = renderHook(() => useLLMSettings());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.setApiKey('openai', 'sk-test-key');
    });

    expect(settingsApi.validateProvider).toHaveBeenCalledWith({
      provider: 'openai',
      api_key: 'sk-test-key',
      model: 'gpt-5.5',
    });
    expect(settingsApi.updateLLMSettings).toHaveBeenCalledWith({
      provider: 'openai',
      api_key: 'sk-test-key',
      model: 'gpt-5.5',
    });
    expect(result.current.validationStatus).toBe('valid');
  });
});
