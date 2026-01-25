"""
Schema Resolver - Extract target fields and generate extraction hints from IDTA templates.

Reuses patterns from mapper/service.py:_extract_target_fields() but generates
extraction hints with keywords for LLM-based extraction.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.schemas.magic_import import ExtractionHint
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)


class SchemaResolver:
    """Resolve template schema to extraction hints."""

    # AAS element types that can hold leaf values
    LEAF_TYPES = {
        "Property",
        "MultiLanguageProperty",
        "Range",
        "File",
        "ReferenceElement",
    }

    def __init__(
        self,
        fetcher: TemplateFetcherService | None = None,
        parser: ParserService | None = None,
    ) -> None:
        # Lazy-load services if not provided
        self._fetcher = fetcher
        self._parser = parser

    @property
    def fetcher(self) -> TemplateFetcherService:
        if self._fetcher is None:
            from app.dependencies import get_fetcher
            self._fetcher = get_fetcher()
        return self._fetcher

    @property
    def parser(self) -> ParserService:
        if self._parser is None:
            from app.dependencies import get_parser
            self._parser = get_parser()
        return self._parser

    def resolve_hints(
        self,
        template_name: str,
        template_status: str = "published",
        template_version: str | None = None,
    ) -> list[ExtractionHint]:
        """
        Resolve template schema to extraction hints.

        Args:
            template_name: Name of the IDTA template
            template_status: Template status (published/deprecated)
            template_version: Optional specific version

        Returns:
            List of extraction hints for all fillable fields
        """
        import asyncio

        # Fetch template (handle async in sync context)
        loop = asyncio.new_event_loop()
        try:
            template_bytes = loop.run_until_complete(
                self._fetch_template(template_name, template_status, template_version)
            )
        finally:
            loop.close()

        # Parse to UI schema
        schema = self.parser.parse_aasx_to_ui_schema(template_bytes)

        # Extract hints from schema elements
        elements = schema.get("elements", [])
        hints = self._extract_hints(elements)

        logger.info(
            "Resolved %d extraction hints for template %s",
            len(hints),
            template_name,
        )

        return hints

    async def _fetch_template(
        self,
        template_name: str,
        template_status: str,
        template_version: str | None,
    ) -> bytes:
        """Fetch template AASX bytes."""
        template_path = f"{template_status}/{template_name}"
        if template_version:
            template_path = f"{template_path}/{template_version}"
        return await self.fetcher.fetch_template_aasx(template_path)

    def _extract_hints(
        self,
        elements: list[dict],
        path: list[str] | None = None,
    ) -> list[ExtractionHint]:
        """Recursively extract hints from schema elements."""
        if path is None:
            path = []

        result: list[ExtractionHint] = []

        for element in elements:
            model_type = element.get("modelType", "")
            id_short = element.get("idShort", "")

            # Handle SubmodelElementList
            if model_type == "SubmodelElementList":
                list_path = [*path, f"{id_short}[]"]
                template = element.get("itemTemplate") or (
                    element.get("items", [{}])[0] if element.get("items") else None
                )
                if template:
                    if template.get("modelType") in self.LEAF_TYPES:
                        leaf_path = list_path + [template.get("idShort", "value")]
                        result.append(self._make_hint(template, leaf_path))
                    else:
                        base_path = list_path + [template.get("idShort", "")]
                        if template.get("elements"):
                            result.extend(self._extract_hints(template["elements"], base_path))
                        if template.get("statements"):
                            result.extend(self._extract_hints(template["statements"], base_path))
                continue

            next_path = [*path, id_short]

            # Extract leaf elements as hints
            if model_type in self.LEAF_TYPES:
                result.append(self._make_hint(element, next_path))

            # Recurse into nested elements
            if element.get("elements"):
                result.extend(self._extract_hints(element["elements"], next_path))
            if element.get("statements"):
                result.extend(self._extract_hints(element["statements"], next_path))

        return result

    def _make_hint(self, element: dict, path: list[str]) -> ExtractionHint:
        """Create an ExtractionHint from a schema element."""
        id_short = element.get("idShort", path[-1] if path else "")
        cardinality = element.get("cardinality", "") or "[1]"
        required = self._min_cardinality(cardinality) >= 1

        # Extract semantic ID
        semantic_id = None
        semantic_label = element.get("semanticLabel")
        sem_ref = element.get("semanticId")
        if isinstance(sem_ref, str):
            semantic_id = sem_ref
        elif sem_ref and isinstance(sem_ref, dict):
            keys = sem_ref.get("keys", [])
            if keys and isinstance(keys, list):
                semantic_id = keys[-1].get("value")
        elif sem_ref is not None:
            semantic_id = str(sem_ref)

        # Generate keywords for search
        keywords = self._generate_keywords(
            id_short=id_short,
            path=path,
            semantic_label=semantic_label,
            semantic_id=semantic_id,
        )

        return ExtractionHint(
            path=".".join(path),
            label=id_short,
            element_type=element.get("modelType", "Property"),
            value_type=element.get("valueType"),
            semantic_id=semantic_id,
            semantic_label=semantic_label,
            keywords=keywords,
            required=required,
        )

    def _generate_keywords(
        self,
        id_short: str,
        path: list[str],
        semantic_label: str | None,
        semantic_id: str | None,
    ) -> list[str]:
        """
        Generate search keywords for a field.

        Keywords are used for BM25-style retrieval of relevant snippets.
        """
        keywords: list[str] = []

        # Tokenize idShort (split camelCase and underscores)
        keywords.extend(self._tokenize(id_short))

        # Add path components (excluding list markers)
        for segment in path:
            if not segment.endswith("[]"):
                keywords.extend(self._tokenize(segment))

        # Add semantic label tokens
        if semantic_label:
            keywords.extend(self._tokenize(semantic_label))

        # Extract meaningful parts from semantic ID
        if semantic_id:
            # ECLASS format: 0173-1#01-AAA123#001
            # IEC CDD format: 0112/2///61987#ABB123#001
            # Extract the property name if embedded
            keywords.extend(self._extract_semantic_id_tokens(semantic_id))

        # Add common synonyms for known field types
        keywords.extend(self._get_field_synonyms(id_short))

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw_lower) > 1:
                seen.add(kw_lower)
                unique_keywords.append(kw_lower)

        return unique_keywords[:20]  # Limit to top 20 keywords

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into tokens (handles camelCase, underscores, etc.)."""
        if not text:
            return []

        # Split camelCase
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        # Split on non-alphanumeric
        tokens = re.split(r"[^a-zA-Z0-9]+", text)
        # Filter empty and single-char tokens
        return [t for t in tokens if len(t) > 1]

    @staticmethod
    def _min_cardinality(cardinality: str) -> int:
        """Parse minimum cardinality from bracket or legacy formats."""
        value = str(cardinality).strip()
        if not value:
            return 1

        mapping = {
            "ZeroToOne": "[0..1]",
            "ZeroToMany": "[0..*]",
            "OneToMany": "[1..*]",
            "One": "[1]",
            "Zero": "[0]",
        }
        if value in mapping:
            value = mapping[value]
        if ".." in value and not value.startswith("["):
            value = f"[{value}]"

        match = re.match(r"^\\[(\\d+)(?:\\.\\.(\\d+|\\*))?\\]$", value)
        if match:
            return int(match.group(1))

        if value.isdigit():
            return int(value)

        return 1

    @staticmethod
    def _extract_semantic_id_tokens(semantic_id: str) -> list[str]:
        """Extract meaningful tokens from semantic IDs."""
        tokens = []

        # For IRIs, extract the fragment or last path segment
        if semantic_id.startswith("http"):
            # Get fragment after #
            if "#" in semantic_id:
                fragment = semantic_id.split("#")[-1]
                tokens.extend(SchemaResolver._tokenize(fragment))
            # Get last path segment
            elif "/" in semantic_id:
                segment = semantic_id.rstrip("/").split("/")[-1]
                tokens.extend(SchemaResolver._tokenize(segment))

        return tokens

    @staticmethod
    def _get_field_synonyms(id_short: str) -> list[str]:
        """Get common synonyms for known field types."""
        synonyms_map = {
            # Nameplate fields
            "manufacturername": ["manufacturer", "company", "vendor", "supplier", "made by"],
            "manufacturerproductdesignation": ["product name", "product", "designation", "model"],
            "serialnumber": ["serial", "s/n", "serial no", "sn"],
            "yearconstruction": ["year", "manufactured", "production year", "built"],
            "countrycode": ["country", "origin", "made in"],
            "street": ["address", "street address"],
            "zipcode": ["postal", "zip", "postcode", "plz"],
            "citytown": ["city", "town", "location"],
            # Technical data
            "weight": ["mass", "kg", "weight"],
            "height": ["h", "height", "tall"],
            "width": ["w", "width", "wide"],
            "length": ["l", "length", "long"],
            "voltage": ["v", "volt", "voltage"],
            "current": ["a", "amp", "ampere", "current"],
            "power": ["w", "watt", "power", "kw"],
            "frequency": ["hz", "hertz", "frequency"],
            "temperature": ["temp", "temperature", "celsius", "fahrenheit"],
            # PCF fields
            "pcfcalculationmethod": ["calculation method", "pcf method", "carbon method"],
            "co2footprinttotal": ["carbon footprint", "co2", "emissions", "ghg"],
            "biogeniccarbon": ["biogenic", "bio carbon"],
        }

        id_lower = id_short.lower()
        for key, syns in synonyms_map.items():
            if key in id_lower or id_lower in key:
                return syns

        return []
