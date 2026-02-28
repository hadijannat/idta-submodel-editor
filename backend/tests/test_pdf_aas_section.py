"""
Tests for PDF AAS section and conformance summary functionality.

Tests the parser AAS metadata extraction, conformance summary generation,
and PDF template rendering with AAS/conformance data.
"""

from unittest.mock import MagicMock

from app.services.parser import ParserService
from app.services.pdf_conformance import (
    ConformanceCheck,
    ConformanceSummary,
    generate_conformance_summary,
)


class TestParserAASExtraction:
    """Tests for AAS metadata extraction in ParserService."""

    def test_find_aas_returns_none_for_empty_store(self):
        """Test that _find_aas returns None when no AAS exists."""
        parser = ParserService()
        mock_store = MagicMock()
        mock_store.__iter__ = MagicMock(return_value=iter([]))

        result = parser._find_aas(mock_store)
        assert result is None

    def test_find_aas_returns_first_aas(self):
        """Test that _find_aas returns the first AAS in the store."""
        from basyx.aas import model

        parser = ParserService()

        # Create a mock AAS
        mock_aas = MagicMock(spec=model.AssetAdministrationShell)

        mock_store = MagicMock()
        mock_store.__iter__ = MagicMock(return_value=iter([mock_aas]))

        result = parser._find_aas(mock_store)
        assert result is mock_aas

    def test_serialize_asset_information_none(self):
        """Test serializing None asset information."""
        parser = ParserService()
        result = parser._serialize_asset_information(None)

        assert result == {
            "assetKind": None,
            "globalAssetId": None,
            "specificAssetIds": [],
            "assetType": None,
        }

    def test_serialize_asset_information_instance(self):
        """Test serializing AssetInformation for an Instance asset."""
        from basyx.aas import model

        parser = ParserService()

        mock_asset_info = MagicMock()
        mock_asset_info.asset_kind = model.AssetKind.INSTANCE
        mock_asset_info.global_asset_id = "https://example.com/asset/123"
        mock_asset_info.specific_asset_id = []

        result = parser._serialize_asset_information(mock_asset_info)

        assert result["assetKind"] == "INSTANCE"
        assert result["globalAssetId"] == "https://example.com/asset/123"
        assert result["specificAssetIds"] == []

    def test_serialize_asset_information_type(self):
        """Test serializing AssetInformation for a Type asset."""
        from basyx.aas import model

        parser = ParserService()

        mock_asset_info = MagicMock()
        mock_asset_info.asset_kind = model.AssetKind.TYPE
        mock_asset_info.global_asset_id = None
        mock_asset_info.specific_asset_id = []

        result = parser._serialize_asset_information(mock_asset_info)

        assert result["assetKind"] == "TYPE"
        assert result["globalAssetId"] is None

    def test_serialize_specific_asset_ids_empty(self):
        """Test serializing empty specific asset IDs list."""
        parser = ParserService()
        result = parser._serialize_specific_asset_ids(None)
        assert result == []

        result = parser._serialize_specific_asset_ids([])
        assert result == []

    def test_serialize_specific_asset_ids_with_values(self):
        """Test serializing specific asset IDs with values."""
        parser = ParserService()

        mock_id = MagicMock()
        mock_id.name = "serialNumber"
        mock_id.value = "ABC123"
        mock_id.external_subject_id = None

        result = parser._serialize_specific_asset_ids([mock_id])

        assert len(result) == 1
        assert result[0]["name"] == "serialNumber"
        assert result[0]["value"] == "ABC123"
        assert "externalSubjectId" not in result[0]

    def test_serialize_specific_asset_ids_with_external_subject(self):
        """Test serializing specific asset IDs with external subject."""
        parser = ParserService()

        mock_ref = MagicMock()
        mock_ref.key = [MagicMock(value="https://example.com/subject")]

        mock_id = MagicMock()
        mock_id.name = "batchId"
        mock_id.value = "BATCH001"
        mock_id.external_subject_id = mock_ref

        result = parser._serialize_specific_asset_ids([mock_id])

        assert len(result) == 1
        assert result[0]["name"] == "batchId"
        assert result[0]["value"] == "BATCH001"
        assert result[0]["externalSubjectId"] == "https://example.com/subject"

    def test_extract_aas_metadata(self):
        """Test complete AAS metadata extraction."""
        from basyx.aas import model

        parser = ParserService()

        # Create mock AAS
        mock_asset_info = MagicMock()
        mock_asset_info.asset_kind = model.AssetKind.INSTANCE
        mock_asset_info.global_asset_id = "https://example.com/asset/123"
        mock_asset_info.specific_asset_id = []

        mock_aas = MagicMock()
        # The parser uses getattr(aas, "id_", None) or getattr(aas, "id", None)
        mock_aas.id_ = "https://example.com/aas/1"
        mock_aas.id_short = "TestAAS"
        mock_aas.asset_information = mock_asset_info
        mock_aas.submodel = []
        mock_aas.derived_from = None
        mock_aas.administration = None

        result = parser._extract_aas_metadata(mock_aas)

        assert result["id"] == "https://example.com/aas/1"
        assert result["idShort"] == "TestAAS"
        assert result["assetInformation"]["assetKind"] == "INSTANCE"
        assert result["assetInformation"]["globalAssetId"] == "https://example.com/asset/123"
        assert result["submodelRefs"] == []
        assert result["derivedFrom"] is None


