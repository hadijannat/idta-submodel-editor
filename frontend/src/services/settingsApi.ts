/**
 * API client for LLM provider settings.
 */

import { API_BASE_URL, ApiError } from './api';

// ============================================================================
// Types
// ============================================================================

export type ProviderType = 'openai' | 'anthropic' | 'openrouter' | 'local';

export interface ProviderStatus {
  configured: boolean;
  healthy: boolean | null;
  latency_ms: number | null;
}

export interface LLMSettings {
  provider: ProviderType;
  model: string;
  api_key_configured: boolean;
  api_key_masked: string | null;
  base_url: string | null;
  confidence_threshold: number;
  ocr_enabled: boolean;
  providers: Record<string, ProviderStatus>;
}

export interface LLMSettingsUpdate {
  provider?: ProviderType;
  api_key?: string;
  model?: string;
  base_url?: string;
  confidence_threshold?: number;
  ocr_enabled?: boolean;
}

export interface ProviderValidationRequest {
  provider: ProviderType;
  api_key?: string;
  base_url?: string;
}

export interface ProviderValidationResponse {
  valid: boolean;
  message: string;
  models: string[];
}

export interface ModelsResponse {
  provider: ProviderType;
  models: string[];
  default_model: string;
}

export interface ProviderQuickStatus {
  configured: boolean;
  provider: ProviderType | null;
  model: string | null;
  healthy: boolean;
  message: string;
  available_providers?: string[];
}

// ============================================================================
// Provider Info
// ============================================================================

export interface ProviderInfo {
  id: ProviderType;
  name: string;
  description: string;
  icon: string;
  requiresApiKey: boolean;
  docsUrl: string;
}

export const PROVIDERS: ProviderInfo[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4o-mini, GPT-4 Turbo',
    icon: '🤖',
    requiresApiKey: true,
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus',
    icon: '🧠',
    requiresApiKey: true,
    docsUrl: 'https://console.anthropic.com/settings/keys',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: '100+ models: Claude, GPT-4, Gemini, Llama, Mistral',
    icon: '🌐',
    requiresApiKey: true,
    docsUrl: 'https://openrouter.ai/keys',
  },
  {
    id: 'local',
    name: 'Local (Ollama)',
    description: 'Self-hosted models via Ollama',
    icon: '💻',
    requiresApiKey: false,
    docsUrl: 'https://ollama.ai/',
  },
];

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get current LLM settings.
 */
export async function getLLMSettings(): Promise<LLMSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings/llm`);

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to load LLM settings', response.status, details);
  }

  return response.json();
}

/**
 * Update LLM settings.
 */
export async function updateLLMSettings(
  settings: LLMSettingsUpdate
): Promise<LLMSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings/llm`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to update LLM settings', response.status, details);
  }

  return response.json();
}

/**
 * Validate provider credentials without storing.
 */
export async function validateProvider(
  request: ProviderValidationRequest
): Promise<ProviderValidationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings/llm/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Validation request failed', response.status, details);
  }

  return response.json();
}

/**
 * Get available models for a provider.
 */
export async function getProviderModels(
  provider: ProviderType
): Promise<ModelsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/llm/models/${provider}`
  );

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to load models', response.status, details);
  }

  return response.json();
}

/**
 * Delete stored API key for a provider.
 */
export async function deleteProviderApiKey(
  provider: ProviderType
): Promise<{ deleted: boolean; provider: string }> {
  const response = await fetch(
    `${API_BASE_URL}/api/settings/llm/api-key/${provider}`,
    { method: 'DELETE' }
  );

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to delete API key', response.status, details);
  }

  return response.json();
}

/**
 * Get quick provider status for Magic Import panel.
 */
export async function getProviderQuickStatus(): Promise<ProviderQuickStatus> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/provider-status`);

  if (!response.ok) {
    // Return a default unconfigured status on error
    return {
      configured: false,
      provider: null,
      model: null,
      healthy: false,
      message: 'Could not check provider status',
    };
  }

  return response.json();
}
