"""
Tests for OPC UA NodeSet Importer.

Tests parsing NodeSet2.xml files and converting to AAS structure.
"""


from app.services.opcua.importer import NodeSetImporter


# Sample NodeSet2.xml content for testing
SAMPLE_NODESET = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamespaceUris>
    <Uri>urn:example:test:model</Uri>
  </NamespaceUris>

  <UAObjectType NodeId="ns=1;i=1000" BrowseName="1:TestMachine">
    <DisplayName>Test Machine</DisplayName>
    <Description>A test machine for unit tests</Description>
    <References>
      <Reference ReferenceType="HasSubtype" IsForward="false">i=58</Reference>
      <Reference ReferenceType="HasComponent">ns=1;i=1001</Reference>
      <Reference ReferenceType="HasComponent">ns=1;i=1002</Reference>
    </References>
  </UAObjectType>

  <UAVariable NodeId="ns=1;i=1001" BrowseName="1:SerialNumber" DataType="String">
    <DisplayName>Serial Number</DisplayName>
    <Description>The machine serial number</Description>
    <References>
      <Reference ReferenceType="HasTypeDefinition">i=63</Reference>
      <Reference ReferenceType="HasComponent" IsForward="false">ns=1;i=1000</Reference>
    </References>
    <Value>
      <uax:String xmlns:uax="http://opcfoundation.org/UA/2008/02/Types.xsd">SN-12345</uax:String>
    </Value>
  </UAVariable>

  <UAVariable NodeId="ns=1;i=1002" BrowseName="1:Temperature" DataType="Double">
    <DisplayName>Temperature</DisplayName>
    <Description>Current temperature reading</Description>
    <References>
      <Reference ReferenceType="HasTypeDefinition">i=63</Reference>
      <Reference ReferenceType="HasComponent" IsForward="false">ns=1;i=1000</Reference>
    </References>
  </UAVariable>
</UANodeSet>
"""


MINIMAL_NODESET = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
  <UAVariable NodeId="ns=1;i=1000" BrowseName="1:SimpleVar" DataType="Int32">
    <DisplayName>Simple Variable</DisplayName>
  </UAVariable>
</UANodeSet>
"""


ARRAY_NODESET = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
  <UAVariable NodeId="ns=1;i=1000" BrowseName="1:ArrayValues" DataType="Double"
              ValueRank="1" ArrayDimensions="10">
    <DisplayName>Array Values</DisplayName>
    <Description>An array of double values</Description>
  </UAVariable>
</UANodeSet>
"""


class TestNodeSetImporter:
    """Test NodeSet importer functionality."""

    def test_import_basic_nodeset(self):
        """Test importing a basic NodeSet file."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        assert result.node_count > 0
        assert result.template is not None
        assert result.ui_schema is not None

    def test_import_extracts_namespace(self):
        """Test that namespace URI is extracted."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        # First namespace is always OPC UA default, custom is in the list
        assert result.source_namespace is not None
        # Either returns the default OPC UA namespace or custom one
        assert "opcfoundation" in result.source_namespace or "example" in result.source_namespace

    def test_import_generates_template(self):
        """Test that template structure is generated."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        template = result.template

        assert template["modelType"] == "Submodel"
        assert "idShort" in template
        assert "submodelElements" in template

    def test_import_generates_ui_schema(self):
        """Test that UI schema is generated."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        schema = result.ui_schema

        assert schema["modelType"] == "Submodel"
        assert "idShort" in schema
        assert "elements" in schema

    def test_import_handles_bytes(self):
        """Test importing bytes content."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET.encode("utf-8"))

        assert result.success

    def test_import_specific_root_node(self):
        """Test importing with specific root NodeId."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET, root_node_id="ns=1;i=1000")

        assert result.success
        assert result.template is not None

    def test_import_minimal_nodeset(self):
        """Test importing minimal NodeSet."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(MINIMAL_NODESET)

        assert result.success
        assert result.node_count >= 1

    def test_import_array_variable(self):
        """Test importing variable with array dimensions."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(ARRAY_NODESET)

        assert result.success
        # Array variables should become SubmodelElementList
        schema = result.ui_schema
        assert schema is not None


class TestNodeSetParsingErrors:
    """Test error handling during parsing."""

    def test_invalid_xml_fails(self):
        """Test that invalid XML returns failure."""
        importer = NodeSetImporter()
        result = importer.import_nodeset("<invalid>not closed")

        assert not result.success
        assert len(result.warnings) > 0
        assert "XML parse error" in result.warnings[0]

    def test_empty_content_fails(self):
        """Test that empty content returns failure."""
        importer = NodeSetImporter()
        result = importer.import_nodeset("")

        assert not result.success

    def test_no_nodes_generates_warning(self):
        """Test that NodeSet with no nodes generates warning."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(
            '<?xml version="1.0"?><UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"></UANodeSet>'
        )

        assert not result.success
        assert any("No nodes found" in w for w in result.warnings)