class TestConformanceSummary:
    """Tests for conformance summary generation."""

    def test_conformance_summary_creation(self):
        """Test creating a ConformanceSummary."""
        summary = ConformanceSummary(
            template_name="TestTemplate",
            template_version="1.0",
        )

        assert summary.template_name == "TestTemplate"
        assert summary.template_version == "1.0"
        assert summary.metamodel_version == "IDTA Metamodel V3.0"
        assert summary.validation_status == "valid"
        assert summary.error_count == 0
        assert summary.checks == []

    def test_conformance_summary_to_dict(self):
        """Test converting ConformanceSummary to dictionary."""
        summary = ConformanceSummary(
            template_name="TestTemplate",
            template_version="1.0",
            validation_status="valid",
            error_count=0,
            warning_count=2,
            checks=[
                ConformanceCheck(
                    name="Asset Kind",
                    status="pass",
                    message="Asset kind specified: INSTANCE",
                )
            ],
        )

        result = summary.to_dict()

        assert result["templateName"] == "TestTemplate"
        assert result["templateVersion"] == "1.0"
        assert result["validationStatus"] == "valid"
        assert result["errorCount"] == 0
        assert result["warningCount"] == 2
        assert len(result["checks"]) == 1
        assert result["checks"][0]["name"] == "Asset Kind"
        assert result["checks"][0]["status"] == "pass"

    def test_generate_conformance_summary_valid(self):
        """Test generating conformance summary with no errors."""
        schema = {
            "idShort": "TestSubmodel",
            "administration": {"version": "1", "revision": "0"},
            "aas": {
                "id": "https://example.com/aas/1",
                "assetInformation": {
                    "assetKind": "INSTANCE",
                    "globalAssetId": "https://example.com/asset/1",
                    "specificAssetIds": [],
                },
                "submodelRefs": ["https://example.com/submodel/1"],
            },
        }
        form_data = {"elements": {}}

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
            errors=[],
            warnings=[],
            template_name="Test",
        )

        assert summary.validation_status == "valid"
        assert summary.template_name == "Test"
        assert any(c.name == "Asset Kind" and c.status == "pass" for c in summary.checks)

    def test_generate_conformance_summary_with_errors(self):
        """Test generating conformance summary with errors."""
        schema = {"idShort": "TestSubmodel"}
        form_data = {"elements": {}}
        errors = [MagicMock()]

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
            errors=errors,
            warnings=[],
        )

        assert summary.validation_status == "invalid"
        assert summary.error_count == 1

    def test_generate_conformance_summary_with_warnings(self):
        """Test generating conformance summary with warnings only."""
        schema = {"idShort": "TestSubmodel"}
        form_data = {"elements": {}}
        warnings = [MagicMock(), MagicMock()]

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
            errors=[],
            warnings=warnings,
        )

        assert summary.validation_status == "warnings"
        assert summary.warning_count == 2

    def test_generate_conformance_summary_no_aas(self):
        """Test conformance summary for submodel-only template."""
        schema = {
            "idShort": "TestSubmodel",
            "aas": None,
        }
        form_data = {"elements": {}}

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
        )

        # Should have info notice about no AAS wrapper
        assert any(
            c.name == "AAS Wrapper" and c.status == "info"
            for c in summary.checks
        )

    def test_generate_conformance_summary_missing_asset_kind(self):
        """Test conformance summary with missing assetKind."""
        schema = {
            "idShort": "TestSubmodel",
            "aas": {
                "id": "https://example.com/aas/1",
                "assetInformation": {
                    "assetKind": None,
                    "globalAssetId": "https://example.com/asset/1",
                },
            },
        }
        form_data = {"elements": {}}

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
        )

        # Should have fail check for missing assetKind
        assert any(
            c.name == "Asset Kind" and c.status == "fail"
            for c in summary.checks
        )

    def test_generate_conformance_summary_no_asset_id(self):
        """Test conformance summary with no asset identification."""
        schema = {
            "idShort": "TestSubmodel",
            "aas": {
                "id": "https://example.com/aas/1",
                "assetInformation": {
                    "assetKind": "INSTANCE",
                    "globalAssetId": None,
                    "specificAssetIds": [],
                },
            },
        }
        form_data = {"elements": {}}

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
        )

        # Should have warning for missing asset identification
        assert any(
            c.name == "Asset Identification" and c.status == "warning"
            for c in summary.checks
        )


