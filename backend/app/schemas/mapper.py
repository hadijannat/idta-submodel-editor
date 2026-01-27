"""
Schemas for Smart Mapper (CSV/XLSX bulk import).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DatasetFileInfo(BaseModel):
    name: str
    size: int
    type: str | None = None


class DatasetSheetInfo(BaseModel):
    name: str
    rows: int | None = None
    cols: int | None = None


class DatasetColumnProfile(BaseModel):
    name_original: str
    name_normalized: str
    index: int
    inferred_type: str
    null_rate: float
    distinct_count: int
    examples: list[str] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    profile_id: str
    file: DatasetFileInfo
    sheets: list[DatasetSheetInfo] = Field(default_factory=list)
    columns: list[DatasetColumnProfile]
    sample_rows: list[list[str | None]] = Field(default_factory=list)
    row_count: int | None = None
    header_row: int = 1
    warnings: list[str] = Field(default_factory=list)


class MapperSourceColumn(BaseModel):
    column_name: str
    column_index: int | None = None


class MapperTargetField(BaseModel):
    id_short_path: str
    element_type: str
    value_type: str | None = None
    field: str | None = None
    language: str | None = None


class MapperTransform(BaseModel):
    trim: bool = True
    default_value: str | None = None
    decimal: str | None = "."
    thousands: str | None = None
    date_format: str | None = None
    true_values: list[str] | None = None
    false_values: list[str] | None = None


class MappingItem(BaseModel):
    source: MapperSourceColumn
    target: MapperTargetField
    transform: MapperTransform | None = None
    required: bool = False


class MapperMode(BaseModel):
    type: Literal["single", "row-per-submodel", "grouped"] = "single"
    group_by: list[str] = Field(default_factory=list)


class MapperTemplateRef(BaseModel):
    name: str
    version: str | None = None
    status: Literal["published", "deprecated"] = "published"
    schema_digest: str | None = None  # SHA-256 for schema change detection


class MapperSourceProfileRef(BaseModel):
    format: Literal["csv", "xlsx"]
    sheet: str | None = None
    header_row: int = 1
    header_fingerprint: str | None = None


class MapperRecipe(BaseModel):
    name: str
    schema_version: str = "1.0.0"
    template: MapperTemplateRef
    source_profile: MapperSourceProfileRef
    mode: MapperMode = Field(default_factory=MapperMode)
    mappings: list[MappingItem]


class MapperRunRequest(BaseModel):
    template_name: str
    status: Literal["published", "deprecated"] = "published"
    version: str | None = None
    profile_id: str
    recipe: MapperRecipe
    output_format: Literal["form", "aasx", "json", "pdf"] = "form"
    row_index: int | None = None


class MapperDiagnostic(BaseModel):
    severity: Literal["error", "warning"]
    row_index: int | None = None
    source_column: str | None = None
    target_path: str | None = None
    code: str | None = None
    message: str
    sample: str | None = None


class MapperRunResponse(BaseModel):
    mode: MapperMode
    diagnostics: list[MapperDiagnostic] = Field(default_factory=list)
    form_data: dict | None = None
    form_data_batch: list[dict] | None = None
    row_count: int | None = None


class MapperRecipeList(BaseModel):
    recipes: list[MapperRecipe] = Field(default_factory=list)


class MapperTargetFieldInfo(BaseModel):
    """Target field info with semantic enrichment for auto-mapping."""

    id_short_path: str
    element_type: str
    value_type: str | None = None
    label: str
    required: bool = False
    semantic_id: str | None = None
    semantic_label: str | None = None
    semantic_synonyms: list[str] = Field(default_factory=list)
    languages: list[str] | None = None


class MapperSuggestedMapping(BaseModel):
    """A suggested column-to-field mapping with confidence score."""

    source_column: str
    source_index: int
    target_path: str
    target_type: str
    target_value_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_reason: str


class MapperAutoSuggestRequest(BaseModel):
    """Request for auto-suggesting mappings."""

    template_name: str
    status: Literal["published", "deprecated"] = "published"
    version: str | None = None
    profile_id: str
    use_semantics: bool = True
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)


class MapperAutoSuggestResponse(BaseModel):
    """Response with suggested mappings."""

    suggestions: list[MapperSuggestedMapping]
    target_fields: list[MapperTargetFieldInfo]
    semantic_resolved: int = 0
    semantic_errors: int = 0
