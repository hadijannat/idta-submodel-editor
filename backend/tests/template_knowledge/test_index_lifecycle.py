"""Lifecycle tests for the template knowledge index."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.template_knowledge.index import TemplateKnowledgeIndex


@pytest.mark.asyncio
async def test_index_close_closes_embedding_client(tmp_path: Path):
    embedding_client = AsyncMock()
    index = TemplateKnowledgeIndex(
        db_path=tmp_path / "index.db",
        embedding_client=embedding_client,
    )

    await index.close()

    embedding_client.close.assert_awaited_once()
