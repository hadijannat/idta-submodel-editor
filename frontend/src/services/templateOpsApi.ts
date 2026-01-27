/**
 * API client for Template Operations (TemplateOps) tool.
 *
 * Provides functions for schema digest computation, recipe migration,
 * form data migration, template diff, and version mismatch detection.
 */

import { apiFetch } from './api';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export interface SchemaDigest {
  digest: string;
  element_count: number;
  computed_at: string;
}

export interface SchemaDigestRequest {
  template_name: string;
  template_version?: string | null;
  template_status?: 'published' | 'deprecated' | 'local';
}

export interface MappingMigrationItem {
  original_path: string;
  migrated_path: string | null;
  confidence: number;
  match_reason: 'exact_path' | 'semantic_id' | 'fuzzy' | 'unmapped';
  breaking_change: boolean;
  details?: Record<string, unknown> | null;
}

export interface RecipeMigrationRequest {
  recipe: Record<string, unknown>;
  target_template: string;
  target_version?: string | null;
  target_status?: 'published' | 'deprecated' | 'local';
  min_confidence?: number;
  preserve_transforms?: boolean;
}

export interface RecipeMigrationResult {
  migrated_recipe: Record<string, unknown> | null;
  mapping_migrations: MappingMigrationItem[];
  breaking_changes: string[];
  migration_coverage: number;
  warnings: string[];
}

export interface ValueMigrationItem {
  original_path: string;
  migrated_path: string | null;
  original_value: unknown;
  migrated_value: unknown;
  confidence: number;
  match_reason: 'exact_path' | 'semantic_id' | 'fuzzy' | 'unmapped';
}

export interface FormDataMigrationRequest {
  form_data: Record<string, unknown>;
  source_template: string;
  source_version?: string | null;
  source_status?: 'published' | 'deprecated' | 'local';
  target_template: string;
  target_version?: string | null;
  target_status?: 'published' | 'deprecated' | 'local';
  min_confidence?: number;
}

export interface FormDataMigrationResult {
  migrated_form_data: Record<string, unknown> | null;
  value_migrations: ValueMigrationItem[];
  migration_coverage: number;
  warnings: string[];
}

export interface VersionMismatchRequest {
  artifact_type: 'recipe' | 'form_data';
  created_for_digest: string | null;
  template_name: string;
  template_version?: string | null;
  template_status?: 'published' | 'deprecated' | 'local';
}

export interface VersionMismatchCheck {
  artifact_type: 'recipe' | 'form_data';
  created_for_digest: string | null;
  current_digest: string;
  has_mismatch: boolean;
  breaking_changes_detected: boolean;
  affected_paths: string[];
}

export interface ElementChange {
  path: string;
  change_type: 'added' | 'removed' | 'modified' | 'moved' | 'renamed';
  old_value?: string | null;
  new_value?: string | null;
  details?: Record<string, unknown> | null;
}

export interface CardinalityChange {
  path: string;
  old_cardinality: string;
  new_cardinality: string;
  breaking: boolean;
}

export interface SemanticChange {
  path: string;
  old_semantic_id: string | null;
  new_semantic_id: string | null;
}

export interface TemplateDiffRequest {
  source_template: string;
  source_version?: string | null;
  source_status?: 'published' | 'deprecated' | 'local';
  target_template: string;
  target_version?: string | null;
  target_status?: 'published' | 'deprecated' | 'local';
  include_semantic_changes?: boolean;
}

export interface TemplateDiffResult {
  source_template: string;
  source_version: string | null;
  target_template: string;
  target_version: string | null;
  elements_added: string[];
  elements_removed: string[];
  elements_modified: ElementChange[];
  cardinality_changes: CardinalityChange[];
  semantic_changes: SemanticChange[];
  is_breaking: boolean;
  summary: string;
}

export interface MigrationPlanRequest {
  source_template: string;
  source_version?: string | null;
  source_status?: 'published' | 'deprecated' | 'local';
  target_template: string;
  target_version?: string | null;
  target_status?: 'published' | 'deprecated' | 'local';
  use_semantics?: boolean;
  min_confidence?: number;
}

export interface MigrationMappingPlanItem {
  source_path: string;
  target_path: string;
  confidence: number;
  match_reason: 'exact' | 'semantic' | 'fuzzy' | 'manual';
  transform?: string | null;
}

export interface MigrationPlan {
  source_template: string;
  source_version: string | null;
  target_template: string;
  target_version: string | null;
  auto_mappings: MigrationMappingPlanItem[];
  unmapped_source: string[];
  unmapped_target: string[];
  mapping_coverage: number;
  warnings: string[];
}

// -----------------------------------------------------------------------------
// API Functions
// -----------------------------------------------------------------------------

/**
 * Compute the schema digest for a template.
 */
export async function computeSchemaDigest(
  request: SchemaDigestRequest
): Promise<SchemaDigest> {
  return apiFetch<SchemaDigest>('/api/template-ops/schema-digest', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Migrate a mapper recipe to a new template version.
 */
export async function migrateRecipe(
  request: RecipeMigrationRequest
): Promise<RecipeMigrationResult> {
  return apiFetch<RecipeMigrationResult>('/api/template-ops/migrate-recipe', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Migrate form data to a new template version.
 */
export async function migrateFormData(
  request: FormDataMigrationRequest
): Promise<FormDataMigrationResult> {
  return apiFetch<FormDataMigrationResult>('/api/template-ops/migrate-form', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Check if an artifact's schema digest mismatches the current template.
 */
export async function checkVersionMismatch(
  request: VersionMismatchRequest
): Promise<VersionMismatchCheck> {
  return apiFetch<VersionMismatchCheck>('/api/template-ops/check-mismatch', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Compare two template versions and get a diff.
 */
export async function getTemplateDiff(
  request: TemplateDiffRequest
): Promise<TemplateDiffResult> {
  return apiFetch<TemplateDiffResult>('/api/template-ops/diff', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Generate a migration plan between template versions.
 */
export async function generateMigrationPlan(
  request: MigrationPlanRequest
): Promise<MigrationPlan> {
  return apiFetch<MigrationPlan>('/api/template-ops/migrate', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
