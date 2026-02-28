"""
SAMM Parser - Parses SAMM TTL/JSON-LD models.

Supports parsing of Catena-X Semantic Aspect Meta Model files
into internal representation for conversion to AAS.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.samm.models import (
    SAMMAspect,
    SAMMCharacteristic,
    SAMMEntity,
    SAMMEnumeration,
    SAMMProperty,
)

logger = logging.getLogger(__name__)


# SAMM namespace prefixes
SAMM_NAMESPACES = {
    "samm": "urn:samm:org.eclipse.esmf.samm:meta-model:",
    "samm-c": "urn:samm:org.eclipse.esmf.samm:characteristic:",
    "samm-e": "urn:samm:org.eclipse.esmf.samm:entity:",
    "unit": "urn:samm:org.eclipse.esmf.samm:unit:",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


class SAMMParser:
    """
    Parser for SAMM (Semantic Aspect Meta Model) files.

    Supports:
    - TTL (Turtle) format
    - JSON-LD format
    """

    def __init__(self):
        self._prefixes: dict[str, str] = {}

    def parse(self, content: str | bytes, format: str = "ttl") -> SAMMAspect:
        """
        Parse a SAMM model from content.

        Args:
            content: Model content (TTL or JSON-LD)
            format: Content format ("ttl" or "json-ld")

        Returns:
            Parsed SAMMAspect model
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        if format == "ttl":
            return self._parse_ttl(content)
        elif format == "json-ld":
            return self._parse_json_ld(content)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _parse_ttl(self, content: str) -> SAMMAspect:
        """Parse TTL format SAMM model."""
        # Try to use rdflib if available
        try:
            return self._parse_ttl_rdflib(content)
        except ImportError:
            logger.warning("rdflib not available, using basic TTL parser")
            return self._parse_ttl_basic(content)

    def _parse_ttl_rdflib(self, content: str) -> SAMMAspect:
        """Parse TTL using rdflib."""
        from rdflib import Graph, Namespace, URIRef
        from rdflib.namespace import RDF

        g = Graph()
        g.parse(data=content, format="turtle")

        # SAMM namespaces
        SAMM = Namespace("urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#")
        SAMM_C = Namespace("urn:samm:org.eclipse.esmf.samm:characteristic:2.1.0#")

        # Find the aspect
        aspect_uri = None
        aspect_name = None
        aspect_version = "1.0.0"

        for s in g.subjects(RDF.type, SAMM.Aspect):
            aspect_uri = str(s)
            # Extract name from URN
            match = re.search(r"#([^#]+)$", aspect_uri)
            if match:
                aspect_name = match.group(1)
            break

        if not aspect_uri or not aspect_name:
            raise ValueError("No SAMM Aspect found in TTL content")

        # Extract version from URN if present
        version_match = re.search(r":(\d+\.\d+\.\d+)#", aspect_uri)
        if version_match:
            aspect_version = version_match.group(1)

        # Parse description
        description = None
        for o in g.objects(URIRef(aspect_uri), SAMM.description):
            description = str(o)
            break

        # Parse preferred names
        preferred_names: dict[str, str] = {}
        for o in g.objects(URIRef(aspect_uri), SAMM.preferredName):
            if hasattr(o, "language") and o.language:
                preferred_names[o.language] = str(o)
            else:
                preferred_names["en"] = str(o)

        # Parse properties
        properties: list[SAMMProperty] = []
        for prop_uri in g.objects(URIRef(aspect_uri), SAMM.properties):
            prop = self._parse_property_rdflib(g, prop_uri, SAMM, SAMM_C)
            if prop:
                properties.append(prop)

        # Parse entities
        entities: list[SAMMEntity] = []
        for s in g.subjects(RDF.type, SAMM.Entity):
            entity = self._parse_entity_rdflib(g, s, SAMM)
            if entity:
                entities.append(entity)

        # Parse characteristics
        characteristics: list[SAMMCharacteristic] = []
        for char_type in [SAMM.Characteristic, SAMM_C.Text, SAMM_C.Boolean]:
            for s in g.subjects(RDF.type, char_type):
                char = self._parse_characteristic_rdflib(g, s, SAMM, SAMM_C)
                if char:
                    characteristics.append(char)

        # Parse enumerations
        enumerations: list[SAMMEnumeration] = []
        for s in g.subjects(RDF.type, SAMM_C.Enumeration):
            enum = self._parse_enumeration_rdflib(g, s, SAMM, SAMM_C)
            if enum:
                enumerations.append(enum)

        return SAMMAspect(
            urn=aspect_uri,
            name=aspect_name,
            version=aspect_version,
            description=description,
            preferred_names=preferred_names,
            properties=properties,
            entities=entities,
            characteristics=characteristics,
            enumerations=enumerations,
        )

    def _parse_property_rdflib(self, g, prop_uri, SAMM, SAMM_C) -> SAMMProperty | None:
        """Parse a property using rdflib."""

        uri = str(prop_uri)
        match = re.search(r"#([^#]+)$", uri)
        name = match.group(1) if match else uri

        description = None
        for o in g.objects(prop_uri, SAMM.description):
            description = str(o)
            break

        characteristic = None
        for o in g.objects(prop_uri, SAMM.characteristic):
            characteristic = str(o)
            break

        optional = False
        for o in g.objects(prop_uri, SAMM.optional):
            optional = str(o).lower() == "true"
            break

        example_value = None
        for o in g.objects(prop_uri, SAMM.exampleValue):
            example_value = str(o)
            break

        preferred_names: dict[str, str] = {}
        for o in g.objects(prop_uri, SAMM.preferredName):
            if hasattr(o, "language") and o.language:
                preferred_names[o.language] = str(o)
            else:
                preferred_names["en"] = str(o)

        return SAMMProperty(
            urn=uri,
            name=name,
            description=description,
            preferred_names=preferred_names,
            characteristic=characteristic,
            example_value=example_value,
            optional=optional,
        )

    def _parse_entity_rdflib(self, g, entity_uri, SAMM) -> SAMMEntity | None:
        """Parse an entity using rdflib."""
        uri = str(entity_uri)
        match = re.search(r"#([^#]+)$", uri)
        name = match.group(1) if match else uri

        description = None
        for o in g.objects(entity_uri, SAMM.description):
            description = str(o)
            break

        properties: list[str] = []
        for o in g.objects(entity_uri, SAMM.properties):
            properties.append(str(o))

        preferred_names: dict[str, str] = {}
        for o in g.objects(entity_uri, SAMM.preferredName):
            if hasattr(o, "language") and o.language:
                preferred_names[o.language] = str(o)
            else:
                preferred_names["en"] = str(o)

        return SAMMEntity(
            urn=uri,
            name=name,
            description=description,
            preferred_names=preferred_names,
            properties=properties,
        )

    def _parse_characteristic_rdflib(
        self, g, char_uri, SAMM, SAMM_C
    ) -> SAMMCharacteristic | None:
        """Parse a characteristic using rdflib."""
        uri = str(char_uri)
        match = re.search(r"#([^#]+)$", uri)
        name = match.group(1) if match else uri

        description = None
        for o in g.objects(char_uri, SAMM.description):
            description = str(o)
            break

        data_type = None
        for o in g.objects(char_uri, SAMM.dataType):
            data_type = str(o)
            break

        unit = None
        for o in g.objects(char_uri, SAMM_C.unit):
            unit = str(o)
            break

        preferred_names: dict[str, str] = {}
        for o in g.objects(char_uri, SAMM.preferredName):
            if hasattr(o, "language") and o.language:
                preferred_names[o.language] = str(o)
            else:
                preferred_names["en"] = str(o)

        return SAMMCharacteristic(
            urn=uri,
            name=name,
            description=description,
            data_type=data_type,
            unit=unit,
            preferred_names=preferred_names,
        )

    def _parse_enumeration_rdflib(
        self, g, enum_uri, SAMM, SAMM_C
    ) -> SAMMEnumeration | None:
        """Parse an enumeration using rdflib."""
        uri = str(enum_uri)
        match = re.search(r"#([^#]+)$", uri)
        name = match.group(1) if match else uri

        description = None
        for o in g.objects(enum_uri, SAMM.description):
            description = str(o)
            break

        values: list[Any] = []
        for o in g.objects(enum_uri, SAMM_C.values):
            # Handle collection
            values.append(str(o))

        data_type = None
        for o in g.objects(enum_uri, SAMM.dataType):
            data_type = str(o)
            break

        return SAMMEnumeration(
            urn=uri,
            name=name,
            description=description,
            values=values,
            data_type=data_type,
        )

    def _parse_ttl_basic(self, content: str) -> SAMMAspect:
        """Basic TTL parser without rdflib."""
        # Extract prefixes (including empty prefix with just ":")
        self._prefixes = {}
        for match in re.finditer(r"@prefix\s*(\w*):\s+<([^>]+)>", content):
            prefix = match.group(1)  # Can be empty string for default prefix
            self._prefixes[prefix] = match.group(2)

        # Find aspect definition
        aspect_match = re.search(
            r":(\w+)\s+a\s+samm:Aspect\s*[;\.]", content, re.MULTILINE
        )
        if not aspect_match:
            raise ValueError("No SAMM Aspect found in TTL content")

        aspect_name = aspect_match.group(1)

        # Extract base URN from default prefix (empty string key)
        base_urn = self._prefixes.get("", "urn:samm:unknown:")
        # Remove trailing # if present (we'll add it when constructing URIs)
        if base_urn.endswith("#"):
            base_urn = base_urn[:-1]
        aspect_urn = f"{base_urn}#{aspect_name}"

        # Extract version from URN
        version_match = re.search(r":(\d+\.\d+\.\d+)#?", base_urn)
        version = version_match.group(1) if version_match else "1.0.0"

        # Extract description (handle language tags like @en)
        desc_match = re.search(
            rf":{aspect_name}\s+[^.]*?samm:description\s+\"([^\"]+)\"(?:@\w+)?",
            content,
            re.DOTALL,
        )
        description = desc_match.group(1) if desc_match else None

        # Extract properties (basic extraction)
        properties: list[SAMMProperty] = []
        props_match = re.search(
            rf":{aspect_name}\s+[^.]*?samm:properties\s+\(\s*([^)]+)\s*\)",
            content,
            re.DOTALL,
        )
        if props_match:
            props_content = props_match.group(1)
            for prop_name in re.findall(r":(\w+)", props_content):
                # Try to extract property description
                prop_desc_match = re.search(
                    rf":{prop_name}\s+[^.]*?samm:description\s+\"([^\"]+)\"",
                    content,
                    re.DOTALL,
                )
                prop_description = (
                    prop_desc_match.group(1) if prop_desc_match else None
                )

                properties.append(
                    SAMMProperty(
                        urn=f"{base_urn}#{prop_name}",
                        name=prop_name,
                        description=prop_description,
                    )
                )

        return SAMMAspect(
            urn=aspect_urn,
            name=aspect_name,
            version=version,
            description=description,
            properties=properties,
        )

    def _parse_json_ld(self, content: str) -> SAMMAspect:
        """Parse JSON-LD format SAMM model."""
        data = json.loads(content)

        # JSON-LD can have @graph or direct representation
        if "@graph" in data:
            graph = data["@graph"]
        else:
            graph = [data] if isinstance(data, dict) else data

        # Find the aspect
        aspect_data = None
        for item in graph:
            item_types = item.get("@type", [])
            if isinstance(item_types, str):
                item_types = [item_types]
            if any("Aspect" in t for t in item_types):
                aspect_data = item
                break

        if not aspect_data:
            raise ValueError("No SAMM Aspect found in JSON-LD content")

        aspect_id = aspect_data.get("@id", "")
        match = re.search(r"#([^#]+)$", aspect_id)
        name = match.group(1) if match else aspect_id

        version_match = re.search(r":(\d+\.\d+\.\d+)#?", aspect_id)
        version = version_match.group(1) if version_match else "1.0.0"

        return SAMMAspect(
            urn=aspect_id,
            name=name,
            version=version,
            description=aspect_data.get("samm:description"),
            properties=[],  # Would need full parsing
        )
