"""
Schema Resolver - Extract target fields and generate extraction hints from IDTA templates.

Reuses patterns from mapper/service.py:_extract_target_fields() but generates
extraction hints with keywords for LLM-based extraction.

Enhanced with Template Knowledge Index for dynamic keyword generation when available.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.schemas.magic_import import ExtractionHint
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService

if TYPE_CHECKING:
    from app.services.template_knowledge import TemplateKnowledgeIndex

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

    # Context-aware synonyms: parent context → field → keywords
    # This prevents confusion between manufacturer vs supplier/vendor
    CONTEXT_SYNONYMS: dict[str, dict[str, list[str]]] = {
        "ContactInformation": {
            "email": ["email", "e-mail", "electronic mail", "email address", "mail"],
            "phone": ["phone", "telephone", "tel", "tel.", "mobile", "cell", "phone number"],
            "fax": ["fax", "telefax"],
            "website": ["website", "web", "homepage", "url", "www"],
            "street": ["street", "address", "road", "addr", "address line"],
            "zipcode": ["zip", "postal", "postcode", "plz", "zip code"],
            "citytown": ["city", "town", "location", "place"],
            "nationalcode": ["country", "nation", "country code"],
            "po_box": ["po box", "p.o. box", "post box"],
        },
        "Nameplate": {
            # Manufacturer fields - do NOT include vendor/supplier
            "manufacturername": ["manufacturer", "producer", "made by", "hersteller"],
            "manufacturerproductdesignation": ["product name", "product", "designation", "model name"],
            "manufacturerproductfamily": ["product family", "family", "series"],
            "serialnumber": ["serial", "s/n", "serial no", "sn", "serial number"],
            "batchnumber": ["batch", "lot", "batch no", "lot no"],
            "yearconstruction": ["year", "manufactured", "production year", "built", "construction year"],
        },
        "TechnicalData": {
            "weight": ["weight", "mass", "kg", "gross weight", "net weight"],
            "height": ["height", "h", "tall"],
            "width": ["width", "w", "wide"],
            "length": ["length", "l", "long", "depth"],
            "voltage": ["voltage", "v", "volt", "rated voltage"],
            "current": ["current", "a", "amp", "ampere", "rated current"],
            "power": ["power", "w", "watt", "kw", "rated power"],
            "frequency": ["frequency", "hz", "hertz"],
        },
        "ProductCarbonFootprint": {
            "pcfcalculationmethod": ["calculation method", "pcf method", "methodology"],
            "co2footprinttotal": ["carbon footprint", "co2", "emissions", "ghg", "co2e"],
            "biogeniccarbon": ["biogenic", "bio carbon", "biogenic carbon content"],
        },
    }

    # Semantic ID to keyword mapping (ECLASS/IEC CDD IRDIs)
    SEMANTIC_ID_KEYWORDS: dict[str, list[str]] = {
        # Nameplate semantic IDs (ECLASS)
        "0173-1#01-AAS001#001": ["manufacturer", "producer"],
        "0173-1#02-AAO677#002": ["manufacturer", "company name"],
        "0173-1#02-AAW338#001": ["product designation", "product name"],
        "0173-1#02-AAO676#002": ["serial number", "serial", "s/n"],
        # Contact semantic IDs
        "0173-1#02-AAQ832#002": ["email", "e-mail"],
        "0173-1#02-AAO133#002": ["phone", "telephone"],
        "0173-1#02-AAO132#002": ["fax", "telefax"],
    }

    # Global synonyms - used as fallback, reduced scope (no vendor/supplier for manufacturer)
    GLOBAL_SYNONYMS: dict[str, list[str]] = {
        "serialnumber": ["serial", "s/n", "serial no", "sn"],
        "yearconstruction": ["year", "manufactured", "production year"],
        "countrycode": ["country", "origin", "made in"],
        "street": ["address", "street address"],
        "zipcode": ["postal", "zip", "postcode", "plz"],
        "citytown": ["city", "town", "location"],
        "email": ["email", "e-mail", "mail"],
        "phone": ["phone", "telephone", "tel", "tel."],
        "fax": ["fax", "telefax"],
        "website": ["website", "web", "homepage", "url", "www"],
        "weight": ["mass", "kg"],
        "voltage": ["v", "volt"],
        "current": ["a", "amp", "ampere"],
        "power": ["w", "watt", "kw"],
        "frequency": ["hz", "hertz"],
        "temperature": ["temp", "celsius", "fahrenheit"],
    }

    DESCRIPTION_STOPWORDS = {
        "information",
        "recommendation",
        "property",
        "definition",
        "required",
        "value",
        "language",
        "independent",
        "declaration",
        "specification",
        "characterization",
        "enumeration",
        "should",
        "may",
        "shall",
        "used",
        "according",
        "accord",
        "to",
        "with",
        "for",
        "the",
        "and",
        "is",
        "of",
        "as",
        "by",
        "its",
    }

    def __init__(
        self,
        fetcher: TemplateFetcherService | None = None,
        parser: ParserService | None = None,
        knowledge_index: "TemplateKnowledgeIndex | None" = None,
    ) -> None:
        # Lazy-load services if not provided
        self._fetcher = fetcher
        self._parser = parser
        self._knowledge_index = knowledge_index
        self._knowledge_index_checked = False

    @property
    def knowledge_index(self) -> "TemplateKnowledgeIndex | None":
        """Get the Template Knowledge Index if available."""
        if not self._knowledge_index_checked:
            self._knowledge_index_checked = True
            if self._knowledge_index is None:
                try:
                    from app.config import get_settings
                    from app.services.template_knowledge import TemplateKnowledgeIndex

                    settings = get_settings()
                    if settings.template_knowledge_enabled:
                        db_path = settings.magic_import_cache_dir / "template_knowledge" / "index.db"
                        if db_path.exists():
                            self._knowledge_index = TemplateKnowledgeIndex(db_path=db_path)
                            logger.info("Template Knowledge Index loaded from %s", db_path)
                        else:
                            logger.debug("Template Knowledge Index not found at %s", db_path)
                except Exception as e:
                    logger.debug("Could not load Template Knowledge Index: %s", e)
        return self._knowledge_index

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

        # Extract IDTA number for Knowledge Index lookup
        template_idta = self._extract_idta_number(template_name)

        # Extract hints from schema elements
        elements = schema.get("elements", [])
        hints = self._extract_hints(elements, template_idta=template_idta)

        logger.info(
            "Resolved %d extraction hints for template %s (IDTA: %s)",
            len(hints),
            template_name,
            template_idta,
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
        template_idta: str | None = None,
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
                        result.append(self._make_hint(template, leaf_path, template_idta))
                    else:
                        base_path = list_path + [template.get("idShort", "")]
                        if template.get("elements"):
                            result.extend(self._extract_hints(template["elements"], base_path, template_idta))
                        if template.get("statements"):
                            result.extend(self._extract_hints(template["statements"], base_path, template_idta))
                continue

            next_path = [*path, id_short]

            # Extract leaf elements as hints
            if model_type in self.LEAF_TYPES:
                result.append(self._make_hint(element, next_path, template_idta))

            # Recurse into nested elements
            if element.get("elements"):
                result.extend(self._extract_hints(element["elements"], next_path, template_idta))
            if element.get("statements"):
                result.extend(self._extract_hints(element["statements"], next_path, template_idta))

        return result

    @staticmethod
    def _extract_idta_number(template_name: str) -> str | None:
        """Extract IDTA number from template name."""
        # Pattern: IDTA_02006_DigitalNameplate -> 02006
        match = re.search(r"IDTA[_-]?(\d{5})", template_name, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _make_hint(
        self, element: dict, path: list[str], template_idta: str | None = None
    ) -> ExtractionHint:
        """Create an ExtractionHint from a schema element."""
        id_short = element.get("idShort", path[-1] if path else "")
        cardinality = element.get("cardinality", "") or "[1]"
        required = self._min_cardinality(cardinality) >= 1
        description = element.get("description")

        value_type = element.get("valueType")
        if isinstance(value_type, str) and value_type.startswith("xsd:"):
            value_type = "xs:" + value_type[4:]

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

        # Generate keywords for search (using Knowledge Index if available)
        keywords = self._generate_keywords(
            id_short=id_short,
            path=path,
            semantic_label=semantic_label,
            semantic_id=semantic_id,
            description=description,
            template_idta=template_idta,
        )

        return ExtractionHint(
            path=".".join(path),
            label=id_short,
            element_type=element.get("modelType", "Property"),
            value_type=value_type,
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
        description: dict | list | str | None,
        template_idta: str | None = None,
    ) -> list[str]:
        """
        Generate search keywords for a field.

        Keywords are used for BM25-style retrieval of relevant snippets.
        Uses priority:
        1. Template Knowledge Index (if available)
        2. Semantic ID > context-aware > global synonyms (fallback)
        """
        keywords: list[str] = []

        # Try to get keywords from Knowledge Index first
        if self.knowledge_index and template_idta:
            path_str = ".".join(path)
            try:
                indexed_keywords = self.knowledge_index.get_keywords_for_field(
                    template_idta=template_idta,
                    path=path_str,
                    include_similar=True,
                    max_keywords=20,
                )
                if indexed_keywords:
                    logger.debug("Using %d keywords from Knowledge Index for %s", len(indexed_keywords), path_str)
                    return indexed_keywords
            except Exception as e:
                logger.debug("Knowledge Index lookup failed for %s: %s", path_str, e)

        # Fallback to static keyword generation
        # Tokenize idShort (split camelCase and underscores)
        keywords.extend(self._tokenize(id_short))

        # Add path components (excluding list markers)
        for segment in path:
            if not segment.endswith("[]"):
                keywords.extend(self._tokenize(segment))

        # Add semantic label tokens
        if semantic_label:
            keywords.extend(self._tokenize(semantic_label))

        # Add description tokens (if any)
        description_texts = self._collect_description_texts(description)
        for text in description_texts:
            keywords.extend(self._tokenize(text))

        # Extract meaningful parts from semantic ID
        if semantic_id:
            # ECLASS format: 0173-1#01-AAA123#001
            # IEC CDD format: 0112/2///61987#ABB123#001
            # Extract the property name if embedded
            keywords.extend(self._extract_semantic_id_tokens(semantic_id))

        # Add context-aware synonyms (priority: semantic ID > context > global)
        keywords.extend(self._get_field_synonyms(id_short, path, semantic_id))

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw_lower) > 1:
                seen.add(kw_lower)
                unique_keywords.append(kw_lower)

        # Drop noisy tokens and cap to top 20
        filtered = [
            kw for kw in unique_keywords
            if kw not in self.DESCRIPTION_STOPWORDS
        ]
        return filtered[:20]

    @staticmethod
    def _collect_description_texts(description: dict | list | str | None) -> list[str]:
        """Extract description strings from UI-schema description fields."""
        if not description:
            return []
        if isinstance(description, str):
            return [description]
        if isinstance(description, dict):
            return [str(v) for v in description.values() if v]
        if isinstance(description, list):
            texts: list[str] = []
            for item in description:
                if isinstance(item, dict) and "text" in item:
                    texts.append(str(item["text"]))
                elif isinstance(item, str):
                    texts.append(item)
            return texts
        return []

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

        match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", value)
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

    def _get_field_synonyms(
        self,
        id_short: str,
        path: list[str],
        semantic_id: str | None,
    ) -> list[str]:
        """
        Get context-aware synonyms for a field.

        Priority order:
        1. Semantic ID specific (most precise)
        2. Context-aware (based on parent element)
        3. Global synonyms (fallback, reduced scope)

        This prevents confusion like manufacturer vs vendor/supplier.
        """
        synonyms: list[str] = []

        # 1. Check semantic ID first (most precise)
        if semantic_id:
            for sem_id, keywords in self.SEMANTIC_ID_KEYWORDS.items():
                if sem_id in semantic_id:
                    synonyms.extend(keywords)
                    return synonyms  # Semantic ID match is authoritative

        # 2. Check context-aware synonyms based on path
        id_lower = id_short.lower()
        for context_name, field_synonyms in self.CONTEXT_SYNONYMS.items():
            # Check if any path segment matches the context
            context_lower = context_name.lower()
            path_matches_context = any(
                context_lower in segment.lower() for segment in path
            )
            if path_matches_context:
                # Look for matching field in this context
                for field_key, syns in field_synonyms.items():
                    if field_key in id_lower or id_lower in field_key:
                        synonyms.extend(syns)
                        return synonyms  # Context match found

        # 3. Fallback to global synonyms (reduced scope)
        for key, syns in self.GLOBAL_SYNONYMS.items():
            if key in id_lower or id_lower in key:
                synonyms.extend(syns)
                return synonyms

        return []
