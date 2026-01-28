"""
OPC UA NodeSet2.xml Exporter.

Exports AAS structures to OPC UA NodeSet2 XML format
following the I4AAS (Industry 4.0 Asset Administration Shell) companion spec.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from xml.dom import minidom
from xml.etree import ElementTree as ET

from app.services.opcua.type_mapper import OPCUATypeMapper

logger = logging.getLogger(__name__)


# OPC UA NodeSet2 namespaces
OPCUA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


@dataclass
class ExportResult:
    """Result of NodeSet export operation."""

    success: bool
    nodeset_xml: str | None = None
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0
    namespace_uri: str | None = None
    exported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NodeSetExporter:
    """
    Exports AAS structures to OPC UA NodeSet2.xml format.

    The exporter follows these mapping rules:
    - Submodel → ObjectType with Variables/Objects
    - SubmodelElementCollection → Object with HasComponent references
    - Property → Variable
    - SubmodelElementList → Variable with array dimensions
    """

    def __init__(self, namespace_uri: str | None = None):
        """
        Initialize exporter.

        Args:
            namespace_uri: Custom namespace URI for generated nodes
        """
        self._type_mapper = OPCUATypeMapper()
        self._namespace_uri = namespace_uri or "urn:idta:generated:aas"
        self._node_counter = 0
        self._next_node_id = 1000  # Start custom nodes at ns=1;i=1000

    def export_template(self, template: dict, version: str = "1.0.0") -> ExportResult:
        """
        Export an AAS template to NodeSet2.xml format.

        Args:
            template: AAS template structure (from parser)
            version: Version string for the model

        Returns:
            ExportResult with NodeSet XML content
        """
        warnings: list[str] = []

        try:
            # Create root UANodeSet element
            root = ET.Element("UANodeSet")
            root.set("xmlns", OPCUA_NS)
            root.set("xmlns:xsi", XSI_NS)
            root.set("xmlns:uax", "http://opcfoundation.org/UA/2008/02/Types.xsd")

            # Add NamespaceUris
            ns_uris = ET.SubElement(root, "NamespaceUris")
            ns_uri = ET.SubElement(ns_uris, "Uri")
            ns_uri.text = self._namespace_uri

            # Add Models element
            models = ET.SubElement(root, "Models")
            model = ET.SubElement(models, "Model")
            model.set("ModelUri", self._namespace_uri)
            model.set("Version", version)
            model.set("PublicationDate", datetime.now(timezone.utc).isoformat())

            # Reset counters
            self._node_counter = 0
            self._next_node_id = 1000

            # Convert template to nodes
            id_short = template.get("idShort", "GeneratedSubmodel")
            elements = template.get("submodelElements", [])

            if not elements:
                # Check for UI schema format
                elements = template.get("elements", [])

            # Create root ObjectType
            root_node_id = self._get_next_node_id()
            root_type = self._create_object_type(
                root,
                root_node_id,
                id_short,
                template.get("description"),
                template.get("semanticId"),
            )

            # Add child elements
            for elem in elements:
                self._convert_element(root, root_type, root_node_id, elem, warnings)

            # Format XML with proper indentation
            xml_string = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")

            # Remove extra blank lines
            lines = [line for line in pretty_xml.split("\n") if line.strip()]
            nodeset_xml = "\n".join(lines)

            return ExportResult(
                success=True,
                nodeset_xml=nodeset_xml,
                warnings=warnings,
                node_count=self._node_counter,
                namespace_uri=self._namespace_uri,
            )

        except Exception as e:
            logger.exception("NodeSet export failed")
            return ExportResult(
                success=False,
                warnings=[f"Export error: {e}"],
            )

    def _get_next_node_id(self) -> str:
        """Get next unique NodeId."""
        node_id = f"ns=1;i={self._next_node_id}"
        self._next_node_id += 1
        self._node_counter += 1
        return node_id

    def _create_object_type(
        self,
        root: ET.Element,
        node_id: str,
        browse_name: str,
        description: str | dict | list | None,
        semantic_id: dict | str | None,
    ) -> ET.Element:
        """Create a UAObjectType element."""
        obj_type = ET.SubElement(root, "UAObjectType")
        obj_type.set("NodeId", node_id)
        obj_type.set("BrowseName", f"1:{browse_name}")

        # Display name
        display = ET.SubElement(obj_type, "DisplayName")
        display.text = browse_name

        # Description
        desc_text = self._extract_description(description)
        if desc_text:
            desc = ET.SubElement(obj_type, "Description")
            desc.text = desc_text

        # References - inherit from BaseObjectType
        refs = ET.SubElement(obj_type, "References")
        ref = ET.SubElement(refs, "Reference")
        ref.set("ReferenceType", "HasSubtype")
        ref.set("IsForward", "false")
        ref.text = "i=58"  # BaseObjectType

        return obj_type

    def _create_variable(
        self,
        root: ET.Element,
        parent_node_id: str,
        node_id: str,
        browse_name: str,
        data_type: str,
        description: str | dict | list | None,
        value: str | None = None,
        value_rank: int = -1,
        array_dimensions: str | None = None,
    ) -> ET.Element:
        """Create a UAVariable element."""
        variable = ET.SubElement(root, "UAVariable")
        variable.set("NodeId", node_id)
        variable.set("BrowseName", f"1:{browse_name}")
        variable.set("DataType", self._get_data_type_node_id(data_type))

        if value_rank >= 0:
            variable.set("ValueRank", str(value_rank))
        if array_dimensions:
            variable.set("ArrayDimensions", array_dimensions)

        # Display name
        display = ET.SubElement(variable, "DisplayName")
        display.text = browse_name

        # Description
        desc_text = self._extract_description(description)
        if desc_text:
            desc = ET.SubElement(variable, "Description")
            desc.text = desc_text

        # References
        refs = ET.SubElement(variable, "References")

        # HasTypeDefinition to BaseDataVariableType
        type_ref = ET.SubElement(refs, "Reference")
        type_ref.set("ReferenceType", "HasTypeDefinition")
        type_ref.text = "i=63"  # BaseDataVariableType

        # HasComponent from parent
        parent_ref = ET.SubElement(refs, "Reference")
        parent_ref.set("ReferenceType", "HasComponent")
        parent_ref.set("IsForward", "false")
        parent_ref.text = parent_node_id

        # Value if present
        if value is not None:
            self._add_value(variable, data_type, value)

        return variable

    def _create_object(
        self,
        root: ET.Element,
        parent_node_id: str,
        node_id: str,
        browse_name: str,
        description: str | dict | list | None,
    ) -> ET.Element:
        """Create a UAObject element."""
        obj = ET.SubElement(root, "UAObject")
        obj.set("NodeId", node_id)
        obj.set("BrowseName", f"1:{browse_name}")

        # Display name
        display = ET.SubElement(obj, "DisplayName")
        display.text = browse_name

        # Description
        desc_text = self._extract_description(description)
        if desc_text:
            desc = ET.SubElement(obj, "Description")
            desc.text = desc_text

        # References
        refs = ET.SubElement(obj, "References")

        # HasTypeDefinition to BaseObjectType
        type_ref = ET.SubElement(refs, "Reference")
        type_ref.set("ReferenceType", "HasTypeDefinition")
        type_ref.text = "i=58"  # BaseObjectType

        # HasComponent from parent
        parent_ref = ET.SubElement(refs, "Reference")
        parent_ref.set("ReferenceType", "HasComponent")
        parent_ref.set("IsForward", "false")
        parent_ref.text = parent_node_id

        return obj

    def _convert_element(
        self,
        root: ET.Element,
        parent_elem: ET.Element,
        parent_node_id: str,
        element: dict,
        warnings: list[str],
    ) -> None:
        """Convert an AAS element to OPC UA nodes."""
        model_type = element.get("modelType", "Property")
        id_short = element.get("idShort", "Element")

        if model_type == "SubmodelElementCollection":
            # Create Object for collection
            node_id = self._get_next_node_id()
            obj = self._create_object(
                root,
                parent_node_id,
                node_id,
                id_short,
                element.get("description"),
            )

            # Add HasComponent reference from parent
            self._add_component_reference(parent_elem, node_id)

            # Recursively add children
            children = element.get("value", []) or element.get("elements", [])
            for child in children:
                self._convert_element(root, obj, node_id, child, warnings)

        elif model_type == "SubmodelElementList":
            # Create Variable with array dimensions
            node_id = self._get_next_node_id()
            value_type = element.get(
                "valueTypeListElement", element.get("valueType", "xs:string")
            )
            opcua_type = self._type_mapper.aas_to_opcua(value_type)

            self._create_variable(
                root,
                parent_node_id,
                node_id,
                id_short,
                opcua_type,
                element.get("description"),
                value_rank=1,  # One-dimensional array
            )

            # Add HasComponent reference from parent
            self._add_component_reference(parent_elem, node_id)

        elif model_type == "Property":
            # Create Variable
            node_id = self._get_next_node_id()
            value_type = element.get("valueType", "xs:string")
            opcua_type = self._type_mapper.aas_to_opcua(value_type)

            self._create_variable(
                root,
                parent_node_id,
                node_id,
                id_short,
                opcua_type,
                element.get("description"),
                element.get("value"),
            )

            # Add HasComponent reference from parent
            self._add_component_reference(parent_elem, node_id)

        elif model_type == "MultiLanguageProperty":
            # Map to LocalizedText variable
            node_id = self._get_next_node_id()
            self._create_variable(
                root,
                parent_node_id,
                node_id,
                id_short,
                "LocalizedText",
                element.get("description"),
            )
            self._add_component_reference(parent_elem, node_id)

        elif model_type in ("Range", "Blob", "File", "ReferenceElement"):
            # Create Object to contain the complex structure
            node_id = self._get_next_node_id()
            self._create_object(
                root,
                parent_node_id,
                node_id,
                id_short,
                element.get("description"),
            )
            self._add_component_reference(parent_elem, node_id)
            warnings.append(
                f"Element '{id_short}' ({model_type}) mapped to Object placeholder"
            )

        elif model_type == "Operation":
            # OPC UA Methods require more complex handling
            warnings.append(
                f"Operation '{id_short}' skipped - Method export not fully supported"
            )

        else:
            # Default: create as Variable
            node_id = self._get_next_node_id()
            self._create_variable(
                root,
                parent_node_id,
                node_id,
                id_short,
                "String",
                element.get("description"),
            )
            self._add_component_reference(parent_elem, node_id)
            warnings.append(
                f"Unknown element type '{model_type}' for '{id_short}', mapped to Variable"
            )

    def _add_component_reference(
        self, parent_elem: ET.Element, child_node_id: str
    ) -> None:
        """Add HasComponent reference to parent element."""
        refs = parent_elem.find("References")
        if refs is None:
            refs = ET.SubElement(parent_elem, "References")

        ref = ET.SubElement(refs, "Reference")
        ref.set("ReferenceType", "HasComponent")
        ref.text = child_node_id

    def _get_data_type_node_id(self, opcua_type: str) -> str:
        """Get OPC UA NodeId for a data type."""
        # Map OPC UA type names to base NodeIds
        type_ids = {
            "Boolean": "i=1",
            "SByte": "i=2",
            "Byte": "i=3",
            "Int16": "i=4",
            "UInt16": "i=5",
            "Int32": "i=6",
            "UInt32": "i=7",
            "Int64": "i=8",
            "UInt64": "i=9",
            "Float": "i=10",
            "Double": "i=11",
            "String": "i=12",
            "DateTime": "i=13",
            "Guid": "i=14",
            "ByteString": "i=15",
            "XmlElement": "i=16",
            "NodeId": "i=17",
            "ExpandedNodeId": "i=18",
            "StatusCode": "i=19",
            "QualifiedName": "i=20",
            "LocalizedText": "i=21",
        }
        return type_ids.get(opcua_type, "i=12")  # Default to String

    def _add_value(
        self, variable: ET.Element, opcua_type: str, value: str | None
    ) -> None:
        """Add Value element to variable."""
        if value is None:
            return

        value_elem = ET.SubElement(variable, "Value")

        # Wrap value in appropriate type element
        type_tag = opcua_type if opcua_type != "String" else "String"
        type_elem = ET.SubElement(value_elem, f"uax:{type_tag}")
        type_elem.text = str(value)

    def _extract_description(
        self, description: str | dict | list | None
    ) -> str | None:
        """Extract description text from various formats."""
        if description is None:
            return None

        if isinstance(description, str):
            return description

        if isinstance(description, list):
            # Multi-language property format
            for item in description:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        return text
            return None

        if isinstance(description, dict):
            return description.get("text") or description.get("en")

        return None
