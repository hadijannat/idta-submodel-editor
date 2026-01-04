"""
Hydrator Service for UI-to-AAS reconstitution.

Merges user-provided form values into complete AAS structures while
preserving all metadata (Qualifiers, EmbeddedDataSpecifications) that
the UI didn't render.
"""

import copy
import logging
from io import BytesIO
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import aasx, json as aas_json

from app.utils.aasx_reader import SafeAASXReader

logger = logging.getLogger(__name__)


class HydratorService:
    """
    Service for hydrating AAS templates with form data.

    The hydration process:
    1. Load the original template AASX
    2. Walk the element tree and merge form values
    3. Preserve all metadata not rendered in the UI
    4. Return complete, valid AASX output
    """

    def hydrate_submodel(
        self,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
    ) -> bytes:
        """
        Hydrate a submodel template with form data.

        Args:
            template_aasx_bytes: Original template AASX as bytes
            form_data: Form data with structure matching UI schema

        Returns:
            Hydrated AASX file as bytes
        """
        object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        file_store = aasx.DictSupplementaryFileContainer()

        # Load the template
        with SafeAASXReader(BytesIO(template_aasx_bytes)) as reader:
            reader.read_into(object_store, file_store)

        # Find the submodel
        submodel = self._find_submodel(object_store)
        if not submodel:
            raise ValueError("No Submodel found in template")

        logger.info(f"Hydrating submodel: {submodel.id_short}")

        # Hydrate the submodel elements
        elements_data = form_data.get("elements", {})
        self._hydrate_elements(submodel.submodel_element, elements_data)

        # Write back to AASX
        output = BytesIO()
        with aasx.AASXWriter(output) as writer:
            aas_ids = [
                obj.id for obj in object_store if isinstance(obj, model.AssetAdministrationShell)
            ]
            if aas_ids:
                writer.write_aas(
                    aas_ids=aas_ids,
                    object_store=object_store,
                    file_store=file_store,
                    write_json=False,
                )
            else:
                writer.write_all_aas_objects(
                    "/aasx/data.xml",
                    object_store,
                    file_store,
                    write_json=False,
                )

        return output.getvalue()

    def hydrate_to_json(
        self,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
    ) -> str:
        """
        Hydrate a submodel and return as JSON.

        Args:
            template_aasx_bytes: Original template AASX as bytes
            form_data: Form data with structure matching UI schema

        Returns:
            Hydrated submodel as JSON string
        """
        object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        file_store = aasx.DictSupplementaryFileContainer()

        with SafeAASXReader(BytesIO(template_aasx_bytes)) as reader:
            reader.read_into(object_store, file_store)

        submodel = self._find_submodel(object_store)
        if not submodel:
            raise ValueError("No Submodel found in template")

        elements_data = form_data.get("elements", {})
        self._hydrate_elements(submodel.submodel_element, elements_data)

        # Serialize to JSON
        output = BytesIO()
        aas_json.write_aas_json_file(output, object_store)
        return output.getvalue().decode("utf-8")

    def _find_submodel(
        self, object_store: model.DictObjectStore
    ) -> model.Submodel | None:
        """Find the first Submodel in the object store."""
        for obj in object_store:
            if isinstance(obj, model.Submodel):
                return obj
        return None

    def _hydrate_elements(
        self,
        elements,
        form_values: dict[str, Any],
    ) -> None:
        """
        Recursively hydrate SubmodelElements with form values.

        Modifies elements in-place while preserving metadata.
        """
        for element in elements:
            id_short = element.id_short
            if id_short not in form_values:
                continue

            value_data = form_values[id_short]
            self._hydrate_single_element(element, value_data)

    def _hydrate_single_element(
        self,
        element: model.SubmodelElement,
        value_data: dict[str, Any],
    ) -> None:
        """
        Hydrate a single element with its form data.

        Handles each element type appropriately.
        """
        if isinstance(element, model.Property):
            self._hydrate_property(element, value_data)

        elif isinstance(element, model.MultiLanguageProperty):
            self._hydrate_multilang(element, value_data)

        elif isinstance(element, model.SubmodelElementCollection):
            self._hydrate_collection(element, value_data)

        elif isinstance(element, model.SubmodelElementList):
            self._hydrate_list(element, value_data)

        elif isinstance(element, model.File):
            self._hydrate_file(element, value_data)

        elif isinstance(element, model.Blob):
            self._hydrate_blob(element, value_data)

        elif isinstance(element, model.Range):
            self._hydrate_range(element, value_data)

        elif isinstance(element, model.ReferenceElement):
            self._hydrate_reference(element, value_data)

        elif isinstance(element, model.Entity):
            self._hydrate_entity(element, value_data)

        elif isinstance(element, model.RelationshipElement):
            self._hydrate_relationship(element, value_data)

        elif isinstance(element, model.AnnotatedRelationshipElement):
            self._hydrate_annotated_relationship(element, value_data)

    def _hydrate_property(
        self,
        element: model.Property,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a Property element."""
        if "value" in value_data:
            element.value = self._coerce_value(value_data["value"], element.value_type)

    def _hydrate_multilang(
        self,
        element: model.MultiLanguageProperty,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a MultiLanguageProperty element."""
        if "value" in value_data and isinstance(value_data["value"], dict):
            # Filter out empty values
            filtered_values = {
                k: v
                for k, v in value_data["value"].items()
                if v is not None and str(v).strip()
            }
            if filtered_values:
                element.value = model.MultiLanguageTextType(filtered_values)

    def _hydrate_collection(
        self,
        element: model.SubmodelElementCollection,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a SubmodelElementCollection element."""
        if "elements" in value_data:
            self._hydrate_elements(element.value, value_data["elements"])

    def _hydrate_list(
        self,
        element: model.SubmodelElementList,
        value_data: dict[str, Any],
    ) -> None:
        """
        Hydrate a SubmodelElementList element.

        Handles dynamic add/remove of list items.
        """
        if "items" not in value_data:
            return

        items_data = value_data["items"]
        if not isinstance(items_data, list):
            return

        existing_items = list(element.value)

        # If we have a template, use it for new items
        template_item = existing_items[0] if existing_items else None

        # Clear and rebuild the list
        element.value.clear()

        for idx, item_data in enumerate(items_data):
            if idx < len(existing_items):
                # Update existing item
                item = existing_items[idx]
                self._hydrate_single_element(item, item_data)
                self._ensure_list_item_id_short(item)
                element.value.add(item)
            else:
                # Clone template for new item or create from list type
                if template_item:
                    new_item = self._clone_element(template_item)
                    self._ensure_list_item_id_short(new_item)
                else:
                    new_item = self._create_list_item(element, idx)

                if new_item is None:
                    continue

                self._hydrate_single_element(new_item, item_data)
                self._ensure_list_item_id_short(new_item)
                element.value.add(new_item)

    def _create_list_item(
        self,
        list_element: model.SubmodelElementList,
        idx: int,
    ) -> model.SubmodelElement | None:
        """
        Create a list item when the template list is empty.

        Falls back to minimal constructors based on the list element type.
        """
        element_type = list_element.type_value_list_element
        if element_type is None:
            return None

        value_type = list_element.value_type_list_element or model.datatypes.String

        try:
            if issubclass(element_type, model.Property):
                return element_type(id_short=None, value_type=value_type)

            if issubclass(element_type, model.Range):
                return element_type(id_short=None, value_type=value_type)

            if issubclass(element_type, model.MultiLanguageProperty):
                return element_type(id_short=None, value={})

            if issubclass(element_type, model.SubmodelElementCollection):
                return element_type(id_short=None, value=())

            if issubclass(element_type, model.SubmodelElementList):
                return element_type(
                    id_short=None,
                    type_value_list_element=model.Property,
                    value_type_list_element=model.datatypes.String,
                    value=(),
                )

            if issubclass(element_type, model.File):
                return element_type(
                    id_short=None,
                    content_type="application/octet-stream",
                    value=None,
                )

            if issubclass(element_type, model.Blob):
                return element_type(
                    id_short=None,
                    content_type="application/octet-stream",
                    value=None,
                )

            if issubclass(element_type, model.ReferenceElement):
                return element_type(id_short=None, value=None)

            if issubclass(element_type, model.Entity):
                return element_type(
                    id_short=None,
                    entity_type=model.EntityType.CO_MANAGED_ENTITY,
                    statement=(),
                )

            if issubclass(element_type, model.AnnotatedRelationshipElement):
                placeholder = self._external_reference("urn:placeholder")
                return element_type(
                    id_short=None,
                    first=placeholder,
                    second=placeholder,
                    annotation=(),
                )

            if issubclass(element_type, model.RelationshipElement):
                placeholder = self._external_reference("urn:placeholder")
                return element_type(
                    id_short=None,
                    first=placeholder,
                    second=placeholder,
                )
        except Exception:
            return None

        return None

    def _hydrate_file(
        self,
        element: model.File,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a File element."""
        if "value" in value_data:
            element.value = value_data["value"]
        if "contentType" in value_data:
            element.content_type = value_data["contentType"]

    def _hydrate_blob(
        self,
        element: model.Blob,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a Blob element."""
        if "value" in value_data and value_data["value"]:
            element.value = value_data["value"].encode("utf-8")
        if "contentType" in value_data:
            element.content_type = value_data["contentType"]

    def _hydrate_range(
        self,
        element: model.Range,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a Range element."""
        if "min" in value_data:
            element.min = self._coerce_value(value_data["min"], element.value_type)
        if "max" in value_data:
            element.max = self._coerce_value(value_data["max"], element.value_type)

    def _hydrate_reference(
        self,
        element: model.ReferenceElement,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a ReferenceElement."""
        if "value" in value_data and value_data["value"]:
            ref_value = value_data["value"]
            element.value = self._build_reference(ref_value, element.value)

    def _hydrate_entity(
        self,
        element: model.Entity,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate an Entity element."""
        if "globalAssetId" in value_data:
            element.global_asset_id = value_data["globalAssetId"]
        if "statements" in value_data:
            self._hydrate_elements(element.statement, value_data["statements"])

    def _hydrate_relationship(
        self,
        element: model.RelationshipElement,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate a RelationshipElement."""
        if "first" in value_data and value_data["first"]:
            element.first = self._build_reference(value_data["first"], element.first)
        if "second" in value_data and value_data["second"]:
            element.second = self._build_reference(value_data["second"], element.second)

    def _hydrate_annotated_relationship(
        self,
        element: model.AnnotatedRelationshipElement,
        value_data: dict[str, Any],
    ) -> None:
        """Hydrate an AnnotatedRelationshipElement."""
        self._hydrate_relationship(element, value_data)
        if "annotations" in value_data and element.annotation:
            for idx, annot_data in enumerate(value_data["annotations"]):
                if idx < len(element.annotation):
                    self._hydrate_single_element(
                        list(element.annotation)[idx], annot_data
                    )

    def _coerce_value(self, value: Any, value_type) -> Any:
        """
        Coerce a value to the appropriate Python type based on XSD type.

        Args:
            value: The value to coerce
            value_type: The XSD value type

        Returns:
            Coerced value
        """
        if value is None or value == "":
            return None

        type_str = str(value_type).lower() if value_type else "xs:string"

        try:
            if "int" in type_str or "integer" in type_str:
                return int(float(value))  # Handle "123.0" -> 123
            elif any(t in type_str for t in ["float", "double", "decimal"]):
                return float(value)
            elif "bool" in type_str:
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ("true", "1", "yes")
            elif "datetime" in type_str:
                from datetime import datetime

                if isinstance(value, datetime):
                    return value
                return datetime.fromisoformat(str(value))
            elif type_str.endswith("date") or "date" in type_str:
                from datetime import date

                if isinstance(value, date):
                    return value
                return date.fromisoformat(str(value))
            elif "time" in type_str:
                from datetime import time

                if isinstance(value, time):
                    return value
                return time.fromisoformat(str(value))
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)

    def _external_reference(self, value: str) -> model.ExternalReference:
        """Create an ExternalReference from a string value."""
        return model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),),
        )

    def _build_reference(
        self,
        value: str,
        existing: model.Reference | None,
    ) -> model.Reference:
        """Create a reference, preserving type when possible."""
        if isinstance(existing, model.ModelReference):
            keys = list(existing.key or ())
            if not keys:
                return self._external_reference(value)
            keys[-1] = model.Key(keys[-1].type, value)
            existing_type = (
                getattr(existing, "type_", None)
                or getattr(existing, "type", None)
                or model.Referable
            )
            return model.ModelReference(
                key=tuple(keys),
                type_=existing_type,
                referred_semantic_id=getattr(existing, "referred_semantic_id", None),
            )
        if isinstance(existing, model.ExternalReference):
            keys = list(existing.key or ())
            if not keys:
                return self._external_reference(value)
            keys[-1] = model.Key(keys[-1].type, value)
            return model.ExternalReference(
                key=tuple(keys),
                referred_semantic_id=existing.referred_semantic_id,
            )
        return self._external_reference(value)

    def _ensure_list_item_id_short(self, item: model.SubmodelElement) -> None:
        """Ensure list items comply with AASd-120 (no idShort)."""
        if hasattr(item, "id_short") and item.id_short is not None:
            item.id_short = None

    def _clone_element(self, element: model.SubmodelElement) -> model.SubmodelElement:
        """
        Create a deep copy of a SubmodelElement.

        Uses copy.deepcopy but handles special cases.
        """
        return copy.deepcopy(element)


class PDFExportService:
    """
    Service for exporting submodel data to PDF.

    Uses WeasyPrint to render Jinja2 templates to PDF.
    """

    def __init__(self, template_dir: str = "app/templates"):
        self.template_dir = template_dir

    def generate_pdf(
        self,
        submodel_data: dict[str, Any],
        template_name: str = "pdf_report.html",
    ) -> bytes:
        """
        Generate PDF from submodel data.

        Args:
            submodel_data: Parsed submodel UI schema
            template_name: Jinja2 template file name

        Returns:
            PDF file as bytes
        """
        try:
            from jinja2 import Environment, FileSystemLoader
            from weasyprint import HTML, pdf as weasy_pdf
            import inspect
            import pydyf
        except ImportError:
            raise ImportError(
                "PDF export requires weasyprint and jinja2. "
                "Install with: pip install weasyprint jinja2"
            )

        # WeasyPrint expects pydyf.PDF to accept (version, identifier).
        # Some pydyf versions expose a no-arg __init__, so add a thin shim.
        if not inspect.signature(pydyf.PDF).parameters:
            class _CompatPDF(pydyf.PDF):
                def __init__(self, *args, **kwargs):
                    super().__init__()
                    version = args[0] if len(args) > 0 else None
                    if version is None:
                        version = b"1.7"
                    elif isinstance(version, str):
                        version = version.encode()
                    self.version = version
                    self.identifier = args[1] if len(args) > 1 else None

            weasy_pdf.pydyf.PDF = _CompatPDF

        # Load and render template
        env = Environment(loader=FileSystemLoader(self.template_dir))
        template = env.get_template(template_name)
        html_content = template.render(
            submodel=submodel_data,
            elements=submodel_data.get("elements", []),
        )

        # Convert to PDF
        html = HTML(string=html_content)
        return html.write_pdf()

    def generate_pdf_from_form(
        self,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
        template_name: str = "pdf_report.html",
    ) -> bytes:
        """
        Generate PDF from form data.

        Hydrates the template and then generates PDF.
        """
        from app.services.parser import ParserService

        # First hydrate, then parse for display
        hydrator = HydratorService()
        hydrated = hydrator.hydrate_submodel(template_aasx_bytes, form_data)

        parser = ParserService()
        parsed = parser.parse_aasx_to_ui_schema(hydrated)

        return self.generate_pdf(parsed, template_name)
