"""
SAMM Generator - Generates SAMM TTL from AAS structures.

Converts AAS (Asset Administration Shell) submodels
to Catena-X SAMM (Semantic Aspect Meta Model) format.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.services.samm.models import (
    AAS_TO_SAMM_TYPE_MAP,
    SAMMAspect,
    SAMMCharacteristic,
    SAMMEntity,
    SAMMProperty,
)

logger = logging.getLogger(__name__)


class SAMMGenerator:
    """
    Generator for SAMM models from AAS structures.

    Converts AAS UI schema or submodel templates to SAMM TTL format.
    """

    def __init__(self, namespace: str = "org.idta.generated"):
        """
        Initialize the SAMM generator.

        Args:
            namespace: Base namespace for generated models
        """
        self.namespace = namespace

    def generate_from_ui_schema(
        self,
        schema: dict,
        version: str = "1.0.0",
    ) -> tuple[SAMMAspect, str]:
        """
        Generate SAMM model from AAS UI schema.

        Args:
            schema: AAS UI schema dictionary
            version: Version for the generated model

        Returns:
            Tuple of (SAMMAspect model, TTL content)
        """
        # Extract basic info
        template_name = schema.get("idShort", "GeneratedAspect")
        semantic_id = schema.get("semanticId", "")

        # Clean name for URN
        aspect_name = self._clean_name(template_name)
        base_urn = f"urn:samm:{self.namespace}:{aspect_name}:{version}#"

        # Parse elements
        elements = schema.get("elements", [])
        properties: list[SAMMProperty] = []
        entities: list[SAMMEntity] = []
        characteristics: list[SAMMCharacteristic] = []

        for element in elements:
            self._process_element(
                element, base_urn, properties, entities, characteristics
            )

        # Build aspect
        aspect = SAMMAspect(
            urn=f"{base_urn}{aspect_name}",
            name=aspect_name,
            version=version,
            description=f"Generated from AAS template: {template_name}",
            properties=properties,
            entities=entities,
            characteristics=characteristics,
            see=[semantic_id] if semantic_id else [],
        )

        # Generate TTL
        ttl = self._generate_ttl(aspect, base_urn)

        return aspect, ttl

    def _process_element(
        self,
        element: dict,
        base_urn: str,
        properties: list[SAMMProperty],
        entities: list[SAMMEntity],
        characteristics: list[SAMMCharacteristic],
    ) -> None:
        """Process a single AAS element."""
        element_type = element.get("modelType", "")
        id_short = element.get("idShort", "")

        if not id_short:
            return

        name = self._clean_name(id_short)
        urn = f"{base_urn}{name}"

        if element_type == "Property":
            # Create characteristic for the property
            char_urn = f"{base_urn}{name}Characteristic"
            value_type = element.get("valueType", "xs:string")
            samm_type = AAS_TO_SAMM_TYPE_MAP.get(value_type, "xsd:string")

            characteristics.append(
                SAMMCharacteristic(
                    urn=char_urn,
                    name=f"{name}Characteristic",
                    description=element.get("description"),
                    data_type=samm_type,
                )
            )

            # Create property
            cardinality = element.get("cardinality", {})
            optional = cardinality.get("min", 1) == 0

            properties.append(
                SAMMProperty(
                    urn=urn,
                    name=name,
                    description=element.get("description"),
                    characteristic=char_urn,
                    optional=optional,
                    example_value=element.get("value"),
                )
            )

        elif element_type == "SubmodelElementCollection":
            # Create entity for collection
            entity_props: list[str] = []
            nested_elements = element.get("elements", [])

            for nested in nested_elements:
                nested_name = self._clean_name(nested.get("idShort", ""))
                if nested_name:
                    entity_props.append(f"{base_urn}{nested_name}")
                    # Recursively process nested elements
                    self._process_element(
                        nested, base_urn, properties, entities, characteristics
                    )

            entities.append(
                SAMMEntity(
                    urn=urn,
                    name=name,
                    description=element.get("description"),
                    properties=entity_props,
                )
            )

            # Create characteristic for the entity
            char_urn = f"{base_urn}{name}Characteristic"
            characteristics.append(
                SAMMCharacteristic(
                    urn=char_urn,
                    name=f"{name}Characteristic",
                    description=f"Characteristic for {name} entity",
                    data_type=urn,  # Entity as data type
                )
            )

            # Create property referencing the entity
            cardinality = element.get("cardinality", {})
            optional = cardinality.get("min", 1) == 0

            properties.append(
                SAMMProperty(
                    urn=f"{base_urn}{name}Property",
                    name=name,
                    description=element.get("description"),
                    characteristic=char_urn,
                    optional=optional,
                )
            )

        elif element_type == "SubmodelElementList":
            # Create collection characteristic
            item_type = element.get("typeValueListElement", "Property")
            char_urn = f"{base_urn}{name}Characteristic"

            characteristics.append(
                SAMMCharacteristic(
                    urn=char_urn,
                    name=f"{name}Characteristic",
                    description=f"Collection of {name}",
                    # Would need element characteristic for proper SAMM
                )
            )

            properties.append(
                SAMMProperty(
                    urn=urn,
                    name=name,
                    description=element.get("description"),
                    characteristic=char_urn,
                    optional=element.get("cardinality", {}).get("min", 1) == 0,
                )
            )

    def _generate_ttl(self, aspect: SAMMAspect, base_urn: str) -> str:
        """Generate TTL content from SAMMAspect."""
        lines = []

        # Prefixes
        lines.append(f"@prefix : <{base_urn}> .")
        lines.append("@prefix samm: <urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#> .")
        lines.append(
            "@prefix samm-c: <urn:samm:org.eclipse.esmf.samm:characteristic:2.1.0#> ."
        )
        lines.append("@prefix samm-e: <urn:samm:org.eclipse.esmf.samm:entity:2.1.0#> .")
        lines.append("@prefix unit: <urn:samm:org.eclipse.esmf.samm:unit:2.1.0#> .")
        lines.append("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
        lines.append("")

        # Aspect definition
        lines.append(f":{aspect.name} a samm:Aspect ;")
        if aspect.description:
            lines.append(f'    samm:description "{self._escape_ttl(aspect.description)}"@en ;')

        # Properties
        if aspect.properties:
            prop_urns = " ".join(f":{p.name}" for p in aspect.properties)
            lines.append(f"    samm:properties ( {prop_urns} ) ;")

        lines.append("    .")
        lines.append("")

        # Property definitions
        for prop in aspect.properties:
            lines.append(f":{prop.name} a samm:Property ;")
            if prop.description:
                lines.append(
                    f'    samm:description "{self._escape_ttl(prop.description)}"@en ;'
                )
            if prop.characteristic:
                char_name = prop.characteristic.split("#")[-1]
                lines.append(f"    samm:characteristic :{char_name} ;")
            if prop.example_value:
                lines.append(
                    f'    samm:exampleValue "{self._escape_ttl(str(prop.example_value))}" ;'
                )
            if prop.optional:
                lines.append('    samm:optional "true"^^xsd:boolean ;')
            lines.append("    .")
            lines.append("")

        # Entity definitions
        for entity in aspect.entities:
            lines.append(f":{entity.name} a samm:Entity ;")
            if entity.description:
                lines.append(
                    f'    samm:description "{self._escape_ttl(entity.description)}"@en ;'
                )
            if entity.properties:
                prop_names = " ".join(
                    f":{p.split('#')[-1]}" for p in entity.properties
                )
                lines.append(f"    samm:properties ( {prop_names} ) ;")
            lines.append("    .")
            lines.append("")

        # Characteristic definitions
        for char in aspect.characteristics:
            lines.append(f":{char.name} a samm:Characteristic ;")
            if char.description:
                lines.append(
                    f'    samm:description "{self._escape_ttl(char.description)}"@en ;'
                )
            if char.data_type:
                if char.data_type.startswith("xsd:"):
                    lines.append(f"    samm:dataType {char.data_type} ;")
                else:
                    type_name = char.data_type.split("#")[-1]
                    lines.append(f"    samm:dataType :{type_name} ;")
            lines.append("    .")
            lines.append("")

        return "\n".join(lines)

    def _clean_name(self, name: str) -> str:
        """Clean a name for use in URN."""
        # Remove invalid characters
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "", name)
        # Ensure starts with letter
        if cleaned and not cleaned[0].isalpha():
            cleaned = "Element" + cleaned
        return cleaned or "Unknown"

    def _escape_ttl(self, value: str) -> str:
        """Escape a string for TTL format."""
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
