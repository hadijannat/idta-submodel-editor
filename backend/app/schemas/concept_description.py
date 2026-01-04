"""
Pydantic model for ConceptDescription responses.
"""

from pydantic import BaseModel


class ConceptDescriptionResponse(BaseModel):
    id: str | None = None
    idShort: str | None = None
    description: dict[str, str] | None = None
    displayName: dict[str, str] | None = None
    preferredName: dict[str, str] | None = None
    shortName: dict[str, str] | None = None
    definition: dict[str, str] | None = None
    dataType: str | None = None
    unit: str | None = None
    unitId: str | None = None
    sourceOfDefinition: str | None = None
    symbol: str | None = None
    valueFormat: str | None = None
    value: str | None = None
