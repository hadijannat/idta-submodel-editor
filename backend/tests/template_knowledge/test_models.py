"""Tests for Template Knowledge System data models."""

import pytest
from datetime import datetime

from app.services.template_knowledge.models import (
    FieldInfo,
    TemplateInfo,
    ExtractionPattern,
    SemanticRecommendation,
    IndexStatus,
)


class TestTemplateInfo:
    """Tests for TemplateInfo model."""

    def test_create_template_info(self):
        """Test creating a TemplateInfo instance."""
        template = TemplateInfo(
            idta_number="02006",
            title="Digital Nameplate",
            version="2.0",
            semantic_id="https://admin-shell.io/idta/Submodel/Nameplate/2/0",
            status="published",
            field_count=45,
        )

        assert template.idta_number == "02006"
        assert template.title == "Digital Nameplate"
        assert template.version == "2.0"
        assert template.status == "published"
        assert template.field_count == 45

    def test_template_info_defaults(self):
        """Test default values for TemplateInfo."""
        template = TemplateInfo(
            idta_number="02023",
            title="Carbon Footprint",
            version="1.0",
        )

        assert template.status == "published"
        assert template.field_count == 0
        assert template.semantic_id is None
        assert template.source_path is None
        assert isinstance(template.last_indexed, datetime)


class TestFieldInfo:
    """Tests for FieldInfo model."""

    def test_create_field_info(self):
        """Test creating a FieldInfo instance."""
        field = FieldInfo(
            template_idta="02006",
            path="ManufacturerName",
            id_short="ManufacturerName",
            model_type="Property",
            value_type="xs:string",
            semantic_id="0173-1#02-AAO677#002",
            semantic_label="Manufacturer name",
            definition="Legal name of the manufacturer.",
            keywords=["manufacturer", "producer", "company"],
            is_required=True,
        )

        assert field.template_idta == "02006"
        assert field.path == "ManufacturerName"
        assert field.model_type == "Property"
        assert field.semantic_id == "0173-1#02-AAO677#002"
        assert len(field.keywords) == 3
        assert field.is_required is True

    def test_field_info_embedding_text(self):
        """Test building embedding text from field info."""
        field = FieldInfo(
            template_idta="02006",
            path="SerialNumber",
            id_short="SerialNumber",
            model_type="Property",
            semantic_label="Serial number",
            definition="Unique identifier assigned by the manufacturer.",
            keywords=["serial", "sn", "identifier"],
            synonyms=["s/n", "serial no"],
        )

        text = field.get_embedding_text()

        assert "SerialNumber" in text
        assert "Serial number" in text
        assert "serial" in text
        assert "s/n" in text
        assert "Unique identifier" in text

    def test_field_info_defaults(self):
        """Test default values for FieldInfo."""
        field = FieldInfo(
            template_idta="02006",
            path="TestField",
            id_short="TestField",
            model_type="Property",
        )

        assert field.cardinality == "[1]"
        assert field.keywords == []
        assert field.synonyms == []
        assert field.embedding_vector is None
        assert field.is_required is False


class TestExtractionPattern:
    """Tests for ExtractionPattern model."""

    def test_create_pattern(self):
        """Test creating an ExtractionPattern instance."""
        pattern = ExtractionPattern(
            field_path="*.ContactInformation.*",
            context_type="ContactInformation",
            keywords=["email", "phone", "address", "contact"],
            regex_patterns=[r"[\w\.-]+@[\w\.-]+\.\w+", r"\+?[\d\s\-\(\)]{7,}"],
            table_hints=["Contact", "Address", "Phone"],
            confidence_weight=1.0,
        )

        assert pattern.context_type == "ContactInformation"
        assert len(pattern.keywords) == 4
        assert len(pattern.regex_patterns) == 2
        assert pattern.confidence_weight == 1.0


class TestSemanticRecommendation:
    """Tests for SemanticRecommendation model."""

    def test_create_recommendation(self):
        """Test creating a SemanticRecommendation instance."""
        rec = SemanticRecommendation(
            irdi="0173-1#02-AAO677#002",
            label="Manufacturer name",
            definition="Legal name of the manufacturer.",
            confidence=0.92,
            source_template="02006",
            usage_count=15,
        )

        assert rec.irdi == "0173-1#02-AAO677#002"
        assert rec.confidence == 0.92
        assert rec.is_current is False
        assert rec.usage_count == 15


class TestIndexStatus:
    """Tests for IndexStatus model."""

    def test_index_status(self):
        """Test IndexStatus model."""
        status = IndexStatus(
            templates_indexed=25,
            fields_indexed=1500,
            patterns_indexed=100,
            embedding_model="nomic-embed-text",
            ollama_available=True,
        )

        assert status.templates_indexed == 25
        assert status.fields_indexed == 1500
        assert status.ollama_available is True
        assert status.index_version == "1.0"
