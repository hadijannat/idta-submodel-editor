"""
Safe AASX reader utilities.

Provides a reader that tolerates missing supplementary file parts
so template parsing doesn't fail on incomplete AASX packages.
"""

from __future__ import annotations

import logging
import pprint

import io
import re
from io import BytesIO
from xml.parsers import expat

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter.json import json_deserialization, read_aas_json_file
from basyx.aas.adapter.xml import xml_deserialization, read_aas_xml_file

from app.config import get_settings

logger = logging.getLogger(__name__)

_AAS_XML_NAMESPACES = (
    b"https://admin-shell.io/aas/3/0",
    b"https://admin-shell.io/aas/3/1",
)
_EXPECTED_AAS_XML_NAMESPACE = (
    xml_deserialization.NS_AAS.removeprefix("{").removesuffix("}").encode()
)
_AAS_XML_NAMESPACE_DECLARATION = re.compile(
    rb"(xmlns(?::[A-Za-z_][\w.-]*)?\s*=\s*(['\"]))"
    + rb"("
    + rb"|".join(re.escape(namespace) for namespace in _AAS_XML_NAMESPACES)
    + rb")"
    + rb"(\2)"
)

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
        if _EXPECTED_AAS_XML_NAMESPACE in root_tag:
            return None

        mapped = _AAS_XML_NAMESPACE_DECLARATION.sub(
            lambda match: (
                match.group(1) + _EXPECTED_AAS_XML_NAMESPACE + match.group(4)
            ),
            root_tag,
        )
        if mapped == root_tag:
            return None
        return raw[:root_start] + mapped + raw[root_end:]

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
            if "decoder" not in kwargs and lenient:
                kwargs["decoder"] = LenientAASFromXmlDecoder
            patched = self._map_xml_namespace_to_sdk(raw)
            if patched is not None:
                logger.warning(
                    "AAS namespace in %s is not native to this SDK; mapping it to %s",
                    part_name,
                    _EXPECTED_AAS_XML_NAMESPACE.decode(),
                )
            return read_aas_xml_file(BytesIO(patched or raw), **kwargs)

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
