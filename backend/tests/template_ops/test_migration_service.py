"""
Tests for the migration service.

Tests the schema digest computation, recipe migration, and form data migration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.template_ops.migration_service import MigrationService
from app.schemas.template_ops import (
    RecipeMigrationRequest,
    FormDataMigrationRequest,
    VersionMismatchRequest,
)


@pytest.fixture
def mock_fetcher():
    """Create a mock fetcher service."""
    return MagicMock()


@pytest.fixture
def mock_parser():
    """Create a mock parser service."""
    return MagicMock()


@pytest.fixture
def migration_service(mock_fetcher, mock_parser):
    """Create a migration service with mocked dependencies."""
    return MigrationService(fetcher=mock_fetcher, parser=mock_parser)


class TestComputeSchemaDigest:
    """Tests for compute_schema_digest method."""

    def test_compute_schema_digest_deterministic(self, migration_service):
        """Digest should be deterministic for the same schema."""
        schema = {
            "elements": [
                {
                    "idShort": "Manufacturer",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "semanticId": "0173-1#02-AAO677#002",
                },
                {
                    "idShort": "SerialNumber",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "semanticId": "0173-1#02-AAM556#002",
                },
            ]
        }

        digest1 = migration_service.compute_schema_digest(schema)
        digest2 = migration_service.compute_schema_digest(schema)

        assert digest1.digest == digest2.digest
        assert digest1.element_count == 2
        assert len(digest1.digest) == 64  # SHA-256 hex

    def test_compute_schema_digest_different_for_different_schemas(
        self, migration_service
    ):
        """Different schemas should produce different digests."""
        schema1 = {
            "elements": [
                {"idShort": "Manufacturer", "modelType": "Property"},
            ]
        }
        schema2 = {
            "elements": [
                {"idShort": "SerialNumber", "modelType": "Property"},
            ]
        }

        digest1 = migration_service.compute_schema_digest(schema1)
        digest2 = migration_service.compute_schema_digest(schema2)

        assert digest1.digest != digest2.digest

    def test_compute_schema_digest_handles_nested_elements(self, migration_service):
        """Digest should include nested elements."""
        schema = {
            "elements": [
                {
                    "idShort": "ContactInfo",
                    "modelType": "SubmodelElementCollection",
                    "elements": [
                        {"idShort": "Email", "modelType": "Property"},
                        {"idShort": "Phone", "modelType": "Property"},
                    ],
                },
            ]
        }

        digest = migration_service.compute_schema_digest(schema)

        # Should count parent + 2 children
        assert digest.element_count == 3


class TestBuildMigrationMapping:
    """Tests for the internal _build_migration_mapping method."""

    def test_exact_path_match_confidence_1(self, migration_service):
        """Exact path match should have confidence 1.0."""
        source_index = {
            "Manufacturer": {
                "idShort": "Manufacturer",
                "modelType": "Property",
                "valueType": "xs:string",
            }
        }
        target_index = {
            "Manufacturer": {
                "idShort": "Manufacturer",
                "modelType": "Property",
                "valueType": "xs:string",
            }
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.5
        )

        assert "Manufacturer" in mapping
        assert mapping["Manufacturer"]["confidence"] == 1.0
        assert mapping["Manufacturer"]["match_reason"] == "exact_path"
        assert mapping["Manufacturer"]["breaking"] is False

    def test_semantic_id_match_finds_renamed(self, migration_service):
        """Semantic ID match should find renamed elements."""
        semantic_id = "0173-1#02-AAO677#002"
        source_index = {
            "ManufacturerName": {
                "idShort": "ManufacturerName",
                "modelType": "Property",
                "semanticId": semantic_id,
            }
        }
        target_index = {
            "Manufacturer": {
                "idShort": "Manufacturer",
                "modelType": "Property",
                "semanticId": semantic_id,
            }
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.5
        )

        assert "ManufacturerName" in mapping
        assert mapping["ManufacturerName"]["target_path"] == "Manufacturer"
        assert mapping["ManufacturerName"]["confidence"] == 0.95
        assert mapping["ManufacturerName"]["match_reason"] == "semantic_id"

    def test_semantic_id_match_different_type_lower_confidence(self, migration_service):
        """Semantic ID match with different type should have lower confidence."""
        semantic_id = "0173-1#02-AAO677#002"
        source_index = {
            "Value": {
                "idShort": "Value",
                "modelType": "Property",
                "semanticId": semantic_id,
            }
        }
        target_index = {
            "Value": {
                "idShort": "Value",
                "modelType": "MultiLanguageProperty",  # Different type
                "semanticId": semantic_id,
            }
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.5
        )

        assert "Value" in mapping
        # Same path but different type detected via semantic match first
        assert mapping["Value"]["confidence"] == 1.0  # Exact path wins
        assert mapping["Value"]["breaking"] is True  # Type changed

    def test_fuzzy_match_similar_idshort(self, migration_service):
        """Fuzzy match should find elements with similar idShort."""
        source_index = {
            "ManufacturerName": {
                "idShort": "ManufacturerName",
                "modelType": "Property",
            }
        }
        target_index = {
            "ManufacturerFullName": {
                "idShort": "ManufacturerFullName",
                "modelType": "Property",
            }
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.3
        )

        assert "ManufacturerName" in mapping
        assert mapping["ManufacturerName"]["target_path"] == "ManufacturerFullName"
        assert mapping["ManufacturerName"]["match_reason"] == "fuzzy"
        assert 0.3 <= mapping["ManufacturerName"]["confidence"] < 1.0

    def test_unmapped_when_removed(self, migration_service):
        """Elements not in target should not be mapped."""
        source_index = {
            "OldField": {"idShort": "OldField", "modelType": "Property"},
            "SharedField": {"idShort": "SharedField", "modelType": "Property"},
        }
        target_index = {
            "SharedField": {"idShort": "SharedField", "modelType": "Property"},
            "NewField": {"idShort": "NewField", "modelType": "Property"},
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.9  # High threshold
        )

        assert "SharedField" in mapping
        assert "OldField" not in mapping  # Not mapped due to high threshold

    def test_breaking_change_on_type_change(self, migration_service):
        """Type change should be flagged as breaking."""
        source_index = {
            "Value": {
                "idShort": "Value",
                "modelType": "Property",
                "valueType": "xs:string",
            }
        }
        target_index = {
            "Value": {
                "idShort": "Value",
                "modelType": "SubmodelElementCollection",  # Changed type
            }
        }

        mapping = migration_service._build_migration_mapping(
            source_index, target_index, min_confidence=0.5
        )

        assert "Value" in mapping
        assert mapping["Value"]["breaking"] is True
        assert mapping["Value"]["source_type"] == "Property"
        assert mapping["Value"]["target_type"] == "SubmodelElementCollection"


class TestMigrateRecipe:
    """Tests for migrate_recipe method."""

    @pytest.mark.asyncio
    async def test_migrate_recipe_preserves_transforms(
        self, migration_service, mock_fetcher, mock_parser
    ):
        """Recipe transforms should be preserved during migration."""
        source_schema = {
            "elements": [
                {"idShort": "Weight", "modelType": "Property", "valueType": "xs:decimal"}
            ]
        }
        target_schema = {
            "elements": [
                {"idShort": "Weight", "modelType": "Property", "valueType": "xs:decimal"}
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(
            side_effect=[source_schema, target_schema]
        )

        recipe = {
            "name": "test-recipe",
            "template": {"name": "TestTemplate", "version": "1.0", "status": "published"},
            "mappings": [
                {
                    "source": {"column": "weight_kg"},
                    "target": {"id_short_path": "Weight", "element_type": "Property"},
                    "transform": {"type": "multiply", "factor": 1000},
                }
            ],
        }

        request = RecipeMigrationRequest(
            recipe=recipe,
            target_template="TestTemplate",
            target_version="2.0",
            preserve_transforms=True,
        )

        result = await migration_service.migrate_recipe(request)

        assert result.migrated_recipe is not None
        assert len(result.migrated_recipe["mappings"]) == 1
        assert result.migrated_recipe["mappings"][0]["transform"] == {
            "type": "multiply",
            "factor": 1000,
        }
        assert result.migration_coverage == 1.0

    @pytest.mark.asyncio
    async def test_migrate_recipe_reports_unmapped(
        self, migration_service, mock_fetcher, mock_parser
    ):
        """Unmapped fields should be reported."""
        source_schema = {
            "elements": [
                {"idShort": "OldField", "modelType": "Property"},
            ]
        }
        target_schema = {
            "elements": [
                {"idShort": "NewField", "modelType": "Property"},  # Different field
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(
            side_effect=[source_schema, target_schema]
        )

        recipe = {
            "name": "test-recipe",
            "template": {"name": "TestTemplate", "version": "1.0", "status": "published"},
            "mappings": [
                {
                    "source": {"column": "old_data"},
                    "target": {"id_short_path": "OldField"},
                }
            ],
        }

        request = RecipeMigrationRequest(
            recipe=recipe,
            target_template="TestTemplate",
            target_version="2.0",
            min_confidence=0.9,  # High threshold to force unmapped
        )

        result = await migration_service.migrate_recipe(request)

        assert len(result.mapping_migrations) == 1
        assert result.mapping_migrations[0].match_reason == "unmapped"
        assert result.mapping_migrations[0].breaking_change is True
        assert "OldField" in result.breaking_changes[0]


class TestMigrateFormData:
    """Tests for migrate_form_data method."""

    @pytest.mark.asyncio
    async def test_migrate_form_data_nested_elements(
        self, migration_service, mock_fetcher, mock_parser
    ):
        """Nested form data should be migrated correctly."""
        source_schema = {
            "elements": [
                {
                    "idShort": "Contact",
                    "modelType": "SubmodelElementCollection",
                    "elements": [
                        {"idShort": "Email", "modelType": "Property"},
                    ],
                }
            ]
        }
        target_schema = {
            "elements": [
                {
                    "idShort": "Contact",
                    "modelType": "SubmodelElementCollection",
                    "elements": [
                        {"idShort": "Email", "modelType": "Property"},
                    ],
                }
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(
            side_effect=[source_schema, target_schema]
        )

        form_data = {
            "elements": {
                "Contact": {
                    "elements": {
                        "Email": {"value": "test@example.com"},
                    }
                }
            }
        }

        request = FormDataMigrationRequest(
            form_data=form_data,
            source_template="TestTemplate",
            source_version="1.0",
            target_template="TestTemplate",
            target_version="2.0",
        )

        result = await migration_service.migrate_form_data(request)

        assert result.migrated_form_data is not None
        assert result.migration_coverage == 1.0

    @pytest.mark.asyncio
    async def test_migrate_form_data_list_items_preserves_indices(
        self, migration_service, mock_fetcher, mock_parser
    ):
        source_schema = {
            "elements": [
                {
                    "idShort": "Markings",
                    "modelType": "SubmodelElementList",
                    "itemTemplate": {
                        "idShort": "Marking",
                        "modelType": "SubmodelElementCollection",
                        "elements": [
                            {"idShort": "MarkingName", "modelType": "Property"}
                        ],
                    },
                }
            ]
        }
        target_schema = source_schema

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(
            side_effect=[source_schema, target_schema]
        )

        form_data = {
            "elements": {
                "Markings": {
                    "items": [
                        {"elements": {"MarkingName": {"value": "CE"}}},
                        {"elements": {"MarkingName": {"value": "UL"}}},
                    ]
                }
            }
        }

        request = FormDataMigrationRequest(
            form_data=form_data,
            source_template="TestTemplate",
            source_version="1.0",
            target_template="TestTemplate",
            target_version="2.0",
        )

        result = await migration_service.migrate_form_data(request)

        assert result.migrated_form_data is not None
        migrated = result.migrated_form_data["elements"]["Markings"]["items"]
        assert migrated[0]["elements"]["MarkingName"]["value"] == "CE"
        assert migrated[1]["elements"]["MarkingName"]["value"] == "UL"

    @pytest.mark.asyncio
    async def test_migrate_form_data_range_and_file(self, migration_service, mock_fetcher, mock_parser):
        source_schema = {
            "elements": [
                {"idShort": "Voltage", "modelType": "Range"},
                {"idShort": "MarkingFile", "modelType": "File"},
            ]
        }
        target_schema = source_schema

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(
            side_effect=[source_schema, target_schema]
        )

        form_data = {
            "elements": {
                "Voltage": {"min": 110, "max": 220},
                "MarkingFile": {"value": "file.png", "contentType": "image/png"},
            }
        }

        request = FormDataMigrationRequest(
            form_data=form_data,
            source_template="TestTemplate",
            source_version="1.0",
            target_template="TestTemplate",
            target_version="2.0",
        )

        result = await migration_service.migrate_form_data(request)

        assert result.migrated_form_data is not None
        migrated = result.migrated_form_data["elements"]
        assert migrated["Voltage"]["min"] == 110
        assert migrated["Voltage"]["max"] == 220
        assert migrated["MarkingFile"]["value"] == "file.png"
        assert migrated["MarkingFile"]["contentType"] == "image/png"


class TestCheckVersionMismatch:
    """Tests for check_version_mismatch method."""

    @pytest.mark.asyncio
    async def test_detects_mismatch(self, migration_service, mock_fetcher, mock_parser):
        """Should detect when digest doesn't match current template."""
        schema = {
            "elements": [
                {"idShort": "Field", "modelType": "Property"},
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(return_value=schema)

        # Compute current digest
        current_digest = migration_service.compute_schema_digest(schema)

        request = VersionMismatchRequest(
            artifact_type="recipe",
            created_for_digest="different_digest_value",  # Different from current
            template_name="TestTemplate",
        )

        result = await migration_service.check_version_mismatch(request)

        assert result.has_mismatch is True
        assert result.current_digest == current_digest.digest

    @pytest.mark.asyncio
    async def test_no_mismatch_when_digest_matches(
        self, migration_service, mock_fetcher, mock_parser
    ):
        """Should not detect mismatch when digests match."""
        schema = {
            "elements": [
                {"idShort": "Field", "modelType": "Property"},
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(return_value=schema)

        # Compute current digest
        current_digest = migration_service.compute_schema_digest(schema)

        request = VersionMismatchRequest(
            artifact_type="recipe",
            created_for_digest=current_digest.digest,  # Same as current
            template_name="TestTemplate",
        )

        result = await migration_service.check_version_mismatch(request)

        assert result.has_mismatch is False

    @pytest.mark.asyncio
    async def test_no_mismatch_when_no_previous_digest(
        self, migration_service, mock_fetcher, mock_parser
    ):
        """Should not detect mismatch when artifact has no stored digest."""
        schema = {
            "elements": [
                {"idShort": "Field", "modelType": "Property"},
            ]
        }

        mock_fetcher.fetch_template_aasx = AsyncMock(return_value=b"mock")
        mock_parser.parse_aasx_to_ui_schema = MagicMock(return_value=schema)

        request = VersionMismatchRequest(
            artifact_type="recipe",
            created_for_digest=None,  # No previous digest
            template_name="TestTemplate",
        )

        result = await migration_service.check_version_mismatch(request)

        assert result.has_mismatch is False


class TestSemanticIdRelation:
    """Tests for semantic ID relation detection."""

    def test_eclass_same_concept_different_version(self, migration_service):
        """ECLASS IDs with same concept code should be related."""
        id1 = "0173-1#02-AAO677#002"
        id2 = "0173-1#02-AAO677#003"

        assert migration_service._semantic_ids_related(id1, id2) is True

    def test_eclass_different_concepts_not_related(self, migration_service):
        """ECLASS IDs with different concept codes should not be related."""
        id1 = "0173-1#02-AAO677#002"
        id2 = "0173-1#02-AAM556#002"

        assert migration_service._semantic_ids_related(id1, id2) is False

    def test_iri_same_base_different_version(self, migration_service):
        """IRI IDs with same base but different versions should be related."""
        id1 = "https://example.org/concept/123/v1"
        id2 = "https://example.org/concept/123/v2"

        assert migration_service._semantic_ids_related(id1, id2) is True

    def test_completely_different_ids_not_related(self, migration_service):
        """Completely different IDs should not be related."""
        id1 = "urn:example:concept1"
        id2 = "urn:example:concept2"

        assert migration_service._semantic_ids_related(id1, id2) is False
