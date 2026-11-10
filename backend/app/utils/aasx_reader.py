"""
Safe AASX reader utilities.

Reads submodel templates as they are published rather than as the SDK would
like them to be:

- missing supplementary file parts are skipped instead of failing the read
- package parts that are declared as external but ship inside the package are
  found
- template content that only breaks rules for finished submodels is kept: a
  self-managed entity whose asset ID is still to be filled in, and a list
  declared with an abstract element type
- whatever still cannot be read is reported in ``read_issues`` instead of
  disappearing without a trace
"""

from __future__ import annotations

import json
import logging
import pprint
import threading

import io
from io import BytesIO
from typing import Any, Iterable
from xml.etree import ElementTree
from xml.parsers import expat

import pyecma376_2
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter.json import json_deserialization, read_aas_json_file
from basyx.aas.adapter.xml import xml_deserialization, read_aas_xml_file
from pyecma376_2.package_model import normalize_part_name, part_realpath

from app.config import get_settings

logger = logging.getLogger(__name__)

# Element types a SubmodelElementList may declare without naming one concrete
# class. The SDK compares the declared type by identity, so no element can ever
# match one of these.
_ABSTRACT_ELEMENT_TYPES = (
    model.SubmodelElement,
    model.DataElement,
    model.EventElement,
)

# XML tag and JSON modelType names of submodel elements (lower-cased).
_SUBMODEL_ELEMENT_NAMES = frozenset(
    name.lower()
    for name in (
        "Property",
        "MultiLanguageProperty",
        "SubmodelElementCollection",
        "SubmodelElementList",
        "File",
        "Blob",
        "Range",
        "ReferenceElement",
        "Entity",
        "RelationshipElement",
        "AnnotatedRelationshipElement",
        "Operation",
        "Capability",
        "BasicEventElement",
    )
)

_MAX_REPORTED_READ_ERRORS = 5


def construct_template_entity(
    id_short: Any,
    entity_type: model.EntityType | None,
    global_asset_id: str | None = None,
    specific_asset_id: Iterable[model.SpecificAssetId] = (),
) -> model.Entity:
    """
    Build an Entity, accepting a self-managed entity without an asset ID.

    AASd-014 demands a ``globalAssetId`` or ``specificAssetId`` for every
    self-managed entity. In a template that ID is precisely what the user is
    asked to enter, so the element has to survive the read without it. The
    constraint applies again as soon as an ID is set.
    """
    try:
        return model.Entity(
            id_short=id_short,
            entity_type=entity_type,
            global_asset_id=global_asset_id,
            specific_asset_id=specific_asset_id,
        )
    except model.AASConstraintViolation as exc:
        if (
            exc.constraint_id != 14
            or entity_type != model.EntityType.SELF_MANAGED_ENTITY
        ):
            raise
    entity = model.Entity(
        id_short=id_short,
        entity_type=None,
        global_asset_id=global_asset_id,
        specific_asset_id=specific_asset_id,
    )
    # Entity.__init__ assigns this attribute directly as well; going through
    # the property would run the check that was just bypassed.
    entity._entity_type = entity_type
    return entity


def construct_template_list(*args: Any, **kwargs: Any) -> model.SubmodelElementList:
    """
    Build a SubmodelElementList that accepts the items of an abstract type.

    A list declared as ``typeValueListElement=SubmodelElement`` may hold any
    submodel element, but the SDK rejects every item because no object is of
    exactly that abstract class (AASd-108). Items that are instances of the
    declared abstract type are let through; lists with a concrete element type
    keep the strict check.
    """
    list_ = model.SubmodelElementList(*args, **kwargs)
    declared = list_.type_value_list_element
    if declared not in _ABSTRACT_ELEMENT_TYPES:
        return list_

    items = list_.value
    strict_check = items._item_add_hook

    def check(new: model.SubmodelElement, existing: Iterable[model.SubmodelElement]) -> None:
        id_short = new.id_short
        try:
            strict_check(new, existing)
        except model.AASConstraintViolation as exc:
            if exc.constraint_id != 108 or not isinstance(new, declared):
                raise
            # The strict check clears the generated idShort before it raises.
            new.id_short = id_short

    items._item_add_hook = check
    return list_


