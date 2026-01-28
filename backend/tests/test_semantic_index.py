# Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
# SPDX-License-Identifier: MIT
"""Tests for SemanticIndex performance optimization."""

import pytest
from basyx.aas import model

from app.utils.semantic_index import SemanticIndex


class TestSemanticIndex:
    """Tests for O(1) ConceptDescription lookup index."""

    def test_empty_object_store(self):
        """Index should handle empty object store."""
        object_store: model.DictObjectStore = model.DictObjectStore()
        index = SemanticIndex(object_store)

        assert len(index) == 0
        assert index.resolve("any_id") is None

    def test_index_by_id(self):
        """Index should support lookup by id."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProperty",
            id_short="TestProperty",
        )
        object_store.add(cd)

        index = SemanticIndex(object_store)

        assert len(index) == 1
        assert index.resolve("https://example.org/cd/TestProperty") is cd

    def test_index_by_id_short(self):
        """Index should support lookup by id_short."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProperty",
            id_short="TestProperty",
        )
        object_store.add(cd)

        index = SemanticIndex(object_store)

        assert index.resolve("TestProperty") is cd

    def test_no_suffix_match(self):
        """Index should NOT support suffix matching (intentionally removed for O(1) guarantees)."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProperty",
            id_short="TestProperty",
        )
        object_store.add(cd)

        index = SemanticIndex(object_store)

        # id_short exact match should work
        assert index.resolve("TestProperty") is cd
        # Full id exact match should work
        assert index.resolve("https://example.org/cd/TestProperty") is cd
        # Partial suffix should NOT match (returns None)
        assert index.resolve("cd/TestProperty") is None
        assert index.resolve("org/cd/TestProperty") is None

    def test_multiple_concept_descriptions(self):
        """Index should handle multiple ConceptDescriptions."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd1 = model.ConceptDescription(
            id_="https://example.org/cd/Prop1",
            id_short="Prop1",
        )
        cd2 = model.ConceptDescription(
            id_="https://example.org/cd/Prop2",
            id_short="Prop2",
        )
        cd3 = model.ConceptDescription(
            id_="https://example.org/cd/Prop3",
            id_short="Prop3",
        )
        object_store.add(cd1)
        object_store.add(cd2)
        object_store.add(cd3)

        index = SemanticIndex(object_store)

        assert len(index) == 3
        assert index.resolve("https://example.org/cd/Prop1") is cd1
        assert index.resolve("https://example.org/cd/Prop2") is cd2
        assert index.resolve("Prop3") is cd3

    def test_contains_operator(self):
        """Index should support 'in' operator."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProp",
            id_short="TestProp",
        )
        object_store.add(cd)

        index = SemanticIndex(object_store)

        assert "https://example.org/cd/TestProp" in index
        assert "TestProp" in index
        assert "NonExistent" not in index

    def test_ignores_non_concept_descriptions(self):
        """Index should only index ConceptDescriptions."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProp",
            id_short="TestProp",
        )
        submodel = model.Submodel(
            id_="https://example.org/sm/TestSubmodel",
            id_short="TestSubmodel",
        )
        object_store.add(cd)
        object_store.add(submodel)

        index = SemanticIndex(object_store)

        # Only the ConceptDescription should be indexed
        assert len(index) == 1
        assert index.resolve("https://example.org/cd/TestProp") is cd
        assert index.resolve("https://example.org/sm/TestSubmodel") is None

    def test_whitespace_handling(self):
        """Index should strip whitespace from identifiers."""
        object_store: model.DictObjectStore = model.DictObjectStore()

        cd = model.ConceptDescription(
            id_="https://example.org/cd/TestProp",
            id_short="TestProp",
        )
        object_store.add(cd)

        index = SemanticIndex(object_store)

        # Whitespace should be stripped
        assert index.resolve("  https://example.org/cd/TestProp  ") is cd
        assert index.resolve("  TestProp  ") is cd

    def test_none_identifier(self):
        """Index should handle None identifier gracefully."""
        object_store: model.DictObjectStore = model.DictObjectStore()
        index = SemanticIndex(object_store)

        assert index.resolve(None) is None
        assert index.resolve("") is None
