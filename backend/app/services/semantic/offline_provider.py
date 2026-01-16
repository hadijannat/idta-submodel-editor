"""Offline semantic provider backed by a JSON index."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.semantic import SemanticEntry, SemanticKind


class OfflineSemanticProvider:
    """Search and resolve entries from a local JSON index."""

    def __init__(
        self,
        provider_id: str,
        label: str,
        data_path: Path,
        enabled: bool = True,
    ) -> None:
        self.id = provider_id
        self.label = label
        self._data_path = data_path
        self._enabled = enabled
        self._status_reason: str | None = None
        self._entries: list[dict] = []
        self._load_data()

    def status(self) -> tuple[str, str | None]:
        if not self._enabled:
            return ("disabled", self._status_reason or "disabled by configuration")
        if not self._entries:
            return ("error", self._status_reason or "index is empty")
        return ("ready", None)

    async def search(
        self,
        q: str,
        kind: SemanticKind | None,
        lang: str,
        limit: int,
        offset: int,
    ) -> tuple[list[SemanticEntry], int]:
        if not self._enabled:
            return ([], 0)

        query = q.lower().strip()
        if not query:
            return ([], 0)

        matches: list[tuple[float, dict]] = []
        for entry in self._entries:
            if kind and entry.get("kind") != kind:
                continue

            preferred = _pick_lang(entry.get("preferredName"), lang)
            definition = _pick_lang(entry.get("definition"), lang)
            synonyms = entry.get("synonyms") or []

            score = 0.0
            if preferred and query in preferred.lower():
                score = 1.0
            elif any(query in s.lower() for s in synonyms if isinstance(s, str)):
                score = 0.8
            elif definition and query in definition.lower():
                score = 0.6

            if score > 0:
                matches.append((score, entry))

        matches.sort(key=lambda item: item[0], reverse=True)
        total = len(matches)
        sliced = matches[offset : offset + limit]
        results = [self._to_entry(entry, lang, score) for score, entry in sliced]
        return (results, total)

    async def resolve(self, identifier: str, lang: str) -> SemanticEntry | None:
        if not self._enabled:
            return None

        lookup = identifier.strip()
        if not lookup:
            return None

        for entry in self._entries:
            if entry.get("canonicalId") == lookup:
                return self._to_entry(entry, lang)
            if entry.get("canonicalIri") == lookup:
                return self._to_entry(entry, lang)

        return None

    def _load_data(self) -> None:
        if not self._enabled:
            self._status_reason = "disabled by configuration"
            return

        if not self._data_path.exists():
            self._enabled = False
            self._status_reason = f"index not found at {self._data_path}"
            return

        try:
            raw = json.loads(self._data_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._entries = raw
            elif isinstance(raw, dict) and "entries" in raw:
                self._entries = raw.get("entries", []) or []
            else:
                self._entries = []
        except Exception as exc:
            self._enabled = False
            self._status_reason = f"failed to read index: {exc}"

    def _to_entry(self, entry: dict, lang: str, score: float | None = None) -> SemanticEntry:
        preferred_name = _pick_lang(entry.get("preferredName"), lang)
        definition = _pick_lang(entry.get("definition"), lang)
        return SemanticEntry(
            provider=self.id,
            kind=entry.get("kind"),
            canonicalId=entry.get("canonicalId"),
            canonicalIri=entry.get("canonicalIri"),
            preferredName=preferred_name,
            definition=definition,
            datatypeHint=entry.get("datatypeHint"),
            unitHint=entry.get("unitHint"),
            labels=entry.get("preferredName"),
            definitions=entry.get("definition"),
            synonyms=entry.get("synonyms"),
            score=score,
        )


def _pick_lang(value: dict | None, lang: str) -> str | None:
    if not value:
        return None
    if lang in value:
        return value[lang]
    if "en" in value:
        return value["en"]
    return next(iter(value.values()), None)
