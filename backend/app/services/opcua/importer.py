"""
OPC UA NodeSet2.xml Importer.

Parses OPC UA NodeSet2 XML files and converts them to AAS template structures
following the I4AAS (Industry 4.0 Asset Administration Shell) companion spec.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.opcua.type_mapper import OPCUATypeMapper

logger = logging.getLogger(__name__)

# Maximum recursion depth for node hierarchy traversal (protection against deep attacks)
MAX_HIERARCHY_DEPTH = 100

# Maximum size for NodeSet XML content (10 MB) - protection against XML bombs
MAX_NODESET_SIZE = 10 * 1024 * 1024

# OPC UA NodeSet2 namespaces
NS = {
    "ns": "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "uax": "http://opcfoundation.org/UA/2008/02/Types.xsd",
}


@dataclass
class OPCUANode:
    """Represents a parsed OPC UA node."""

    node_id: str
    browse_name: str
    display_name: str
    description: str | None = None
    node_class: str = "Variable"
    data_type: str | None = None
    value: Any = None
    value_rank: int = -1  # -1 = scalar
    array_dimensions: list[int] | None = None
    references: list[dict[str, str]] = field(default_factory=list)
    children: list["OPCUANode"] = field(default_factory=list)


@dataclass
class ImportResult:
    """Result of NodeSet import operation."""

    success: bool
    template: dict | None = None
    ui_schema: dict | None = None
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0
    source_namespace: str | None = None
    imported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NodeSetImporter:
    """
    Imports OPC UA NodeSet2.xml files and converts to AAS structure.

    The importer follows these mapping rules:
    - ObjectTypes → SubmodelElementCollection
    - Variables → Property
    - Methods → Operation (placeholder)
    - References → Used to build hierarchy
    """

    def __init__(self):
        self._type_mapper = OPCUATypeMapper()
        self._nodes: dict[str, OPCUANode] = {}
        self._namespaces: list[str] = []

    def import_nodeset(
        self, content: str | bytes, root_node_id: str | None = None
    ) -> ImportResult:
        """
        Import a NodeSet2.xml file and convert to AAS template.

        Args:
            content: XML content (string or bytes)
            root_node_id: Optional NodeId to use as root (defaults to first ObjectType)

        Returns:
            ImportResult with AAS template and UI schema
        """
        warnings: list[str] = []

        try:
            # Convert bytes to string and check size for XML bomb protection
            if isinstance(content, bytes):
                if len(content) > MAX_NODESET_SIZE:
                    return ImportResult(
                        success=False,
                        warnings=[
                            f"NodeSet file too large ({len(content)} bytes). "
                            f"Maximum size is {MAX_NODESET_SIZE} bytes (10 MB)."
                        ],
                    )
                content = content.decode("utf-8")
            elif len(content) > MAX_NODESET_SIZE:
                return ImportResult(
                    success=False,
                    warnings=[
                        f"NodeSet content too large ({len(content)} characters). "
                        f"Maximum size is {MAX_NODESET_SIZE} characters."
                    ],
                )

            # Parse XML using defusedxml if available, otherwise standard ET
            try:
                import defusedxml.ElementTree as DefusedET

                root = DefusedET.fromstring(content)
            except ImportError:
                # Fall back to standard ET with size limit already checked
                root = ET.fromstring(content)

            # Extract namespaces
            self._parse_namespaces(root)

            # Parse all nodes
            self._nodes = {}
            self._parse_nodes(root, warnings)

            if not self._nodes:
                return ImportResult(
                    success=False,
                    warnings=["No nodes found in NodeSet file"],
                )

            # Find root node for template
            root_node = self._find_root_node(root_node_id)
            if not root_node:
                return ImportResult(
                    success=False,
                    warnings=["Could not find suitable root node for template"],
                )

            # Build node hierarchy
            self._build_hierarchy()

            # Convert to AAS template structure
            template = self._convert_to_template(root_node)
            ui_schema = self._generate_ui_schema(root_node)

            return ImportResult(
                success=True,
                template=template,
                ui_schema=ui_schema,
                warnings=warnings,
                node_count=len(self._nodes),
                source_namespace=self._namespaces[0] if self._namespaces else None,
            )

        except ET.ParseError as e:
            return ImportResult(
                success=False,
                warnings=[f"XML parse error: {e}"],
            )
        except Exception as e:
            logger.exception("NodeSet import failed")
            return ImportResult(
                success=False,
                warnings=[f"Import error: {e}"],
            )

    def _parse_namespaces(self, root: ET.Element) -> None:
        """Extract namespace URIs from NodeSet."""
        self._namespaces = []

        # Default OPC UA namespace
        self._namespaces.append("http://opcfoundation.org/UA/")

        # Custom namespaces from NamespaceUris element
        ns_uris = root.find("ns:NamespaceUris", NS)
        if ns_uris is None:
            ns_uris = root.find("NamespaceUris")
        if ns_uris is not None:
            uris = ns_uris.findall("ns:Uri", NS)
            if not uris:
                uris = ns_uris.findall("Uri")
            for uri in uris:
                if uri.text:
                    self._namespaces.append(uri.text)

    def _parse_nodes(self, root: ET.Element, warnings: list[str]) -> None:
        """Parse all nodes from NodeSet."""
        # Parse ObjectTypes
        for obj_type in root.findall("ns:UAObjectType", NS) or root.findall(
            "UAObjectType"
        ):
            node = self._parse_object_type(obj_type)
            if node:
                self._nodes[node.node_id] = node

        # Parse Variables
        for variable in root.findall("ns:UAVariable", NS) or root.findall("UAVariable"):
            node = self._parse_variable(variable)
            if node:
                self._nodes[node.node_id] = node

        # Parse Objects
        for obj in root.findall("ns:UAObject", NS) or root.findall("UAObject"):
            node = self._parse_object(obj)
            if node:
                self._nodes[node.node_id] = node

        # Parse Methods
        for method in root.findall("ns:UAMethod", NS) or root.findall("UAMethod"):
            node = self._parse_method(method)
            if node:
                self._nodes[node.node_id] = node

        logger.info(f"Parsed {len(self._nodes)} nodes from NodeSet")

    def _parse_object_type(self, elem: ET.Element) -> OPCUANode | None:
        """Parse a UAObjectType element."""
        node_id = elem.get("NodeId")
        browse_name = elem.get("BrowseName", "")

        if not node_id:
            return None

        # Get display name
        display_name = self._get_text_element(elem, "DisplayName") or browse_name

        # Get description
        description = self._get_text_element(elem, "Description")

        # Parse references
        references = self._parse_references(elem)

        return OPCUANode(
            node_id=node_id,
            browse_name=browse_name,
            display_name=display_name,
            description=description,
            node_class="ObjectType",
            references=references,
        )

    def _parse_variable(self, elem: ET.Element) -> OPCUANode | None:
        """Parse a UAVariable element."""
        node_id = elem.get("NodeId")
        browse_name = elem.get("BrowseName", "")
        data_type = elem.get("DataType", "String")

        if not node_id:
            return None

        # Get display name
        display_name = self._get_text_element(elem, "DisplayName") or browse_name

        # Get description
        description = self._get_text_element(elem, "Description")

        # Get value rank and array dimensions
        value_rank = int(elem.get("ValueRank", "-1"))
        array_dims = elem.get("ArrayDimensions")
        array_dimensions = None
        if array_dims:
            array_dimensions = [int(d) for d in array_dims.split(",")]

        # Parse value if present
        value = self._parse_value(elem)

        # Parse references
        references = self._parse_references(elem)

        return OPCUANode(
            node_id=node_id,
            browse_name=browse_name,
            display_name=display_name,
            description=description,
            node_class="Variable",
            data_type=data_type,
            value=value,
            value_rank=value_rank,
            array_dimensions=array_dimensions,
            references=references,
        )

    def _parse_object(self, elem: ET.Element) -> OPCUANode | None:
        """Parse a UAObject element."""
        node_id = elem.get("NodeId")
        browse_name = elem.get("BrowseName", "")

        if not node_id:
            return None

        display_name = self._get_text_element(elem, "DisplayName") or browse_name
        description = self._get_text_element(elem, "Description")
        references = self._parse_references(elem)

        return OPCUANode(
            node_id=node_id,
            browse_name=browse_name,
            display_name=display_name,
            description=description,
            node_class="Object",
            references=references,
        )

    def _parse_method(self, elem: ET.Element) -> OPCUANode | None:
        """Parse a UAMethod element."""
        node_id = elem.get("NodeId")
        browse_name = elem.get("BrowseName", "")

        if not node_id:
            return None

        display_name = self._get_text_element(elem, "DisplayName") or browse_name
        description = self._get_text_element(elem, "Description")
        references = self._parse_references(elem)

        return OPCUANode(
            node_id=node_id,
            browse_name=browse_name,
            display_name=display_name,
            description=description,
            node_class="Method",
            references=references,
        )

    def _get_text_element(self, elem: ET.Element, name: str) -> str | None:
        """Get text content from a child element."""
        child = elem.find(f"ns:{name}", NS)
        if child is None:
            child = elem.find(name)
        if child is not None and child.text:
            return child.text.strip()
        return None

    def _parse_references(self, elem: ET.Element) -> list[dict[str, str]]:
        """Parse References element."""
        references = []
        refs_elem = elem.find("ns:References", NS)
        if refs_elem is None:
            refs_elem = elem.find("References")

        if refs_elem is not None:
            refs = refs_elem.findall("ns:Reference", NS)
            if not refs:
                refs = refs_elem.findall("Reference")
            for ref in refs:
                ref_type = ref.get("ReferenceType", "")
                is_forward = ref.get("IsForward", "true") == "true"
                target = ref.text or ""

                references.append(
                    {
                        "type": ref_type,
                        "is_forward": is_forward,
                        "target": target,
                    }
                )

        return references

    def _parse_value(self, elem: ET.Element) -> Any:
        """Parse Value element if present."""
        value_elem = elem.find("ns:Value", NS)
        if value_elem is None:
            value_elem = elem.find("Value")
        if value_elem is None:
            return None

        # Handle various value types
        for child in value_elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child.text:
                return child.text.strip()

        return None

    def _find_root_node(self, root_node_id: str | None) -> OPCUANode | None:
        """Find the root node for template generation."""
        if root_node_id and root_node_id in self._nodes:
            return self._nodes[root_node_id]

        # Find first ObjectType that isn't a base type
        for node in self._nodes.values():
            if node.node_class == "ObjectType":
                # Skip base types (ns=0)
                if not node.node_id.startswith("i="):
                    return node

        # Fallback: first Object
        for node in self._nodes.values():
            if node.node_class == "Object":
                return node

        # Fallback: any node
        return next(iter(self._nodes.values())) if self._nodes else None

    def _build_hierarchy(self) -> None:
        """Build parent-child relationships based on references with cycle detection."""
        # Track which nodes have been added as children to detect cycles
        added_as_child: set[str] = set()

        for node in self._nodes.values():
            for ref in node.references:
                if ref["type"] in (
                    "HasComponent",
                    "HasProperty",
                    "HasSubtype",
                    "Organizes",
                ):
                    if ref["is_forward"]:
                        target_id = ref["target"]
                        if target_id in self._nodes:
                            # Skip if this would create a cycle
                            if target_id == node.node_id:
                                logger.warning(
                                    "Skipping self-referencing node: %s", target_id
                                )
                                continue
                            if target_id in added_as_child:
                                # Node already has a parent - skip to avoid diamond/cycle
                                logger.debug(
                                    "Node %s already has a parent, skipping", target_id
                                )
                                continue
                            node.children.append(self._nodes[target_id])
                            added_as_child.add(target_id)

    def _convert_to_template(self, root_node: OPCUANode) -> dict:
        """Convert OPC UA node hierarchy to AAS template structure."""
        visited: set[str] = set()
        return {
            "idShort": self._sanitize_id_short(root_node.browse_name),
            "modelType": "Submodel",
            "semanticId": {
                "type": "ExternalReference",
                "keys": [
                    {
                        "type": "GlobalReference",
                        "value": f"urn:opcua:{root_node.node_id}",
                    }
                ],
            },
            "submodelElements": [
                self._convert_node_to_element(child, visited, depth=1)
                for child in root_node.children
            ],
        }

    def _convert_node_to_element(
        self,
        node: OPCUANode,
        visited: set[str] | None = None,
        depth: int = 0,
    ) -> dict:
        """
        Convert a single OPC UA node to AAS SubmodelElement.

        Args:
            node: The OPC UA node to convert
            visited: Set of already-visited node IDs for cycle detection
            depth: Current recursion depth for protection against deep attacks
        """
        if visited is None:
            visited = set()

        id_short = self._sanitize_id_short(node.browse_name)

        # Cycle detection: if we've already visited this node, return a placeholder
        if node.node_id in visited:
            logger.warning("Cycle detected at node %s, returning placeholder", node.node_id)
            return {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": "xs:string",
                "value": f"[Cycle: {node.node_id}]",
            }

        # Depth limit protection
        if depth > MAX_HIERARCHY_DEPTH:
            logger.warning(
                "Max hierarchy depth exceeded at node %s, returning placeholder",
                node.node_id,
            )
            return {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": "xs:string",
                "value": f"[Max depth exceeded: {node.node_id}]",
            }

        visited.add(node.node_id)

        if node.node_class in ("ObjectType", "Object"):
            # Convert to SubmodelElementCollection
            return {
                "idShort": id_short,
                "modelType": "SubmodelElementCollection",
                "description": [{"language": "en", "text": node.description}]
                if node.description
                else None,
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": f"urn:opcua:{node.node_id}",
                        }
                    ],
                },
                "value": [
                    self._convert_node_to_element(child, visited, depth + 1)
                    for child in node.children
                ],
            }

        elif node.node_class == "Variable":
            # Convert to Property
            aas_type = self._type_mapper.opcua_to_aas(node.data_type or "String")

            elem = {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": aas_type,
                "description": [{"language": "en", "text": node.description}]
                if node.description
                else None,
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": f"urn:opcua:{node.node_id}",
                        }
                    ],
                },
            }

            # Add value if present
            if node.value is not None:
                elem["value"] = str(node.value)

            # Handle arrays
            if node.value_rank >= 0:
                # It's an array - convert to SubmodelElementList
                return {
                    "idShort": id_short,
                    "modelType": "SubmodelElementList",
                    "typeValueListElement": "Property",
                    "valueTypeListElement": aas_type,
                    "description": [{"language": "en", "text": node.description}]
                    if node.description
                    else None,
                    "value": [],
                }

            return elem

        elif node.node_class == "Method":
            # Convert to Operation (basic placeholder)
            return {
                "idShort": id_short,
                "modelType": "Operation",
                "description": [{"language": "en", "text": node.description}]
                if node.description
                else None,
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": f"urn:opcua:{node.node_id}",
                        }
                    ],
                },
            }

        # Default: Property
        return {
            "idShort": id_short,
            "modelType": "Property",
            "valueType": "xs:string",
        }

    def _generate_ui_schema(self, root_node: OPCUANode) -> dict:
        """Generate UI schema from node hierarchy."""
        visited: set[str] = set()
        return {
            "idShort": self._sanitize_id_short(root_node.browse_name),
            "modelType": "Submodel",
            "semanticId": f"urn:opcua:{root_node.node_id}",
            "description": root_node.description or "Imported from OPC UA NodeSet",
            "elements": [
                self._convert_node_to_ui_element(child, visited, depth=1)
                for child in root_node.children
            ],
        }

    def _convert_node_to_ui_element(
        self,
        node: OPCUANode,
        visited: set[str] | None = None,
        depth: int = 0,
    ) -> dict:
        """
        Convert OPC UA node to UI schema element.

        Args:
            node: The OPC UA node to convert
            visited: Set of already-visited node IDs for cycle detection
            depth: Current recursion depth for protection against deep attacks
        """
        if visited is None:
            visited = set()

        id_short = self._sanitize_id_short(node.browse_name)

        # Cycle detection
        if node.node_id in visited:
            return {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": "xs:string",
                "cardinality": {"min": 0, "max": 1},
                "description": f"[Cycle: {node.node_id}]",
            }

        # Depth limit protection
        if depth > MAX_HIERARCHY_DEPTH:
            return {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": "xs:string",
                "cardinality": {"min": 0, "max": 1},
                "description": f"[Max depth exceeded: {node.node_id}]",
            }

        visited.add(node.node_id)

        if node.node_class in ("ObjectType", "Object"):
            return {
                "idShort": id_short,
                "modelType": "SubmodelElementCollection",
                "description": node.description,
                "cardinality": {"min": 0, "max": 1},
                "elements": [
                    self._convert_node_to_ui_element(child, visited, depth + 1)
                    for child in node.children
                ],
            }

        elif node.node_class == "Variable":
            aas_type = self._type_mapper.opcua_to_aas(node.data_type or "String")

            if node.value_rank >= 0:
                # Array
                return {
                    "idShort": id_short,
                    "modelType": "SubmodelElementList",
                    "description": node.description,
                    "cardinality": {"min": 0, "max": "*"},
                    "typeValueListElement": "Property",
                    "valueTypeListElement": aas_type,
                }

            return {
                "idShort": id_short,
                "modelType": "Property",
                "valueType": aas_type,
                "description": node.description,
                "cardinality": {"min": 0, "max": 1},
            }

        elif node.node_class == "Method":
            return {
                "idShort": id_short,
                "modelType": "Operation",
                "description": node.description,
                "cardinality": {"min": 0, "max": 1},
            }

        return {
            "idShort": id_short,
            "modelType": "Property",
            "valueType": "xs:string",
            "cardinality": {"min": 0, "max": 1},
        }

    def _sanitize_id_short(self, name: str) -> str:
        """Sanitize a name for use as idShort."""
        # Remove namespace prefix
        if ":" in name:
            name = name.split(":", 1)[1]

        # Replace invalid characters
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        # Ensure doesn't start with number
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized

        return sanitized or "Element"
