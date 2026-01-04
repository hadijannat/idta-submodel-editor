"""
Safe AASX reader utilities.

Provides a reader that tolerates missing supplementary file parts
so template parsing doesn't fail on incomplete AASX packages.
"""

from __future__ import annotations

import logging

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.util import traversal

logger = logging.getLogger(__name__)


class SafeAASXReader(aasx.AASXReader):
    """AASXReader that skips missing supplementary files instead of raising."""

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
