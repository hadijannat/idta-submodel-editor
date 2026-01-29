"""
Template Knowledge Builder - Build comprehensive index from IDTA templates.

Fetches all published templates, parses their schema, extracts field metadata,
generates embeddings, and discovers extraction patterns.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from app.services.template_knowledge.embeddings import OllamaEmbeddingClient
from app.services.template_knowledge.models import (
    ExtractionPattern,
    FieldInfo,
    TemplateInfo,
)

if TYPE_CHECKING:
    from app.services.fetcher import TemplateFetcherService
    from app.services.parser import ParserService
    from app.services.template_knowledge.index import TemplateKnowledgeIndex

logger = logging.getLogger(__name__)


class TemplateKnowledgeBuilder:
    """Build knowledge index from all IDTA templates."""

    # AAS element types that can hold leaf values
    LEAF_TYPES = {
        "Property",
        "MultiLanguageProperty",
        "Range",
        "File",
        "ReferenceElement",
    }

    # Context type patterns for categorization
    CONTEXT_PATTERNS = {
        "ContactInformation": ["contact", "email", "phone", "address", "fax"],
        "Nameplate": ["manufacturer", "serial", "batch", "product", "designation"],
        "TechnicalData": [
            "weight",
            "height",
            "width",
            "length",
            "voltage",
            "current",
            "power",
        ],
        "ProductCarbonFootprint": ["carbon", "co2", "pcf", "emission", "footprint"],
        "Documentation": ["document", "manual", "certificate", "datasheet"],
        "Identification": ["id", "identifier", "code", "number", "serial"],
    }

    def __init__(
        self,
        fetcher: TemplateFetcherService,
        parser: ParserService,
        embedding_client: OllamaEmbeddingClient | None = None,
    ) -> None:
        """
        Initialize builder with required services.

        Args:
            fetcher: Service for fetching template AASX files
            parser: Service for parsing AASX to UI schema
            embedding_client: Optional Ollama client for embeddings
        """
        self.fetcher = fetcher
        self.parser = parser
        self.embedding_client = embedding_client or OllamaEmbeddingClient()

    async def build_full_index(
        self,
        index: TemplateKnowledgeIndex,
        status_filter: list[str] | None = None,
        generate_embeddings: bool = True,
        max_templates: int | None = None,
    ) -> dict:
        """
        Fetch all templates and build comprehensive index.

        Args:
            index: Target index to populate
            status_filter: Only index templates with these statuses (default: ["published"])
            generate_embeddings: Whether to generate Ollama embeddings
            max_templates: Maximum templates to index (for testing)

        Returns:
            Build statistics dictionary
        """
        if status_filter is None:
            status_filter = ["published"]

        stats = {
            "templates_processed": 0,
            "templates_failed": 0,
            "fields_indexed": 0,
            "patterns_created": 0,
            "embeddings_generated": 0,
            "start_time": datetime.utcnow().isoformat(),
        }

        # Check Ollama availability if embeddings requested
        if generate_embeddings:
            ollama_available = await self.embedding_client.is_available()
            if not ollama_available:
                logger.warning(
                    "Ollama not available. Embeddings will be skipped. "
                    "Run 'ollama pull nomic-embed-text' to enable embeddings."
                )
                generate_embeddings = False

        # Fetch template list
        templates = await self.fetcher.get_template_list()

        logger.info(
            "Found %d templates. Filtering by status: %s",
            len(templates),
            status_filter,
        )

        # Filter by status
        filtered_templates = [
            t for t in templates if t.get("status", "published") in status_filter
        ]

        if max_templates:
            filtered_templates = filtered_templates[:max_templates]

        logger.info("Indexing %d templates...", len(filtered_templates))

        # Process each template
        for template_meta in filtered_templates:
            try:
                await self._process_template(
                    index=index,
                    template_meta=template_meta,
                    generate_embeddings=generate_embeddings,
                    stats=stats,
                )
            except Exception as e:
                logger.warning(
                    "Failed to index template '%s': %s",
                    template_meta.get("name", "unknown"),
                    e,
                )
                stats["templates_failed"] += 1

        stats["end_time"] = datetime.utcnow().isoformat()

        logger.info(
            "Index build complete. Templates: %d (%d failed), Fields: %d, Patterns: %d",
            stats["templates_processed"],
            stats["templates_failed"],
            stats["fields_indexed"],
            stats["patterns_created"],
        )

        return stats

    async def _process_template(
        self,
        index: TemplateKnowledgeIndex,
        template_meta: dict,
        generate_embeddings: bool,
        stats: dict,
    ) -> None:
        """Process a single template and add to index."""
        template_name = template_meta.get("name", "")
        template_status = template_meta.get("status", "published")

        logger.debug("Processing template: %s", template_name)

        # Fetch template AASX
        template_path = f"{template_status}/{template_name}"
        aasx_bytes = await self.fetcher.fetch_template_aasx(template_path)

        # Parse to UI schema
        schema = self.parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Extract template info
        idta_number = self._extract_idta_number(template_name)
        template_info = TemplateInfo(
            idta_number=idta_number,
            title=template_meta.get("title", template_name),
            version=template_meta.get("version", "1.0"),
            semantic_id=schema.get("semanticId"),
            status=template_status,  # type: ignore
            source_path=template_path,
            description=template_meta.get("description"),
        )

        # Extract all fields recursively
        fields = self._extract_all_fields(schema, idta_number)
        template_info.field_count = len(fields)

        # Add template to index
        index.add_template(template_info)

        # Generate embeddings and add fields
        for field in fields:
            if generate_embeddings:
                embedding_text = field.get_embedding_text()
                try:
                    field.embedding_vector = await self.embedding_client.embed(
                        embedding_text
                    )
                    stats["embeddings_generated"] += 1
                except Exception as e:
                    logger.debug("Failed to generate embedding for %s: %s", field.path, e)

            index.add_field(field)
            stats["fields_indexed"] += 1

        # Discover and add patterns
        patterns = self._discover_patterns(schema, fields)
        for pattern in patterns:
            index.add_pattern(pattern)
            stats["patterns_created"] += 1

        stats["templates_processed"] += 1

    def _extract_all_fields(
        self,
        schema: dict,
        template_idta: str,
        parent_path: str = "",
    ) -> list[FieldInfo]:
        """Recursively extract all field metadata from schema."""
        fields = []
        elements = schema.get("elements", [])

        for element in elements:
            model_type = element.get("modelType", "")
            id_short = element.get("idShort", "")

            # Handle SubmodelElementList
            if model_type == "SubmodelElementList":
                list_path = f"{parent_path}.{id_short}[]" if parent_path else f"{id_short}[]"
                template = element.get("itemTemplate") or (
                    element.get("items", [{}])[0] if element.get("items") else None
                )
                if template:
                    if template.get("modelType") in self.LEAF_TYPES:
                        leaf_path = f"{list_path}.{template.get('idShort', 'value')}"
                        fields.append(
                            self._make_field_info(template, template_idta, leaf_path, list_path)
                        )
                    else:
                        # Recurse into list item template
                        base_path = f"{list_path}.{template.get('idShort', '')}"
                        child_schema = {
                            "elements": template.get("elements", [])
                            + template.get("statements", [])
                        }
                        fields.extend(
                            self._extract_all_fields(child_schema, template_idta, base_path)
                        )
                continue

            # Build path
            path = f"{parent_path}.{id_short}" if parent_path else id_short

            # Extract leaf elements
            if model_type in self.LEAF_TYPES:
                fields.append(self._make_field_info(element, template_idta, path, parent_path))

            # Recurse into nested elements
            child_elements = element.get("elements", []) + element.get("statements", [])
            if child_elements:
                child_schema = {"elements": child_elements}
                fields.extend(self._extract_all_fields(child_schema, template_idta, path))

        return fields

    def _make_field_info(
        self,
        element: dict,
        template_idta: str,
        path: str,
        parent_path: str,
    ) -> FieldInfo:
        """Create a FieldInfo from a schema element."""
        id_short = element.get("idShort", path.split(".")[-1] if path else "")
        cardinality = element.get("cardinality", "") or "[1]"

        # Extract semantic ID
        semantic_id = None
        sem_ref = element.get("semanticId")
        if isinstance(sem_ref, str):
            semantic_id = sem_ref
        elif sem_ref and isinstance(sem_ref, dict):
            keys = sem_ref.get("keys", [])
            if keys and isinstance(keys, list):
                semantic_id = keys[-1].get("value")

        # Parse value type
        value_type = element.get("valueType")
        if isinstance(value_type, str) and value_type.startswith("xsd:"):
            value_type = "xs:" + value_type[4:]

        # Extract description
        definition = self._extract_definition(element.get("description"))

        # Generate keywords
        keywords = self._derive_keywords(element, path)

        # Extract synonyms from semantic info
        synonyms = self._extract_synonyms(element)

        # Determine if required
        is_required = self._min_cardinality(cardinality) >= 1

        return FieldInfo(
            template_idta=template_idta,
            path=path,
            id_short=id_short,
            model_type=element.get("modelType", "Property"),
            value_type=value_type,
            semantic_id=semantic_id,
            semantic_label=element.get("semanticLabel"),
            definition=definition,
            unit=element.get("unit"),
            cardinality=cardinality,
            parent_path=parent_path or None,
            keywords=keywords,
            synonyms=synonyms,
            example_values=element.get("exampleValues", []),
            value_format=element.get("valueFormat"),
            allowed_values=element.get("valueList", []),
            is_required=is_required,
        )

    def _derive_keywords(self, element: dict, path: str) -> list[str]:
        """Derive extraction keywords from element metadata."""
        keywords = set()

        # From idShort (split camelCase)
        keywords.update(self._tokenize(element.get("idShort", "")))

        # From path segments
        for segment in path.split("."):
            if not segment.endswith("[]"):
                keywords.update(self._tokenize(segment))

        # From semantic label
        if element.get("semanticLabel"):
            keywords.update(self._tokenize(element["semanticLabel"]))

        # From description (first 50 words)
        description = element.get("description")
        if description:
            text = self._extract_definition(description) or ""
            words = text.split()[:50]
            for word in words:
                if len(word) > 2:
                    keywords.add(word.lower())

        # Clean up
        stopwords = {
            "the", "and", "for", "with", "from", "this", "that", "which",
            "shall", "should", "may", "can", "will", "must", "is", "are",
            "of", "to", "in", "on", "by", "as", "an", "a",
        }

        return [
            kw for kw in sorted(keywords)
            if kw.lower() not in stopwords and len(kw) > 1
        ][:20]

    def _extract_synonyms(self, element: dict) -> list[str]:
        """Extract synonyms from element's ConceptDescription data."""
        synonyms = []

        # From embedded data specification
        data_spec = element.get("embeddedDataSpecifications", [])
        for spec in data_spec if isinstance(data_spec, list) else []:
            content = spec.get("dataSpecificationContent", {})

            # Preferred name variations
            pref_name = content.get("preferredName", [])
            for name in pref_name if isinstance(pref_name, list) else []:
                if isinstance(name, dict) and name.get("text"):
                    synonyms.append(name["text"])
                elif isinstance(name, str):
                    synonyms.append(name)

            # Short names
            short_name = content.get("shortName", [])
            for name in short_name if isinstance(short_name, list) else []:
                if isinstance(name, dict) and name.get("text"):
                    synonyms.append(name["text"])
                elif isinstance(name, str):
                    synonyms.append(name)

        return list(set(synonyms))

    def _discover_patterns(
        self,
        schema: dict,
        fields: list[FieldInfo],
    ) -> list[ExtractionPattern]:
        """Discover extraction patterns from template structure."""
        patterns = []

        # Group fields by detected context
        context_fields: dict[str, list[FieldInfo]] = {}
        for field in fields:
            context = self._detect_context(field)
            if context:
                context_fields.setdefault(context, []).append(field)

        # Create patterns for each context
        for context_type, context_field_list in context_fields.items():
            # Aggregate keywords from all fields in context
            all_keywords = set()
            for field in context_field_list:
                all_keywords.update(field.keywords[:5])

            pattern = ExtractionPattern(
                field_path=f"*.{context_type}.*",
                context_type=context_type,
                keywords=list(all_keywords)[:15],
                regex_patterns=self._get_common_patterns(context_type),
                table_hints=self._get_table_hints(context_type),
                confidence_weight=1.0,
            )
            patterns.append(pattern)

        return patterns

    def _detect_context(self, field: FieldInfo) -> str | None:
        """Detect context type for a field based on path and keywords."""
        path_lower = field.path.lower()
        keywords_lower = [k.lower() for k in field.keywords]

        for context, markers in self.CONTEXT_PATTERNS.items():
            # Check path contains context marker
            for marker in markers:
                if marker in path_lower:
                    return context
                if marker in keywords_lower:
                    return context

        return None

    def _get_common_patterns(self, context_type: str) -> list[str]:
        """Get common regex patterns for a context type."""
        patterns = {
            "ContactInformation": [
                r"[\w\.-]+@[\w\.-]+\.\w+",  # Email
                r"\+?[\d\s\-\(\)]{7,}",  # Phone
                r"\d{5}",  # Zip code
            ],
            "Nameplate": [
                r"[A-Z]{2,}\d+",  # Serial number pattern
                r"\d{4}",  # Year
            ],
            "TechnicalData": [
                r"\d+\.?\d*\s*(?:kg|g|mm|cm|m|V|A|W|kW|Hz)",  # Number with unit
            ],
            "ProductCarbonFootprint": [
                r"\d+\.?\d*\s*(?:kg\s*CO2|kg\s*CO2e|t\s*CO2)",  # CO2 values
            ],
        }
        return patterns.get(context_type, [])

    def _get_table_hints(self, context_type: str) -> list[str]:
        """Get table header hints for a context type."""
        hints = {
            "ContactInformation": ["Contact", "Address", "Phone", "Email"],
            "Nameplate": ["Specification", "Nameplate", "Product", "Technical"],
            "TechnicalData": ["Technical Data", "Specifications", "Parameters", "Ratings"],
            "ProductCarbonFootprint": ["Carbon Footprint", "Emissions", "CO2", "PCF"],
        }
        return hints.get(context_type, [])

    @staticmethod
    def _extract_idta_number(template_name: str) -> str:
        """Extract IDTA number from template name."""
        # Pattern: IDTA_02006_DigitalNameplate -> 02006
        match = re.search(r"IDTA[_-]?(\d{5})", template_name, re.IGNORECASE)
        if match:
            return match.group(1)

        # Fallback: use template name as-is
        return template_name.replace("_", "-").replace(" ", "-")[:20]

    @staticmethod
    def _extract_definition(description: dict | list | str | None) -> str | None:
        """Extract definition text from description field."""
        if not description:
            return None
        if isinstance(description, str):
            return description
        if isinstance(description, dict):
            # Prefer English, then first available
            for lang in ["en", "en-US", "en-GB"]:
                if lang in description:
                    return str(description[lang])
            return str(next(iter(description.values()), ""))
        if isinstance(description, list):
            for item in description:
                if isinstance(item, dict) and "text" in item:
                    return str(item["text"])
                if isinstance(item, str):
                    return item
        return None

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into tokens (handles camelCase, underscores)."""
        if not text:
            return []
        # Split camelCase
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        # Split on non-alphanumeric
        tokens = re.split(r"[^a-zA-Z0-9]+", text)
        return [t.lower() for t in tokens if len(t) > 1]

    @staticmethod
    def _min_cardinality(cardinality: str) -> int:
        """Parse minimum cardinality from bracket format."""
        value = str(cardinality).strip()
        if not value:
            return 1

        # Legacy format mapping
        mapping = {
            "ZeroToOne": "[0..1]",
            "ZeroToMany": "[0..*]",
            "OneToMany": "[1..*]",
            "One": "[1]",
            "Zero": "[0]",
        }
        if value in mapping:
            value = mapping[value]

        match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", value)
        if match:
            return int(match.group(1))

        return 1
