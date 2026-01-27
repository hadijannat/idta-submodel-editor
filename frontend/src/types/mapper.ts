export interface DatasetFileInfo {
  name: string;
  size: number;
  type?: string | null;
}

export interface DatasetSheetInfo {
  name: string;
  rows?: number | null;
  cols?: number | null;
}

export interface DatasetColumnProfile {
  name_original: string;
  name_normalized: string;
  index: number;
  inferred_type: string;
  null_rate: number;
  distinct_count: number;
  examples: string[];
}

export interface DatasetProfile {
  profile_id: string;
  file: DatasetFileInfo;
  sheets: DatasetSheetInfo[];
  columns: DatasetColumnProfile[];
  sample_rows: Array<Array<string | null>>;
  row_count?: number | null;
  header_row: number;
  warnings: string[];
}

export interface MapperSourceColumn {
  column_name: string;
  column_index?: number | null;
}

export interface MapperTargetField {
  id_short_path: string;
  element_type: string;
  value_type?: string | null;
  field?: string | null;
  language?: string | null;
}

export interface MapperTransform {
  trim?: boolean;
  default_value?: string | null;
  decimal?: string | null;
  thousands?: string | null;
  date_format?: string | null;
  true_values?: string[] | null;
  false_values?: string[] | null;
}

export interface MappingItem {
  source: MapperSourceColumn;
  target: MapperTargetField;
  transform?: MapperTransform | null;
  required?: boolean;
}

export type MapperModeType = 'single' | 'row-per-submodel' | 'grouped';

export interface MapperMode {
  type: MapperModeType;
  group_by: string[];
}

export interface MapperTemplateRef {
  name: string;
  version?: string | null;
  status: 'published' | 'deprecated';
  schema_digest?: string | null;
}

export interface MapperSourceProfileRef {
  format: 'csv' | 'xlsx';
  sheet?: string | null;
  header_row: number;
  header_fingerprint?: string | null;
}

export interface MapperRecipe {
  name: string;
  schema_version: string;
  template: MapperTemplateRef;
  source_profile: MapperSourceProfileRef;
  mode: MapperMode;
  mappings: MappingItem[];
}

export interface MapperDiagnostic {
  severity: 'error' | 'warning';
  row_index?: number | null;
  source_column?: string | null;
  target_path?: string | null;
  code?: string | null;
  message: string;
  sample?: string | null;
}

export interface MapperRunRequest {
  template_name: string;
  status: 'published' | 'deprecated';
  version?: string | null;
  profile_id: string;
  recipe: MapperRecipe;
  output_format: 'form' | 'aasx' | 'json' | 'pdf';
  row_index?: number | null;
}

export interface MapperRunResponse {
  mode: MapperMode;
  diagnostics: MapperDiagnostic[];
  form_data?: Record<string, unknown> | null;
  form_data_batch?: Array<Record<string, unknown>> | null;
  row_count?: number | null;
}

export interface MapperTargetFieldInfo {
  id_short_path: string;
  element_type: string;
  value_type?: string | null;
  label: string;
  required: boolean;
  semantic_id?: string | null;
  semantic_label?: string | null;
  semantic_synonyms: string[];
  languages?: string[] | null;
}

export interface MapperSuggestedMapping {
  source_column: string;
  source_index: number;
  target_path: string;
  target_type: string;
  target_value_type?: string | null;
  confidence: number;
  match_reason: string;
}

export interface MapperAutoSuggestRequest {
  template_name: string;
  status: 'published' | 'deprecated';
  version?: string | null;
  profile_id: string;
  use_semantics?: boolean;
  min_confidence?: number;
}

export interface MapperAutoSuggestResponse {
  suggestions: MapperSuggestedMapping[];
  target_fields: MapperTargetFieldInfo[];
  semantic_resolved: number;
  semantic_errors: number;
}