def drop_duplicate_qualifiers_in_xml(element: Any) -> None:
    """
    Remove repeated qualifier types from an element's ``qualifiers``, keeping the first.

    A qualifiable may carry each qualifier type once (AASd-021). The SDK fails
    the whole element, children included, on a repeat; losing the extra
    qualifier is the smaller loss.
    """
    for container in element:
        if not isinstance(container.tag, str) or not container.tag.endswith("}qualifiers"):
            continue
        seen: set[str] = set()
        for qualifier in list(container):
            type_text = next(
                (
                    (child.text or "").strip()
                    for child in qualifier
                    if isinstance(child.tag, str) and child.tag.endswith("}type")
                ),
                None,
            )
            if type_text is None:
                continue
            if type_text in seen:
                logger.warning(
                    "Ignoring repeated qualifier type %r on line %s",
                    type_text,
                    getattr(qualifier, "sourceline", "?"),
                )
                container.remove(qualifier)
            else:
                seen.add(type_text)


def drop_duplicate_qualifiers_in_json(dct: dict) -> None:
    """JSON counterpart of :func:`drop_duplicate_qualifiers_in_xml`."""
    qualifiers = dct.get("qualifiers")
    if not isinstance(qualifiers, list):
        return
    seen: set[str] = set()
    kept = []
    for qualifier in qualifiers:
        # The decoder builds objects bottom-up, so entries are Qualifier
        # objects by now; plain dicts only appear if that construction failed.
        type_text = getattr(qualifier, "type", None)
        if type_text is None and isinstance(qualifier, dict):
            type_text = qualifier.get("type")
        if isinstance(type_text, str) and type_text in seen:
            logger.warning("Ignoring repeated qualifier type %r", type_text)
            continue
        if isinstance(type_text, str):
            seen.add(type_text)
        kept.append(qualifier)
    if len(kept) != len(qualifiers):
        dct["qualifiers"] = kept


def count_submodel_elements_in_xml(raw: bytes) -> int | None:
    """Number of submodel elements below ``submodels`` in an AAS XML document."""
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return None
    count = 0
    for child in root:
        if child.tag.rsplit("}", 1)[-1] != "submodels":
            continue
        for element in child.iter():
            if element.tag.rsplit("}", 1)[-1].lower() in _SUBMODEL_ELEMENT_NAMES:
                count += 1
    return count


def count_submodel_elements_in_json(document: Any) -> int | None:
    """Number of submodel elements below ``submodels`` in an AAS JSON document."""
    if not isinstance(document, dict):
        return None

    def walk(node: Any) -> int:
        if isinstance(node, list):
            return sum(walk(item) for item in node)
        if not isinstance(node, dict):
            return 0
        own = 1 if str(node.get("modelType", "")).lower() in _SUBMODEL_ELEMENT_NAMES else 0
        return own + sum(walk(value) for value in node.values())

    return walk(document.get("submodels") or [])


def count_submodel_elements(objects: Iterable[Any]) -> int:
    """Number of submodel elements in the submodels among ``objects``."""

    def walk(elements: Iterable[Any] | None) -> int:
        total = 0
        for element in elements or ():
            if not isinstance(element, model.SubmodelElement):
                # Older SDK releases wrap operation variables in a holder object.
                element = getattr(element, "value", None)
                if not isinstance(element, model.SubmodelElement):
                    continue
            total += 1
            if isinstance(
                element, (model.SubmodelElementCollection, model.SubmodelElementList)
            ):
                total += walk(element.value)
            elif isinstance(element, model.Entity):
                total += walk(element.statement)
            elif isinstance(element, model.AnnotatedRelationshipElement):
                total += walk(element.annotation)
            elif isinstance(element, model.Operation):
                total += walk(element.input_variable)
                total += walk(element.output_variable)
                total += walk(element.in_output_variable)
        return total

    return sum(
        walk(obj.submodel_element) for obj in objects if isinstance(obj, model.Submodel)
    )


