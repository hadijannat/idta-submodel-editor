"""
Tests for migration endpoints in template_ops router.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.dependencies import get_migration_service
from app.schemas.template_ops import SchemaDigest, RecipeMigrationResult, VersionMismatchCheck


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear settings cache before each test."""
    get_settings.cache_clear()


@pytest.fixture
def mock_migration_service():
    """Create a mock migration service."""
    return MagicMock()


@pytest.fixture
def client(mock_migration_service, monkeypatch):
    """Create a test client with mocked migration service."""
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()

    # Override the dependency
    app.dependency_overrides[get_migration_service] = lambda: mock_migration_service

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


class TestSchemaDigestEndpoint:
    """Tests for POST /api/template-ops/schema-digest."""

    def test_schema_digest_returns_digest(self, client, mock_migration_service):
        """Should return a schema digest for a valid template."""
        mock_digest = SchemaDigest(
            digest="abc123def456",
            element_count=10,
            computed_at="2024-01-01T00:00:00Z",
        )
        mock_migration_service.compute_schema_digest_for_template = AsyncMock(
            return_value=mock_digest
        )

        response = client.post(
            "/api/template-ops/schema-digest",
            json={"template_name": "Digital Nameplate"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest"] == "abc123def456"
        assert data["element_count"] == 10


class TestMigrateRecipeEndpoint:
    """Tests for POST /api/template-ops/migrate-recipe."""

    def test_migrate_recipe_returns_result(self, client, mock_migration_service):
        """Should return migration result for valid recipe."""
        mock_result = RecipeMigrationResult(
            migrated_recipe={"name": "migrated"},
            mapping_migrations=[],
            breaking_changes=[],
            migration_coverage=1.0,
            warnings=[],
        )
        mock_migration_service.migrate_recipe = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/template-ops/migrate-recipe",
            json={
                "recipe": {
                    "name": "test",
                    "template": {"name": "Test", "status": "published"},
                    "mappings": [],
                },
                "target_template": "Test",
                "target_version": "2.0",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["migration_coverage"] == 1.0


class TestMigrateFormEndpoint:
    """Tests for POST /api/template-ops/migrate-form."""

    def test_migrate_form_returns_result(self, client, mock_migration_service):
        """Should return migration result for valid form data."""
        from app.schemas.template_ops import FormDataMigrationResult

        mock_result = FormDataMigrationResult(
            migrated_form_data={"elements": {}},
            value_migrations=[],
            migration_coverage=1.0,
            warnings=[],
        )
        mock_migration_service.migrate_form_data = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/template-ops/migrate-form",
            json={
                "form_data": {"elements": {}},
                "source_template": "Test",
                "target_template": "Test",
                "target_version": "2.0",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["migration_coverage"] == 1.0


class TestCheckMismatchEndpoint:
    """Tests for POST /api/template-ops/check-mismatch."""

    def test_check_mismatch_returns_result(self, client, mock_migration_service):
        """Should return mismatch check result."""
        mock_result = VersionMismatchCheck(
            artifact_type="recipe",
            created_for_digest="old_digest",
            current_digest="new_digest",
            has_mismatch=True,
            breaking_changes_detected=True,
            affected_paths=[],
        )
        mock_migration_service.check_version_mismatch = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/template-ops/check-mismatch",
            json={
                "artifact_type": "recipe",
                "created_for_digest": "old_digest",
                "template_name": "Test",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_mismatch"] is True
        assert data["current_digest"] == "new_digest"

    def test_check_mismatch_no_mismatch(self, client, mock_migration_service):
        """Should return no mismatch when digests match."""
        mock_result = VersionMismatchCheck(
            artifact_type="recipe",
            created_for_digest="same_digest",
            current_digest="same_digest",
            has_mismatch=False,
            breaking_changes_detected=False,
            affected_paths=[],
        )
        mock_migration_service.check_version_mismatch = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/template-ops/check-mismatch",
            json={
                "artifact_type": "recipe",
                "created_for_digest": "same_digest",
                "template_name": "Test",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_mismatch"] is False
