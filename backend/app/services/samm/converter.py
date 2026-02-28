"""
SAMM Converter - Bidirectional SAMM ↔ AAS conversion.

Bridges Catena-X SAMM (Semantic Aspect Meta Model) and
IDTA AAS (Asset Administration Shell) ecosystems.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.samm.generator import SAMMGenerator
from app.services.samm.models import (
    ConversionDirection,
    ConversionResult,
    ConversionWarning,
    SAMMAspect,
    SAMM_TO_AAS_TYPE_MAP,
)
from app.services.samm.parser import SAMMParser

if TYPE_CHECKING:
    from app.services.parser import ParserService
    from app.services.fetcher import TemplateFetcherService

logger = logging.getLogger(__name__)


class SAMMConverter:
    """
    Bidirectional converter between SAMM and AAS.

    Provides:
    - SAMM → AAS: Import Aspect Model, generate SubmodelTemplate skeleton
    - AAS → SAMM: Export Submodel, generate SAMM Aspect Model + example payload
    """

    def __init__(
        self,
        fetcher: "TemplateFetcherService | None" = None,
        parser: "ParserService | None" = None,
        namespace: str = "org.idta.generated",
    ):
        self._fetcher = fetcher
        self._parser = parser
        self._samm_parser = SAMMParser()
        self._samm_generator = SAMMGenerator(namespace=namespace)

    async def convert_samm_to_aas(
        self,
        content: str | bytes,
        format: str = "ttl",
    ) -> ConversionResult:
        """
        Convert a SAMM model to AAS structure.

        Args:
            content: SAMM model content (TTL or JSON-LD)
            format: Content format ("ttl" or "json-ld")

        Returns:
            ConversionResult with AAS template and UI schema
        """
        now = datetime.now(timezone.utc)
        warnings: list[ConversionWarning] = []

        try:
            # Parse SAMM model
            aspect = self._samm_parser.parse(content, format=format)
            logger.info("Parsed SAMM aspect: %s (v%s)", aspect.name, aspect.version)

            # Convert to AAS structure
            aas_template, aas_schema, conv_warnings = self._convert_aspect_to_aas(
                aspect
            )
            warnings.extend(conv_warnings)

            elements_converted = (
                len(aspect.properties)
                + len(aspect.entities)
                + len(aspect.characteristics)
            )

            return ConversionResult(
                success=True,
                direction=ConversionDirection.SAMM_TO_AAS,
                aas_template=aas_template,
                aas_schema=aas_schema,
                source_urn=aspect.urn,
                target_name=f"SAMM-{aspect.name}",
                warnings=warnings,
                converted_at=now,
                elements_converted=elements_converted,
            )

        except Exception as e:
            logger.exception("SAMM to AAS conversion failed")
            return ConversionResult(
                success=False,
                direction=ConversionDirection.SAMM_TO_AAS,
                warnings=[
                    ConversionWarning(
                        element="SAMM model",
                        message=str(e),
                    )
                ],
                converted_at=now,
            )

    async def convert_aas_to_samm(
        self,
        template_name: str,
        template_status: str = "published",
        template_version: str | None = None,
        version: str = "1.0.0",
    ) -> ConversionResult:
        """
        Convert an AAS template to SAMM model.

        Args:
            template_name: Name of the AAS template
            template_status: Template status (published/deprecated)
            template_version: Optional specific version
            version: Version for the generated SAMM model

        Returns:
            ConversionResult with SAMM model and TTL content
        """
        now = datetime.now(timezone.utc)
        warnings: list[ConversionWarning] = []

        if not self._fetcher or not self._parser:
            return ConversionResult(
                success=False,
                direction=ConversionDirection.AAS_TO_SAMM,
                warnings=[
                    ConversionWarning(
                        element="converter",
                        message="Fetcher and parser required for AAS to SAMM conversion",
                    )
                ],
                converted_at=now,
            )

        try:
            # Fetch and parse the AAS template
            template_path = f"{template_status}/{template_name}"
            if template_version:
                template_path = f"{template_path}/{template_version}"

            template_bytes = await self._fetcher.fetch_template_aasx(template_path)
            ui_schema = self._parser.parse_aasx_to_ui_schema(template_bytes)

            # Generate SAMM model
            aspect, ttl = self._samm_generator.generate_from_ui_schema(
                ui_schema, version=version
            )

            elements_converted = (
                len(aspect.properties)
                + len(aspect.entities)
                + len(aspect.characteristics)
            )

            return ConversionResult(
                success=True,
                direction=ConversionDirection.AAS_TO_SAMM,
                samm_model=aspect,
                samm_ttl=ttl,
                source_urn=ui_schema.get("semanticId", ""),
                target_name=aspect.name,
                warnings=warnings,
                converted_at=now,
                elements_converted=elements_converted,
            )

        except Exception as e:
            logger.exception("AAS to SAMM conversion failed")
            return ConversionResult(
                success=False,
                direction=ConversionDirection.AAS_TO_SAMM,
                warnings=[
                    ConversionWarning(
                        element=template_name,
                        message=str(e),
                    )
                ],
                converted_at=now,
            )

    def _convert_aspect_to_aas(
        self, aspect: SAMMAspect
    ) -> tuple[dict, dict, list[ConversionWarning]]:
        """Convert SAMM aspect to AAS template structure and UI schema."""
        warnings: list[ConversionWarning] = []

        char_map = {c.urn: c for c in aspect.characteristics}
        entity_map = {e.urn: e for e in aspect.entities}

        # Generate UI schema elements
        elements: list[dict] = []

        for prop in aspect.properties:
            element = self._convert_property_to_element(
                prop, char_map, entity_map, warnings
            )
            if element:
                elements.append(element)

        # Build UI schema
        ui_schema = {
            "idShort": aspect.name,
            "description": aspect.description,
            "semanticId": aspect.urn,
            "modelType": "Submodel",
            "elements": elements,
        }

        # Build template structure (simplified AAS format)
        aas_template = {
            "modelType": "Submodel",
            "idShort": aspect.name,
            "id": aspect.urn,
            "semanticId": {
                "type": "ExternalReference",
                "keys": [
                    {
                        "type": "GlobalReference",
                        "value": aspect.urn,
                    }
                ],
            },
            "submodelElements": [
                self._element_to_submodel_element(el) for el in elements
            ],
        }

        return aas_template, ui_schema, warnings

    def _convert_property_to_element(
        self,
        prop,
        char_map: dict,
        entity_map: dict,
        warnings: list[ConversionWarning],
    ) -> dict | None:
        """Convert SAMM property to AAS element."""
        # Get characteristic
        char = char_map.get(prop.characteristic) if prop.characteristic else None

        # Determine if this is an entity reference
        if char and char.data_type in entity_map:
            # Entity becomes SubmodelElementCollection
            entity = entity_map[char.data_type]
            return self._convert_entity_to_smc(entity, char_map, entity_map, warnings)

        # Default to Property
        value_type = "xs:string"
        if char and char.data_type:
            samm_type = char.data_type
            if samm_type in SAMM_TO_AAS_TYPE_MAP:
                value_type = SAMM_TO_AAS_TYPE_MAP[samm_type]
            elif samm_type.startswith("xsd:"):
                # Try direct mapping
                value_type = samm_type.replace("xsd:", "xs:")
            else:
                warnings.append(
                    ConversionWarning(
                        element=prop.name,
                        message=f"Unknown SAMM type: {samm_type}, using xs:string",
                        suggestion="Define custom type mapping",
                    )
                )

        return {
            "idShort": prop.name,
            "modelType": "Property",
            "description": prop.description
            or (prop.preferred_names.get("en") if prop.preferred_names else None),
            "semanticId": prop.urn,
            "valueType": value_type,
            "value": prop.example_value,
            "cardinality": {
                "min": 0 if prop.optional else 1,
                "max": 1,
            },
        }

    def _convert_entity_to_smc(
        self,
        entity,
        char_map: dict,
        entity_map: dict,
        warnings: list[ConversionWarning],
    ) -> dict:
        """Convert SAMM entity to SubmodelElementCollection."""
        elements = []

        # Would need to resolve entity properties
        # For now, create placeholder

        return {
            "idShort": entity.name,
            "modelType": "SubmodelElementCollection",
            "description": entity.description
            or (entity.preferred_names.get("en") if entity.preferred_names else None),
            "semanticId": entity.urn,
            "elements": elements,
            "cardinality": {
                "min": 0,
                "max": 1,
            },
        }

    def _element_to_submodel_element(self, element: dict) -> dict:
        """Convert UI schema element to AAS submodel element format."""
        model_type = element.get("modelType", "Property")

        if model_type == "Property":
            return {
                "modelType": "Property",
                "idShort": element.get("idShort"),
                "semanticId": (
                    {
                        "type": "ExternalReference",
                        "keys": [
                            {"type": "GlobalReference", "value": element.get("semanticId")}
                        ],
                    }
                    if element.get("semanticId")
                    else None
                ),
                "valueType": element.get("valueType", "xs:string"),
                "value": element.get("value"),
            }
        elif model_type == "SubmodelElementCollection":
            return {
                "modelType": "SubmodelElementCollection",
                "idShort": element.get("idShort"),
                "semanticId": (
                    {
                        "type": "ExternalReference",
                        "keys": [
                            {"type": "GlobalReference", "value": element.get("semanticId")}
                        ],
                    }
                    if element.get("semanticId")
                    else None
                ),
                "value": [
                    self._element_to_submodel_element(el)
                    for el in element.get("elements", [])
                ],
            }
        else:
            return element
