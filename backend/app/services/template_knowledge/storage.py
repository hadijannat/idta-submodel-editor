"""
SQLite persistence layer for the Template Knowledge Index.

Provides efficient storage and retrieval of template metadata, field information,
and embedding vectors for semantic similarity search.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from app.services.template_knowledge.models import (
    ExtractionPattern,
    FieldInfo,
    IndexStatus,
    TemplateInfo,
)

logger = logging.getLogger(__name__)


class TemplateKnowledgeStorage:
    """SQLite persistence for template knowledge index."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, db_path: Path | str) -> None:
        """
        Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Create database schema if not exists."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Template metadata
                CREATE TABLE IF NOT EXISTS templates (
                    idta_number TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    version TEXT,
                    semantic_id TEXT,
                    status TEXT DEFAULT 'published',
                    field_count INTEGER DEFAULT 0,
                    last_indexed TEXT,
                    source_path TEXT,
                    description TEXT
                );

                -- Field metadata with embeddings
                CREATE TABLE IF NOT EXISTS fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_idta TEXT NOT NULL,
                    path TEXT NOT NULL,
                    id_short TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    value_type TEXT,
                    semantic_id TEXT,
                    semantic_label TEXT,
                    definition TEXT,
                    unit TEXT,
                    cardinality TEXT DEFAULT '[1]',
                    parent_path TEXT,
                    keywords_json TEXT,
                    synonyms_json TEXT,
                    embedding BLOB,
                    example_values_json TEXT,
                    value_format TEXT,
                    allowed_values_json TEXT,
                    is_required INTEGER DEFAULT 0,
                    UNIQUE(template_idta, path),
                    FOREIGN KEY(template_idta) REFERENCES templates(idta_number)
                        ON DELETE CASCADE
                );

                -- Extraction patterns (learned from templates)
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_path TEXT NOT NULL,
                    context_type TEXT,
                    keywords_json TEXT,
                    regex_patterns_json TEXT,
                    table_hints_json TEXT,
                    confidence_weight REAL DEFAULT 1.0,
                    example_matches_json TEXT
                );

                -- Index status and metadata
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                -- Indexes for efficient queries
                CREATE INDEX IF NOT EXISTS idx_fields_semantic_id
                    ON fields(semantic_id);
                CREATE INDEX IF NOT EXISTS idx_fields_template
                    ON fields(template_idta);
                CREATE INDEX IF NOT EXISTS idx_fields_model_type
                    ON fields(model_type);
                CREATE INDEX IF NOT EXISTS idx_patterns_context
                    ON patterns(context_type);

                -- Full-text search for keyword queries
                CREATE VIRTUAL TABLE IF NOT EXISTS fields_fts USING fts5(
                    id_short,
                    semantic_label,
                    definition,
                    keywords,
                    synonyms,
                    content='fields',
                    content_rowid='id'
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS fields_ai AFTER INSERT ON fields BEGIN
                    INSERT INTO fields_fts(rowid, id_short, semantic_label, definition, keywords, synonyms)
                    VALUES (
                        NEW.id,
                        NEW.id_short,
                        NEW.semantic_label,
                        NEW.definition,
                        COALESCE(NEW.keywords_json, ''),
                        COALESCE(NEW.synonyms_json, '')
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS fields_ad AFTER DELETE ON fields BEGIN
                    INSERT INTO fields_fts(fields_fts, rowid, id_short, semantic_label, definition, keywords, synonyms)
                    VALUES (
                        'delete',
                        OLD.id,
                        OLD.id_short,
                        OLD.semantic_label,
                        OLD.definition,
                        COALESCE(OLD.keywords_json, ''),
                        COALESCE(OLD.synonyms_json, '')
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS fields_au AFTER UPDATE ON fields BEGIN
                    INSERT INTO fields_fts(fields_fts, rowid, id_short, semantic_label, definition, keywords, synonyms)
                    VALUES (
                        'delete',
                        OLD.id,
                        OLD.id_short,
                        OLD.semantic_label,
                        OLD.definition,
                        COALESCE(OLD.keywords_json, ''),
                        COALESCE(OLD.synonyms_json, '')
                    );
                    INSERT INTO fields_fts(rowid, id_short, semantic_label, definition, keywords, synonyms)
                    VALUES (
                        NEW.id,
                        NEW.id_short,
                        NEW.semantic_label,
                        NEW.definition,
                        COALESCE(NEW.keywords_json, ''),
                        COALESCE(NEW.synonyms_json, '')
                    );
                END;
            """)

            # Set schema version
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
                ("schema_version", self.SCHEMA_VERSION),
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Template operations
    # -------------------------------------------------------------------------

    def add_template(self, template: TemplateInfo) -> None:
        """Add or update a template in the index."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO templates
                (idta_number, title, version, semantic_id, status, field_count,
                 last_indexed, source_path, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.idta_number,
                    template.title,
                    template.version,
                    template.semantic_id,
                    template.status,
                    template.field_count,
                    template.last_indexed.isoformat() if template.last_indexed else None,
                    template.source_path,
                    template.description,
                ),
            )
            conn.commit()

    def get_template(self, idta_number: str) -> TemplateInfo | None:
        """Get a template by IDTA number."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM templates WHERE idta_number = ?",
                (idta_number,),
            ).fetchone()

            if not row:
                return None

            return TemplateInfo(
                idta_number=row["idta_number"],
                title=row["title"],
                version=row["version"] or "",
                semantic_id=row["semantic_id"],
                status=row["status"],
                field_count=row["field_count"],
                last_indexed=datetime.fromisoformat(row["last_indexed"])
                if row["last_indexed"]
                else datetime.utcnow(),
                source_path=row["source_path"],
                description=row["description"],
            )

    def list_templates(self) -> list[TemplateInfo]:
        """List all indexed templates."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM templates ORDER BY idta_number"
            ).fetchall()

            return [
                TemplateInfo(
                    idta_number=row["idta_number"],
                    title=row["title"],
                    version=row["version"] or "",
                    semantic_id=row["semantic_id"],
                    status=row["status"],
                    field_count=row["field_count"],
                    last_indexed=datetime.fromisoformat(row["last_indexed"])
                    if row["last_indexed"]
                    else datetime.utcnow(),
                    source_path=row["source_path"],
                    description=row["description"],
                )
                for row in rows
            ]

    def delete_template(self, idta_number: str) -> None:
        """Delete a template and all its fields."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM templates WHERE idta_number = ?", (idta_number,))
            conn.commit()

    # -------------------------------------------------------------------------
    # Field operations
    # -------------------------------------------------------------------------

    def add_field(self, field: FieldInfo) -> int:
        """Add or update a field in the index. Returns the field ID."""
        embedding_blob = self._encode_embedding(field.embedding_vector)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO fields
                (template_idta, path, id_short, model_type, value_type,
                 semantic_id, semantic_label, definition, unit, cardinality,
                 parent_path, keywords_json, synonyms_json, embedding,
                 example_values_json, value_format, allowed_values_json, is_required)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    field.template_idta,
                    field.path,
                    field.id_short,
                    field.model_type,
                    field.value_type,
                    field.semantic_id,
                    field.semantic_label,
                    field.definition,
                    field.unit,
                    field.cardinality,
                    field.parent_path,
                    json.dumps(field.keywords) if field.keywords else None,
                    json.dumps(field.synonyms) if field.synonyms else None,
                    embedding_blob,
                    json.dumps(field.example_values) if field.example_values else None,
                    field.value_format,
                    json.dumps(field.allowed_values) if field.allowed_values else None,
                    1 if field.is_required else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_field(self, template_idta: str, path: str) -> FieldInfo | None:
        """Get a specific field by template and path."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM fields WHERE template_idta = ? AND path = ?",
                (template_idta, path),
            ).fetchone()

            if not row:
                return None

            return self._row_to_field(row)

    def get_fields_for_template(self, template_idta: str) -> list[FieldInfo]:
        """Get all fields for a template."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fields WHERE template_idta = ? ORDER BY path",
                (template_idta,),
            ).fetchall()

            return [self._row_to_field(row) for row in rows]

    def get_fields_by_semantic_id(self, semantic_id: str) -> list[FieldInfo]:
        """Get all fields with a specific semantic ID."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fields WHERE semantic_id = ?",
                (semantic_id,),
            ).fetchall()

            return [self._row_to_field(row) for row in rows]

    def search_fields_fts(self, query: str, limit: int = 20) -> list[FieldInfo]:
        """Search fields using full-text search."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT f.* FROM fields f
                JOIN fields_fts fts ON f.id = fts.rowid
                WHERE fields_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()

            return [self._row_to_field(row) for row in rows]

    def get_all_fields_with_embeddings(self) -> list[tuple[FieldInfo, list[float]]]:
        """Get all fields that have embedding vectors."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fields WHERE embedding IS NOT NULL"
            ).fetchall()

            results = []
            for row in rows:
                field = self._row_to_field(row)
                embedding = self._decode_embedding(row["embedding"])
                if embedding:
                    results.append((field, embedding))

            return results

    def _row_to_field(self, row: sqlite3.Row) -> FieldInfo:
        """Convert a database row to a FieldInfo model."""
        return FieldInfo(
            template_idta=row["template_idta"],
            path=row["path"],
            id_short=row["id_short"],
            model_type=row["model_type"],
            value_type=row["value_type"],
            semantic_id=row["semantic_id"],
            semantic_label=row["semantic_label"],
            definition=row["definition"],
            unit=row["unit"],
            cardinality=row["cardinality"] or "[1]",
            parent_path=row["parent_path"],
            keywords=json.loads(row["keywords_json"]) if row["keywords_json"] else [],
            synonyms=json.loads(row["synonyms_json"]) if row["synonyms_json"] else [],
            embedding_vector=self._decode_embedding(row["embedding"]),
            example_values=json.loads(row["example_values_json"])
            if row["example_values_json"]
            else [],
            value_format=row["value_format"],
            allowed_values=json.loads(row["allowed_values_json"])
            if row["allowed_values_json"]
            else [],
            is_required=bool(row["is_required"]),
        )

    # -------------------------------------------------------------------------
    # Pattern operations
    # -------------------------------------------------------------------------

    def add_pattern(self, pattern: ExtractionPattern) -> int:
        """Add an extraction pattern. Returns the pattern ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO patterns
                (field_path, context_type, keywords_json, regex_patterns_json,
                 table_hints_json, confidence_weight, example_matches_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern.field_path,
                    pattern.context_type,
                    json.dumps(pattern.keywords) if pattern.keywords else None,
                    json.dumps(pattern.regex_patterns) if pattern.regex_patterns else None,
                    json.dumps(pattern.table_hints) if pattern.table_hints else None,
                    pattern.confidence_weight,
                    json.dumps(pattern.example_matches) if pattern.example_matches else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_patterns_for_context(self, context_type: str) -> list[ExtractionPattern]:
        """Get extraction patterns for a context type."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM patterns WHERE context_type = ?",
                (context_type,),
            ).fetchall()

            return [
                ExtractionPattern(
                    field_path=row["field_path"],
                    context_type=row["context_type"] or "",
                    keywords=json.loads(row["keywords_json"])
                    if row["keywords_json"]
                    else [],
                    regex_patterns=json.loads(row["regex_patterns_json"])
                    if row["regex_patterns_json"]
                    else [],
                    table_hints=json.loads(row["table_hints_json"])
                    if row["table_hints_json"]
                    else [],
                    confidence_weight=row["confidence_weight"],
                    example_matches=json.loads(row["example_matches_json"])
                    if row["example_matches_json"]
                    else [],
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Index status
    # -------------------------------------------------------------------------

    def get_status(self) -> IndexStatus:
        """Get index status and statistics."""
        with self._get_connection() as conn:
            template_count = conn.execute(
                "SELECT COUNT(*) FROM templates"
            ).fetchone()[0]
            field_count = conn.execute("SELECT COUNT(*) FROM fields").fetchone()[0]
            pattern_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]

            last_updated_row = conn.execute(
                "SELECT MAX(last_indexed) FROM templates"
            ).fetchone()
            last_updated = (
                datetime.fromisoformat(last_updated_row[0])
                if last_updated_row[0]
                else None
            )

            embedding_model_row = conn.execute(
                "SELECT value FROM index_meta WHERE key = 'embedding_model'"
            ).fetchone()
            embedding_model = (
                embedding_model_row[0] if embedding_model_row else "nomic-embed-text"
            )

            return IndexStatus(
                templates_indexed=template_count,
                fields_indexed=field_count,
                patterns_indexed=pattern_count,
                last_updated=last_updated,
                embedding_model=embedding_model,
                ollama_available=False,  # Will be updated by caller
            )

    def set_meta(self, key: str, value: str) -> None:
        """Set a metadata value."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def get_meta(self, key: str) -> str | None:
        """Get a metadata value."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM index_meta WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    # -------------------------------------------------------------------------
    # Embedding encoding/decoding
    # -------------------------------------------------------------------------

    @staticmethod
    def _encode_embedding(embedding: list[float] | None) -> bytes | None:
        """Encode embedding vector to binary blob."""
        if not embedding:
            return None
        return struct.pack(f"{len(embedding)}f", *embedding)

    @staticmethod
    def _decode_embedding(blob: bytes | None) -> list[float] | None:
        """Decode embedding vector from binary blob."""
        if not blob:
            return None
        count = len(blob) // 4  # 4 bytes per float
        return list(struct.unpack(f"{count}f", blob))

    # -------------------------------------------------------------------------
    # Maintenance
    # -------------------------------------------------------------------------

    def clear_all(self) -> None:
        """Clear all data from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM patterns")
            conn.execute("DELETE FROM fields")
            conn.execute("DELETE FROM templates")
            conn.commit()

    def vacuum(self) -> None:
        """Optimize database storage."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")
