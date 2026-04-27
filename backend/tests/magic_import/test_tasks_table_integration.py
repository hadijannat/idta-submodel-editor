"""Tests for table integration in the Magic Import task pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.schemas.magic_import import (
    BBox,
    CandidateSet,
    ExtractionHint,
    ExtractedTable,
    ExtractedTableCell,
    LLMCandidateResponse,
    PDFIndex,
    PDFIndexInfo,
)
from app.services.magic_import.job_manager import JobManager
from app.services.magic_import.table_extractor import TableExtractionResult


def test_process_job_adds_table_derived_snippets(monkeypatch, tmp_path: Path):
    """Non-empty table extraction should enrich snippets without crashing."""
    settings = MagicMock(
        magic_import_cache_dir=tmp_path,
        magic_import_confidence_threshold=0.8,
        magic_import_ocr_enabled=False,
        magic_import_validation_mode="off",
        magic_import_experiment_id=None,
    )
    monkeypatch.setattr(
        "app.services.magic_import.tasks.get_settings",
        lambda: settings,
    )

    from app.services import settings_service

    monkeypatch.setattr(settings_service, "has_llm_settings", lambda: False)
    monkeypatch.setattr(settings_service, "get_effective_provider", lambda: "local")
    monkeypatch.setattr(settings_service, "get_effective_model", lambda provider: "test-model")

    manager = JobManager()
    job = manager.create_job(
        b"%PDF-1.4\n%%EOF",
        "datasheet.pdf",
        "Digital Nameplate",
    )

    index = PDFIndex(
        job_id=job.job_id,
        pdf_path=str(manager.get_pdf_path(job.job_id)),
        info=PDFIndexInfo(
            total_pages=1,
            pages_with_text=1,
            pages_needing_ocr=0,
            total_words=0,
        ),
        pages=[],
        words=[],
    )

    table = ExtractedTable(
        table_id="table-1",
        page=0,
        bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.4),
        rows=2,
        cols=2,
        cells=[
            ExtractedTableCell(row=0, col=0, text="Field", is_header=True),
            ExtractedTableCell(row=0, col=1, text="Value", is_header=True),
            ExtractedTableCell(row=1, col=0, text="Serial"),
            ExtractedTableCell(row=1, col=1, text="SN-123"),
        ],
        headers=["Field", "Value"],
        accuracy=1.0,
        method="LATTICE",
    )

    hint = ExtractionHint(
        path="SerialNumber",
        label="Serial Number",
        element_type="Property",
        keywords=["serial"],
    )

    monkeypatch.setattr(
        "app.services.magic_import.pdf_indexer.PDFIndexer.index_pdf",
        lambda self, pdf_path, job_id: index,
    )
    monkeypatch.setattr(
        "app.services.magic_import.table_extractor.TableExtractor.extract_tables",
        lambda self, pdf_path: TableExtractionResult.from_tables([table]),
    )
    monkeypatch.setattr(
        "app.services.magic_import.schema_resolver.SchemaResolver.resolve_hints",
        lambda self, *_args, **_kwargs: [hint],
    )
    monkeypatch.setattr(
        "app.services.magic_import.retriever.SnippetRetriever.retrieve_snippets",
        lambda self, *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.magic_import.retriever.SnippetRetriever.collect_retrieval_diagnostics",
        lambda self, *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.magic_import.extractor.Extractor.generate_candidates",
        lambda self, hints, snippets: LLMCandidateResponse(
            candidate_sets=[CandidateSet(path=hint.path, candidates=[])],
            tokens_used=0,
            model="test-model",
        ),
    )
    monkeypatch.setattr(
        "app.services.magic_import.extractor.Extractor.verify_candidates",
        lambda self, *_args, **_kwargs: [],
    )

    from app.services.magic_import.tasks import process_magic_import_job

    result = process_magic_import_job.run(job.job_id, use_two_pass=True)
    snippets = manager.load_artifact(job.job_id, "snippets")

    assert result["status"] == "done"
    assert result["tables_found"] == 1
    assert snippets is not None
    assert snippets[0]["context_before"] == "[TABLE]"
    assert "Serial | SN-123" in snippets[0]["text"]
