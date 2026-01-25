"""SQLite FTS provider for semantic lookup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.schemas.semantic import SemanticEntry, SemanticKind


class SQLiteSemanticProvider:
    """Search semantic entries using SQLite FTS5 index."""

    def __init__(
        self,
        provider_id: str,
        label: str,
        db_path: Path,
        enabled: bool = True,
    ) -> None:
        self.id = provider_id
        self.label = label
        self._db_path = db_path
        self._enabled = enabled
        self._status_reason: str | None = None
        self._validate_db()

    def status(self) -> tuple[str, str | None]:
        if not self._enabled:
            return ("disabled", self._status_reason or "disabled by configuration")
        if not self._db_path.exists():
            return ("error", self._status_reason or "index not found")
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

        query = q.strip()
        if not query:
            return ([], 0)

        where_clause = "" if kind is None else "AND e.kind = ?"
        count_params = [query]
        if kind is not None:
            count_params.append(kind)

        sql = (
            "SELECT e.canonical_id, e.canonical_iri, e.kind, e.preferred_name_json, "
            "e.definition_json, e.datatype_hint, e.unit_hint, e.synonyms_json, "
            "(1.0 / (1.0 + bm25(semantic_fts))) AS score "
            "FROM semantic_fts JOIN semantic_entries e ON semantic_fts.rowid = e.id "
            "WHERE semantic_fts MATCH ? "
            f"{where_clause} "
            "ORDER BY score DESC LIMIT ? OFFSET ?"
        )
        params = [query]
        if kind is not None:
            params.append(kind)
        params.extend([limit, offset])

        results: list[SemanticEntry] = []
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM semantic_fts JOIN semantic_entries e "
                f"ON semantic_fts.rowid = e.id WHERE semantic_fts MATCH ? {where_clause}",
                count_params,
            ).fetchone()[0]

            for row in conn.execute(sql, params):
                results.append(
                    _row_to_entry(self.id, row, lang, score=row["score"])
                )

        return results, total

    async def resolve(self, identifier: str, lang: str) -> SemanticEntry | None:
        if not self._enabled:
            return None

        lookup = identifier.strip()
        if not lookup:
            return None

        sql = (
            "SELECT canonical_id, canonical_iri, kind, preferred_name_json, "
            "definition_json, datatype_hint, unit_hint, synonyms_json "
            "FROM semantic_entries WHERE canonical_id = ? OR canonical_iri = ?"
        )

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, (lookup, lookup)).fetchone()
            if not row:
                return None
            return _row_to_entry(self.id, row, lang)

    def _validate_db(self) -> None:
        if not self._enabled:
            self._status_reason = "disabled by configuration"
            return
        if not self._db_path.exists():
            self._enabled = False
            self._status_reason = f"index not found at {self._db_path}"
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1 FROM semantic_entries LIMIT 1")
                conn.execute("SELECT 1 FROM semantic_fts LIMIT 1")
        except sqlite3.Error as exc:
            self._enabled = False
            self._status_reason = f"invalid index: {exc}"


def _row_to_entry(
    provider_id: str, row: sqlite3.Row, lang: str, score: float | None = None
) -> SemanticEntry:
    preferred_name = _pick_lang(_parse_json(row["preferred_name_json"]), lang)
    definition = _pick_lang(_parse_json(row["definition_json"]), lang)
    synonyms = _parse_json(row["synonyms_json"]) or []
    return SemanticEntry(
        provider=provider_id,
        kind=row["kind"],
        canonicalId=row["canonical_id"],
        canonicalIri=row["canonical_iri"],
        preferredName=preferred_name,
        definition=definition,
        datatypeHint=row["datatype_hint"],
        unitHint=row["unit_hint"],
        labels=_parse_json(row["preferred_name_json"]),
        definitions=_parse_json(row["definition_json"]),
        synonyms=synonyms,
        score=score,
    )


def _parse_json(value: str | None):
    if not value:
        return None
    import json

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _pick_lang(value: dict | None, lang: str) -> str | None:
    if not value:
        return None
    if lang in value:
        return value[lang]
    if "en" in value:
        return value["en"]
    return next(iter(value.values()), None)
