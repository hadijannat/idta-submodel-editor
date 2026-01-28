"""
Tests for SAMM Converter.

Tests bidirectional SAMM ↔ AAS conversion including:
- SAMM TTL parsing
- AAS to SAMM generation
- Type mapping
"""

import pytest
from datetime import datetime, timezone

from app.services.samm.converter import SAMMConverter
from app.services.samm.generator import SAMMGenerator
from app.services.samm.models import (
    ConversionDirection,
    SAMM_TO_AAS_TYPE_MAP,
    AAS_TO_SAMM_TYPE_MAP,
)
from app.services.samm.parser import SAMMParser


# Sample SAMM TTL content
SAMPLE_TTL = """
@prefix : <urn:samm:org.example:TestAspect:1.0.0#> .
@prefix samm: <urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#> .
@prefix samm-c: <urn:samm:org.eclipse.esmf.samm:characteristic:2.1.0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:TestAspect a samm:Aspect ;
    samm:description "A test aspect for unit tests"@en ;
    samm:properties ( :testProperty ) .

:testProperty a samm:Property ;
    samm:description "A test property"@en ;
    samm:characteristic :TestCharacteristic ;
    samm:exampleValue "example" .

:TestCharacteristic a samm:Characteristic ;
    samm:description "Test characteristic"@en ;
    samm:dataType xsd:string .
"""

# Sample AAS UI schema
SAMPLE_UI_SCHEMA = {
    "idShort": "TestSubmodel",
    "semanticId": "urn:samm:org.test:1.0.0#TestSubmodel",
    "modelType": "Submodel",
    "elements": [
        {
            "idShort": "StringProperty",
            "modelType": "Property",
            "valueType": "xs:string",
            "description": "A string property",
            "cardinality": {"min": 1, "max": 1},
        },
        {
            "idShort": "IntegerProperty",
            "modelType": "Property",
            "valueType": "xs:int",
            "description": "An integer property",
            "cardinality": {"min": 0, "max": 1},
        },
        {
            "idShort": "NestedCollection",
            "modelType": "SubmodelElementCollection",
            "description": "A nested collection",
            "elements": [
                {
                    "idShort": "NestedProperty",
                    "modelType": "Property",
                    "valueType": "xs:boolean",
                    "cardinality": {"min": 1, "max": 1},
                }
            ],
        },
    ],
}


class TestSAMMParser:
    """Test SAMM parsing functionality."""

    def test_parse_basic_ttl(self):
        """Test parsing basic TTL content."""
        parser = SAMMParser()
        aspect = parser.parse(SAMPLE_TTL, format="ttl")

        assert aspect.name == "TestAspect"
        assert aspect.version == "1.0.0"
        assert "test" in aspect.description.lower()

    def test_parse_extracts_properties(self):
        """Test that properties are extracted."""
        parser = SAMMParser()
        aspect = parser.parse(SAMPLE_TTL, format="ttl")

        # Should have at least one property
        assert len(aspect.properties) >= 1

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        parser = SAMMParser()

        with pytest.raises(ValueError, match="Unsupported format"):
            parser.parse("content", format="xml")


class TestSAMMGenerator:
    """Test SAMM generation functionality."""

    def test_generate_from_ui_schema(self):
        """Test generating SAMM from UI schema."""
        generator = SAMMGenerator(namespace="org.test")
        aspect, ttl = generator.generate_from_ui_schema(SAMPLE_UI_SCHEMA)

        assert aspect.name == "TestSubmodel"
        assert "1.0.0" in aspect.version
        assert len(aspect.properties) > 0

    def test_generated_ttl_has_prefixes(self):
        """Test that generated TTL has required prefixes."""
        generator = SAMMGenerator()
        _, ttl = generator.generate_from_ui_schema(SAMPLE_UI_SCHEMA)

        assert "@prefix samm:" in ttl
        assert "@prefix xsd:" in ttl

    def test_generated_ttl_has_aspect(self):
        """Test that generated TTL has aspect definition."""
        generator = SAMMGenerator()
        _, ttl = generator.generate_from_ui_schema(SAMPLE_UI_SCHEMA)

        assert "a samm:Aspect" in ttl

    def test_optional_property_marked(self):
        """Test that optional properties are marked correctly."""
        generator = SAMMGenerator()
        aspect, ttl = generator.generate_from_ui_schema(SAMPLE_UI_SCHEMA)

        # IntegerProperty has min=0, so should be optional
        optional_props = [p for p in aspect.properties if p.optional]
        assert len(optional_props) >= 1


