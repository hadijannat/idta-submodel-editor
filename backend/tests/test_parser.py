"""
Tests for the Parser service.
"""

import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO

from app.services.parser import ParserService


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

    def test_serialize_reference_none(self):
        """Test serializing None reference."""
        parser = ParserService()
        result = parser._serialize_reference(None)
        assert result is None

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
