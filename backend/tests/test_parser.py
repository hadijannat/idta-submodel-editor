"""
Tests for the Parser service.
"""

import pytest
from unittest.mock import MagicMock
from io import BytesIO

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.parser import ParserService


def _external_reference(value: str) -> model.ExternalReference:
    return model.ExternalReference(
        key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),),
    )


def _create_aasx_with_elements(elements) -> bytes:
    submodel = model.Submodel(
        id_="urn:test:submodel",
        id_short="TestSubmodel",
        submodel_element=list(elements),
    )
    aas_obj = model.AssetAdministrationShell(
        id_="urn:test:aas",
        id_short="TestAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:test:asset",
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )

    object_store: model.DictObjectStore = model.DictObjectStore([aas_obj, submodel])
    file_store = aasx.DictSupplementaryFileContainer()
    output = BytesIO()
    with aasx.AASXWriter(output) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml",
            object_store,
            file_store,
            write_json=False,
        )
    return output.getvalue()


def _create_aasx_with_blob(blob_value: bytes) -> bytes:
    blob = model.Blob(
        id_short="BlobValue",
        content_type="application/octet-stream",
        value=blob_value,
    )
    return _create_aasx_with_elements([blob])


class TestParserService:
    """Tests for ParserService."""

    def test_parser_initialization(self):
        """Test that parser service can be initialized."""
        parser = ParserService()
        assert parser is not None

    @pytest.mark.asyncio
    async def test_parse_aasx_invalid_bytes(self):
        """Test parsing invalid AASX content."""
        parser = ParserService()

        with pytest.raises(Exception):
            parser.parse_aasx_to_ui_schema(b"not a valid aasx file")

    def test_parse_aasx_blob_non_utf8_is_base64_payload(self):
        """Binary blob values should be represented deterministically."""
        parser = ParserService()
        aasx_bytes = _create_aasx_with_blob(b"\xff\xfe\x00\x01")

        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)
        blob = schema["elements"][0]

        assert blob["modelType"] == "Blob"
        assert blob["valueEncoding"] == "base64"
        assert blob["value"].startswith("base64:")

    def test_parse_aasx_blob_utf8_marks_utf8_encoding(self):
        """UTF-8 blob values should preserve plain-text representation."""
        parser = ParserService()
        aasx_bytes = _create_aasx_with_blob("hello".encode("utf-8"))

        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)
        blob = schema["elements"][0]

        assert blob["modelType"] == "Blob"
        assert blob["valueEncoding"] == "utf-8"
        assert blob["value"] == "hello"

    def test_parse_annotated_relationship_includes_annotations(self):
        """AnnotatedRelationshipElement must keep annotation schemas."""
        parser = ParserService()
        annotation = model.Property(
            id_short="AnnotationValue",
            value_type=model.datatypes.String,
            value="note",
        )
        relationship = model.AnnotatedRelationshipElement(
            id_short="AnnotatedRelationship",
            first=_external_reference("urn:first"),
            second=_external_reference("urn:second"),
            annotation=(annotation,),
        )
        aasx_bytes = _create_aasx_with_elements([relationship])

        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)
        element = schema["elements"][0]

        assert element["modelType"] == "AnnotatedRelationshipElement"
        assert element["first"] == "urn:first"
        assert element["second"] == "urn:second"
        assert element["annotations"][0]["idShort"] == "AnnotationValue"
        assert element["annotations"][0]["value"] == "note"

    def test_create_list_item_template_covers_blob_and_entity_shapes(self):
        """Empty lists with type metadata should emit form-compatible templates."""
        parser = ParserService()

        blob_template = parser._create_template_from_type(model.Blob)
        entity_template = parser._create_template_from_type(model.Entity)

        assert blob_template["modelType"] == "Blob"
        assert blob_template["contentType"] == "application/octet-stream"
        assert "valueEncoding" in blob_template
        assert entity_template["modelType"] == "Entity"
        assert entity_template["statements"] == []

    def test_serialize_reference_none(self):
        """Test serializing None reference."""
        parser = ParserService()
        result = parser._serialize_reference(None)
        assert result is None

    def test_serialize_reference_uses_last_key(self):
        """Test serializing reference uses the most specific key."""
        parser = ParserService()
        mock_ref = MagicMock()
        mock_ref.key = [MagicMock(value="first"), MagicMock(value="last")]
        result = parser._serialize_reference(mock_ref)
        assert result == "last"

    def test_extract_cardinality_default(self):
        """Test extracting default cardinality."""
        parser = ParserService()

        # Mock element without qualifiers
        mock_element = MagicMock()
        mock_element.qualifier = []

        result = parser._extract_cardinality(mock_element)
        assert result == "[1]"

    def test_extract_cardinality_from_qualifier(self):
        """Test extracting cardinality from qualifier."""
        parser = ParserService()

        # Mock element with cardinality qualifier
        mock_qualifier = MagicMock()
        mock_qualifier.type_ = "Multiplicity"
        mock_qualifier.value = "[0..1]"

        mock_element = MagicMock()
        mock_element.qualifier = [mock_qualifier]

        result = parser._extract_cardinality(mock_element)
        assert result == "[0..1]"


class TestXSDMapping:
    """Tests for XSD to HTML input mapping."""

    def test_string_type(self):
        """Test xs:string maps to text input."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type("xs:string") == "text"

    def test_integer_type(self):
        """Test xs:integer maps to number input."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type("xs:integer") == "number"

    def test_date_type(self):
        """Test xs:date maps to date input."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type("xs:date") == "date"

    def test_boolean_type(self):
        """Test xs:boolean maps to checkbox."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type("xs:boolean") == "checkbox"

    def test_unknown_type(self):
        """Test unknown type defaults to text."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type("xs:unknownType") == "text"

    def test_none_type(self):
        """Test None type defaults to text."""
        from app.utils.xsd_mapping import get_input_type

        assert get_input_type(None) == "text"