class TestSAMMConverter:
    """Test SAMM converter functionality."""

    @pytest.fixture
    def converter(self) -> SAMMConverter:
        """Create converter without fetcher/parser for basic tests."""
        return SAMMConverter()

    @pytest.mark.asyncio
    async def test_convert_samm_to_aas_success(self, converter):
        """Test successful SAMM to AAS conversion."""
        result = await converter.convert_samm_to_aas(SAMPLE_TTL, format="ttl")

        assert result.success
        assert result.direction == ConversionDirection.SAMM_TO_AAS
        assert result.aas_schema is not None
        assert result.aas_template is not None

    @pytest.mark.asyncio
    async def test_convert_samm_to_aas_sets_metadata(self, converter):
        """Test that conversion sets metadata."""
        result = await converter.convert_samm_to_aas(SAMPLE_TTL, format="ttl")

        assert result.source_urn is not None
        assert result.target_name is not None
        assert result.converted_at is not None
        assert result.elements_converted > 0

    @pytest.mark.asyncio
    async def test_convert_invalid_samm_fails(self, converter):
        """Test that invalid SAMM content returns failure."""
        result = await converter.convert_samm_to_aas(
            "invalid content", format="ttl"
        )

        assert not result.success
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_convert_aas_to_samm_without_deps_fails(self, converter):
        """Test that AAS to SAMM requires fetcher/parser."""
        result = await converter.convert_aas_to_samm("TestTemplate")

        assert not result.success
        assert any("fetcher" in w.message.lower() for w in result.warnings)


class TestTypeMappings:
    """Test SAMM ↔ AAS type mappings."""

    def test_samm_to_aas_mapping_complete(self):
        """Test that common SAMM types are mapped."""
        assert "xsd:string" in SAMM_TO_AAS_TYPE_MAP
        assert "xsd:boolean" in SAMM_TO_AAS_TYPE_MAP
        assert "xsd:int" in SAMM_TO_AAS_TYPE_MAP
        assert "xsd:double" in SAMM_TO_AAS_TYPE_MAP
        assert "xsd:dateTime" in SAMM_TO_AAS_TYPE_MAP

    def test_aas_to_samm_mapping_complete(self):
        """Test that common AAS types are mapped."""
        assert "xs:string" in AAS_TO_SAMM_TYPE_MAP
        assert "xs:boolean" in AAS_TO_SAMM_TYPE_MAP
        assert "xs:int" in AAS_TO_SAMM_TYPE_MAP
        assert "xs:double" in AAS_TO_SAMM_TYPE_MAP
        assert "xs:dateTime" in AAS_TO_SAMM_TYPE_MAP

    def test_mapping_bidirectional(self):
        """Test that mappings are bidirectional."""
        for samm_type, aas_type in SAMM_TO_AAS_TYPE_MAP.items():
            # Reverse mapping should exist (with some exceptions)
            if aas_type in AAS_TO_SAMM_TYPE_MAP:
                assert AAS_TO_SAMM_TYPE_MAP[aas_type] is not None

    def test_string_type_mapping(self):
        """Test string type mapping."""
        assert SAMM_TO_AAS_TYPE_MAP["xsd:string"] == "xs:string"
        assert AAS_TO_SAMM_TYPE_MAP["xs:string"] == "xsd:string"


class TestConversionResult:
    """Test ConversionResult model."""

    @pytest.mark.asyncio
    async def test_result_contains_warnings(self):
        """Test that result can contain warnings."""
        converter = SAMMConverter()

        # Parse valid but simple TTL
        result = await converter.convert_samm_to_aas(SAMPLE_TTL, format="ttl")

        # Result should be successful but may have warnings
        assert result.success
        assert isinstance(result.warnings, list)

    @pytest.mark.asyncio
    async def test_result_has_timestamp(self):
        """Test that result has conversion timestamp."""
        converter = SAMMConverter()
        result = await converter.convert_samm_to_aas(SAMPLE_TTL, format="ttl")

        assert result.converted_at is not None
        assert isinstance(result.converted_at, datetime)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Test handling of empty content."""
        converter = SAMMConverter()
        result = await converter.convert_samm_to_aas("", format="ttl")

        assert not result.success

    @pytest.mark.asyncio
    async def test_bytes_content(self):
        """Test handling of bytes content."""
        converter = SAMMConverter()
        result = await converter.convert_samm_to_aas(
            SAMPLE_TTL.encode("utf-8"), format="ttl"
        )

        assert result.success

    def test_generator_with_empty_schema(self):
        """Test generator with minimal schema."""
        generator = SAMMGenerator()
        aspect, ttl = generator.generate_from_ui_schema(
            {"idShort": "Empty", "elements": []}
        )

        assert aspect.name == "Empty"
        assert len(aspect.properties) == 0
