"""
Data models for SAMM Converter.

Defines SAMM (Semantic Aspect Meta Model) structures
and conversion result types.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversionDirection(str, Enum):
    """Direction of SAMM ↔ AAS conversion."""

    SAMM_TO_AAS = "samm_to_aas"
    AAS_TO_SAMM = "aas_to_samm"


class SAMMDataType(str, Enum):
    """SAMM data types based on XSD."""

    STRING = "xsd:string"
    BOOLEAN = "xsd:boolean"
    DECIMAL = "xsd:decimal"
    INTEGER = "xsd:integer"
    INT = "xsd:int"
    LONG = "xsd:long"
    FLOAT = "xsd:float"
    DOUBLE = "xsd:double"
    DATE = "xsd:date"
    DATE_TIME = "xsd:dateTime"
    DATE_TIME_STAMP = "xsd:dateTimeStamp"
    TIME = "xsd:time"
    G_YEAR = "xsd:gYear"
    G_MONTH = "xsd:gMonth"
    G_DAY = "xsd:gDay"
    G_YEAR_MONTH = "xsd:gYearMonth"
    G_MONTH_DAY = "xsd:gMonthDay"
    DURATION = "xsd:duration"
    YEAR_MONTH_DURATION = "xsd:yearMonthDuration"
    DAY_TIME_DURATION = "xsd:dayTimeDuration"
    BYTE = "xsd:byte"
    SHORT = "xsd:short"
    UNSIGNED_BYTE = "xsd:unsignedByte"
    UNSIGNED_SHORT = "xsd:unsignedShort"
    UNSIGNED_INT = "xsd:unsignedInt"
    UNSIGNED_LONG = "xsd:unsignedLong"
    POSITIVE_INTEGER = "xsd:positiveInteger"
    NON_NEGATIVE_INTEGER = "xsd:nonNegativeInteger"
    NEGATIVE_INTEGER = "xsd:negativeInteger"
    NON_POSITIVE_INTEGER = "xsd:nonPositiveInteger"
    HEX_BINARY = "xsd:hexBinary"
    BASE64_BINARY = "xsd:base64Binary"
    ANY_URI = "xsd:anyURI"
    CURIE = "samm:curie"
    LANG_STRING = "rdf:langString"


class SAMMCharacteristic(BaseModel):
    """SAMM Characteristic defining how a property value is interpreted."""

    urn: str = Field(description="Full URN of the characteristic")
    name: str = Field(description="Local name of the characteristic")
    description: str | None = Field(default=None)
    data_type: str | None = Field(default=None, description="Base data type")
    preferred_names: dict[str, str] = Field(
        default_factory=dict, description="Localized preferred names"
    )

    # For enumerations
    values: list[str] | None = Field(default=None, description="Enumeration values")

    # For collections
    element_characteristic: str | None = Field(
        default=None, description="URN of element characteristic for collections"
    )

    # For quantifiable values
    unit: str | None = Field(default=None, description="Unit URN")


class SAMMUnit(BaseModel):
    """SAMM Unit definition."""

    urn: str = Field(description="Full URN of the unit")
    name: str = Field(description="Local name")
    symbol: str | None = Field(default=None)
    quantity_kind: str | None = Field(default=None)
    reference_unit: str | None = Field(default=None)
    conversion_factor: float | None = Field(default=None)


class SAMMConstraint(BaseModel):
    """SAMM Constraint on a characteristic."""

    urn: str = Field(description="Full URN of the constraint")
    constraint_type: str = Field(description="Type of constraint")
    value: Any = Field(default=None, description="Constraint value")
    # For range constraints
    min_value: Any | None = Field(default=None)
    max_value: Any | None = Field(default=None)
    # For length constraints
    min_length: int | None = Field(default=None)
    max_length: int | None = Field(default=None)
    # For pattern constraints
    pattern: str | None = Field(default=None)


class SAMMProperty(BaseModel):
    """SAMM Property definition."""

    urn: str = Field(description="Full URN of the property")
    name: str = Field(description="Local name")
    description: str | None = Field(default=None)
    preferred_names: dict[str, str] = Field(
        default_factory=dict, description="Localized preferred names"
    )
    characteristic: str | None = Field(
        default=None, description="URN of the characteristic"
    )
    example_value: Any = Field(default=None)
    optional: bool = Field(default=False)
    not_in_payload: bool = Field(default=False)
    payload_name: str | None = Field(default=None)


class SAMMEntity(BaseModel):
    """SAMM Entity (complex type) definition."""

    urn: str = Field(description="Full URN of the entity")
    name: str = Field(description="Local name")
    description: str | None = Field(default=None)
    preferred_names: dict[str, str] = Field(
        default_factory=dict, description="Localized preferred names"
    )
    properties: list[str] = Field(
        default_factory=list, description="URNs of properties"
    )
    extends: str | None = Field(default=None, description="URN of parent entity")


class SAMMEnumeration(BaseModel):
    """SAMM Enumeration definition."""

    urn: str = Field(description="Full URN of the enumeration")
    name: str = Field(description="Local name")
    description: str | None = Field(default=None)
    values: list[Any] = Field(default_factory=list)
    data_type: str | None = Field(default=None)


class SAMMOperation(BaseModel):
    """SAMM Operation definition."""

    urn: str = Field(description="Full URN of the operation")
    name: str = Field(description="Local name")
    description: str | None = Field(default=None)
    input_properties: list[str] = Field(default_factory=list)
    output_property: str | None = Field(default=None)


class SAMMEvent(BaseModel):
    """SAMM Event definition."""

    urn: str = Field(description="Full URN of the event")
    name: str = Field(description="Local name")
    description: str | None = Field(default=None)
    parameters: list[str] = Field(default_factory=list)


class SAMMAspect(BaseModel):
    """SAMM Aspect Model - the top-level container."""

    urn: str = Field(description="Full URN of the aspect")
    name: str = Field(description="Aspect name")
    version: str = Field(description="Aspect version (semantic versioning)")
    description: str | None = Field(default=None)
    preferred_names: dict[str, str] = Field(
        default_factory=dict, description="Localized preferred names"
    )

    # Model elements
    properties: list[SAMMProperty] = Field(default_factory=list)
    entities: list[SAMMEntity] = Field(default_factory=list)
    characteristics: list[SAMMCharacteristic] = Field(default_factory=list)
    enumerations: list[SAMMEnumeration] = Field(default_factory=list)
    units: list[SAMMUnit] = Field(default_factory=list)
    constraints: list[SAMMConstraint] = Field(default_factory=list)
    operations: list[SAMMOperation] = Field(default_factory=list)
    events: list[SAMMEvent] = Field(default_factory=list)

    # Metadata
    see: list[str] = Field(default_factory=list, description="Reference URIs")


class ConversionWarning(BaseModel):
    """Warning generated during conversion."""

    element: str = Field(description="Element that caused the warning")
    message: str = Field(description="Warning message")
    suggestion: str | None = Field(default=None, description="Suggested fix")


class ConversionResult(BaseModel):
    """Result of a SAMM ↔ AAS conversion."""

    success: bool = Field(description="Whether conversion succeeded")
    direction: ConversionDirection = Field(description="Conversion direction")

    # For SAMM → AAS
    aas_template: dict | None = Field(
        default=None, description="Generated AAS template structure"
    )
    aas_schema: dict | None = Field(
        default=None, description="Generated UI schema"
    )

    # For AAS → SAMM
    samm_model: SAMMAspect | None = Field(
        default=None, description="Generated SAMM model"
    )
    samm_ttl: str | None = Field(default=None, description="Generated TTL content")

    # Conversion metadata
    source_urn: str | None = Field(default=None, description="Source model URN")
    target_name: str | None = Field(default=None, description="Generated target name")
    warnings: list[ConversionWarning] = Field(
        default_factory=list, description="Conversion warnings"
    )
    converted_at: datetime = Field(description="Conversion timestamp")
    elements_converted: int = Field(default=0, description="Number of elements converted")


# Type mapping: SAMM data types to AAS DataTypeDefXsd
SAMM_TO_AAS_TYPE_MAP: dict[str, str] = {
    "xsd:string": "xs:string",
    "xsd:boolean": "xs:boolean",
    "xsd:decimal": "xs:decimal",
    "xsd:integer": "xs:integer",
    "xsd:int": "xs:int",
    "xsd:long": "xs:long",
    "xsd:float": "xs:float",
    "xsd:double": "xs:double",
    "xsd:date": "xs:date",
    "xsd:dateTime": "xs:dateTime",
    "xsd:dateTimeStamp": "xs:dateTime",
    "xsd:time": "xs:time",
    "xsd:gYear": "xs:gYear",
    "xsd:gMonth": "xs:gMonth",
    "xsd:gDay": "xs:gDay",
    "xsd:gYearMonth": "xs:gYearMonth",
    "xsd:gMonthDay": "xs:gMonthDay",
    "xsd:duration": "xs:duration",
    "xsd:byte": "xs:byte",
    "xsd:short": "xs:short",
    "xsd:unsignedByte": "xs:unsignedByte",
    "xsd:unsignedShort": "xs:unsignedShort",
    "xsd:unsignedInt": "xs:unsignedInt",
    "xsd:unsignedLong": "xs:unsignedLong",
    "xsd:positiveInteger": "xs:positiveInteger",
    "xsd:nonNegativeInteger": "xs:nonNegativeInteger",
    "xsd:negativeInteger": "xs:negativeInteger",
    "xsd:nonPositiveInteger": "xs:nonPositiveInteger",
    "xsd:hexBinary": "xs:hexBinary",
    "xsd:base64Binary": "xs:base64Binary",
    "xsd:anyURI": "xs:anyURI",
    "rdf:langString": "xs:string",
    "samm:curie": "xs:string",
}

# Reverse mapping: AAS to SAMM (explicit to handle multiple SAMM types mapping to same AAS type)
# When multiple SAMM types map to the same AAS type, we use the canonical XSD type
AAS_TO_SAMM_TYPE_MAP: dict[str, str] = {
    "xs:string": "xsd:string",  # Canonical - not rdf:langString or samm:curie
    "xs:boolean": "xsd:boolean",
    "xs:decimal": "xsd:decimal",
    "xs:integer": "xsd:integer",
    "xs:int": "xsd:int",
    "xs:long": "xsd:long",
    "xs:float": "xsd:float",
    "xs:double": "xsd:double",
    "xs:date": "xsd:date",
    "xs:dateTime": "xsd:dateTime",  # Canonical - not xsd:dateTimeStamp
    "xs:time": "xsd:time",
    "xs:gYear": "xsd:gYear",
    "xs:gMonth": "xsd:gMonth",
    "xs:gDay": "xsd:gDay",
    "xs:gYearMonth": "xsd:gYearMonth",
    "xs:gMonthDay": "xsd:gMonthDay",
    "xs:duration": "xsd:duration",
    "xs:byte": "xsd:byte",
    "xs:short": "xsd:short",
    "xs:unsignedByte": "xsd:unsignedByte",
    "xs:unsignedShort": "xsd:unsignedShort",
    "xs:unsignedInt": "xsd:unsignedInt",
    "xs:unsignedLong": "xsd:unsignedLong",
    "xs:positiveInteger": "xsd:positiveInteger",
    "xs:nonNegativeInteger": "xsd:nonNegativeInteger",
    "xs:negativeInteger": "xsd:negativeInteger",
    "xs:nonPositiveInteger": "xsd:nonPositiveInteger",
    "xs:hexBinary": "xsd:hexBinary",
    "xs:base64Binary": "xsd:base64Binary",
    "xs:anyURI": "xsd:anyURI",
}
