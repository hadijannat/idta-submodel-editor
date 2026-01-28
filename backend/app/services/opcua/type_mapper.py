"""
Type mapping between OPC UA and AAS data types.

Follows I4AAS (Industry 4.0 Asset Administration Shell) companion spec
for OPC UA <-> AAS type mappings.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class OPCUABuiltInType(str, Enum):
    """OPC UA built-in data types (NodeIds 1-31)."""

    BOOLEAN = "Boolean"  # NodeId 1
    SBYTE = "SByte"  # NodeId 2
    BYTE = "Byte"  # NodeId 3
    INT16 = "Int16"  # NodeId 4
    UINT16 = "UInt16"  # NodeId 5
    INT32 = "Int32"  # NodeId 6
    UINT32 = "UInt32"  # NodeId 7
    INT64 = "Int64"  # NodeId 8
    UINT64 = "UInt64"  # NodeId 9
    FLOAT = "Float"  # NodeId 10
    DOUBLE = "Double"  # NodeId 11
    STRING = "String"  # NodeId 12
    DATE_TIME = "DateTime"  # NodeId 13
    GUID = "Guid"  # NodeId 14
    BYTE_STRING = "ByteString"  # NodeId 15
    XML_ELEMENT = "XmlElement"  # NodeId 16
    NODE_ID = "NodeId"  # NodeId 17
    EXPANDED_NODE_ID = "ExpandedNodeId"  # NodeId 18
    STATUS_CODE = "StatusCode"  # NodeId 19
    QUALIFIED_NAME = "QualifiedName"  # NodeId 20
    LOCALIZED_TEXT = "LocalizedText"  # NodeId 21
    EXTENSION_OBJECT = "ExtensionObject"  # NodeId 22
    DATA_VALUE = "DataValue"  # NodeId 23
    VARIANT = "Variant"  # NodeId 24
    DIAGNOSTIC_INFO = "DiagnosticInfo"  # NodeId 25


# OPC UA to AAS DataTypeDefXsd mapping
# Based on I4AAS companion specification
OPCUA_TO_AAS_TYPE_MAP: dict[str, str] = {
    # Basic numeric types
    "Boolean": "xs:boolean",
    "SByte": "xs:byte",
    "Byte": "xs:unsignedByte",
    "Int16": "xs:short",
    "UInt16": "xs:unsignedShort",
    "Int32": "xs:int",
    "UInt32": "xs:unsignedInt",
    "Int64": "xs:long",
    "UInt64": "xs:unsignedLong",
    "Float": "xs:float",
    "Double": "xs:double",
    # String and text types
    "String": "xs:string",
    "LocalizedText": "xs:string",
    "QualifiedName": "xs:string",
    # Date/time types
    "DateTime": "xs:dateTime",
    # Binary types
    "ByteString": "xs:base64Binary",
    "XmlElement": "xs:string",
    # URI and ID types
    "NodeId": "xs:anyURI",
    "ExpandedNodeId": "xs:anyURI",
    "Guid": "xs:string",
    # Complex types (mapped to string)
    "StatusCode": "xs:unsignedInt",
    "ExtensionObject": "xs:string",
    "DataValue": "xs:string",
    "Variant": "xs:string",
    "DiagnosticInfo": "xs:string",
}


# AAS to OPC UA mapping
# When multiple OPC UA types map to same AAS type, use most common type
AAS_TO_OPCUA_TYPE_MAP: dict[str, str] = {
    "xs:boolean": "Boolean",
    "xs:byte": "SByte",
    "xs:unsignedByte": "Byte",
    "xs:short": "Int16",
    "xs:unsignedShort": "UInt16",
    "xs:int": "Int32",
    "xs:unsignedInt": "UInt32",
    "xs:integer": "Int64",
    "xs:long": "Int64",
    "xs:unsignedLong": "UInt64",
    "xs:float": "Float",
    "xs:double": "Double",
    "xs:decimal": "Double",
    "xs:string": "String",
    "xs:dateTime": "DateTime",
    "xs:date": "DateTime",
    "xs:time": "String",
    "xs:base64Binary": "ByteString",
    "xs:hexBinary": "ByteString",
    "xs:anyURI": "String",
    "xs:duration": "String",
    "xs:gYear": "String",
    "xs:gMonth": "String",
    "xs:gDay": "String",
    "xs:gYearMonth": "String",
    "xs:gMonthDay": "String",
    "xs:positiveInteger": "UInt64",
    "xs:nonNegativeInteger": "UInt64",
    "xs:negativeInteger": "Int64",
    "xs:nonPositiveInteger": "Int64",
}


# NodeClass to AAS element mapping
NODECLASS_TO_AAS_MAP: dict[str, str] = {
    "Object": "SubmodelElementCollection",
    "ObjectType": "SubmodelElementCollection",
    "Variable": "Property",
    "VariableType": "Property",
    "Method": "Operation",
    "View": "SubmodelElementCollection",
    "DataType": "ConceptDescription",
    "ReferenceType": "Reference",
}


# AAS element to NodeClass mapping
AAS_TO_NODECLASS_MAP: dict[str, str] = {
    "Submodel": "Object",
    "SubmodelElementCollection": "Object",
    "SubmodelElementList": "Object",
    "Property": "Variable",
    "MultiLanguageProperty": "Variable",
    "Range": "Object",
    "Blob": "Variable",
    "File": "Variable",
    "ReferenceElement": "Variable",
    "RelationshipElement": "Object",
    "AnnotatedRelationshipElement": "Object",
    "Entity": "Object",
    "BasicEventElement": "Object",
    "Operation": "Method",
}


class OPCUATypeMapper:
    """Utility class for OPC UA <-> AAS type mapping."""

    @staticmethod
    def opcua_to_aas(opcua_type: str) -> str:
        """
        Map OPC UA data type to AAS DataTypeDefXsd.

        Args:
            opcua_type: OPC UA built-in type name

        Returns:
            AAS DataTypeDefXsd value
        """
        return OPCUA_TO_AAS_TYPE_MAP.get(opcua_type, "xs:string")

    @staticmethod
    def aas_to_opcua(aas_type: str) -> str:
        """
        Map AAS DataTypeDefXsd to OPC UA data type.

        Args:
            aas_type: AAS DataTypeDefXsd value

        Returns:
            OPC UA built-in type name
        """
        return AAS_TO_OPCUA_TYPE_MAP.get(aas_type, "String")

    @staticmethod
    def nodeclass_to_aas(node_class: str) -> str:
        """
        Map OPC UA NodeClass to AAS element type.

        Args:
            node_class: OPC UA NodeClass name

        Returns:
            AAS SubmodelElement type
        """
        return NODECLASS_TO_AAS_MAP.get(node_class, "Property")

    @staticmethod
    def aas_to_nodeclass(aas_element: str) -> str:
        """
        Map AAS element type to OPC UA NodeClass.

        Args:
            aas_element: AAS SubmodelElement type

        Returns:
            OPC UA NodeClass name
        """
        return AAS_TO_NODECLASS_MAP.get(aas_element, "Variable")

    @staticmethod
    def convert_value(
        value: Any, from_type: str, to_type: str, direction: str = "opcua_to_aas"
    ) -> Any:
        """
        Convert a value between OPC UA and AAS type systems.

        Args:
            value: The value to convert
            from_type: Source type
            to_type: Target type
            direction: 'opcua_to_aas' or 'aas_to_opcua'

        Returns:
            Converted value
        """
        if value is None:
            return None

        # Handle boolean conversion
        if to_type in ("xs:boolean", "Boolean"):
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)

        # Handle numeric conversions
        if to_type in (
            "xs:int",
            "xs:long",
            "xs:short",
            "Int32",
            "Int64",
            "Int16",
            "xs:integer",
        ):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0

        if to_type in (
            "xs:unsignedInt",
            "xs:unsignedLong",
            "xs:unsignedShort",
            "UInt32",
            "UInt64",
            "UInt16",
        ):
            try:
                return max(0, int(value))
            except (ValueError, TypeError):
                return 0

        if to_type in ("xs:float", "xs:double", "xs:decimal", "Float", "Double"):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        # Default: convert to string
        return str(value) if value is not None else ""

    @staticmethod
    def get_default_value(aas_type: str) -> Any:
        """
        Get the default value for an AAS data type.

        Args:
            aas_type: AAS DataTypeDefXsd value

        Returns:
            Default value for the type
        """
        defaults: dict[str, Any] = {
            "xs:boolean": False,
            "xs:byte": 0,
            "xs:unsignedByte": 0,
            "xs:short": 0,
            "xs:unsignedShort": 0,
            "xs:int": 0,
            "xs:unsignedInt": 0,
            "xs:long": 0,
            "xs:unsignedLong": 0,
            "xs:integer": 0,
            "xs:float": 0.0,
            "xs:double": 0.0,
            "xs:decimal": 0.0,
            "xs:string": "",
            "xs:dateTime": "",
            "xs:date": "",
            "xs:time": "",
            "xs:base64Binary": "",
            "xs:hexBinary": "",
            "xs:anyURI": "",
        }
        return defaults.get(aas_type, "")
