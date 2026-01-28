"""
Tests for OPC UA NodeSet Exporter.

Tests converting AAS structures to NodeSet2.xml format.
"""

import pytest

from app.services.opcua.exporter import NodeSetExporter, ExportResult


# Sample AAS template for testing
SAMPLE_AAS_TEMPLATE = {
    "idShort": "TestSubmodel",
    "modelType": "Submodel",
    "semanticId": {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": "urn:example:test"}],
    },
    "submodelElements": [
        {
            "idShort": "StringProperty",
            "modelType": "Property",
            "valueType": "xs:string",
            "description": [{"language": "en", "text": "A string property"}],
            "value": "test value",
        },
        {
            "idShort": "IntegerProperty",
            "modelType": "Property",
            "valueType": "xs:int",
            "description": [{"language": "en", "text": "An integer property"}],
        },
        {
            "idShort": "NestedCollection",
            "modelType": "SubmodelElementCollection",
            "description": [{"language": "en", "text": "A nested collection"}],
            "value": [
                {
                    "idShort": "NestedProperty",
                    "modelType": "Property",
                    "valueType": "xs:boolean",
                }
            ],
        },
    ],
}


SAMPLE_UI_SCHEMA = {
    "idShort": "TestSubmodel",
    "modelType": "Submodel",
    "semanticId": "urn:example:test",
    "description": "A test submodel",
    "elements": [
        {
            "idShort": "StringProperty",
            "modelType": "Property",
            "valueType": "xs:string",
            "description": "A string property",
            "cardinality": {"min": 1, "max": 1},
        },
        {
            "idShort": "DoubleProperty",
            "modelType": "Property",
            "valueType": "xs:double",
            "description": "A double property",
            "cardinality": {"min": 0, "max": 1},
        },
        {
            "idShort": "ListProperty",
            "modelType": "SubmodelElementList",
            "typeValueListElement": "Property",
            "valueTypeListElement": "xs:string",
            "description": "A list of strings",
            "cardinality": {"min": 0, "max": "*"},
        },
    ],
}


class TestNodeSetExporter:
    """Test NodeSet exporter functionality."""

    def test_export_basic_template(self):
        """Test exporting a basic template."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert result.nodeset_xml is not None
        assert result.node_count > 0

    def test_export_generates_xml_declaration(self):
        """Test that export generates valid XML."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert result.nodeset_xml.startswith("<?xml")

    def test_export_includes_namespace_uri(self):
        """Test that export includes namespace URI."""
        exporter = NodeSetExporter(namespace_uri="urn:test:custom")
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert "urn:test:custom" in result.nodeset_xml
        assert result.namespace_uri == "urn:test:custom"

    def test_export_creates_objecttype(self):
        """Test that export creates UAObjectType for root."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert "<UAObjectType" in result.nodeset_xml
        assert "TestSubmodel" in result.nodeset_xml

    def test_export_creates_variables(self):
        """Test that export creates UAVariable for properties."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert "<UAVariable" in result.nodeset_xml
        assert "StringProperty" in result.nodeset_xml

    def test_export_handles_collections(self):
        """Test that export handles SubmodelElementCollections."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert "<UAObject" in result.nodeset_xml
        assert "NestedCollection" in result.nodeset_xml

    def test_export_ui_schema(self):
        """Test exporting from UI schema format."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_UI_SCHEMA)

        assert result.success
        assert result.nodeset_xml is not None

    def test_export_with_version(self):
        """Test exporting with custom version."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE, version="2.0.0")

        assert result.success
        assert 'Version="2.0.0"' in result.nodeset_xml


class TestTypeConversionInExport:
    """Test type conversion during export."""

    def test_string_converts_to_string(self):
        """Test xs:string converts to String."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        # String type should map to NodeId i=12
        assert 'DataType="i=12"' in result.nodeset_xml

    def test_int_converts_to_int32(self):
        """Test xs:int converts to Int32."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        # Int32 type should map to NodeId i=6
        assert 'DataType="i=6"' in result.nodeset_xml

    def test_boolean_converts_correctly(self):
        """Test xs:boolean converts to Boolean."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        # Boolean type should map to NodeId i=1
        assert 'DataType="i=1"' in result.nodeset_xml


class TestListExport:
    """Test SubmodelElementList export."""

    def test_list_creates_array_variable(self):
        """Test that lists create variables with ValueRank."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_UI_SCHEMA)

        assert result.success
        # Lists should have ValueRank="1"
        assert 'ValueRank="1"' in result.nodeset_xml


class TestReferences:
    """Test reference generation."""

    def test_hascomponent_references_created(self):
        """Test that HasComponent references are created."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert 'ReferenceType="HasComponent"' in result.nodeset_xml

    def test_hastypedefinition_references_created(self):
        """Test that HasTypeDefinition references are created."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert 'ReferenceType="HasTypeDefinition"' in result.nodeset_xml


class TestDescriptionExport:
    """Test description handling in export."""

    def test_string_description_exported(self):
        """Test string description is exported."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_UI_SCHEMA)

        assert result.success
        assert "<Description>" in result.nodeset_xml

    def test_multilang_description_exported(self):
        """Test multi-language description is exported."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        # Should extract text from language array
        assert "A string property" in result.nodeset_xml


class TestExportResult:
    """Test ExportResult dataclass."""

    def test_result_has_timestamp(self):
        """Test that result has export timestamp."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.exported_at is not None

    def test_result_tracks_node_count(self):
        """Test that result tracks node count."""
        exporter = NodeSetExporter()
        result = exporter.export_template(SAMPLE_AAS_TEMPLATE)

        assert result.success
        assert result.node_count > 0


class TestEdgeCases:
    """Test edge cases in export."""

    def test_empty_template(self):
        """Test exporting empty template."""
        exporter = NodeSetExporter()
        result = exporter.export_template({"idShort": "Empty", "submodelElements": []})

        assert result.success
        assert result.nodeset_xml is not None

    def test_deeply_nested_collections(self):
        """Test exporting deeply nested collections."""
        nested = {
            "idShort": "DeepNested",
            "submodelElements": [
                {
                    "idShort": "Level1",
                    "modelType": "SubmodelElementCollection",
                    "value": [
                        {
                            "idShort": "Level2",
                            "modelType": "SubmodelElementCollection",
                            "value": [
                                {
                                    "idShort": "Level3Property",
                                    "modelType": "Property",
                                    "valueType": "xs:string",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        exporter = NodeSetExporter()
        result = exporter.export_template(nested)

        assert result.success
        assert "Level3Property" in result.nodeset_xml

    def test_special_element_types_generate_warnings(self):
        """Test that special element types generate warnings."""
        special = {
            "idShort": "Special",
            "submodelElements": [
                {
                    "idShort": "FileElement",
                    "modelType": "File",
                    "description": "A file element",
                }
            ],
        }

        exporter = NodeSetExporter()
        result = exporter.export_template(special)

        assert result.success
        # File element should generate a warning about placeholder mapping
        assert any("placeholder" in w.lower() for w in result.warnings)

    def test_operation_generates_warning(self):
        """Test that Operation generates warning."""
        with_operation = {
            "idShort": "WithOperation",
            "submodelElements": [
                {
                    "idShort": "TestOp",
                    "modelType": "Operation",
                    "description": "A test operation",
                }
            ],
        }

        exporter = NodeSetExporter()
        result = exporter.export_template(with_operation)

        assert result.success
        assert any("Method" in w or "Operation" in w for w in result.warnings)
