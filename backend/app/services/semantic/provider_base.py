"""Provider interface for semantic dictionary lookups."""

from typing import Protocol

from app.schemas.semantic import SemanticEntry, SemanticKind


class SemanticProvider(Protocol):
    """Protocol that all semantic providers must implement."""

    id: str
    label: str

    def status(self) -> tuple[str, str | None]:
        """Return (status, reason) for provider availability."""

    async def search(
        self,
        q: str,
        kind: SemanticKind | None,
        lang: str,
        limit: int,
        offset: int,
    ) -> tuple[list[SemanticEntry], int]:
        """Search provider entries."""

    async def resolve(self, identifier: str, lang: str) -> SemanticEntry | None:
        """Resolve a single entry by canonical ID or IRI."""
