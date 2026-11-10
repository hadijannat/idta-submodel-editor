"""
AASX writer utilities.

Provides a writer whose relationships name supplementary files exactly as
they are stored in the package.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, BinaryIO

import pyecma376_2
from basyx.aas import model
from basyx.aas.adapter import aasx
from pyecma376_2.package_model import normalize_part_name


class _ExactTargetPackageWriter:
    """
    View of an OPC package writer that keeps relationship targets literal.

    It remembers the names of the parts written through it and replaces a
    relationship target that is only an equivalent spelling of such a part
    (other letter case or percent-encoding) with the name the part was
    written under.
    """

    def __init__(self, package_writer: pyecma376_2.OPCPackageWriter) -> None:
        self._package_writer = package_writer
        # Written part names by their normalised spelling.
        self._written_part_names: dict[str, str] = {}

    def open_part(self, name: str, content_type: str) -> BinaryIO:
        part = self._package_writer.open_part(name, content_type)
        self._written_part_names.setdefault(normalize_part_name(name), name)
        return part

    def write_relationships(
        self,
        relationships: Iterable[pyecma376_2.OPCRelationship],
        part_name: str = "/",
    ) -> None:
        self._package_writer.write_relationships(
            [self._with_written_target(relationship) for relationship in relationships],
            part_name,
        )

    def _with_written_target(
        self, relationship: pyecma376_2.OPCRelationship
    ) -> pyecma376_2.OPCRelationship:
        if relationship.target_mode is not pyecma376_2.OPCTargetMode.INTERNAL:
            return relationship
        written_name = self._written_part_names.get(normalize_part_name(relationship.target))
        if written_name is None:
            return relationship
        return relationship._replace(target=written_name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._package_writer, name)


class ConformantAASXWriter(aasx.AASXWriter):
    """
    AASXWriter that references supplementary files by their stored part names.

    The BaSyx writer stores a supplementary file under the name used by the
    ``File`` element (or thumbnail), but lower-cases and percent-encodes that
    name for the aas-suppl relationship of the AAS data part. Part names are
    case-insensitive in OPC, yet ZIP item names are not, and conformance
    checkers such as aas-test-engines look relationship targets up literally.
    A file with upper-case letters in its name then appears as a relationship
    with a non-existing target.
    """

    def write_all_aas_objects(
        self,
        part_name: str,
        objects: model.AbstractObjectStore[model.Identifier, model.Identifiable],
        file_store: aasx.AbstractSupplementaryFileContainer,
        write_json: bool = False,
        split_part: bool = False,
        additional_relationships: Iterable[pyecma376_2.OPCRelationship] = (),
    ) -> None:
        package_writer = self.writer
        self.writer = _ExactTargetPackageWriter(package_writer)  # type: ignore[assignment]
        try:
            super().write_all_aas_objects(
                part_name,
                objects,
                file_store,
                write_json,
                split_part,
                additional_relationships,
            )
        finally:
            self.writer = package_writer
