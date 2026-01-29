"""Tests for Template Knowledge System storage layer."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from app.services.template_knowledge.storage import TemplateKnowledgeStorage
from app.services.template_knowledge.models import (
    FieldInfo,
    TemplateInfo,
    ExtractionPattern,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_knowledge.db"
        yield db_path


@pytest.fixture
def storage(temp_db):
    """Create a storage instance with temporary database."""
    return TemplateKnowledgeStorage(temp_db)


class TestTemplateKnowledgeStorage:
    """Tests for TemplateKnowledgeStorage."""

    def test_init_creates_schema(self, temp_db):
        """Test that initialization creates the database schema."""
        storage = TemplateKnowledgeStorage(temp_db)
        assert temp_db.exists()

        # Check tables exist
        status = storage.get_status()
        assert status.templates_indexed == 0
        assert status.fields_indexed == 0

    def test_add_and_get_template(self, storage):
        """Test adding and retrieving a template."""
        template = TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
            semantic_id="https://example.com/nameplate",
            status="published",
            field_count=45,
        )

        storage.add_template(template)

        retrieved = storage.get_template("02006")
        assert retrieved is not None
        assert retrieved.idta_number == "02006"
        assert retrieved.title == "Digital Nameplate"
        assert retrieved.field_count == 45

    def test_list_templates(self, storage):
        """Test listing all templates."""
        storage.add_template(TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
        ))
        storage.add_template(TemplateInfo(
            idta_number="02023",
            title="Carbon Footprint",
            version="1.0",
        ))

        templates = storage.list_templates()
        assert len(templates) == 2
        # Should be ordered by idta_number
        assert templates[0].idta_number == "02006"
        assert templates[1].idta_number == "02023"

    def test_delete_template(self, storage):
        """Test deleting a template."""
        storage.add_template(TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
        ))

        storage.delete_template("02006")
        assert storage.get_template("02006") is None

    def test_add_and_get_field(self, storage):
        """Test adding and retrieving a field."""
        # Add parent template first
        storage.add_template(TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
        ))

        field = FieldInfo(
            template_idta="02006",
            path="ManufacturerName",
            id_short="ManufacturerName",
            model_type="Property",
            value_type="xs:string",
            semantic_id="0173-1#02-AAO677#002",
            keywords=["manufacturer", "producer"],
            synonyms=["company", "vendor"],
            is_required=True,
        )

        field_id = storage.add_field(field)
        assert field_id > 0

        retrieved = storage.get_field("02006", "ManufacturerName")
        assert retrieved is not None
        assert retrieved.path == "ManufacturerName"
        assert retrieved.semantic_id == "0173-1#02-AAO677#002"
        assert retrieved.keywords == ["manufacturer", "producer"]
        assert retrieved.synonyms == ["company", "vendor"]

    def test_get_fields_for_template(self, storage):
        """Test getting all fields for a template."""
        storage.add_template(TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
        ))

        storage.add_field(FieldInfo(
            template_idta="02006",
            path="ManufacturerName",
            id_short="ManufacturerName",
            model_type="Property",
        ))
        storage.add_field(FieldInfo(
            template_idta="02006",
            path="SerialNumber",
            id_short="SerialNumber",
            model_type="Property",
        ))

        fields = storage.get_fields_for_template("02006")
        assert len(fields) == 2

    def test_get_fields_by_semantic_id(self, storage):
        """Test finding fields by semantic ID across templates."""
        storage.add_template(TemplateInfo(
            idta_number="02006", title="Nameplate", version="2.0"
        ))
        storage.add_template(TemplateInfo(
            idta_number="02023", title="PCF", version="1.0"
        ))

        semantic_id = "0173-1#02-AAO677#002"

        storage.add_field(FieldInfo(
            template_idta="02006",
            path="ManufacturerName",
            id_short="ManufacturerName",
            model_type="Property",
            semantic_id=semantic_id,
        ))
        storage.add_field(FieldInfo(
            template_idta="02023",
            path="Manufacturer",
            id_short="Manufacturer",
            model_type="Property",
            semantic_id=semantic_id,
        ))

        fields = storage.get_fields_by_semantic_id(semantic_id)
        assert len(fields) == 2
        assert all(f.semantic_id == semantic_id for f in fields)

    def test_embedding_storage(self, storage):
        """Test storing and retrieving embedding vectors."""
        storage.add_template(TemplateInfo(
            idta_number="02006", title="Nameplate", version="2.0"
        ))

        # Create a field with an embedding vector
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        field = FieldInfo(
            template_idta="02006",
            path="TestField",
            id_short="TestField",
            model_type="Property",
            embedding_vector=embedding,
        )

        storage.add_field(field)

        retrieved = storage.get_field("02006", "TestField")
        assert retrieved is not None
        assert retrieved.embedding_vector is not None
        assert len(retrieved.embedding_vector) == 5
        assert abs(retrieved.embedding_vector[0] - 0.1) < 0.0001

    def test_add_and_get_pattern(self, storage):
        """Test adding and retrieving extraction patterns."""
        pattern = ExtractionPattern(
            field_path="*.ContactInformation.*",
            context_type="ContactInformation",
            keywords=["email", "phone", "address"],
            regex_patterns=[r"[\w\.-]+@[\w\.-]+"],
            table_hints=["Contact", "Phone"],
            confidence_weight=1.0,
        )

        pattern_id = storage.add_pattern(pattern)
        assert pattern_id > 0

        patterns = storage.get_patterns_for_context("ContactInformation")
        assert len(patterns) == 1
        assert patterns[0].context_type == "ContactInformation"
        assert "email" in patterns[0].keywords

    def test_get_status(self, storage):
        """Test getting index status."""
        storage.add_template(TemplateInfo(
            idta_number="02006", title="Nameplate", version="2.0"
        ))
        storage.add_field(FieldInfo(
            template_idta="02006",
            path="Field1",
            id_short="Field1",
            model_type="Property",
        ))
        storage.add_pattern(ExtractionPattern(
            field_path="*", context_type="Test", keywords=[]
        ))

        status = storage.get_status()
        assert status.templates_indexed == 1
        assert status.fields_indexed == 1
        assert status.patterns_indexed == 1

    def test_clear_all(self, storage):
        """Test clearing all data."""
        storage.add_template(TemplateInfo(
            idta_number="02006", title="Nameplate", version="2.0"
        ))
        storage.add_field(FieldInfo(
            template_idta="02006",
            path="Field1",
            id_short="Field1",
            model_type="Property",
        ))

        storage.clear_all()

        status = storage.get_status()
        assert status.templates_indexed == 0
        assert status.fields_indexed == 0

    def test_full_text_search(self, storage):
        """Test full-text search on fields."""
        storage.add_template(TemplateInfo(
            idta_number="02006", title="Nameplate", version="2.0"
        ))

        storage.add_field(FieldInfo(
            template_idta="02006",
            path="ManufacturerName",
            id_short="ManufacturerName",
            model_type="Property",
            semantic_label="Manufacturer name",
            definition="The legal name of the manufacturer",
            keywords=["manufacturer", "producer", "company"],
        ))

        storage.add_field(FieldInfo(
            template_idta="02006",
            path="SerialNumber",
            id_short="SerialNumber",
            model_type="Property",
            semantic_label="Serial number",
            definition="Unique identifier assigned by manufacturer",
        ))

        # Search for "manufacturer"
        results = storage.search_fields_fts("manufacturer")
        assert len(results) >= 1
        # ManufacturerName should be found
        paths = [f.path for f in results]
        assert "ManufacturerName" in paths
