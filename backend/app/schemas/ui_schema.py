"""
Pydantic models for UI schema representation.

These models define the structure of the JSON schema sent to the frontend
for form rendering.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class AllowedValueSchema(BaseModel):
    """One entry of an enumeration a template defines for a value."""

    value: str
    label: str | None = None
    valueId: str | None = None


class AllowedRangeSchema(BaseModel):
    """Numeric range declared with an SMT/AllowedRange qualifier."""

    min: int | float | None = None
    max: int | float | None = None


class FormatHintSchema(BaseModel):
    """
    Format standard recognised in the specification text of an element
    (e.g. ISO 3166-1 alpha-2 country code). Advisory: mismatches are warnings.
    """

    id: str
    label: str
    description: str
    pattern: str | None = None
    example: str | None = None
    options: str | None = None
    transform: str | None = None
    source: str = "description"


class ElementSchema(BaseModel):
    """
    Schema for a SubmodelElement.

    This is the recursive structure that represents any AAS element
    in a form-renderable format.
    """

    idShort: str
    modelType: str
    semanticId: str | None = None
    supplementalSemanticIds: list[str] = Field(default_factory=list)
    semanticLabel: str | None = None
    # Human-readable field label (displayName, preferred name or idShort)
    label: str | None = None
    description: dict[str, str] | None = None
    # Definition from the ConceptDescription, when the element also carries
    # its own description (which in IDTA templates holds the spec notes)
    definition: dict[str, str] | None = None
    qualifiers: list[QualifierSchema] = Field(default_factory=list)
    cardinality: str = "[1]"
    category: str | None = None

    # Requirements declared by the template (qualifiers / IEC 61360)
    exampleValues: list[str] | None = None
    defaultValue: str | None = None
    initialValue: str | None = None
    allowedValues: list[AllowedValueSchema] | None = None
    allowedValuesStrict: bool | None = None
    pattern: str | None = None
    allowedRange: AllowedRangeSchema | None = None
    requiredLanguages: list[str] | None = None
    eitherOr: str | None = None
    allowedIdShort: str | None = None
    editIdShort: bool | None = None
    accessMode: str | None = None
    readOnly: bool | None = None
    formTitle: str | None = None
    formInfo: str | None = None
    formUrl: str | None = None
    notes: list[str] | None = None
    valueFormat: str | None = None
    valueFormatDescription: str | None = None
    maxLength: int | None = None
    minLength: int | None = None
    sourceOfDefinition: str | None = None

    # Requirements recognised in the specification text
    formatHint: FormatHintSchema | None = None
    standards: list[str] | None = None
    # Requirements read from the specification PDF
    specNotes: list[str] | None = None
    specCardinality: str | None = None
    specPage: int | None = None

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
    valueEncoding: str | None = None

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


class SpecificAssetIdSchema(BaseModel):
    """Schema for SpecificAssetId per IDTA Metamodel V3.0."""

    name: str
    value: str
    externalSubjectId: str | None = None


class AssetInformationSchema(BaseModel):
    """
    Schema for AssetInformation per IDTA Metamodel V3.0.

    AssetInformation is MANDATORY in an AAS and contains:
    - assetKind: Whether the asset is a Type or Instance (MANDATORY)
    - globalAssetId: Globally unique identifier
    - specificAssetIds: Additional identifiers (e.g., serial numbers)
    - assetType: Classification of the asset
    """

    assetKind: str | None = None  # "INSTANCE" or "TYPE"
    globalAssetId: str | None = None
    specificAssetIds: list[SpecificAssetIdSchema] = Field(default_factory=list)
    assetType: str | None = None


class AASMetadataSchema(BaseModel):
    """
    Schema for AssetAdministrationShell metadata per IDTA Metamodel V3.0.

    Used for PDF export to display AAS-level information including:
    - AAS identifier
    - Asset information (MANDATORY per metamodel)
    - Submodel references
    - derivedFrom reference (optional inheritance)
    """

    id: str
    idShort: str | None = None
    assetInformation: AssetInformationSchema
    submodelRefs: list[str] = Field(default_factory=list)
    derivedFrom: str | None = None
    administration: AdministrationSchema | None = None


class TemplateDocumentSchema(BaseModel):
    """A file that belongs to a template version (AASX, JSON, PDF, README)."""

    name: str
    path: str | None = None
    url: str | None = None
    downloadUrl: str | None = None
    size: int | None = None


class TemplateDocumentsSchema(BaseModel):
    """Companion documents of the resolved template version."""

    aasx: TemplateDocumentSchema | None = None
    json_: TemplateDocumentSchema | None = Field(default=None, alias="json")
    specification: TemplateDocumentSchema | None = None
    readme: TemplateDocumentSchema | None = None

    model_config = ConfigDict(populate_by_name=True)


class TemplateSourceSchema(BaseModel):
    """Which template release a schema was generated from."""

    name: str
    title: str | None = None
    status: str | None = None
    idtaNumber: str | None = None
    group: str | None = None
    part: str | None = None
    version: str | None = None
    latestVersion: str | None = None
    isLatest: bool | None = None
    source: str | None = None
    stale: bool | None = None
    browseUrl: str | None = None
    documents: TemplateDocumentsSchema | None = None
    variants: list[str] = Field(default_factory=list)


class SubmodelUISchema(BaseModel):
    """
    Complete UI schema for a Submodel.

    This is the top-level structure returned by the parser.
    """

    aas: AASMetadataSchema | None = None
    templateName: str | None = None
    templatePath: str | None = None
    # Resolved release of the template and its companion documents
    template: TemplateSourceSchema | None = None
    kind: str | None = None
    formTitle: str | None = None
    formInfo: str | None = None
    formUrl: str | None = None
    submodelId: str
    idShort: str
    semanticId: str | None = None
    description: dict[str, str] | None = None
    administration: AdministrationSchema | None = None
    elements: list[ElementSchema]
    supplementaryFiles: list[str] = Field(default_factory=list)
    pcfActivityListInjected: bool | None = None
    readWarnings: list[str] = Field(
        default_factory=list,
        description=(
            "What could not be read from the template, for example elements "
            "the AAS library rejected. Empty when the template was read in full."
        ),
    )


class TemplateInfo(BaseModel):
    """Information about an available template."""

    name: str
    path: str
    url: str
    idta_number: str | None = None
    title: str | None = None
    sha: str | None = None
    status: Literal["published", "deprecated"] | None = None
    # Multi-part templates (e.g. Digital Battery Passport) list one entry per
    # part; ``group`` is the template they belong to.
    group: str | None = None
    part: str | None = None
    latest_version: str | None = None
    versions: list[str] = Field(default_factory=list)
    has_specification: bool | None = None


class TemplateVersionInfo(BaseModel):
    """Information about a template version."""

    version: str
    path: str
    sha: str | None = None
    file: str | None = None
    latest: bool | None = None
    has_specification: bool | None = None
    sample_only: bool | None = None


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