class _ReadErrorCollector(logging.Handler):
    """Collects the SDK's error messages emitted by the current thread."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self._thread = threading.get_ident()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread:
            return
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - a malformed log call must not break reading
            return
        summary = " ".join(message.split())
        if summary and summary not in self.messages:
            self.messages.append(summary)

_AAS_XML_NAMESPACES = (
    b"https://admin-shell.io/aas/3/0",
    b"https://admin-shell.io/aas/3/1",
)
_EXPECTED_AAS_XML_NAMESPACE = (
    xml_deserialization.NS_AAS.removeprefix("{").removesuffix("}").encode()
)

_LENIENT_LANG_STRING_MAX_LENGTH = {
    model.MultiLanguageNameType: 64,
    model.PreferredNameTypeIEC61360: 255,
    model.ShortNameTypeIEC61360: 18,
}


class TemplateAASFromJsonDecoder(json_deserialization.AASFromJsonDecoder):
    """JSON decoder that keeps template content the strict model rejects."""

    @classmethod
    def _amend_abstract_attributes(cls, obj, dct):
        drop_duplicate_qualifiers_in_json(dct)
        super()._amend_abstract_attributes(obj, dct)

    @classmethod
    def _construct_entity(cls, dct, object_class=model.Entity):
        if object_class is model.Entity:
            object_class = construct_template_entity
        return super()._construct_entity(dct, object_class)

    @classmethod
    def _construct_submodel_element_list(cls, dct, object_class=model.SubmodelElementList):
        if object_class is model.SubmodelElementList:
            object_class = construct_template_list
        return super()._construct_submodel_element_list(dct, object_class)


class LenientAASFromJsonDecoder(TemplateAASFromJsonDecoder):
    """JSON decoder that also truncates overlong constrained lang string values."""

    @classmethod
    def _construct_lang_string_set(cls, lst, object_class):
        max_len = _LENIENT_LANG_STRING_MAX_LENGTH.get(object_class)
        if not max_len:
            return super()._construct_lang_string_set(lst, object_class)

        ret: dict[str, str] = {}
        for desc in lst:
            try:
                lang = json_deserialization._get_ts(desc, "language", str)
                text = json_deserialization._get_ts(desc, "text", str)
                if len(text) > max_len:
                    logger.warning(
                        "Truncating %s text for '%s' from %d to %d chars",
                        object_class.__name__,
                        lang,
                        len(text),
                        max_len,
                    )
                    text = text[:max_len]
                ret[lang] = text
            except (KeyError, TypeError) as exc:
                error_message = (
                    "Error while trying to convert JSON object into {}: {} >>> {}".format(
                        object_class.__name__,
                        exc,
                        pprint.pformat(desc, depth=2, width=2**14, compact=True),
                    )
                )
                if cls.failsafe:
                    logger.error(error_message, exc_info=exc)
                else:
                    raise type(exc)(error_message) from exc
        return object_class(ret)


class TemplateAASFromXmlDecoder(xml_deserialization.AASFromXmlDecoder):
    """XML decoder that keeps template content the strict model rejects."""

    @classmethod
    def _amend_abstract_attributes(cls, obj, element):
        drop_duplicate_qualifiers_in_xml(element)
        super()._amend_abstract_attributes(obj, element)

    @classmethod
    def construct_entity(cls, element, object_class=model.Entity, **kwargs):
        if object_class is model.Entity:
            object_class = construct_template_entity
        return super().construct_entity(element, object_class, **kwargs)

    @classmethod
    def construct_submodel_element_list(
        cls, element, object_class=model.SubmodelElementList, **kwargs
    ):
        if object_class is model.SubmodelElementList:
            object_class = construct_template_list
        return super().construct_submodel_element_list(element, object_class, **kwargs)


class LenientAASFromXmlDecoder(TemplateAASFromXmlDecoder):
    """XML decoder that also truncates overlong constrained lang string values."""

    @classmethod
    def construct_lang_string_set(
        cls, element, expected_tag: str, object_class, **_kwargs
    ):
        max_len = _LENIENT_LANG_STRING_MAX_LENGTH.get(object_class)
        if not max_len:
            return super().construct_lang_string_set(
                element, expected_tag, object_class, **_kwargs
            )

        collected: dict[str, str] = {}
        for lang_string_elem in xml_deserialization._get_all_children_expect_tag(
            element, expected_tag, cls.failsafe
        ):
            lang = xml_deserialization._child_text_mandatory(
                lang_string_elem, xml_deserialization.NS_AAS + "language"
            )
            text = xml_deserialization._child_text_mandatory(
                lang_string_elem, xml_deserialization.NS_AAS + "text"
            )
            if len(text) > max_len:
                logger.warning(
                    "Truncating %s text for '%s' from %d to %d chars",
                    object_class.__name__,
                    lang,
                    len(text),
                    max_len,
                )
                text = text[:max_len]
            collected[lang] = text
        return object_class(collected)


class SafeAASXReader(aasx.AASXReader):
    """
    AASXReader for published templates.

    After :meth:`read_into`, :attr:`read_issues` lists what could not be read,
    in words meant for the person looking at the form.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.read_issues: list[str] = []
        self._accept_internal_targets_declared_external()

    def _accept_internal_targets_declared_external(self) -> None:
        """
        Follow relationships marked ``TargetMode="External"`` to parts in the package.

        Some authoring tools mark every relationship as external, including the
        ones to the AAS files inside the package. The package reader skips
        external relationships, so such a package looks empty ("aasx-origin
        Relationship is missing"). A target that exists as a part of this
        package is internal whatever the attribute says.
        """
        reader = self.reader
        related_parts = reader.get_related_parts_by_type
        known_parts = {normalize_part_name(name) for name, _ in reader.list_parts()}
        patched: set[str] = set()

        def related_parts_including_mislabelled(part_name: str = "/"):
            result = related_parts(part_name)
            source = normalize_part_name(part_name)
            if source in patched:
                return result
            patched.add(source)
            for relationship in reader.get_raw_relationships(source):
                if relationship.target_mode == pyecma376_2.OPCTargetMode.INTERNAL:
                    continue
                target = relationship.target
                if not target or "://" in target:
                    continue
                resolved = part_realpath(target, source)
                if (
                    normalize_part_name(resolved) in known_parts
                    and resolved not in result[relationship.type]
                ):
                    logger.warning(
                        "Relationship from %s to %s is marked external but the "
                        "part is in the package; reading it",
                        part_name,
                        resolved,
                    )
                    result[relationship.type].append(resolved)
            return result

        reader.get_related_parts_by_type = related_parts_including_mislabelled

    def read_into(self, *args: Any, **kwargs: Any):
        collector = _ReadErrorCollector()
        sdk_logger = logging.getLogger("basyx.aas.adapter")
        self._lost_elements = 0
        self._total_elements = 0
        sdk_logger.addHandler(collector)
        try:
            result = super().read_into(*args, **kwargs)
        finally:
            sdk_logger.removeHandler(collector)

        self.read_issues = []
        if self._lost_elements:
            self.read_issues.append(
                f"{self._lost_elements} of {self._total_elements} elements in this "
                "template could not be read and are missing from the form."
            )
            self.read_issues.extend(collector.messages[:_MAX_REPORTED_READ_ERRORS])
            hidden = len(collector.messages) - _MAX_REPORTED_READ_ERRORS
            if hidden > 0:
                self.read_issues.append(f"{hidden} more read error(s) not shown.")
            for issue in self.read_issues:
                logger.warning("AASX read issue: %s", issue)
        return result

    def _record_element_loss(self, expected: int | None, objects: Iterable[Any]) -> None:
        """Compare the elements a part contains with the elements that were built."""
        if expected is None:
            return
        self._total_elements = getattr(self, "_total_elements", 0) + expected
        lost = expected - count_submodel_elements(objects)
        if lost > 0:
            self._lost_elements = getattr(self, "_lost_elements", 0) + lost

    @staticmethod
    def _map_xml_namespace_to_sdk(raw: bytes) -> bytes | None:
        class _RootElementFound(Exception):
            pass

        parser = expat.ParserCreate()
        root_start: int | None = None

        def capture_root(_name, _attributes) -> None:
            nonlocal root_start
            root_start = parser.CurrentByteIndex
            raise _RootElementFound

        parser.StartElementHandler = capture_root
        try:
            parser.Parse(raw, True)
        except _RootElementFound:
            pass

        if root_start is None:
            return None

        quote: int | None = None
        root_end: int | None = None
        for index in range(root_start, len(raw)):
            byte = raw[index]
            if quote is not None:
                if byte == quote:
                    quote = None
            elif byte in (ord('"'), ord("'")):
                quote = byte
            elif byte == ord(">"):
                root_end = index + 1
                break

        if root_end is None:
            return None

        root_tag = raw[root_start:root_end]
        position = 1
        name_end = position
        while (
            name_end < len(root_tag)
            and not chr(root_tag[name_end]).isspace()
            and root_tag[name_end] not in (ord("/"), ord(">"))
        ):
            name_end += 1
        root_name = root_tag[position:name_end]
        namespace_attribute = (
            b"xmlns:" + root_name.split(b":", 1)[0]
            if b":" in root_name
            else b"xmlns"
        )
        position = name_end

        while position < len(root_tag):
            while position < len(root_tag) and chr(root_tag[position]).isspace():
                position += 1
            if position >= len(root_tag) or root_tag[position] in (ord("/"), ord(">")):
                break

            attribute_start = position
            while (
                position < len(root_tag)
                and not chr(root_tag[position]).isspace()
                and root_tag[position] not in (ord("="), ord("/"), ord(">"))
            ):
                position += 1
            attribute_name = root_tag[attribute_start:position]
            while position < len(root_tag) and chr(root_tag[position]).isspace():
                position += 1
            if position >= len(root_tag) or root_tag[position] != ord("="):
                return None
            position += 1
            while position < len(root_tag) and chr(root_tag[position]).isspace():
                position += 1
            if position >= len(root_tag) or root_tag[position] not in (
                ord('"'),
                ord("'"),
            ):
                return None

            quote = root_tag[position]
            value_start = position + 1
            value_end = root_tag.find(bytes((quote,)), value_start)
            if value_end < 0:
                return None

            if attribute_name == namespace_attribute:
                namespace = root_tag[value_start:value_end]
                if namespace == _EXPECTED_AAS_XML_NAMESPACE:
                    return None
                if namespace in _AAS_XML_NAMESPACES:
                    mapped_tag = (
                        root_tag[:value_start]
                        + _EXPECTED_AAS_XML_NAMESPACE
                        + root_tag[value_end:]
                    )
                    return raw[:root_start] + mapped_tag + raw[root_end:]
                return None

            position = value_end + 1

        return None

    def _parse_aas_part(self, part_name: str, **kwargs) -> model.DictIdentifiableStore:
        settings = get_settings()
        lenient = settings.aasx_lenient_name_types

        content_type = self.reader.get_content_type(part_name)
        extension = part_name.split("/")[-1].split(".")[-1]
        is_xml = content_type.split(";")[0] in ("text/xml", "application/xml") or (
            content_type == "" and extension == "xml"
        )
        is_json = content_type.split(";")[0] in ("text/json", "application/json") or (
            content_type == "" and extension == "json"
        )

        if is_xml:
            logger.debug("Parsing AAS objects from XML stream in OPC part %s ...", part_name)
            with self.reader.open_part(part_name) as part:
                raw = part.read()
            if "decoder" not in kwargs:
                kwargs["decoder"] = (
                    LenientAASFromXmlDecoder if lenient else TemplateAASFromXmlDecoder
                )
            patched = self._map_xml_namespace_to_sdk(raw)
            if patched is not None:
                logger.debug(
                    "AAS namespace in %s is not native to this SDK; mapping it to %s",
                    part_name,
                    _EXPECTED_AAS_XML_NAMESPACE.decode(),
                )
            objects = read_aas_xml_file(BytesIO(patched or raw), **kwargs)
            self._record_element_loss(count_submodel_elements_in_xml(raw), objects)
            return objects

        if is_json:
            logger.debug("Parsing AAS objects from JSON stream in OPC part %s ...", part_name)
            with self.reader.open_part(part_name) as part:
                text = part.read().decode("utf-8-sig")
            if "decoder" not in kwargs:
                kwargs["decoder"] = (
                    LenientAASFromJsonDecoder if lenient else TemplateAASFromJsonDecoder
                )
            objects = read_aas_json_file(io.StringIO(text), **kwargs)
            try:
                expected = count_submodel_elements_in_json(json.loads(text))
            except ValueError:
                expected = None
            self._record_element_loss(expected, objects)
            return objects

        logger.error(
            "Could not determine part format of AASX part %s (Content Type: %s, extension: %s)",
            part_name,
            content_type,
            extension,
        )
        return model.DictIdentifiableStore()

    def _add_supplementary_file(
        self,
        part_name: str,
        file_path: str,
        file_store: "aasx.AbstractSupplementaryFileContainer",
    ) -> str | None:
        try:
            return super()._add_supplementary_file(part_name, file_path, file_store)
        except KeyError:
            logger.warning(
                "Supplementary file missing in AASX package: %s",
                file_path,
            )
        except Exception as exc:  # pragma: no cover - defensive safety net
            logger.warning(
                "Failed to read supplementary file %s: %s",
                file_path,
                exc,
            )
        return None
