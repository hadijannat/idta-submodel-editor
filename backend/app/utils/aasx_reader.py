"""
Safe AASX reader utilities.

Provides a reader that tolerates missing supplementary file parts
so template parsing doesn't fail on incomplete AASX packages.
"""

from __future__ import annotations

import logging
import pprint

import io
from io import BytesIO

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter.json import json_deserialization, read_aas_json_file
from basyx.aas.adapter.xml import xml_deserialization, read_aas_xml_file
from basyx.aas.util import traversal

from app.config import get_settings

logger = logging.getLogger(__name__)

_LENIENT_LANG_STRING_MAX_LENGTH = {
    model.MultiLanguageNameType: 64,
    model.PreferredNameTypeIEC61360: 255,
    model.ShortNameTypeIEC61360: 18,
}


class LenientAASFromJsonDecoder(json_deserialization.AASFromJsonDecoder):
    """JSON decoder that truncates overlong constrained lang string values."""

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


class LenientAASFromXmlDecoder(xml_deserialization.AASFromXmlDecoder):
    """XML decoder that truncates overlong constrained lang string values."""

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
    """AASXReader that skips missing supplementary files instead of raising."""

    def _parse_aas_part(self, part_name: str, **kwargs) -> model.DictObjectStore:
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
            try:
                if "decoder" not in kwargs and lenient:
                    kwargs["decoder"] = LenientAASFromXmlDecoder
                parsed = read_aas_xml_file(BytesIO(raw), **kwargs)
            except Exception as exc:
                if b"https://admin-shell.io/aas/3/1" in raw and b"https://admin-shell.io/aas/3/0" not in raw:
                    logger.warning(
                        "Detected AAS 3.1 namespace in %s, retrying with 3.0 namespace mapping",
                        part_name,
                    )
                    patched = raw.replace(
                        b"https://admin-shell.io/aas/3/1",
                        b"https://admin-shell.io/aas/3/0",
                    )
                    if "decoder" not in kwargs and lenient:
                        kwargs["decoder"] = LenientAASFromXmlDecoder
                    return read_aas_xml_file(BytesIO(patched), **kwargs)
                raise exc

            if (
                not parsed
                and b"https://admin-shell.io/aas/3/1" in raw
                and b"https://admin-shell.io/aas/3/0" not in raw
            ):
                logger.warning(
                    "Parsed no objects for %s, retrying with 3.0 namespace mapping",
                    part_name,
                )
                patched = raw.replace(
                    b"https://admin-shell.io/aas/3/1",
                    b"https://admin-shell.io/aas/3/0",
                )
                if "decoder" not in kwargs and lenient:
                    kwargs["decoder"] = LenientAASFromXmlDecoder
                return read_aas_xml_file(BytesIO(patched), **kwargs)

            return parsed

        if is_json:
            logger.debug("Parsing AAS objects from JSON stream in OPC part %s ...", part_name)
            with self.reader.open_part(part_name) as part:
                if "decoder" not in kwargs and lenient:
                    kwargs["decoder"] = LenientAASFromJsonDecoder
                return read_aas_json_file(
                    io.TextIOWrapper(part, encoding="utf-8-sig"), **kwargs
                )

        logger.error(
            "Could not determine part format of AASX part %s (Content Type: %s, extension: %s)",
            part_name,
            content_type,
            extension,
        )
        return model.DictObjectStore()

    def _collect_supplementary_files(
        self,
        part_name: str,
        submodel: model.Submodel,
        file_store: "aasx.AbstractSupplementaryFileContainer",
    ) -> None:
        for element in traversal.walk_submodel(submodel):
            if not isinstance(element, model.File):
                continue
            if element.value is None:
                continue
            if element.value.startswith("//") or ":" in element.value.split("/")[0]:
                logger.info(
                    "Skipping supplementary file %s, since it seems to be an absolute URI or network-path URI reference",
                    element.value,
                )
                continue

            absolute_name = aasx.pyecma376_2.package_model.part_realpath(
                element.value,
                part_name,
            )
            logger.debug("Reading supplementary file %s from AASX package ...", absolute_name)
            try:
                with self.reader.open_part(absolute_name) as part:
                    final_name = file_store.add_file(
                        absolute_name,
                        part,
                        self.reader.get_content_type(absolute_name),
                    )
            except KeyError:
                logger.warning(
                    "Supplementary file missing in AASX package: %s (referenced by %s)",
                    absolute_name,
                    element.value,
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive safety net
                logger.warning(
                    "Failed to read supplementary file %s: %s",
                    absolute_name,
                    exc,
                )
                continue

            element.value = final_name
