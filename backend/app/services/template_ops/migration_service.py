"""
Migration service for template operations.

Applies MigrationPlan to recipes and form data, enabling version migration
when upstream templates change.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.fetcher import TemplateFetcherService
    from app.services.parser import ParserService

from app.schemas.template_ops import (
    FormDataMigrationRequest,
    FormDataMigrationResult,
    MappingMigrationItem,
    RecipeMigrationRequest,
    RecipeMigrationResult,
    SchemaDigest,
    ValueMigrationItem,
    VersionMismatchCheck,
    VersionMismatchRequest,
)

logger = logging.getLogger(__name__)


class MigrationService:
    """
    Applies MigrationPlan to recipes and form data.

    Uses a three-phase migration algorithm:
    1. Exact path match (confidence 1.0)
    2. Semantic ID match (confidence 0.95 same type, 0.75 different type)
    3. Fuzzy matching with weighted scoring
    """

    # Weights for fuzzy matching
    WEIGHTS = {
        "semantic_id": 0.40,
        "element_type": 0.20,
        "idshort_similarity": 0.25,
        "parent_context": 0.10,
        "qualifier_overlap": 0.05,
    }

    def __init__(
        self,
        fetcher: "TemplateFetcherService",
        parser: "ParserService",
    ) -> None:
        self.fetcher = fetcher
        self.parser = parser

    def compute_schema_digest(self, schema: dict) -> SchemaDigest:
        """
        Compute a deterministic digest of a schema for change detection.

        The digest is computed from normalized element paths and their types,
        ensuring consistent hashing across sessions.
        """
        elements = schema.get("elements", [])
        index = self._build_path_index(elements)

        # Sort paths for deterministic ordering
        sorted_paths = sorted(index.keys())

        # Build canonical representation
        canonical_parts: list[str] = []
        for path in sorted_paths:
            elem = index[path]
            model_type = elem.get("modelType", "")
            value_type = elem.get("valueType", "")
            semantic_id = elem.get("semanticId", "")
            cardinality = elem.get("cardinality", "")

            canonical_parts.append(
                f"{path}|{model_type}|{value_type}|{semantic_id}|{cardinality}"
            )

        canonical = "\n".join(canonical_parts)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return SchemaDigest(
            digest=digest,
            element_count=len(index),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

    async def compute_schema_digest_for_template(
        self,
        template_name: str,
        template_version: str | None = None,
        template_status: str = "published",
    ) -> SchemaDigest:
        """Fetch template and compute its schema digest."""
        template_path = f"{template_status}/{template_name}"
        if template_version:
            template_path = f"{template_path}/{template_version}"

        template_bytes = await self.fetcher.fetch_template_aasx(template_path)
        schema = self.parser.parse_aasx_to_ui_schema(template_bytes)
        return self.compute_schema_digest(schema)

    async def migrate_recipe(
        self, request: RecipeMigrationRequest
    ) -> RecipeMigrationResult:
        """
        Migrate a mapper recipe to a new template version.

        Returns a migrated recipe with updated target paths, along with
        details about each mapping migration.
        """
        recipe = request.recipe

        # Determine source template info from recipe
        template_ref = recipe.get("template", {})
        source_template = template_ref.get("name", "")
        source_version = template_ref.get("version")
        source_status = template_ref.get("status", "published")

        # Fetch source schema
        source_path = f"{source_status}/{source_template}"
        if source_version:
            source_path = f"{source_path}/{source_version}"
        source_bytes = await self.fetcher.fetch_template_aasx(source_path)
        source_schema = self.parser.parse_aasx_to_ui_schema(source_bytes)

        # Fetch target schema
        target_path = f"{request.target_status}/{request.target_template}"
        if request.target_version:
            target_path = f"{target_path}/{request.target_version}"
        target_bytes = await self.fetcher.fetch_template_aasx(target_path)
        target_schema = self.parser.parse_aasx_to_ui_schema(target_bytes)

        # Build path indices
        source_index = self._build_path_index(source_schema.get("elements", []))
        target_index = self._build_path_index(target_schema.get("elements", []))

        # Build migration mapping
        path_migration = self._build_migration_mapping(
            source_index, target_index, request.min_confidence
        )

        # Migrate recipe mappings
        migrated_mappings: list[dict] = []
        mapping_migrations: list[MappingMigrationItem] = []
        breaking_changes: list[str] = []
        warnings: list[str] = []

        original_mappings = recipe.get("mappings", [])
        for mapping in original_mappings:
            target_field = mapping.get("target", {})
            original_path = target_field.get("id_short_path", "")

            migration_info = path_migration.get(original_path)
            if migration_info:
                migrated_path = migration_info["target_path"]
                confidence = migration_info["confidence"]
                match_reason = migration_info["match_reason"]

                # Create migrated mapping
                migrated_mapping = self._migrate_single_mapping(
                    mapping,
                    migrated_path,
                    target_index.get(migrated_path, {}),
                    request.preserve_transforms,
                )
                migrated_mappings.append(migrated_mapping)

                # Check for breaking changes
                breaking = migration_info.get("breaking", False)
                if breaking:
                    breaking_changes.append(
                        f"Type change for {original_path}: "
                        f"{migration_info.get('source_type')} → "
                        f"{migration_info.get('target_type')}"
                    )

                mapping_migrations.append(
                    MappingMigrationItem(
                        original_path=original_path,
                        migrated_path=migrated_path,
                        confidence=confidence,
                        match_reason=match_reason,
                        breaking_change=breaking,
                        details=migration_info.get("details"),
                    )
                )
            else:
                # Unmapped - element was removed or no match found
                mapping_migrations.append(
                    MappingMigrationItem(
                        original_path=original_path,
                        migrated_path=None,
                        confidence=0.0,
                        match_reason="unmapped",
                        breaking_change=True,
                    )
                )
                breaking_changes.append(f"No mapping found for {original_path}")

        # Calculate coverage
        total_mappings = len(original_mappings)
        mapped_count = sum(
            1 for m in mapping_migrations if m.match_reason != "unmapped"
        )
        coverage = mapped_count / total_mappings if total_mappings > 0 else 1.0

        # Build migrated recipe
        migrated_recipe = None
        if mapped_count > 0:
            migrated_recipe = {
                **recipe,
                "template": {
                    "name": request.target_template,
                    "version": request.target_version,
                    "status": request.target_status,
                    "schema_digest": self.compute_schema_digest(target_schema).digest,
                },
                "mappings": migrated_mappings,
            }

        if not migrated_mappings:
            warnings.append("No mappings could be migrated")

        return RecipeMigrationResult(
            migrated_recipe=migrated_recipe,
            mapping_migrations=mapping_migrations,
            breaking_changes=breaking_changes,
            migration_coverage=coverage,
            warnings=warnings,
        )

    async def migrate_form_data(
        self, request: FormDataMigrationRequest
    ) -> FormDataMigrationResult:
        """
        Migrate form data to a new template version.

        Returns migrated form data with values placed in their new paths.
        """
        # Fetch source schema
        source_path = f"{request.source_status}/{request.source_template}"
        if request.source_version:
            source_path = f"{source_path}/{request.source_version}"
        source_bytes = await self.fetcher.fetch_template_aasx(source_path)
        source_schema = self.parser.parse_aasx_to_ui_schema(source_bytes)

        # Fetch target schema
        target_path = f"{request.target_status}/{request.target_template}"
        if request.target_version:
            target_path = f"{target_path}/{request.target_version}"
        target_bytes = await self.fetcher.fetch_template_aasx(target_path)
        target_schema = self.parser.parse_aasx_to_ui_schema(target_bytes)

        # Build indices
        source_index = self._build_path_index(source_schema.get("elements", []))
        target_index = self._build_path_index(target_schema.get("elements", []))

        # Build migration mapping
        path_migration = self._build_migration_mapping(
            source_index, target_index, request.min_confidence
        )

        # Extract values from form data
        form_values = self._extract_form_values(request.form_data)

        # Migrate values
        migrated_form_data: dict = {"elements": {}}
        value_migrations: list[ValueMigrationItem] = []
        warnings: list[str] = []

        for original_path, original_value in form_values.items():
            migration_info = path_migration.get(original_path)
            if migration_info:
                migrated_path = migration_info["target_path"]
                confidence = migration_info["confidence"]
                match_reason = migration_info["match_reason"]

                # Place value in migrated location
                self._set_form_value(migrated_form_data, migrated_path, original_value)

                value_migrations.append(
                    ValueMigrationItem(
                        original_path=original_path,
                        migrated_path=migrated_path,
                        original_value=original_value,
                        migrated_value=original_value,  # Value unchanged
                        confidence=confidence,
                        match_reason=match_reason,
                    )
                )
            else:
                value_migrations.append(
                    ValueMigrationItem(
                        original_path=original_path,
                        migrated_path=None,
                        original_value=original_value,
                        migrated_value=None,
                        confidence=0.0,
                        match_reason="unmapped",
                    )
                )
                warnings.append(f"Value at {original_path} could not be migrated")

        # Calculate coverage
        total_values = len(form_values)
        mapped_count = sum(
            1 for m in value_migrations if m.match_reason != "unmapped"
        )
        coverage = mapped_count / total_values if total_values > 0 else 1.0

        return FormDataMigrationResult(
            migrated_form_data=migrated_form_data if mapped_count > 0 else None,
            value_migrations=value_migrations,
            migration_coverage=coverage,
            warnings=warnings,
        )

    async def check_version_mismatch(
        self, request: VersionMismatchRequest
    ) -> VersionMismatchCheck:
        """
        Check if an artifact's schema digest mismatches the current template.

        Returns information about whether migration is needed.
        """
        # Compute current digest
        current_digest = await self.compute_schema_digest_for_template(
            request.template_name,
            request.template_version,
            request.template_status,
        )

        has_mismatch = (
            request.created_for_digest is not None
            and request.created_for_digest != current_digest.digest
        )

        # If mismatch, compute affected paths
        affected_paths: list[str] = []
        breaking_changes_detected = False

        if has_mismatch and request.created_for_digest:
            # We can't reconstruct the old schema from just the digest,
            # but we can return the current schema's paths as potentially affected
            # In a real implementation, you'd store schema snapshots
            breaking_changes_detected = True  # Conservative assumption
            affected_paths = []  # Would need schema history to populate

        return VersionMismatchCheck(
            artifact_type=request.artifact_type,
            created_for_digest=request.created_for_digest,
            current_digest=current_digest.digest,
            has_mismatch=has_mismatch,
            breaking_changes_detected=breaking_changes_detected,
            affected_paths=affected_paths,
        )

    def _build_path_index(
        self, elements: list[dict], prefix: str = ""
    ) -> dict[str, dict]:
        """Build a flat index of all elements by their path."""
        index: dict[str, dict] = {}
        for elem in elements:
            id_short = elem.get("idShort", "")
            path = f"{prefix}.{id_short}" if prefix else id_short
            index[path] = elem

            # Recurse into nested elements
            if "elements" in elem and elem["elements"]:
                index.update(self._build_path_index(elem["elements"], path))

            # Handle list item templates
            if "itemTemplate" in elem and elem["itemTemplate"]:
                item_template = elem["itemTemplate"]
                item_path = f"{path}[]"
                index[item_path] = item_template
                if "elements" in item_template:
                    index.update(
                        self._build_path_index(item_template["elements"], item_path)
                    )

        return index

    def _build_migration_mapping(
        self,
        source_index: dict[str, dict],
        target_index: dict[str, dict],
        min_confidence: float,
    ) -> dict[str, dict]:
        """
        Build a mapping from source paths to target paths.

        Uses three-phase algorithm:
        1. Exact path match
        2. Semantic ID match
        3. Fuzzy matching
        """
        migration: dict[str, dict] = {}
        mapped_targets: set[str] = set()

        # Phase 1: Exact path matches
        for source_path, source_elem in source_index.items():
            if source_path in target_index:
                target_elem = target_index[source_path]
                source_type = source_elem.get("modelType", "")
                target_type = target_elem.get("modelType", "")

                migration[source_path] = {
                    "target_path": source_path,
                    "confidence": 1.0,
                    "match_reason": "exact_path",
                    "source_type": source_type,
                    "target_type": target_type,
                    "breaking": source_type != target_type,
                }
                mapped_targets.add(source_path)

        # Phase 2: Semantic ID matches
        target_by_semantic = self._build_semantic_index(target_index, mapped_targets)

        for source_path, source_elem in source_index.items():
            if source_path in migration:
                continue

            semantic_id = source_elem.get("semanticId")
            if not semantic_id:
                continue

            if semantic_id in target_by_semantic:
                for target_path, target_elem in target_by_semantic[semantic_id]:
                    if target_path in mapped_targets:
                        continue

                    source_type = source_elem.get("modelType", "")
                    target_type = target_elem.get("modelType", "")
                    same_type = source_type == target_type

                    confidence = 0.95 if same_type else 0.75

                    migration[source_path] = {
                        "target_path": target_path,
                        "confidence": confidence,
                        "match_reason": "semantic_id",
                        "source_type": source_type,
                        "target_type": target_type,
                        "breaking": not same_type,
                    }
                    mapped_targets.add(target_path)
                    break

        # Phase 3: Fuzzy matching
        for source_path, source_elem in source_index.items():
            if source_path in migration:
                continue

            best_match: tuple[str, float, dict] | None = None

            for target_path, target_elem in target_index.items():
                if target_path in mapped_targets:
                    continue

                score = self._compute_fuzzy_score(
                    source_elem, target_elem, source_path, target_path
                )

                if score >= min_confidence:
                    if best_match is None or score > best_match[1]:
                        best_match = (target_path, score, target_elem)

            if best_match:
                target_path, score, target_elem = best_match
                source_type = source_elem.get("modelType", "")
                target_type = target_elem.get("modelType", "")

                migration[source_path] = {
                    "target_path": target_path,
                    "confidence": score,
                    "match_reason": "fuzzy",
                    "source_type": source_type,
                    "target_type": target_type,
                    "breaking": source_type != target_type,
                    "details": {
                        "source_idShort": source_elem.get("idShort"),
                        "target_idShort": target_elem.get("idShort"),
                    },
                }
                mapped_targets.add(target_path)

        return migration

    def _build_semantic_index(
        self, index: dict[str, dict], exclude: set[str]
    ) -> dict[str, list[tuple[str, dict]]]:
        """Build index of elements by semantic ID."""
        result: dict[str, list[tuple[str, dict]]] = {}
        for path, elem in index.items():
            if path in exclude:
                continue
            semantic_id = elem.get("semanticId")
            if semantic_id:
                if semantic_id not in result:
                    result[semantic_id] = []
                result[semantic_id].append((path, elem))
        return result

    def _compute_fuzzy_score(
        self,
        source_elem: dict,
        target_elem: dict,
        source_path: str,
        target_path: str,
    ) -> float:
        """Compute weighted fuzzy match score between elements."""
        score = 0.0

        # Semantic ID match (partial credit for related IDs)
        source_semantic = source_elem.get("semanticId", "")
        target_semantic = target_elem.get("semanticId", "")
        if source_semantic and target_semantic:
            if source_semantic == target_semantic:
                score += self.WEIGHTS["semantic_id"]
            elif self._semantic_ids_related(source_semantic, target_semantic):
                score += self.WEIGHTS["semantic_id"] * 0.5

        # Element type match
        if source_elem.get("modelType") == target_elem.get("modelType"):
            score += self.WEIGHTS["element_type"]

        # idShort similarity
        source_id = source_elem.get("idShort", "")
        target_id = target_elem.get("idShort", "")
        if source_id and target_id:
            similarity = SequenceMatcher(
                None, source_id.lower(), target_id.lower()
            ).ratio()
            score += self.WEIGHTS["idshort_similarity"] * similarity

        # Parent context similarity
        source_parent = source_path.rsplit(".", 1)[0] if "." in source_path else ""
        target_parent = target_path.rsplit(".", 1)[0] if "." in target_path else ""
        if source_parent and target_parent:
            parent_similarity = SequenceMatcher(
                None, source_parent.lower(), target_parent.lower()
            ).ratio()
            score += self.WEIGHTS["parent_context"] * parent_similarity

        # Qualifier overlap
        source_qualifiers = set(
            q.get("type", "") for q in source_elem.get("qualifiers", [])
        )
        target_qualifiers = set(
            q.get("type", "") for q in target_elem.get("qualifiers", [])
        )
        if source_qualifiers and target_qualifiers:
            overlap = len(source_qualifiers & target_qualifiers)
            total = len(source_qualifiers | target_qualifiers)
            if total > 0:
                score += self.WEIGHTS["qualifier_overlap"] * (overlap / total)

        return score

    def _semantic_ids_related(self, id1: str, id2: str) -> bool:
        """Check if two semantic IDs are related (same concept, different version)."""
        # ECLASS pattern: 0173-1#02-XXX###-###
        eclass_pattern = re.compile(r"^0173-1#02-([A-Z]{3}\d{3})#(\d{3})$")

        match1 = eclass_pattern.match(id1)
        match2 = eclass_pattern.match(id2)

        if match1 and match2:
            # Same concept code, different version
            return match1.group(1) == match2.group(1)

        # IRI pattern: same base, different version suffix
        if id1.startswith("http") and id2.startswith("http"):
            base1 = re.sub(r"/v?\d+(\.\d+)*/?$", "", id1)
            base2 = re.sub(r"/v?\d+(\.\d+)*/?$", "", id2)
            return base1 == base2

        return False

    def _migrate_single_mapping(
        self,
        mapping: dict,
        new_path: str,
        target_elem: dict,
        preserve_transforms: bool,
    ) -> dict:
        """Create a migrated mapping with updated target path."""
        migrated = {**mapping}

        # Update target
        new_target = {
            **mapping.get("target", {}),
            "id_short_path": new_path,
        }

        # Update element type if changed
        if target_elem.get("modelType"):
            new_target["element_type"] = target_elem["modelType"]

        # Update value type if changed
        if target_elem.get("valueType"):
            new_target["value_type"] = target_elem["valueType"]

        migrated["target"] = new_target

        # Optionally preserve transforms
        if not preserve_transforms:
            migrated.pop("transform", None)

        return migrated

    def _extract_form_values(
        self, form_data: dict, prefix: str = ""
    ) -> dict[str, Any]:
        """
        Extract all values from form data with their paths.

        Form data structure: {"elements": {"Path": {"value": ...}}}
        """
        values: dict[str, Any] = {}
        elements = form_data.get("elements", {})

        for path, data in elements.items():
            full_path = f"{prefix}.{path}" if prefix else path

            if isinstance(data, dict):
                # Check for direct value
                if "value" in data:
                    values[full_path] = data["value"]
                elif "langStrings" in data:
                    values[full_path] = data["langStrings"]
                elif "min" in data or "max" in data:
                    values[full_path] = {"min": data.get("min"), "max": data.get("max")}

                # Check for nested elements
                if "elements" in data:
                    nested = self._extract_form_values(data, full_path)
                    values.update(nested)

                # Check for list items
                if "items" in data and isinstance(data["items"], list):
                    for idx, item in enumerate(data["items"]):
                        item_path = f"{full_path}[{idx}]"
                        if isinstance(item, dict):
                            if "value" in item:
                                values[item_path] = item["value"]
                            elif "elements" in item:
                                nested = self._extract_form_values(item, item_path)
                                values.update(nested)

        return values

    def _set_form_value(self, form_data: dict, path: str, value: Any) -> None:
        """Set a value in form data at the given path."""
        parts = path.replace("[", ".[").split(".")
        current = form_data.setdefault("elements", {})

        for i, part in enumerate(parts[:-1]):
            if part.startswith("["):
                # List index - skip for now (complex case)
                continue

            if part not in current:
                current[part] = {"elements": {}}
            current = current[part].setdefault("elements", {})

        # Set the final value
        final_part = parts[-1]
        if final_part.startswith("["):
            # List item - would need more complex handling
            pass
        else:
            current[final_part] = {"value": value}
