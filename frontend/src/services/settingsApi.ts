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

export interface FeatureFlagsSettings {
  dataspace_enabled: boolean;
  source: 'settings' | 'env';
}

export interface FeatureFlagsUpdate {
  dataspace_enabled?: boolean;
}

// ============================================================================
// Provider Detail Types (for enhanced provider selection)
// ============================================================================

export interface ProviderDetailInfo {
  name: string;
  available: boolean;
  model: string | null;
  is_local: boolean;
  privacy_note: string;
  error: string | null;
}

export interface ModelRecommendation {
  model_id: string;
  display_name: string;
  description: string;
  min_memory_gb: number;
  recommended_memory_gb: number;
  quality_tier: 'high' | 'medium' | 'fast';
  parameters: string;
  quantization: string | null;
  is_available: boolean;
}

export interface ProviderDetailResponse {
  providers: ProviderDetailInfo[];
  active_provider: string | null;
  model_recommendations: Record<string, ModelRecommendation[]>;
  fallback_supported: boolean;
}

export interface ProviderSelectResponse {
  success: boolean;
  selected_provider: string;
  active_provider: string | null;
  model: string | null;
  fallback_used: boolean;
  fallback_reason: string | null;
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

/**
 * Get runtime feature flags.
 */
export async function getFeatureFlags(): Promise<FeatureFlagsSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings/features`);

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to load feature flags', response.status, details);
  }

  return response.json();
}

/**
 * Update runtime feature flags.
 */
export async function updateFeatureFlags(
  update: FeatureFlagsUpdate
): Promise<FeatureFlagsSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings/features`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to update feature flags', response.status, details);
  }

  return response.json();
}

// ============================================================================
// Provider Detail API Functions
// ============================================================================

/**
 * Get detailed provider information with model recommendations.
 */
export async function getProviderDetails(): Promise<ProviderDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/api/magic-import/providers/info`);

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to load provider details', response.status, details);
  }

  return response.json();
}

/**
 * Select a provider with optional fallback.
 */
export async function selectProvider(
  provider: ProviderType,
  useFallback: boolean = true
): Promise<ProviderSelectResponse> {
  const params = new URLSearchParams({
    provider,
    use_fallback: String(useFallback),
  });

  const response = await fetch(
    `${API_BASE_URL}/api/magic-import/providers/select?${params}`,
    { method: 'POST' }
  );

  if (!response.ok) {
    const details = await response.json().catch(() => response.statusText);
    throw new ApiError('Failed to select provider', response.status, details);
  }

  return response.json();
}
