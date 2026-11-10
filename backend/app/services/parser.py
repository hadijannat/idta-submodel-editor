# Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
# SPDX-License-Identifier: MIT
"""
Parser Service for AAS-to-UI schema transformation.

Transforms AAS Submodel structures into UI-neutral JSON schema
that the frontend can render without knowledge of AAS specifics.
"""

import logging
import base64
import re
from io import BytesIO
from typing import Any, Protocol

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.format_rules import (
    detect_format_hint,
    find_irdi_enumeration,
    find_referenced_standards,
)
from app.services.template_constraints import (
    extract_constraints,
    normalize_cardinality,
    qualifier_family,
)
from app.utils.semantic_resolver import (
    _resolve_concept_description,
    get_unit_from_concept_description,
    resolve_semantic_label,
    resolve_semantic_description,
)
from app.utils.semantic_index import SemanticIndex
from app.utils.aasx_reader import SafeAASXReader
from app.utils.xsd_mapping import (
    get_input_type,
    get_range_constraints,
    get_step_attribute,
)

logger = logging.getLogger(__name__)

# BaSyx assigns placeholder idShorts to SubmodelElementList children, which
# have none in the AAS metamodel. The placeholder embeds an object id that
# changes on every parse, so it must not leak into the UI schema.
_GENERATED_ID_SHORT_PREFIX = "generated_submodel_list_hack_"

_COUNTER_SUFFIX_RE = re.compile(r"(__\d+__|\{\d+\}|__\d+)$")


def xsd_type_name(value_type: Any) -> str | None:
    """Return the XSD name (``xs:string``) for a BaSyx value type class."""
    if value_type is None:
        return None
    if isinstance(value_type, str):
        return value_type
    name = model.datatypes.XSD_TYPE_NAMES.get(value_type)
    if name:
        return name
    return f"xs:{getattr(value_type, '__name__', str(value_type))}"


