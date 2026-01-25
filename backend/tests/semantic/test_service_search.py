import pytest

from app.schemas.semantic import SemanticEntry
from app.services.semantic.service import SemanticService


class FakeProvider:
    def __init__(self, provider_id: str, scores: list[float]) -> None:
        self.id = provider_id
        self.label = provider_id
        self._scores = scores

    def status(self):
        return ("ready", None)

    async def search(self, q, kind, lang, limit, offset):
        entries = [
            SemanticEntry(
                provider=self.id,
                kind="property",
                canonicalId=f"{self.id}-{idx}",
                preferredName=f"{self.id}-{idx}",
                score=score,
            )
            for idx, score in enumerate(self._scores)
        ]
        sliced = entries[offset : offset + limit]
        return sliced, len(entries)

    async def resolve(self, identifier, lang):
        return None


@pytest.mark.asyncio
async def test_semantic_search_aggregates_with_offset():
    service = SemanticService()
    service._providers = {
        "p1": FakeProvider("p1", [0.9, 0.8, 0.7]),
        "p2": FakeProvider("p2", [0.95, 0.1]),
    }

    results, total = await service.search(
        q="x", provider=None, kind=None, lang="en", limit=2, offset=1
    )

    assert total == 5
    assert [r.score for r in results] == [0.9, 0.8]
