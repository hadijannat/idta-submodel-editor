"""
Parser Service for AAS-to-UI schema transformation.

Transforms AAS Submodel structures into UI-neutral JSON schema
that the frontend can render without knowledge of AAS specifics.
"""

import logging
from io import BytesIO
from typing import Any, Protocol

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.utils.semantic_resolver import (
    get_description_text,
    get_unit_from_concept_description,
    resolve_semantic_label,
    resolve_semantic_description,
)
from app.utils.aasx_reader import SafeAASXReader
from app.utils.xsd_mapping import (
    get_input_type,
    get_range_constraints,
    get_step_attribute,
)

logger = logging.getLogger(__name__)

try:  # Keep compatibility with basyx versions that moved/renamed OperationVariable.
    OperationVariableType = model.OperationVariable  # type: ignore[attr-defined]
except AttributeError:
    class OperationVariableType(Protocol):
        value: model.SubmodelElement


class ParserService:
    """
    Service for parsing AASX files into UI-renderable schemas.

    Transforms BaSyx model objects into JSON structures that describe
    how to render form fields, including:
    - Element types and nesting
    - Value constraints and validation rules
    - Semantic labels from ConceptDescriptions
    - Cardinality from Qualifiers
    """

    def parse_aasx_to_ui_schema(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Parse AASX file and generate UI schema.

        Args:
            aasx_bytes: AASX file contents as bytes

        Returns:
            UI schema dictionary suitable for frontend rendering
        """
        object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        file_store = aasx.DictSupplementaryFileContainer()

        with SafeAASXReader(BytesIO(aasx_bytes)) as reader:
            reader.read_into(object_store, file_store)

        # Find the submodel
        submodel = self._find_submodel(object_store)
        if not submodel:
            raise ValueError("No Submodel found in AASX file")

        submodel_id = getattr(submodel, "id_", None) or getattr(submodel, "id", None)
        logger.info(f"Parsing submodel: {submodel.id_short} ({submodel_id})")

        return {
            "submodelId": submodel_id,
            "idShort": submodel.id_short,
            "semanticId": self._serialize_reference(submodel.semantic_id),
            "description": dict(submodel.description) if submodel.description else None,
            "administration": self._serialize_administration(submodel.administration),
            "elements": [
                self._element_to_schema(e, object_store)
                for e in submodel.submodel_element
            ],
            "supplementaryFiles": list(file_store),
        }

    def _find_submodel(
        self, object_store: model.DictObjectStore
    ) -> model.Submodel | None:
        """Find the first Submodel in the object store."""
        for obj in object_store:
            if isinstance(obj, model.Submodel):
                return obj
        return None

    def _element_to_schema(
        self,
        element: model.SubmodelElement,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """
        Convert a SubmodelElement to UI schema.

        Recursively processes nested elements (SMC, SML, Entity).
        """
        # Base schema applicable to all element types
        description = dict(element.description) if element.description else None
        if not description:
            semantic_description = resolve_semantic_description(element, object_store)
            if semantic_description:
                description = semantic_description

        base_schema: dict[str, Any] = {
            "idShort": element.id_short,
            "modelType": type(element).__name__,
            "semanticId": self._serialize_reference(
                getattr(element, "semantic_id", None)
            ),
            "semanticLabel": resolve_semantic_label(element, object_store),
            "description": (
                description
            ),
            "qualifiers": self._serialize_qualifiers(element),
            "cardinality": self._extract_cardinality(element),
            "category": getattr(element, "category", None),
        }

        # Type-specific schema extensions
        if isinstance(element, model.Property):
            base_schema.update(self._property_schema(element, object_store))

        elif isinstance(element, model.SubmodelElementCollection):
            base_schema.update(self._collection_schema(element, object_store))

        elif isinstance(element, model.SubmodelElementList):
            base_schema.update(self._list_schema(element, object_store))

        elif isinstance(element, model.MultiLanguageProperty):
            base_schema.update(self._multilang_schema(element))

        elif isinstance(element, model.File):
            base_schema.update(self._file_schema(element))

        elif isinstance(element, model.Blob):
            base_schema.update(self._blob_schema(element))

        elif isinstance(element, model.Range):
            base_schema.update(self._range_schema(element, object_store))

        elif isinstance(element, model.ReferenceElement):
            base_schema.update(self._reference_schema(element))

        elif isinstance(element, model.Entity):
            base_schema.update(self._entity_schema(element, object_store))

        elif isinstance(element, model.RelationshipElement):
            base_schema.update(self._relationship_schema(element))

        elif isinstance(element, model.AnnotatedRelationshipElement):
            base_schema.update(self._annotated_relationship_schema(element, object_store))

        elif isinstance(element, model.Operation):
            base_schema.update(self._operation_schema(element, object_store))

        elif isinstance(element, model.Capability):
            base_schema.update(self._capability_schema(element))

        elif isinstance(element, model.BasicEventElement):
            base_schema.update(self._event_schema(element))

        return base_schema

    def _property_schema(
        self,
        element: model.Property,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for Property element."""
        value_type = str(element.value_type) if element.value_type else "xs:string"
        return {
            "valueType": value_type,
            "value": element.value,
            "inputType": get_input_type(value_type),
            "step": get_step_attribute(value_type),
            "constraints": get_range_constraints(value_type),
            "unit": get_unit_from_concept_description(element, object_store),
            "valueId": self._serialize_reference(element.value_id),
        }

    def _collection_schema(
        self,
        element: model.SubmodelElementCollection,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for SubmodelElementCollection."""
        return {
            "elements": [
                self._element_to_schema(e, object_store) for e in element.value
            ],
        }

    def _list_schema(
        self,
        element: model.SubmodelElementList,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for SubmodelElementList."""
        schema: dict[str, Any] = {
            "typeValueListElement": (
                type(element.type_value_list_element).__name__
                if element.type_value_list_element
                else None
            ),
            "orderRelevant": element.order_relevant,
            "valueTypeListElement": (
                str(element.value_type_list_element)
                if element.value_type_list_element
                else None
            ),
            "semanticIdListElement": self._serialize_reference(
                element.semantic_id_list_element
            ),
            "items": [self._element_to_schema(e, object_store) for e in element.value],
        }

        # Create item template from first item or type specification
        if element.value:
            schema["itemTemplate"] = self._element_to_schema(
                element.value[0], object_store
            )
        elif element.type_value_list_element:
            schema["itemTemplate"] = self._create_template_from_type(
                element.type_value_list_element,
                element.value_type_list_element,
            )

        return schema

    def _multilang_schema(self, element: model.MultiLanguageProperty) -> dict[str, Any]:
        """Generate schema for MultiLanguageProperty."""
        return {
            "value": dict(element.value) if element.value else {},
            "supportedLanguages": ["en", "de", "fr", "es", "it", "zh", "ja", "ko", "pt"],
            "valueId": self._serialize_reference(element.value_id),
        }

    def _file_schema(self, element: model.File) -> dict[str, Any]:
        """Generate schema for File element."""
        return {
            "contentType": element.content_type,
            "value": element.value,
        }

    def _blob_schema(self, element: model.Blob) -> dict[str, Any]:
        """Generate schema for Blob element."""
        return {
            "contentType": element.content_type,
            "value": element.value.decode("utf-8") if element.value else None,
        }

    def _range_schema(
        self,
        element: model.Range,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for Range element."""
        value_type = str(element.value_type) if element.value_type else "xs:double"
        return {
            "valueType": value_type,
            "min": element.min,
            "max": element.max,
            "inputType": get_input_type(value_type),
            "step": get_step_attribute(value_type),
            "unit": get_unit_from_concept_description(element, object_store),
        }

    def _reference_schema(self, element: model.ReferenceElement) -> dict[str, Any]:
        """Generate schema for ReferenceElement."""
        return {
            "value": self._serialize_reference(element.value),
        }

    def _entity_schema(
        self,
        element: model.Entity,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for Entity element."""
        return {
            "entityType": str(element.entity_type),
            "globalAssetId": element.global_asset_id,
            "specificAssetIds": (
                [
                    {"name": aid.name, "value": aid.value}
                    for aid in element.specific_asset_id
                ]
                if element.specific_asset_id
                else []
            ),
            "statements": [
                self._element_to_schema(e, object_store) for e in element.statement
            ],
        }

    def _relationship_schema(
        self, element: model.RelationshipElement
    ) -> dict[str, Any]:
        """Generate schema for RelationshipElement."""
        return {
            "first": self._serialize_reference(element.first),
            "second": self._serialize_reference(element.second),
        }

    def _annotated_relationship_schema(
        self,
        element: model.AnnotatedRelationshipElement,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for AnnotatedRelationshipElement."""
        schema = self._relationship_schema(element)
        schema["annotations"] = [
            self._element_to_schema(e, object_store) for e in element.annotation or []
        ]
        return schema

    def _operation_schema(
        self,
        element: model.Operation,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any]:
        """Generate schema for Operation element."""
        return {
            "inputVariables": [
                schema
                for v in (element.input_variable or [])
                if (schema := self._operation_variable_schema(v, object_store)) is not None
            ],
            "outputVariables": [
                schema
                for v in (element.output_variable or [])
                if (schema := self._operation_variable_schema(v, object_store)) is not None
            ],
            "inoutputVariables": [
                schema
                for v in (element.in_output_variable or [])
                if (schema := self._operation_variable_schema(v, object_store)) is not None
            ],
        }

    def _operation_variable_schema(
        self,
        variable: OperationVariableType | model.SubmodelElement,
        object_store: model.DictObjectStore,
    ) -> dict[str, Any] | None:
        """Generate schema for Operation variable."""
        if hasattr(variable, "value"):
            value = getattr(variable, "value", None)
            if value is None:
                logger.warning("Skipping operation variable without value")
                return None
            if not isinstance(value, model.SubmodelElement):
                logger.warning(
                    "Skipping operation variable with non-element value: %s",
                    type(value).__name__,
                )
                return None
            return self._element_to_schema(value, object_store)  # type: ignore[arg-type]
        if not isinstance(variable, model.SubmodelElement):
            logger.warning(
                "Skipping operation variable that is not a submodel element: %s",
                type(variable).__name__,
            )
            return None
        return self._element_to_schema(variable, object_store)

    def _capability_schema(self, element: model.Capability) -> dict[str, Any]:
        """Generate schema for Capability element."""
        return {}  # Capability has no additional properties beyond base

    def _event_schema(self, element: model.BasicEventElement) -> dict[str, Any]:
        """Generate schema for BasicEventElement."""
        return {
            "observed": self._serialize_reference(element.observed),
            "direction": str(element.direction),
            "state": str(element.state),
            "messageTopic": element.message_topic,
            "messageBroker": self._serialize_reference(element.message_broker),
            "lastUpdate": element.last_update,
            "minInterval": element.min_interval,
            "maxInterval": element.max_interval,
        }

    def _extract_cardinality(self, element: model.SubmodelElement) -> str:
        """
        Extract cardinality constraint from Qualifiers.

        Common cardinality values:
        - [0..1]: Optional, at most one
        - [1]: Mandatory, exactly one
        - [0..*]: Optional, any number
        - [1..*]: Mandatory, at least one
        """
        for q in getattr(element, "qualifier", []) or []:
            q_type = getattr(q, "type_", None) or getattr(q, "type", None)
            if q_type in (
                "Multiplicity",
                "cardinality",
                "Cardinality",
                "SMT/Cardinality",
            ):
                normalized = self._normalize_cardinality_value(q.value)
                if normalized:
                    return normalized
        return "[1]"  # Default to mandatory

    @staticmethod
    def _normalize_cardinality_value(value: str | None) -> str | None:
        """Normalize common cardinality encodings to bracket format."""
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None

        mapping = {
            "ZeroToOne": "[0..1]",
            "ZeroToMany": "[0..*]",
            "OneToMany": "[1..*]",
            "One": "[1]",
            "Zero": "[0]",
        }
        if value in mapping:
            return mapping[value]

        if value.startswith("[") and value.endswith("]"):
            return value

        if ".." in value:
            return f"[{value}]"

        if value.isdigit():
            return f"[{value}]"

        return value

    def _serialize_qualifiers(
        self, element: model.SubmodelElement
    ) -> list[dict[str, Any]]:
        """Serialize all qualifiers on an element."""
        qualifiers = []
        for q in getattr(element, "qualifier", []) or []:
            qualifiers.append(
                {
                    "type": getattr(q, "type_", None) or getattr(q, "type", None),
                    "value": q.value,
                    "valueType": str(q.value_type) if q.value_type else None,
                    "semanticId": self._serialize_reference(
                        getattr(q, "semantic_id", None)
                    ),
                    "kind": str(q.kind) if hasattr(q, "kind") and q.kind else None,
                }
            )
        return qualifiers

    def _serialize_reference(self, ref) -> str | None:
        """Serialize a Reference to a string representation."""
        if ref is None:
            return None
        if hasattr(ref, "key") and ref.key:
            # Return the first key's value (typically the identifier)
            return ref.key[0].value
        return str(ref)

    def _serialize_administration(
        self, admin: model.AdministrativeInformation | None
    ) -> dict[str, Any] | None:
        """Serialize AdministrativeInformation."""
        if admin is None:
            return None
        return {
            "version": admin.version,
            "revision": admin.revision,
            "creator": self._serialize_reference(admin.creator),
            "templateId": admin.template_id,
        }

    def _create_template_from_type(
        self, element_type: type, value_type=None
    ) -> dict[str, Any]:
        """
        Create a template schema from a type specification.

        Used when SubmodelElementList has no items but specifies the type.
        """
        type_name = element_type.__name__ if hasattr(element_type, "__name__") else str(element_type)

        template: dict[str, Any] = {
            "idShort": "",
            "modelType": type_name,
            "semanticId": None,
            "semanticLabel": None,
            "description": None,
            "qualifiers": [],
            "cardinality": "[1]",
        }

        if type_name == "Property" and value_type:
            value_type_str = str(value_type)
            template.update(
                {
                    "valueType": value_type_str,
                    "value": None,
                    "inputType": get_input_type(value_type_str),
                }
            )
        elif type_name == "SubmodelElementCollection":
            template["elements"] = []
        elif type_name == "MultiLanguageProperty":
            template.update(
                {
                    "value": {},
                    "supportedLanguages": ["en", "de", "fr", "es", "it"],
                }
            )

        return template


def iterate_elements(
    elements, depth: int = 0
) -> list[tuple[model.SubmodelElement, int]]:
    """
    Recursively iterate through all SubmodelElements.

    Yields tuples of (element, depth) for each element.
    """
    result = []
    for element in elements:
        result.append((element, depth))
        if isinstance(element, model.SubmodelElementCollection):
            result.extend(iterate_elements(element.value, depth + 1))
        elif isinstance(element, model.SubmodelElementList):
            result.extend(iterate_elements(element.value, depth + 1))
        elif isinstance(element, model.Entity):
            result.extend(iterate_elements(element.statement, depth + 1))
    return result