def serialize_xsd_value(value: Any) -> Any:
    """Serialize a typed AAS value to its JSON form (lexical XSD for dates etc.)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return model.datatypes.xsd_repr(value)
    except Exception:  # noqa: BLE001 - never fail a schema over one value
        return str(value)


def humanize_id_short(id_short: str | None) -> str:
    """Turn ``ManufacturerProductDesignation`` into ``Manufacturer Product Designation``."""
    if not id_short:
        return ""
    text = _COUNTER_SUFFIX_RE.sub("", id_short)
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1].upper() + text[1:] if text else id_short


def _preferred_text(lang_map: dict[str, str] | None) -> str | None:
    if not lang_map:
        return None
    for lang in ("en", "en-US", "en-GB"):
        if lang_map.get(lang):
            return lang_map[lang]
    return next((text for text in lang_map.values() if text), None)


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

        # Find the AAS and submodel
        aas = self._find_aas(object_store)
        submodel = self._find_submodel(object_store, aas)
        if not submodel:
            raise ValueError("No Submodel found in AASX file")

        submodel_id = getattr(submodel, "id_", None) or getattr(submodel, "id", None)
        logger.info(f"Parsing submodel: {submodel.id_short} ({submodel_id})")

        # Extract AAS metadata for PDF export
        aas_metadata = self._extract_aas_metadata(aas) if aas else None

        # Build semantic index once for O(1) ConceptDescription lookups
        # This replaces O(M*K) linear scans with O(K) index build + O(M) lookups
        semantic_index = SemanticIndex(object_store)
        logger.debug(f"Built semantic index with {len(semantic_index)} ConceptDescriptions")

        schema = self._build_submodel_schema(
            aas_metadata, submodel, submodel_id, object_store, semantic_index, file_store
        )
        if schema.get("kind") == "Template":
            # Values in a template are illustrations from the specification,
            # not data of the user's asset.
            for element_schema in schema["elements"]:
                self._mark_template_values_as_examples(element_schema)
        return schema

    def _mark_template_values_as_examples(self, schema: dict[str, Any]) -> None:
        """Record the values a template ships with as example values."""
        model_type = schema.get("modelType")
        examples: list[str] = []
        if model_type == "Property":
            value = schema.get("value")
            if value is not None and not isinstance(value, bool) and str(value).strip():
                examples.append(str(value).strip())
        elif model_type == "MultiLanguageProperty":
            for text in (schema.get("value") or {}).values():
                if text and str(text).strip():
                    examples.append(str(text).strip())
        if examples:
            existing = list(schema.get("exampleValues") or [])
            schema["exampleValues"] = existing + [e for e in examples if e not in existing]

        for key in ("elements", "statements", "items", "annotations"):
            for child in schema.get(key) or []:
                self._mark_template_values_as_examples(child)
        if schema.get("itemTemplate"):
            self._mark_template_values_as_examples(schema["itemTemplate"])

    def _build_submodel_schema(
        self,
        aas_metadata: dict[str, Any] | None,
        submodel: model.Submodel,
        submodel_id: str | None,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex,
        file_store,
    ) -> dict[str, Any]:
        return {
            "aas": aas_metadata,
            "submodelId": submodel_id,
            "idShort": submodel.id_short,
            "semanticId": self._serialize_reference(submodel.semantic_id),
            "description": dict(submodel.description) if submodel.description else None,
            "administration": self._serialize_administration(submodel.administration),
            "kind": (
                submodel.kind.name.capitalize()
                if getattr(submodel, "kind", None) is not None
                else None
            ),
            "elements": [
                self._element_to_schema(e, object_store, semantic_index)
                for e in submodel.submodel_element
            ],
            "supplementaryFiles": list(file_store),
            **self._submodel_form_metadata(submodel),
        }

    def _submodel_form_metadata(self, submodel: model.Submodel) -> dict[str, Any]:
        """Form title/info/URL declared as qualifiers on the Submodel."""
        constraints = extract_constraints(self._serialize_qualifiers(submodel))
        return {
            key: constraints[key]
            for key in ("formTitle", "formInfo", "formUrl")
            if constraints.get(key)
        }

    def _find_aas(
        self, object_store: model.DictObjectStore
    ) -> model.AssetAdministrationShell | None:
        """Find the first AssetAdministrationShell in the object store."""
        for obj in object_store:
            if isinstance(obj, model.AssetAdministrationShell):
                return obj
        return None

    def _extract_aas_metadata(
        self, aas: model.AssetAdministrationShell
    ) -> dict[str, Any]:
        """
        Extract AAS-level metadata for PDF rendering.

        Per IDTA AAS Metamodel V3.0, includes:
        - AAS identifier (id, idShort)
        - assetInformation (MANDATORY)
        - submodel references
        - derivedFrom (optional)
        """
        aas_id = getattr(aas, "id_", None) or getattr(aas, "id", None)
        return {
            "id": aas_id,
            "idShort": aas.id_short,
            "assetInformation": self._serialize_asset_information(aas.asset_information),
            "submodelRefs": [
                self._serialize_reference(ref) for ref in (aas.submodel or [])
            ],
            "derivedFrom": (
                self._serialize_reference(aas.derived_from) if aas.derived_from else None
            ),
            "administration": self._serialize_administration(
                getattr(aas, "administration", None)
            ),
        }

    def _serialize_asset_information(
        self, asset_info: model.AssetInformation
    ) -> dict[str, Any]:
        """
        Serialize AssetInformation per IDTA Metamodel V3.0.

        AssetInformation contains:
        - assetKind (MANDATORY): Instance or Type
        - globalAssetId: Globally unique identifier for the asset
        - specificAssetIds: Additional identifiers (e.g., serial number)
        - assetType: Type of asset (optional)
        """
        if asset_info is None:
            return {
                "assetKind": None,
                "globalAssetId": None,
                "specificAssetIds": [],
                "assetType": None,
            }

        return {
            "assetKind": (
                str(asset_info.asset_kind.name) if asset_info.asset_kind else None
            ),
            "globalAssetId": asset_info.global_asset_id,
            "specificAssetIds": self._serialize_specific_asset_ids(
                asset_info.specific_asset_id
            ),
            "assetType": getattr(asset_info, "asset_type", None),
        }

    def _serialize_specific_asset_ids(
        self, specific_asset_ids
    ) -> list[dict[str, Any]]:
        """Serialize SpecificAssetId list for PDF rendering."""
        if not specific_asset_ids:
            return []

        result = []
        for asset_id in specific_asset_ids:
            serialized = {
                "name": asset_id.name,
                "value": asset_id.value,
            }
            # externalSubjectId is optional
            if hasattr(asset_id, "external_subject_id") and asset_id.external_subject_id:
                serialized["externalSubjectId"] = self._serialize_reference(
                    asset_id.external_subject_id
                )
            result.append(serialized)
        return result

    def _find_submodel(
        self,
        object_store: model.DictObjectStore,
        aas: model.AssetAdministrationShell | None = None,
    ) -> model.Submodel | None:
        """Find the primary template Submodel deterministically."""
        submodels = [obj for obj in object_store if isinstance(obj, model.Submodel)]
        if not submodels:
            return None

        def submodel_id(submodel: model.Submodel) -> str:
            return str(getattr(submodel, "id_", None) or getattr(submodel, "id", "") or "")

        def preferred_submodel(candidates: list[model.Submodel]) -> model.Submodel:
            template_submodels = [
                submodel
                for submodel in candidates
                if "submodeltemplate" in submodel_id(submodel).lower()
            ]
            if template_submodels:
                return sorted(template_submodels, key=submodel_id)[0]
            return sorted(candidates, key=submodel_id)[0]

        referenced_ids = self._aas_submodel_reference_ids(aas)
        if referenced_ids:
            referenced_submodels = [
                submodel for submodel in submodels if submodel_id(submodel) in referenced_ids
            ]
            if referenced_submodels:
                return preferred_submodel(referenced_submodels)

        return preferred_submodel(submodels)

    def _aas_submodel_reference_ids(
        self,
        aas: model.AssetAdministrationShell | None,
    ) -> set[str]:
        if aas is None:
            return set()
        result = set()
        for ref in aas.submodel or []:
            if getattr(ref, "key", None):
                result.add(ref.key[-1].value)
        return result

    def _element_to_schema(
        self,
        element: model.SubmodelElement,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
        item_id_short: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert a SubmodelElement to UI schema.

        Recursively processes nested elements (SMC, SML, Entity).

        Args:
            element: SubmodelElement to convert
            object_store: Object store containing ConceptDescriptions
            semantic_index: Pre-built index for O(1) ConceptDescription lookups
        """
        # Base schema applicable to all element types. In IDTA templates the
        # element description carries the specification notes ("Note: country
        # codes accord. to ISO 3166-1 ...") while the ConceptDescription holds
        # the definition of the concept, so both are exposed.
        own_description = dict(element.description) if element.description else None
        definition = resolve_semantic_description(element, object_store, semantic_index)
        description = own_description or definition
        if definition and own_description and _preferred_text(definition) == _preferred_text(
            own_description
        ):
            definition = None
        if not own_description:
            definition = None

        id_short = element.id_short or ""
        generated_id_short = id_short.startswith(_GENERATED_ID_SHORT_PREFIX)
        if generated_id_short:
            id_short = item_id_short or "Item"

        semantic_label = resolve_semantic_label(
            element, object_store, semantic_index=semantic_index
        )
        qualifiers = self._serialize_qualifiers(element)
        iec61360 = self._iec61360_content(element, object_store, semantic_index)

        base_schema: dict[str, Any] = {
            "idShort": id_short,
            "modelType": type(element).__name__,
            "semanticId": self._serialize_reference(
                getattr(element, "semantic_id", None)
            ),
            "supplementalSemanticIds": [
                value
                for value in (
                    self._serialize_reference(ref)
                    for ref in (getattr(element, "supplemental_semantic_id", None) or [])
                )
                if value
            ],
            "semanticLabel": semantic_label,
            "label": self._display_label(element, id_short, semantic_label),
            "description": description,
            "definition": definition,
            "qualifiers": qualifiers,
            "cardinality": self._extract_cardinality(element),
            "category": getattr(element, "category", None),
        }

        constraints = extract_constraints(
            qualifiers,
            value_list=iec61360.get("valueList"),
            value_format=iec61360.get("valueFormat"),
        )
        qualifier_unit = constraints.pop("qualifierUnit", None)
        base_schema.update(constraints)
        if iec61360.get("sourceOfDefinition"):
            base_schema["sourceOfDefinition"] = iec61360["sourceOfDefinition"]

        # Type-specific schema extensions
        if isinstance(element, model.Property):
            base_schema.update(self._property_schema(element, object_store, semantic_index))

        elif isinstance(element, model.SubmodelElementCollection):
            base_schema.update(self._collection_schema(element, object_store, semantic_index))

        elif isinstance(element, model.SubmodelElementList):
            base_schema.update(self._list_schema(element, object_store, semantic_index))

        elif isinstance(element, model.MultiLanguageProperty):
            base_schema.update(self._multilang_schema(element))

        elif isinstance(element, model.File):
            base_schema.update(self._file_schema(element))

        elif isinstance(element, model.Blob):
            base_schema.update(self._blob_schema(element))

        elif isinstance(element, model.Range):
            base_schema.update(self._range_schema(element, object_store, semantic_index))

        elif isinstance(element, model.ReferenceElement):
            base_schema.update(self._reference_schema(element))

        elif isinstance(element, model.Entity):
            base_schema.update(self._entity_schema(element, object_store, semantic_index))

        elif isinstance(element, model.AnnotatedRelationshipElement):
            base_schema.update(self._annotated_relationship_schema(element, object_store, semantic_index))

        elif isinstance(element, model.RelationshipElement):
            base_schema.update(self._relationship_schema(element))

        elif isinstance(element, model.Operation):
            base_schema.update(self._operation_schema(element, object_store, semantic_index))

        elif isinstance(element, model.Capability):
            base_schema.update(self._capability_schema(element))

        elif isinstance(element, model.BasicEventElement):
            base_schema.update(self._event_schema(element))

        if qualifier_unit and not base_schema.get("unit"):
            base_schema["unit"] = qualifier_unit

        self._apply_text_requirements(base_schema)
        return base_schema

    def _display_label(
        self,
        element: model.SubmodelElement,
        id_short: str,
        semantic_label: str | None,
    ) -> str:
        """Human-readable field label: displayName, preferred name, or idShort."""
        display_name = _preferred_text(
            dict(element.display_name) if getattr(element, "display_name", None) else None
        )
        if display_name:
            return display_name

        def key(text: str) -> str:
            return re.sub(r"[^a-z0-9]", "", _COUNTER_SUFFIX_RE.sub("", text).lower())

        if (
            semantic_label
            and len(semantic_label) <= 64
            and key(semantic_label) != key(id_short)
        ):
            return semantic_label[:1].upper() + semantic_label[1:]
        return humanize_id_short(id_short) or id_short

    def _iec61360_content(
        self,
        element: model.SubmodelElement,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None,
    ) -> dict[str, Any]:
        """IEC 61360 attributes of the element's ConceptDescription, if any."""
        semantic_ref = getattr(element, "semantic_id", None)
        if semantic_ref is None:
            return {}
        concept_description = _resolve_concept_description(
            semantic_ref, object_store, semantic_index
        )
        if concept_description is None:
            return {}
        for eds in concept_description.embedded_data_specifications or []:
            content = eds.data_specification_content
            if not isinstance(content, model.DataSpecificationIEC61360):
                continue
            value_list = [
                {
                    "value": pair.value,
                    "valueId": self._serialize_reference(pair.value_id),
                }
                for pair in (content.value_list or [])
            ]
            value_list.sort(key=lambda pair: str(pair["value"]))
            return {
                "valueList": value_list,
                "valueFormat": content.value_format,
                "sourceOfDefinition": content.source_of_definition,
            }
        return {}

    def _apply_text_requirements(self, schema: dict[str, Any]) -> None:
        """
        Derive format hints, enumerations and referenced standards from the
        specification text attached to an element.
        """
        texts: list[str] = []
        for key in ("description", "definition"):
            text = _preferred_text(schema.get(key))
            if text:
                texts.append(text)
        texts.extend(schema.get("notes") or [])
        if schema.get("formInfo"):
            texts.append(schema["formInfo"])
        if not texts and schema.get("modelType") != "Property":
            return

        standards = find_referenced_standards(texts)
        if standards:
            schema["standards"] = standards

        if schema.get("modelType") != "Property":
            return

        if not schema.get("allowedValues"):
            enumeration = find_irdi_enumeration(texts)
            if enumeration:
                schema["allowedValues"] = enumeration
                schema["allowedValuesStrict"] = False

        if schema.get("allowedValues") or schema.get("pattern"):
            return
        hint = detect_format_hint(
            id_short=schema.get("idShort"),
            model_type=schema.get("modelType"),
            value_type=schema.get("valueType"),
            texts=texts,
        )
        if hint is not None:
            schema["formatHint"] = hint.to_dict()

    def _property_schema(
        self,
        element: model.Property,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for Property element."""
        value_type = xsd_type_name(element.value_type) or "xs:string"
        return {
            "valueType": value_type,
            "value": serialize_xsd_value(element.value),
            "inputType": get_input_type(value_type),
            "step": get_step_attribute(value_type),
            "constraints": get_range_constraints(value_type),
            "unit": get_unit_from_concept_description(element, object_store, semantic_index),
            "valueId": self._serialize_reference(element.value_id),
        }

    def _collection_schema(
        self,
        element: model.SubmodelElementCollection,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for SubmodelElementCollection."""
        return {
            "elements": [
                self._element_to_schema(e, object_store, semantic_index)
                for e in element.value
            ],
        }

    def _list_schema(
        self,
        element: model.SubmodelElementList,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for SubmodelElementList."""
        list_element_type = element.type_value_list_element
        item_id_short = f"{element.id_short}Item" if element.id_short else "Item"
        schema: dict[str, Any] = {
            "typeValueListElement": (
                getattr(list_element_type, "__name__", None)
                if list_element_type
                else None
            ),
            "orderRelevant": element.order_relevant,
            "valueTypeListElement": xsd_type_name(element.value_type_list_element),
            "semanticIdListElement": self._serialize_reference(
                element.semantic_id_list_element
            ),
            "items": [
                self._element_to_schema(e, object_store, semantic_index, item_id_short)
                for e in element.value
            ],
        }

        # Create item template from first item or type specification
        if element.value:
            schema["itemTemplate"] = self._element_to_schema(
                element.value[0], object_store, semantic_index, item_id_short
            )
        elif element.type_value_list_element:
            schema["itemTemplate"] = self._create_template_from_type(
                element.type_value_list_element,
                xsd_type_name(element.value_type_list_element),
            )
            schema["itemTemplate"]["idShort"] = item_id_short
            schema["itemTemplate"]["label"] = humanize_id_short(item_id_short)

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
        if not element.value:
            return {
                "contentType": element.content_type,
                "value": None,
                "valueEncoding": None,
            }

        try:
            value = element.value.decode("utf-8")
            value_encoding = "utf-8"
        except UnicodeDecodeError:
            encoded = base64.b64encode(element.value).decode("ascii")
            value = f"base64:{encoded}"
            value_encoding = "base64"

        return {
            "contentType": element.content_type,
            "value": value,
            "valueEncoding": value_encoding,
        }

    def _range_schema(
        self,
        element: model.Range,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for Range element."""
        value_type = xsd_type_name(element.value_type) or "xs:double"
        return {
            "valueType": value_type,
            "min": serialize_xsd_value(element.min),
            "max": serialize_xsd_value(element.max),
            "inputType": get_input_type(value_type),
            "step": get_step_attribute(value_type),
            "unit": get_unit_from_concept_description(element, object_store, semantic_index),
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
        semantic_index: SemanticIndex | None = None,
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
                self._element_to_schema(e, object_store, semantic_index)
                for e in element.statement
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
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for AnnotatedRelationshipElement."""
        schema = self._relationship_schema(element)
        schema["annotations"] = [
            self._element_to_schema(e, object_store, semantic_index)
            for e in element.annotation or []
        ]
        return schema

    def _operation_schema(
        self,
        element: model.Operation,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
    ) -> dict[str, Any]:
        """Generate schema for Operation element."""
        return {
            "inputVariables": [
                schema
                for v in (element.input_variable or [])
                if (schema := self._operation_variable_schema(v, object_store, semantic_index)) is not None
            ],
            "outputVariables": [
                schema
                for v in (element.output_variable or [])
                if (schema := self._operation_variable_schema(v, object_store, semantic_index)) is not None
            ],
            "inoutputVariables": [
                schema
                for v in (element.in_output_variable or [])
                if (schema := self._operation_variable_schema(v, object_store, semantic_index)) is not None
            ],
        }

    def _operation_variable_schema(
        self,
        variable: OperationVariableType | model.SubmodelElement,
        object_store: model.DictObjectStore,
        semantic_index: SemanticIndex | None = None,
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
            return self._element_to_schema(value, object_store, semantic_index)  # type: ignore[arg-type]
        if not isinstance(variable, model.SubmodelElement):
            logger.warning(
                "Skipping operation variable that is not a submodel element: %s",
                type(variable).__name__,
            )
            return None
        return self._element_to_schema(variable, object_store, semantic_index)

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
            "lastUpdate": serialize_xsd_value(element.last_update),
            "minInterval": serialize_xsd_value(element.min_interval),
            "maxInterval": serialize_xsd_value(element.max_interval),
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
            # Published templates spell the type as SMT/Cardinality,
            # Cardinality, Multiplicity and even SMT/SMT/Cardinality.
            if qualifier_family(q_type) in ("cardinality", "multiplicity"):
                normalized = self._normalize_cardinality_value(q.value)
                if normalized:
                    return normalized
        return "[1]"  # Default to mandatory

    @staticmethod
    def _normalize_cardinality_value(value: str | None) -> str | None:
        """Normalize common cardinality encodings to bracket format."""
        return normalize_cardinality(value)

    def _serialize_qualifiers(
        self, element: model.SubmodelElement
    ) -> list[dict[str, Any]]:
        """Serialize all qualifiers on an element."""
        qualifiers = []
        for q in getattr(element, "qualifier", []) or []:
            qualifiers.append(
                {
                    "type": getattr(q, "type_", None) or getattr(q, "type", None),
                    "value": serialize_xsd_value(q.value),
                    "valueType": xsd_type_name(q.value_type),
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
            # Return the last key's value (most specific identifier)
            return ref.key[-1].value
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
            "supplementalSemanticIds": [],
            "semanticLabel": None,
            "label": None,
            "description": None,
            "definition": None,
            "qualifiers": [],
            "cardinality": "[1]",
            "category": None,
        }

        if type_name == "Property" and value_type:
            value_type_str = str(value_type)
            template.update(
                {
                    "valueType": value_type_str,
                    "value": None,
                    "inputType": get_input_type(value_type_str),
                    "step": get_step_attribute(value_type_str),
                    "constraints": get_range_constraints(value_type_str),
                    "unit": None,
                    "valueId": None,
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
        elif type_name == "Range":
            value_type_str = str(value_type or "xs:double")
            template.update(
                {
                    "valueType": value_type_str,
                    "min": None,
                    "max": None,
                    "inputType": get_input_type(value_type_str),
                    "step": get_step_attribute(value_type_str),
                    "unit": None,
                }
            )
        elif type_name == "File":
            template.update(
                {
                    "contentType": "application/octet-stream",
                    "value": None,
                }
            )
        elif type_name == "Blob":
            template.update(
                {
                    "contentType": "application/octet-stream",
                    "value": None,
                    "valueEncoding": None,
                }
            )
        elif type_name == "ReferenceElement":
            template["value"] = None
        elif type_name == "Entity":
            template.update(
                {
                    "entityType": str(model.EntityType.CO_MANAGED_ENTITY),
                    "globalAssetId": None,
                    "specificAssetIds": [],
                    "statements": [],
                }
            )
        elif type_name == "AnnotatedRelationshipElement":
            template.update(
                {
                    "first": None,
                    "second": None,
                    "annotations": [],
                }
            )
        elif type_name == "RelationshipElement":
            template.update(
                {
                    "first": None,
                    "second": None,
                }
            )
        elif type_name == "SubmodelElementList":
            template.update(
                {
                    "typeValueListElement": None,
                    "orderRelevant": True,
                    "valueTypeListElement": None,
                    "semanticIdListElement": None,
                    "items": [],
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