class TestNameplateConformance:
    """Tests for Digital Nameplate (IDTA 02006) conformance checks."""

    def test_nameplate_required_fields_present(self):
        """Test nameplate validation with all required fields present."""
        schema = {
            "idShort": "Nameplate",
            "semanticId": "https://admin-shell.io/idta/Submodel/Nameplate/2/0",
        }
        form_data = {
            "elements": {
                "URIOfTheProduct": {"value": "https://example.com/product/1"},
                "ManufacturerName": {"value": {"en": "Test Manufacturer"}},
                "ManufacturerProductDesignation": {"value": {"en": "Test Product"}},
            }
        }

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
        )

        # All required fields should pass
        nameplate_checks = [c for c in summary.checks if "IDTA 02006" in c.name]
        assert all(c.status == "pass" for c in nameplate_checks)

    def test_nameplate_missing_required_field(self):
        """Test nameplate validation with missing required field."""
        schema = {
            "idShort": "Nameplate",
            "semanticId": "https://admin-shell.io/idta/Submodel/Nameplate/2/0",
        }
        form_data = {
            "elements": {
                "URIOfTheProduct": {"value": "https://example.com/product/1"},
                # ManufacturerName missing
                "ManufacturerProductDesignation": {"value": {"en": "Test Product"}},
            }
        }

        summary = generate_conformance_summary(
            schema=schema,
            form_data=form_data,
        )

        # ManufacturerName check should fail
        assert any(
            "Manufacturer Name" in c.name and c.status == "fail"
            for c in summary.checks
        )


class TestPDFTemplateRendering:
    """Tests for PDF template rendering with AAS data."""

    def test_aas_section_renders_with_data(self):
        """Test that AAS section renders when aas data is present."""
        import os
        from jinja2 import Environment, FileSystemLoader

        # Get the correct template path relative to backend directory
        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "templates",
        )
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("pdf_report.html")

        submodel_data = {
            "idShort": "TestSubmodel",
            "submodelId": "https://example.com/submodel/1",
            "aas": {
                "id": "https://example.com/aas/1",
                "idShort": "TestAAS",
                "assetInformation": {
                    "assetKind": "INSTANCE",
                    "globalAssetId": "https://example.com/asset/1",
                    "specificAssetIds": [
                        {"name": "serialNumber", "value": "SN12345"}
                    ],
                    "assetType": None,
                },
                "submodelRefs": ["https://example.com/submodel/1"],
                "derivedFrom": None,
                "administration": {"version": "1", "revision": "0"},
            },
        }

        html = template.render(
            submodel=submodel_data,
            elements=[],
        )

        # Check that AAS section is rendered
        assert "Asset Administration Shell" in html
        assert "https://example.com/aas/1" in html
        assert "INSTANCE" in html
        assert "https://example.com/asset/1" in html
        assert "serialNumber" in html
        assert "SN12345" in html

    def test_aas_section_missing_notice(self):
        """Test that notice renders when no AAS is present."""
        import os
        from jinja2 import Environment, FileSystemLoader

        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "templates",
        )
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("pdf_report.html")

        submodel_data = {
            "idShort": "TestSubmodel",
            "submodelId": "https://example.com/submodel/1",
            "aas": None,
        }

        html = template.render(
            submodel=submodel_data,
            elements=[],
        )

        # Check that notice is rendered
        assert "No Asset Administration Shell" in html
        assert "Submodel data" in html

    def test_conformance_section_renders(self):
        """Test that conformance summary section renders."""
        import os
        from jinja2 import Environment, FileSystemLoader

        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "templates",
        )
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("pdf_report.html")

        submodel_data = {
            "idShort": "TestSubmodel",
            "submodelId": "https://example.com/submodel/1",
            "aas": None,
        }

        conformance_data = {
            "templateName": "TestTemplate",
            "templateVersion": "1.0",
            "metamodelVersion": "IDTA Metamodel V3.0",
            "validationStatus": "valid",
            "errorCount": 0,
            "warningCount": 0,
            "checks": [
                {
                    "name": "Asset Kind",
                    "status": "pass",
                    "message": "Asset kind specified: INSTANCE",
                }
            ],
        }

        html = template.render(
            submodel=submodel_data,
            elements=[],
            conformance=conformance_data,
        )

        # Check that conformance section is rendered
        assert "Conformance Summary" in html
        assert "TestTemplate" in html
        assert "IDTA Metamodel V3.0" in html
        assert "Asset Kind" in html

    def test_conformance_section_hidden_when_none(self):
        """Test that conformance section is hidden when data is None."""
        import os
        from jinja2 import Environment, FileSystemLoader

        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "templates",
        )
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("pdf_report.html")

        submodel_data = {
            "idShort": "TestSubmodel",
            "submodelId": "https://example.com/submodel/1",
            "aas": None,
        }

        html = template.render(
            submodel=submodel_data,
            elements=[],
            conformance=None,
        )

        # Check that conformance section content is NOT rendered
        # (CSS class names will still be in the styles, so check for actual content)
        assert "conformance-header\">Conformance Summary</div>" not in html
        assert "Compliance Checks" not in html
