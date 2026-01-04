"""
Safe AASX reader utilities.

Provides a reader that tolerates missing supplementary file parts
so template parsing doesn't fail on incomplete AASX packages.
"""

from __future__ import annotations

import logging

import io
from io import BytesIO

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter.json import read_aas_json_file
from basyx.aas.adapter.xml import read_aas_xml_file
from basyx.aas.util import traversal

logger = logging.getLogger(__name__)


class SafeAASXReader(aasx.AASXReader):
    """AASXReader that skips missing supplementary files instead of raising."""

    def _parse_aas_part(self, part_name: str, **kwargs) -> model.DictObjectStore:
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
                return read_aas_xml_file(BytesIO(patched), **kwargs)

            return parsed

        if is_json:
            logger.debug("Parsing AAS objects from JSON stream in OPC part %s ...", part_name)
            with self.reader.open_part(part_name) as part:
                return read_aas_json_file(io.TextIOWrapper(part, encoding="utf-8-sig"), **kwargs)

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
