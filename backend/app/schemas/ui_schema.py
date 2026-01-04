"""
Pydantic models for UI schema representation.

These models define the structure of the JSON schema sent to the frontend
for form rendering.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class QualifierSchema(BaseModel):
    """Schema for a Qualifier on a SubmodelElement."""

    type: str = Field(..., alias="type")
    value: str | int | float | bool | None = None
    valueType: str | None = None
    semanticId: str | None = None
    kind: str | None = None

    class Config:
        populate_by_name = True


class ConstraintSchema(BaseModel):
    """Schema for numeric constraints."""

    min: int | float | None = None
    max: int | float | None = None


class ElementSchema(BaseModel):
    """
    Schema for a SubmodelElement.

    This is the recursive structure that represents any AAS element
    in a form-renderable format.
    """

    idShort: str
    modelType: str
    semanticId: str | None = None
    semanticLabel: str | None = None
    description: dict[str, str] | None = None
    qualifiers: list[QualifierSchema] = Field(default_factory=list)
    cardinality: str = "[1]"
    category: str | None = None

    # Property-specific fields
    valueType: str | None = None
    value: Any = None
    inputType: str | None = None
    step: str | None = None
    constraints: ConstraintSchema | None = None
    unit: str | None = None
    valueId: str | None = None

    # Collection-specific fields
    elements: list["ElementSchema"] | None = None

    # List-specific fields
    typeValueListElement: str | None = None
    orderRelevant: bool | None = None
    valueTypeListElement: str | None = None
    semanticIdListElement: str | None = None
    itemTemplate: "ElementSchema | None" = None
    items: list["ElementSchema"] | None = None

    # MultiLanguageProperty-specific fields
    supportedLanguages: list[str] | None = None

    # File-specific fields
    contentType: str | None = None

    # Range-specific fields
    min: Any = None
    max: Any = None

    # Entity-specific fields
    entityType: str | None = None
    globalAssetId: str | None = None
    specificAssetIds: list[dict[str, str]] | None = None
    statements: list["ElementSchema"] | None = None

    # Relationship-specific fields
    first: str | None = None
    second: str | None = None
    annotations: list["ElementSchema"] | None = None

    # Operation-specific fields
    inputVariables: list["ElementSchema"] | None = None
    outputVariables: list["ElementSchema"] | None = None
    inoutputVariables: list["ElementSchema"] | None = None

    # Event-specific fields
    observed: str | None = None
    direction: str | None = None
    state: str | None = None
    messageTopic: str | None = None
    messageBroker: str | None = None
    lastUpdate: str | None = None
    minInterval: str | None = None
    maxInterval: str | None = None

    class Config:
        extra = "allow"


# Enable forward references
ElementSchema.model_rebuild()


class AdministrationSchema(BaseModel):
    """Schema for AdministrativeInformation."""

    version: str | None = None
    revision: str | None = None
    creator: str | None = None
    templateId: str | None = None


class SubmodelUISchema(BaseModel):
    """
    Complete UI schema for a Submodel.

    This is the top-level structure returned by the parser.
    """

    templateName: str | None = None
    templatePath: str | None = None
    submodelId: str
    idShort: str
    semanticId: str | None = None
    description: dict[str, str] | None = None
    administration: AdministrationSchema | None = None
    elements: list[ElementSchema]
    supplementaryFiles: list[str] = Field(default_factory=list)


class TemplateInfo(BaseModel):
    """Information about an available template."""

    name: str
    path: str
    url: str
    idta_number: str | None = None
    title: str | None = None
    sha: str | None = None


class TemplateVersionInfo(BaseModel):
    """Information about a template version."""

    version: str
    path: str
    sha: str | None = None


class TemplateListResponse(BaseModel):
    """Response for template listing endpoint."""

    templates: list[TemplateInfo]
    total: int
    cached: bool = False


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "unhealthy"]
    version: str
    details: dict[str, Any] | None = None
