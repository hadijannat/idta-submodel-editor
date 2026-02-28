"""
Tests for OPC UA Type Mapper.

Tests type conversion between OPC UA and AAS type systems.
"""


from app.services.opcua.type_mapper import (
    OPCUATypeMapper,
    OPCUABuiltInType,
    OPCUA_TO_AAS_TYPE_MAP,
    AAS_TO_OPCUA_TYPE_MAP,
    NODECLASS_TO_AAS_MAP,
    AAS_TO_NODECLASS_MAP,
)


class TestOPCUAToAASMapping:
    """Test OPC UA to AAS type mapping."""

    def test_boolean_mapping(self):
        """Test boolean type mapping."""
        assert OPCUA_TO_AAS_TYPE_MAP["Boolean"] == "xs:boolean"
        assert OPCUATypeMapper.opcua_to_aas("Boolean") == "xs:boolean"

    def test_numeric_mappings(self):
        """Test numeric type mappings."""
        assert OPCUA_TO_AAS_TYPE_MAP["Int32"] == "xs:int"
        assert OPCUA_TO_AAS_TYPE_MAP["Int64"] == "xs:long"
        assert OPCUA_TO_AAS_TYPE_MAP["UInt32"] == "xs:unsignedInt"
        assert OPCUA_TO_AAS_TYPE_MAP["Double"] == "xs:double"
        assert OPCUA_TO_AAS_TYPE_MAP["Float"] == "xs:float"

    def test_string_mapping(self):
        """Test string type mapping."""
        assert OPCUA_TO_AAS_TYPE_MAP["String"] == "xs:string"
        assert OPCUA_TO_AAS_TYPE_MAP["LocalizedText"] == "xs:string"

    def test_datetime_mapping(self):
        """Test datetime type mapping."""
        assert OPCUA_TO_AAS_TYPE_MAP["DateTime"] == "xs:dateTime"

    def test_binary_mapping(self):
        """Test binary type mapping."""
        assert OPCUA_TO_AAS_TYPE_MAP["ByteString"] == "xs:base64Binary"

    def test_unknown_type_defaults_to_string(self):
        """Test that unknown types default to xs:string."""
        assert OPCUATypeMapper.opcua_to_aas("UnknownType") == "xs:string"


class TestAASToOPCUAMapping:
    """Test AAS to OPC UA type mapping."""

    def test_boolean_mapping(self):
        """Test boolean type mapping."""
        assert AAS_TO_OPCUA_TYPE_MAP["xs:boolean"] == "Boolean"
        assert OPCUATypeMapper.aas_to_opcua("xs:boolean") == "Boolean"

    def test_numeric_mappings(self):
        """Test numeric type mappings."""
        assert AAS_TO_OPCUA_TYPE_MAP["xs:int"] == "Int32"
        assert AAS_TO_OPCUA_TYPE_MAP["xs:long"] == "Int64"
        assert AAS_TO_OPCUA_TYPE_MAP["xs:unsignedInt"] == "UInt32"
        assert AAS_TO_OPCUA_TYPE_MAP["xs:double"] == "Double"
        assert AAS_TO_OPCUA_TYPE_MAP["xs:float"] == "Float"

    def test_string_mapping(self):
        """Test string type mapping."""
        assert AAS_TO_OPCUA_TYPE_MAP["xs:string"] == "String"

    def test_datetime_mapping(self):
        """Test datetime type mapping."""
        assert AAS_TO_OPCUA_TYPE_MAP["xs:dateTime"] == "DateTime"

    def test_unknown_type_defaults_to_string(self):
        """Test that unknown types default to String."""
        assert OPCUATypeMapper.aas_to_opcua("xs:unknownType") == "String"


class TestNodeClassMapping:
    """Test NodeClass to AAS element type mapping."""

    def test_object_type_mapping(self):
        """Test ObjectType maps to SubmodelElementCollection."""
        assert NODECLASS_TO_AAS_MAP["ObjectType"] == "SubmodelElementCollection"

    def test_variable_mapping(self):
        """Test Variable maps to Property."""
        assert NODECLASS_TO_AAS_MAP["Variable"] == "Property"

    def test_method_mapping(self):
        """Test Method maps to Operation."""
        assert NODECLASS_TO_AAS_MAP["Method"] == "Operation"

    def test_reverse_mapping(self):
        """Test AAS to NodeClass mapping."""
        assert AAS_TO_NODECLASS_MAP["SubmodelElementCollection"] == "Object"
        assert AAS_TO_NODECLASS_MAP["Property"] == "Variable"
        assert AAS_TO_NODECLASS_MAP["Operation"] == "Method"


class TestValueConversion:
    """Test value conversion between type systems."""

    def test_boolean_conversion(self):
        """Test boolean value conversion."""
        mapper = OPCUATypeMapper()

        assert mapper.convert_value("true", "Boolean", "xs:boolean") is True
        assert mapper.convert_value("false", "Boolean", "xs:boolean") is False
        assert mapper.convert_value("1", "Boolean", "xs:boolean") is True
        assert mapper.convert_value("0", "Boolean", "xs:boolean") is False

    def test_integer_conversion(self):
        """Test integer value conversion."""
        mapper = OPCUATypeMapper()

        assert mapper.convert_value("42", "Int32", "xs:int") == 42
        assert mapper.convert_value("invalid", "Int32", "xs:int") == 0

    def test_float_conversion(self):
        """Test float value conversion."""
        mapper = OPCUATypeMapper()

        assert mapper.convert_value("3.14", "Double", "xs:double") == 3.14
        assert mapper.convert_value("invalid", "Double", "xs:double") == 0.0

    def test_string_conversion(self):
        """Test string value conversion."""
        mapper = OPCUATypeMapper()

        assert mapper.convert_value(42, "Int32", "xs:string") == "42"

    def test_none_value(self):
        """Test None value handling."""
        mapper = OPCUATypeMapper()

        # None input returns None (preserves null semantics)
        assert mapper.convert_value(None, "String", "xs:string") is None


class TestDefaultValues:
    """Test default value generation."""

    def test_boolean_default(self):
        """Test boolean default value."""
        assert OPCUATypeMapper.get_default_value("xs:boolean") is False

    def test_numeric_defaults(self):
        """Test numeric default values."""
        assert OPCUATypeMapper.get_default_value("xs:int") == 0
        assert OPCUATypeMapper.get_default_value("xs:double") == 0.0
        assert OPCUATypeMapper.get_default_value("xs:float") == 0.0

    def test_string_default(self):
        """Test string default value."""
        assert OPCUATypeMapper.get_default_value("xs:string") == ""

    def test_unknown_default(self):
        """Test unknown type default value."""
        assert OPCUATypeMapper.get_default_value("xs:unknownType") == ""


class TestBuiltInTypeEnum:
    """Test OPCUABuiltInType enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert OPCUABuiltInType.BOOLEAN.value == "Boolean"
        assert OPCUABuiltInType.INT32.value == "Int32"
        assert OPCUABuiltInType.DOUBLE.value == "Double"
        assert OPCUABuiltInType.STRING.value == "String"
        assert OPCUABuiltInType.DATE_TIME.value == "DateTime"