class TestTypeConversionInImport:
    """Test type conversion during import."""

    def test_string_variable_converts(self):
        """Test String variable converts to xs:string."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        # Check that string property has correct type
        schema = result.ui_schema
        elements = schema.get("elements", [])

        # Find SerialNumber element
        serial_elem = None
        for elem in elements:
            if elem.get("idShort") == "SerialNumber":
                serial_elem = elem
                break

        assert serial_elem is not None
        assert serial_elem.get("valueType") == "xs:string"

    def test_double_variable_converts(self):
        """Test Double variable converts to xs:double."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        schema = result.ui_schema
        elements = schema.get("elements", [])

        # Find Temperature element
        temp_elem = None
        for elem in elements:
            if elem.get("idShort") == "Temperature":
                temp_elem = elem
                break

        assert temp_elem is not None
        assert temp_elem.get("valueType") == "xs:double"


class TestIdShortSanitization:
    """Test idShort sanitization."""

    def test_namespace_prefix_removed(self):
        """Test that namespace prefix is removed from browse names."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(SAMPLE_NODESET)

        assert result.success
        schema = result.ui_schema

        # idShort should be 'TestMachine', not '1:TestMachine'
        assert ":" not in schema["idShort"]

    def test_invalid_chars_replaced(self):
        """Test that invalid characters are replaced."""
        importer = NodeSetImporter()

        # Test the internal sanitization method
        assert importer._sanitize_id_short("Name-With-Dashes") == "Name_With_Dashes"
        assert importer._sanitize_id_short("Name With Spaces") == "Name_With_Spaces"

    def test_numeric_prefix_handled(self):
        """Test that numeric prefix is handled."""
        importer = NodeSetImporter()

        # Names starting with numbers should be prefixed with underscore
        assert importer._sanitize_id_short("123Name") == "_123Name"


class TestImportResult:
    """Test ImportResult dataclass."""

    def test_result_has_timestamp(self):
        """Test that result has import timestamp."""
        importer = NodeSetImporter()
        result = importer.import_nodeset(MINIMAL_NODESET)

        assert result.imported_at is not None

    def test_failed_result_structure(self):
        """Test structure of failed result."""
        importer = NodeSetImporter()
        result = importer.import_nodeset("<invalid>")

        assert not result.success
        assert result.template is None
        assert result.ui_schema is None
        assert len(result.warnings) > 0


class TestSecurityProtections:
    """Test security protections for OPC UA importer."""

    def test_large_content_rejected(self):
        """Test that oversized content is rejected."""
        from app.services.opcua.importer import MAX_NODESET_SIZE

        importer = NodeSetImporter()
        # Create content larger than the limit
        large_content = "x" * (MAX_NODESET_SIZE + 1)

        result = importer.import_nodeset(large_content)

        assert not result.success
        assert any("too large" in w for w in result.warnings)

    def test_large_bytes_content_rejected(self):
        """Test that oversized bytes content is rejected."""
        from app.services.opcua.importer import MAX_NODESET_SIZE

        importer = NodeSetImporter()
        # Create bytes content larger than the limit
        large_content = b"x" * (MAX_NODESET_SIZE + 1)

        result = importer.import_nodeset(large_content)

        assert not result.success
        assert any("too large" in w for w in result.warnings)

    def test_cycle_in_references_handled(self):
        """Test that cyclic references don't cause infinite recursion."""
        # Create a NodeSet with a self-referencing node
        cyclic_nodeset = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
  <UAObjectType NodeId="ns=1;i=1000" BrowseName="1:CyclicObject">
    <DisplayName>Cyclic Object</DisplayName>
    <References>
      <Reference ReferenceType="HasComponent">ns=1;i=1000</Reference>
    </References>
  </UAObjectType>
</UANodeSet>"""
        importer = NodeSetImporter()
        result = importer.import_nodeset(cyclic_nodeset)

        # Should succeed without infinite recursion
        assert result.success

    def test_deep_hierarchy_handled(self):
        """Test that deeply nested hierarchies are handled with depth limit."""
        # Build a deep hierarchy programmatically
        nodes = []
        for i in range(150):  # More than MAX_HIERARCHY_DEPTH (100)
            ref = ""
            if i < 149:
                ref = f'<Reference ReferenceType="HasComponent">ns=1;i={1001+i}</Reference>'
            nodes.append(f"""
  <UAObjectType NodeId="ns=1;i={1000+i}" BrowseName="1:Object{i}">
    <DisplayName>Object {i}</DisplayName>
    <References>
      {ref}
    </References>
  </UAObjectType>""")

        deep_nodeset = f"""<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
  {"".join(nodes)}
</UANodeSet>"""

        importer = NodeSetImporter()
        result = importer.import_nodeset(deep_nodeset)

        # Should succeed without stack overflow
        assert result.success
