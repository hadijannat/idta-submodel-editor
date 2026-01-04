"""
Pydantic models for form submission data.

These models define the structure of data submitted from the frontend
when saving or exporting a submodel.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ElementFormData(BaseModel):
    """
    Form data for a single SubmodelElement.

    The structure mirrors the UI schema but only contains
    user-editable values.
    """

    # Common value field for simple types
    value: Any = None

    # For SubmodelElementCollection
    elements: dict[str, "ElementFormData"] | None = None

    # For SubmodelElementList
    items: list["ElementFormData"] | None = None

    # For Range
    min: Any = None
    max: Any = None

    # For Entity
    globalAssetId: str | None = None
    statements: dict[str, "ElementFormData"] | None = None

    # For File
    contentType: str | None = None

    # For Relationship
    first: str | None = None
    second: str | None = None
    annotations: list["ElementFormData"] | None = None

    class Config:
        extra = "allow"


# Enable forward references
ElementFormData.model_rebuild()


class SubmodelFormData(BaseModel):
    """
    Complete form submission data for a Submodel.

    This is the top-level structure submitted when saving or exporting.
    """

    elements: dict[str, ElementFormData] = Field(default_factory=dict)
    metadata: dict[str, Any] | None = None

    @field_validator("elements", mode="before")
    @classmethod
    def ensure_elements_dict(cls, v):
        if v is None:
            return {}
        return v


class ExportRequest(BaseModel):
    """Request for exporting a filled submodel."""

    template_name: str
    form_data: SubmodelFormData
    format: str = "aasx"  # aasx, json, pdf
    filename: str | None = None


class UploadResponse(BaseModel):
    """Response after uploading an AASX file."""

    success: bool
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    error: str | None = None
    filename: str | None = None

    model_config = {
        "populate_by_name": True,
    }


class HydrateResponse(BaseModel):
    """Response after hydrating a template."""

    success: bool
    download_url: str | None = None
    error: str | None = None


class ValidationError(BaseModel):
    """Validation error detail."""

    field: str
    message: str
    code: str | None = None


class ValidationResult(BaseModel):
    """Result of form validation."""

    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
