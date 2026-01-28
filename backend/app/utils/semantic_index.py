# Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
# SPDX-License-Identifier: MIT
"""
Pre-built index for O(1) ConceptDescription lookups.

This module provides an indexed lookup structure that replaces O(K) linear scans
of the object store with O(1) dictionary lookups, where K is the number of
ConceptDescriptions.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from basyx.aas import model


class SemanticIndex:
    """
    Pre-built index for O(1) ConceptDescription lookups.

    Instead of iterating through the entire object store for each semantic
    resolution (O(K) per element, O(M*K) total), this class builds a dictionary
    index once at parse time, enabling O(1) lookups thereafter.

    The index maps:
    - ConceptDescription.id -> ConceptDescription
    - ConceptDescription.id_short -> ConceptDescription

    Usage:
        index = SemanticIndex(object_store)
        cd = index.resolve("https://example.org/cd/1234")
    """

    def __init__(self, object_store: "model.DictObjectStore"):
        """
        Build the semantic index from an object store.

        Args:
            object_store: BaSyx object store containing ConceptDescriptions
        """
        from basyx.aas import model

        self._by_id: dict[str, "model.ConceptDescription"] = {}
        self._by_id_short: dict[str, "model.ConceptDescription"] = {}

        for obj in object_store:
            if isinstance(obj, model.ConceptDescription):
                # Index by id (primary identifier)
                obj_id = getattr(obj, "id", None)
                if obj_id:
                    self._by_id[obj_id] = obj

                # Index by id_short (secondary identifier)
                obj_id_short = getattr(obj, "id_short", None)
                if obj_id_short:
                    self._by_id_short[obj_id_short] = obj

    def resolve(self, identifier: str) -> Optional["model.ConceptDescription"]:
        """
        Resolve a ConceptDescription by identifier.

        Looks up by id first, then by id_short.

        Args:
            identifier: The id or id_short to look up

        Returns:
            ConceptDescription if found, None otherwise
        """
        if not identifier:
            return None

        identifier = identifier.strip()

        # Try exact match by id
        if identifier in self._by_id:
            return self._by_id[identifier]

        # Try exact match by id_short
        if identifier in self._by_id_short:
            return self._by_id_short[identifier]

        # Try suffix match (for partial identifiers)
        for obj_id, cd in self._by_id.items():
            if obj_id.endswith(identifier):
                return cd

        return None

    def __len__(self) -> int:
        """Return the number of indexed ConceptDescriptions."""
        return len(self._by_id)

    def __contains__(self, identifier: str) -> bool:
        """Check if an identifier is in the index."""
        return identifier in self._by_id or identifier in self._by_id_short
