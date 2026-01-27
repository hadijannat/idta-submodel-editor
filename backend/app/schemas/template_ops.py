"""
Schemas for Template Operations tool.

Provides import, diff, migrate, and validate operations for templates.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Schema Digest (for change detection)
# -----------------------------------------------------------------------------


class SchemaDigest(BaseModel):
    """Cryptographic fingerprint for schema change detection."""

    digest: str  # SHA-256
    element_count: int
    computed_at: str  # ISO timestamp


# -----------------------------------------------------------------------------
# Recipe Migration
# -----------------------------------------------------------------------------


class RecipeMigrationRequest(BaseModel):
    """Request to migrate a mapper recipe to a new template version."""

    recipe: dict  # MapperRecipe as dict to avoid circular import
    target_template: str
    target_version: str | None = None
    target_status: Literal["published", "deprecated", "local"] = "published"
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    preserve_transforms: bool = True


class MappingMigrationItem(BaseModel):
    """Describes migration of a single mapping in a recipe."""

    original_path: str
    migrated_path: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    match_reason: Literal["exact_path", "semantic_id", "fuzzy", "unmapped"]
    breaking_change: bool = False
    details: dict | None = None


class RecipeMigrationResult(BaseModel):
    """Result of recipe migration operation."""

    migrated_recipe: dict | None  # MapperRecipe as dict
    mapping_migrations: list[MappingMigrationItem] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    migration_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Form Data Migration
# -----------------------------------------------------------------------------


class ValueMigrationItem(BaseModel):
    """Describes migration of a single form value."""

    original_path: str
    migrated_path: str | None
    original_value: Any = None
    migrated_value: Any = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_reason: Literal["exact_path", "semantic_id", "fuzzy", "unmapped"]


class FormDataMigrationRequest(BaseModel):
    """Request to migrate form data to a new template version."""

    form_data: dict
    source_template: str
    source_version: str | None = None
    source_status: Literal["published", "deprecated", "local"] = "published"
    target_template: str
    target_version: str | None = None
    target_status: Literal["published", "deprecated", "local"] = "published"
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class FormDataMigrationResult(BaseModel):
    """Result of form data migration operation."""

    migrated_form_data: dict | None
    value_migrations: list[ValueMigrationItem] = Field(default_factory=list)
    migration_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Version Mismatch Check
# -----------------------------------------------------------------------------


class VersionMismatchRequest(BaseModel):
    """Request to check for version mismatch."""

    artifact_type: Literal["recipe", "form_data"]
    created_for_digest: str | None
    template_name: str
    template_version: str | None = None
    template_status: Literal["published", "deprecated", "local"] = "published"


class VersionMismatchCheck(BaseModel):
    """Result of version mismatch check."""

    artifact_type: Literal["recipe", "form_data"]
    created_for_digest: str | None
    current_digest: str
    has_mismatch: bool
    breaking_changes_detected: bool = False
    affected_paths: list[str] = Field(default_factory=list)


class TemplateImportRequest(BaseModel):
    """Request to import an existing AASX/JSON as a local template."""

    source_path: str | None = None
    source_url: str | None = None
    template_name: str | None = None
    overwrite: bool = False


class TemplateImportResult(BaseModel):
    """Result of template import operation."""

    success: bool
    template_name: str
    elements_count: int
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class TemplateDiffRequest(BaseModel):
    """Request to compare two template versions."""

    source_template: str
    source_version: str | None = None
    source_status: Literal["published", "deprecated", "local"] = "published"
    target_template: str
    target_version: str | None = None
    target_status: Literal["published", "deprecated", "local"] = "published"
    include_semantic_changes: bool = True


class ElementChange(BaseModel):
    """Describes a change to a template element."""

    path: str
    change_type: Literal["added", "removed", "modified", "moved", "renamed"]
    old_value: str | None = None
    new_value: str | None = None
    details: dict | None = None


class CardinalityChange(BaseModel):
    """Describes a cardinality change."""

    path: str
    old_cardinality: str
    new_cardinality: str
    breaking: bool = False


class SemanticChange(BaseModel):
    """Describes a semantic ID change."""

    path: str
    old_semantic_id: str | None
    new_semantic_id: str | None


class TemplateDiffResult(BaseModel):
    """Result of template diff operation."""

    source_template: str
    source_version: str | None
    target_template: str
    target_version: str | None
    elements_added: list[str] = Field(default_factory=list)
    elements_removed: list[str] = Field(default_factory=list)
    elements_modified: list[ElementChange] = Field(default_factory=list)
    cardinality_changes: list[CardinalityChange] = Field(default_factory=list)
    semantic_changes: list[SemanticChange] = Field(default_factory=list)
    is_breaking: bool = False
    summary: str = ""


class MigrationMappingItem(BaseModel):
    """A single mapping in a migration plan."""

    source_path: str
    target_path: str
    confidence: float = Field(ge=0.0, le=1.0)
    match_reason: Literal["exact", "semantic", "fuzzy", "manual"] = "exact"
    transform: str | None = None


class MigrationPlanRequest(BaseModel):
    """Request to generate a migration plan between template versions."""

    source_template: str
    source_version: str | None = None
    source_status: Literal["published", "deprecated", "local"] = "published"
    target_template: str
    target_version: str | None = None
    target_status: Literal["published", "deprecated", "local"] = "published"
    use_semantics: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MigrationPlan(BaseModel):
    """Migration plan from source to target template."""

    source_template: str
    source_version: str | None
    target_template: str
    target_version: str | None
    auto_mappings: list[MigrationMappingItem] = Field(default_factory=list)
    unmapped_source: list[str] = Field(default_factory=list)
    unmapped_target: list[str] = Field(default_factory=list)
    mapping_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)


class ValidationDiagnostic(BaseModel):
    """A single validation diagnostic."""

    path: str
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    suggestion: str | None = None


class TemplateValidateRequest(BaseModel):
    """Request to run comprehensive validation on a template."""

    template_name: str
    template_version: str | None = None
    template_status: Literal["published", "deprecated", "local"] = "published"
    check_semantic_ids: bool = True
    check_cardinality: bool = True
    check_value_types: bool = True
    check_conformance: bool = True


class ValidationDiagnostics(BaseModel):
    """Comprehensive validation diagnostics for a template."""

    template_name: str
    template_version: str | None
    valid: bool
    errors: list[ValidationDiagnostic] = Field(default_factory=list)
    warnings: list[ValidationDiagnostic] = Field(default_factory=list)
    info: list[ValidationDiagnostic] = Field(default_factory=list)
    element_count: int = 0
    semantic_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    conformance_level: str | None = None
