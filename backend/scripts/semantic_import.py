#!/usr/bin/env python
"""Import semantic dictionary entries into a SQLite FTS index.

Supports JSON and CSV inputs with the following fields:
- canonicalId (required)
- canonicalIri
- kind (property|class|unit|value)
- preferredName (JSON map or string)
- definition (JSON map or string)
- datatypeHint
- unitHint
- synonyms (JSON list or comma-separated string)
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build semantic SQLite index")
    parser.add_argument("--input", required=True, help="Path to JSON or CSV file")
    parser.add_argument("--output", required=True, help="Path to SQLite DB")
    parser.add_argument(
        "--provider",
        default="custom",
        help="Provider id metadata stored in index",
    )
    return parser.parse_args()


def load_entries(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        if isinstance(data, list):
            return data
        raise ValueError("Unsupported JSON format")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader)
    raise ValueError("Unsupported input format")


def to_json(value):
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({"en": text}, ensure_ascii=False)


def to_synonyms(value):
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return json.dumps([v.strip() for v in text.split(",") if v.strip()], ensure_ascii=False)


def build_index(output: Path, entries: list[dict]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with sqlite3.connect(output) as conn:
        conn.execute(
            "CREATE TABLE semantic_entries ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "canonical_id TEXT UNIQUE NOT NULL,"
            "canonical_iri TEXT,"
            "kind TEXT,"
            "preferred_name_json TEXT,"
            "definition_json TEXT,"
            "datatype_hint TEXT,"
            "unit_hint TEXT,"
            "synonyms_json TEXT"
            ")"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE semantic_fts USING fts5("
            "canonical_id, preferred_name, definition, synonyms, content='semantic_entries', content_rowid='id'"
            ")"
        )

        for entry in entries:
            canonical_id = entry.get("canonicalId") or entry.get("canonical_id")
            if not canonical_id:
                continue
            conn.execute(
                "INSERT INTO semantic_entries (canonical_id, canonical_iri, kind, preferred_name_json, "
                "definition_json, datatype_hint, unit_hint, synonyms_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    canonical_id,
                    entry.get("canonicalIri") or entry.get("canonical_iri"),
                    entry.get("kind"),
                    to_json(entry.get("preferredName") or entry.get("preferred_name")),
                    to_json(entry.get("definition")),
                    entry.get("datatypeHint") or entry.get("datatype_hint"),
                    entry.get("unitHint") or entry.get("unit_hint"),
                    to_synonyms(entry.get("synonyms")),
                ),
            )

        conn.execute(
            "INSERT INTO semantic_fts(semantic_fts) VALUES('rebuild')"
        )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    entries = load_entries(input_path)
    build_index(output_path, entries)
    print(f"Built semantic index at {output_path}")


if __name__ == "__main__":
    main()
