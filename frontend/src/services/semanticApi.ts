import { apiFetch } from './api';
import type {
  SemanticApplyPreviewRequest,
  SemanticApplyPreviewResponse,
  SemanticProviderInfo,
  SemanticResolveResponse,
  SemanticSearchResponse,
  SemanticKind,
} from '../types/semantic';

export async function listSemanticProviders(): Promise<SemanticProviderInfo[]> {
  return apiFetch<SemanticProviderInfo[]>('/api/semantic/providers');
}

export interface SemanticSearchParams {
  q: string;
  provider?: string;
  kind?: SemanticKind;
  lang?: string;
  limit?: number;
  offset?: number;
}

export async function searchSemantics(
  params: SemanticSearchParams
): Promise<SemanticSearchResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set('q', params.q);
  if (params.provider) searchParams.set('provider', params.provider);
  if (params.kind) searchParams.set('kind', params.kind);
  if (params.lang) searchParams.set('lang', params.lang);
  if (params.limit) searchParams.set('limit', String(params.limit));
  if (params.offset) searchParams.set('offset', String(params.offset));

  const query = searchParams.toString();
  return apiFetch<SemanticSearchResponse>(
    `/api/semantic/search${query ? `?${query}` : ''}`
  );
}

export async function resolveSemantic(
  identifier: string,
  provider?: string,
  lang?: string
): Promise<SemanticResolveResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set('id', identifier);
  if (provider) searchParams.set('provider', provider);
  if (lang) searchParams.set('lang', lang);
  const query = searchParams.toString();
  return apiFetch<SemanticResolveResponse>(
    `/api/semantic/resolve${query ? `?${query}` : ''}`
  );
}

export async function applySemanticPreview(
  payload: SemanticApplyPreviewRequest
): Promise<SemanticApplyPreviewResponse> {
  return apiFetch<SemanticApplyPreviewResponse>('/api/semantic/apply-preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
