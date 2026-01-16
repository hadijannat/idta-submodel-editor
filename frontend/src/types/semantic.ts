export type SemanticProviderStatus = 'ready' | 'disabled' | 'error';
export type SemanticKind = 'property' | 'class' | 'unit' | 'value';

export interface SemanticProviderInfo {
  id: string;
  label: string;
  status: SemanticProviderStatus;
  reason?: string | null;
}

export interface SemanticEntry {
  provider: string;
  kind: SemanticKind;
  canonicalId: string;
  canonicalIri?: string | null;
  preferredName?: string | null;
  definition?: string | null;
  datatypeHint?: string | null;
  unitHint?: string | null;
  labels?: Record<string, string> | null;
  definitions?: Record<string, string> | null;
  synonyms?: string[] | null;
  score?: number | null;
}

export interface SemanticSearchResponse {
  query: string;
  results: SemanticEntry[];
  total: number;
}

export interface SemanticResolveResponse {
  entry: SemanticEntry;
}

export interface SemanticApplyPreviewRequest {
  identifier: string;
  provider?: string | null;
  elementType?: string | null;
  valueType?: string | null;
  preferIri?: boolean | null;
}

export interface SemanticApplyPreviewResponse {
  semanticId: string;
  elementType?: string | null;
  valueType?: string | null;
  warnings: string[];
  notes: string[];
}
