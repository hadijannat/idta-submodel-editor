"""Lifecycle tests for the template knowledge index."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.template_knowledge.index import TemplateKnowledgeIndex
from app.services.template_knowledge.models import FieldInfo


@pytest.mark.asyncio
async def test_index_close_closes_embedding_client(tmp_path: Path):
    embedding_client = AsyncMock()
    index = TemplateKnowledgeIndex(
        db_path=tmp_path / "index.db",
        embedding_client=embedding_client,
    )

    await index.close()

    embedding_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_index_close_is_noop_without_close_method(tmp_path: Path):
    class NoCloseClient:
        pass

    index = TemplateKnowledgeIndex(
        db_path=tmp_path / "index.db",
        embedding_client=NoCloseClient(),
    )

    await index.close()


@pytest.mark.asyncio
async def test_similarity_search_records_fallback_when_ollama_unavailable(tmp_path: Path):
    embedding_client = AsyncMock()
    embedding_client.is_available = AsyncMock(return_value=False)

    field = FieldInfo(
        template_idta="02006",
        path="TechnicalData.ManufacturerName",
        id_short="ManufacturerName",
        model_type="Property",
        value_type="xs:string",
        semantic_id=None,
        semantic_label="Manufacturer Name",
        definition="Name of manufacturer",
        unit=None,
        cardinality="[1]",
        parent_path="TechnicalData",
        keywords=["manufacturer", "name"],
        synonyms=[],
        embedding_vector=None,
        example_values=[],
        value_format=None,
        allowed_values=[],
        is_required=True,
    )

    index = TemplateKnowledgeIndex(
        db_path=tmp_path / "index.db",
        embedding_client=embedding_client,
    )
    index.storage.search_fields_fts = lambda *_args, **_kwargs: [field]

    results = await index.find_similar_fields_by_text("manufacturer", top_k=1)

    assert len(results) == 1
    assert results[0][0].path == "TechnicalData.ManufacturerName"
    assert index.last_ollama_available is False
