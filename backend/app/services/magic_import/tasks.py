"""
Celery tasks for Magic Import background processing.

Enhanced Pipeline (Two-Pass Extraction):
1. PDF Indexing - Extract text with word positions
2. OCR (if needed) - Process scanned pages
3. Document Classification - Detect doc type, language, tables
4. Table Extraction - Extract structured tables
5. Schema Resolution - Get extraction hints from template
6. Snippet Retrieval - Find relevant document sections
7. Candidate Generation (Pass A) - LLM generates 1-3 candidates per field
8. Candidate Verification (Pass B) - Deterministic grounding check
9. Evidence Localization - Map quotes to bounding boxes
10. Confidence Scoring - Calculate scores, enforce evidence rule
11. Cross-Field Consistency - Check coupled fields, plausibility
12. Validation - Validate against template schema
"""

from __future__ import annotations

import logging
import re
import time

from celery import shared_task

from app.config import get_settings
from app.metrics import (
    magic_import_job_duration_seconds,
    record_magic_import_job,
    record_quality_metrics,
)
from app.schemas.magic_import import (
    JobStatus,
    MagicImportResult,
    FieldExtraction,
    EvidenceRef,
    UnmappedFinding,
    ValidationResult,
    Snippet,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="magic_import.process_job")
def process_magic_import_job(self, job_id: str, use_two_pass: bool = True) -> dict:
    """
    Main orchestrator task for Magic Import processing.

    Executes the enhanced pipeline with two-pass extraction:
    PDF Indexing → OCR → Tables → Candidates → Verification → Scoring → Validation

    Args:
        job_id: The job ID to process
        use_two_pass: Whether to use two-pass extraction (default: True)

    Returns:
        Result summary dictionary
    """
    from app.services.magic_import.job_manager import JobManager
    from app.services.magic_import.pdf_indexer import PDFIndexer
    from app.services.magic_import.ocr import OCRProcessor
    from app.services.magic_import.schema_resolver import SchemaResolver
    from app.services.magic_import.retriever import SnippetRetriever
    from app.services.magic_import.extractor import Extractor
    from app.services.magic_import.localizer import EvidenceLocalizer
    from app.services.magic_import.scorer import ConfidenceScorer
    from app.services.magic_import.table_extractor import TableExtractor
    from app.services.magic_import.rules_engine import RulesEngine

    settings = get_settings()
    from app.services import settings_service
    llm_settings = (
        settings_service.load_llm_settings()
        if settings_service.has_llm_settings()
        else None
    )
    confidence_threshold = (
        llm_settings.confidence_threshold
        if llm_settings is not None
        else settings.magic_import_confidence_threshold
    )
    ocr_enabled = (
        llm_settings.ocr_enabled
        if llm_settings is not None
        else settings.magic_import_ocr_enabled
    )
    active_provider = settings_service.get_effective_provider()
    active_model = settings_service.get_effective_model(active_provider)
    job_manager = JobManager()
    start_time = time.time()

    # Load job
    job = job_manager.get_job(job_id)
    if job is None:
        logger.error("Job %s not found", job_id)
        return {"error": "Job not found", "job_id": job_id}

    pdf_path = job_manager.get_pdf_path(job_id)
    if pdf_path is None:
        job_manager.update_job_status(
            job_id, JobStatus.FAILED, error_message="PDF file not found"
        )
        return {"error": "PDF file not found", "job_id": job_id}

    try:
        from app.services.magic_import.pymupdf_guard import assert_pymupdf_allowed

        assert_pymupdf_allowed(settings)

        # ================================================================
        # Step 1: Index PDF (with artifact persistence)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.05,
            progress_message="Extracting text from PDF...",
        )
        job_manager.append_to_audit_log(job_id, "indexing_start")

        # Check for existing index artifact (resume support)
        cached_index = job_manager.load_artifact(job_id, "pdf_index")
        if cached_index:
            from app.schemas.magic_import import PDFIndex
            index = PDFIndex(**cached_index)
            logger.info("Loaded cached index for job %s", job_id)
        else:
            indexer = PDFIndexer()
            index = indexer.index_pdf(pdf_path, job_id)
            job_manager.save_index(index)
            job_manager.save_artifact(job_id, "pdf_index", index)

        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.15,
            progress_message=f"Indexed {index.info.total_words} words from {index.info.total_pages} pages",
            pdf_info=index.info,
        )
        job_manager.append_to_audit_log(
            job_id, "indexing_complete",
            {"total_words": index.info.total_words, "total_pages": index.info.total_pages}
        )

        # ================================================================
        # Step 2: OCR if needed
        # ================================================================
        if index.info.pages_needing_ocr > 0 and ocr_enabled:
            job_manager.update_job_status(
                job_id,
                JobStatus.OCR,
                progress=0.20,
                progress_message=f"Running OCR on {index.info.pages_needing_ocr} scanned pages...",
            )
            job_manager.append_to_audit_log(
                job_id, "ocr_start",
                {"pages_needing_ocr": index.info.pages_needing_ocr}
            )

            ocr_processor = OCRProcessor()
            if ocr_processor.is_available:
                index = ocr_processor.process_scanned_pages(pdf_path, index)
                job_manager.save_index(index)
                job_manager.save_artifact(job_id, "pdf_index", index)

                job_manager.update_job_status(
                    job_id,
                    JobStatus.OCR,
                    progress=0.28,
                    progress_message=f"OCR complete: {index.info.total_words} total words",
                    pdf_info=index.info,
                )
                job_manager.append_to_audit_log(job_id, "ocr_complete")
            else:
                logger.warning("OCR needed but Tesseract not available")
                job_manager.append_to_audit_log(job_id, "ocr_skipped", {"reason": "tesseract_unavailable"})

        # ================================================================
        # Step 2.5: Classify document
        # ================================================================
        from app.services.magic_import.classifier import DocumentClassifier

        classifier = DocumentClassifier()
        doc_classification = classifier.classify(index)

        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.30,
            progress_message=f"Document classified: {doc_classification.doc_type}, quality={doc_classification.quality_score:.0%}",
            pdf_info=index.info,
            doc_classification=doc_classification,
        )

        logger.info(
            "Classified document %s: type=%s, language=%s, tables=%s, quality=%.2f",
            job_id,
            doc_classification.doc_type,
            doc_classification.language,
            doc_classification.has_tables,
            doc_classification.quality_score,
        )

        # ================================================================
        # Step 2.6: Extract tables (NEW)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.32,
            progress_message="Extracting tables from document...",
        )
        job_manager.append_to_audit_log(job_id, "table_extraction_start")

        # Check for cached tables
        cached_tables = job_manager.load_artifact(job_id, "tables")
        if cached_tables:
            from app.services.magic_import.table_extractor import TableExtractionResult
            table_result = TableExtractionResult(**cached_tables)
            logger.info("Loaded cached tables for job %s", job_id)
        else:
            table_extractor = TableExtractor()
            table_result = table_extractor.extract_tables(pdf_path)
            job_manager.save_artifact(job_id, "tables", table_result)

        job_manager.append_to_audit_log(
            job_id, "table_extraction_complete",
            {"tables_found": table_result.total_tables}
        )
        logger.info("Extracted %d tables from document", table_result.total_tables)

        # ================================================================
        # Step 3: Resolve schema and get extraction hints
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.EXTRACTING,
            progress=0.35,
            progress_message="Resolving template schema...",
        )

        schema_resolver = SchemaResolver()
        hints = schema_resolver.resolve_hints(
            job.template_name,
            job.template_status,
            job.template_version,
        )
        job_manager.save_artifact(job_id, "hints", hints)

        logger.info("Resolved %d extraction hints for template %s", len(hints), job.template_name)

        # ================================================================
        # Step 4: Retrieve relevant snippets (enhanced with table snippets)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.EXTRACTING,
            progress=0.40,
            progress_message="Finding relevant document sections...",
        )

        retrieval_diagnostics = []
        snippets_override_data = job_manager.load_artifact(job_id, "snippet_overrides")
        if snippets_override_data is not None:
            snippets = [Snippet.model_validate(item) for item in snippets_override_data]
            logger.info(
                "Using %d user-reviewed snippet overrides for job %s",
                len(snippets),
                job_id,
            )
        else:
            retriever = SnippetRetriever()
            # Dynamic budget: scale based on template complexity
            # At least 1 snippet per field, max 200 to avoid overwhelming LLM context
            max_total_snippets = min(200, max(50, len(hints)))
            snippets = retriever.retrieve_snippets(
                index,
                hints,
                max_total_snippets=max_total_snippets,
                max_snippets_per_field=3,
            )

            retrieval_diagnostics = retriever.collect_retrieval_diagnostics(index, hints)
            if retrieval_diagnostics:
                job_manager.save_artifact(
                    job_id,
                    "retrieval_diagnostics",
                    retrieval_diagnostics,
                )

            # Add table-derived snippets for better coverage
            table_extractor = TableExtractor()
            for table in table_result.tables:
                table_snippets = table_extractor.table_to_snippets(table, max_rows=15)
                for snippet_text in table_snippets:
                    snippets.append(
                        Snippet(
                            text=snippet_text,
                            page=table.page,
                            start_word_idx=0,
                            end_word_idx=0,
                            score=0.8,  # High score for table data
                            context_before="[TABLE]",
                            context_after="",
                        )
                    )

        job_manager.save_artifact(job_id, "snippets", snippets)
        logger.info("Retrieved %d snippets for extraction (including tables)", len(snippets))

        # ================================================================
        # Step 5: Field Extraction (Two-Pass or Legacy)
        # ================================================================
        extractor = Extractor()
        hints_by_path = {hint.path: hint for hint in hints}
        llm_tokens_used = 0
        llm_prompt_tokens: int | None = None
        llm_completion_tokens: int | None = None

        if use_two_pass:
            # ============================================================
            # Two-Pass Extraction: Generate Candidates → Verify
            # ============================================================
            job_manager.update_job_status(
                job_id,
                JobStatus.EXTRACTING,
                progress=0.45,
                progress_message="Generating extraction candidates with AI...",
            )
            job_manager.append_to_audit_log(job_id, "candidate_generation_start")

            # Pass A: Generate candidates
            candidate_response = extractor.generate_candidates(hints, snippets)
            job_manager.save_artifact(job_id, "candidates", candidate_response)
            llm_tokens_used = candidate_response.tokens_used
            llm_prompt_tokens = candidate_response.prompt_tokens
            llm_completion_tokens = candidate_response.completion_tokens

            logger.info(
                "Generated %d candidate sets (%d tokens)",
                len(candidate_response.candidate_sets),
                candidate_response.tokens_used,
            )
            job_manager.append_to_audit_log(
                job_id, "candidate_generation_complete",
                {"candidate_sets": len(candidate_response.candidate_sets), "tokens": candidate_response.tokens_used}
            )

            # Pass B: Verify candidates
            job_manager.update_job_status(
                job_id,
                JobStatus.EXTRACTING,
                progress=0.55,
                progress_message="Verifying candidates against document...",
            )
            job_manager.append_to_audit_log(job_id, "verification_start")

            extractions_with_evidence = extractor.verify_candidates(
                candidate_response.candidate_sets,
                index,
                hints_by_path,
            )

            verified_count = sum(1 for e in extractions_with_evidence if e.evidence is not None)
            logger.info(
                "Verified %d/%d candidates with document evidence",
                verified_count,
                len(extractions_with_evidence),
            )
            job_manager.append_to_audit_log(
                job_id, "verification_complete",
                {"total": len(extractions_with_evidence), "verified": verified_count}
            )

        else:
            # ============================================================
            # Legacy: Single-pass extraction
            # ============================================================
            job_manager.update_job_status(
                job_id,
                JobStatus.EXTRACTING,
                progress=0.50,
                progress_message="Extracting field values with AI...",
            )

            llm_extractions = extractor.extract_fields(hints, snippets)
            llm_tokens_used = llm_extractions.tokens_used
            llm_prompt_tokens = llm_extractions.prompt_tokens
            llm_completion_tokens = llm_extractions.completion_tokens
            logger.info("LLM extracted %d fields", len(llm_extractions.extractions))

            # Localize evidence
            job_manager.update_job_status(
                job_id,
                JobStatus.LOCALIZING,
                progress=0.65,
                progress_message="Locating evidence in document...",
            )

            localizer = EvidenceLocalizer()
            extractions_with_evidence = localizer.localize_all(
                llm_extractions.extractions,
                index,
                hints_by_path=hints_by_path,
            )

        # ================================================================
        # Step 6: Additional Evidence Localization (for bbox refinement)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.LOCALIZING,
            progress=0.65,
            progress_message="Refining evidence bounding boxes...",
        )

        localizer = EvidenceLocalizer()
        if hasattr(localizer, "refine_bboxes"):
            extractions_with_evidence = localizer.refine_bboxes(
                extractions_with_evidence,
                index,
            )
        else:
            logger.warning(
                "EvidenceLocalizer missing refine_bboxes; skipping bbox refinement"
            )

        # ================================================================
        # Step 6.5: Rule-based contact extraction (fallback for headers/footers)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.LOCALIZING,
            progress=0.70,
            progress_message="Applying rule-based contact extraction...",
        )

        from app.services.magic_import.rules_engine import (
            extract_contact_by_rules,
            merge_rule_extractions_with_llm,
        )

        rule_extractions = extract_contact_by_rules(index, hints)
        if rule_extractions:
            logger.info("Found %d contact values via rule-based extraction", len(rule_extractions))
            extractions_with_evidence = merge_rule_extractions_with_llm(
                extractions_with_evidence,
                rule_extractions,
            )
            job_manager.append_to_audit_log(
                job_id, "rule_extraction_complete",
                {"rule_extractions_added": len(rule_extractions)}
            )

        # ================================================================
        # Step 7: Score confidence (with evidence rule enforcement)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.SCORING,
            progress=0.75,
            progress_message="Calculating confidence scores...",
        )
        job_manager.append_to_audit_log(job_id, "scoring_start")

        scorer = ConfidenceScorer()
        scored_extractions = scorer.score_all(
            extractions_with_evidence,
            index,
            confidence_threshold,
        )

        # ================================================================
        # Step 7.5: Cross-field consistency checks (NEW)
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.SCORING,
            progress=0.80,
            progress_message="Checking cross-field consistency...",
        )

        rules_engine = RulesEngine()
        consistency_warnings = rules_engine.check_consistency(scored_extractions, hints)

        if consistency_warnings:
            logger.info("Found %d consistency warnings", len(consistency_warnings))
            scored_extractions = rules_engine.apply_warnings_to_extractions(
                scored_extractions, consistency_warnings
            )

        job_manager.append_to_audit_log(
            job_id, "scoring_complete",
            {"consistency_warnings": len(consistency_warnings)}
        )

        final_extractions = scored_extractions

        llm_called = llm_tokens_used > 0
        mismatch_suspected, mismatch_reasons = _compute_mismatch_diagnostics(
            hints=hints,
            extractions=final_extractions,
            retrieval_diagnostics=retrieval_diagnostics,
            llm_called=llm_called,
        )

        # ================================================================
        # Step 7.7: Calculate Quality Metrics
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.SCORING,
            progress=0.82,
            progress_message="Computing quality metrics...",
        )

        from app.services.magic_import.metrics_calculator import MetricsCalculator

        metrics_calculator = MetricsCalculator(
            experiment_id=getattr(settings, "magic_import_experiment_id", None),
            experiment_variant=active_model,
        )

        quality_metrics = metrics_calculator.calculate(
            job_id=job_id,
            template_name=job.template_name,
            extractions=scored_extractions,
            hints=hints,
            index=index,
            tables=table_result,
            llm_provider=active_provider,
            llm_model=active_model,
            llm_tokens=llm_tokens_used,
            llm_latency_ms=int((time.time() - start_time) * 1000),
            retrieval_diagnostics=retrieval_diagnostics,
        )

        job_manager.save_artifact(job_id, "quality_metrics", quality_metrics)

        # Record quality metrics to Prometheus
        record_quality_metrics(
            template_name=job.template_name,
            quality_metrics=quality_metrics,
        )

        # ================================================================
        # Step 8: Validate against template schema
        # ================================================================
        job_manager.update_job_status(
            job_id,
            JobStatus.VALIDATING,
            progress=0.90,
            progress_message="Validating against template schema...",
        )

        from app.services.magic_import.validator import ExtractionValidator

        validator = ExtractionValidator()
        validation_mode = settings.magic_import_validation_mode
        if validation_mode == "off":
            validation_result = ValidationResult(is_valid=True, errors=[], warnings=[], skipped=True)
        else:
            validation_result = validator.validate_extractions(
                final_extractions,
                job.template_name,
                job.template_status,
                job.template_version,
                mode="strict" if validation_mode == "strict" else "warn",
            )

        logger.info(
            "Validation complete: valid=%s, errors=%d, warnings=%d",
            validation_result.is_valid,
            len(validation_result.errors),
            len(validation_result.warnings),
        )

        # ================================================================
        # Step 9: Calculate statistics and save result
        # ================================================================
        fields_needing_review = sum(1 for e in final_extractions if e.needs_review)
        avg_confidence = (
            sum(e.confidence for e in final_extractions) / len(final_extractions)
            if final_extractions
            else 0.0
        )

        unmapped_findings = _build_unmapped_findings(
            hints=hints,
            tables=table_result.tables if table_result else [],
            extractions=final_extractions,
        )

        processing_time = time.time() - start_time

        # Save final extractions artifact
        job_manager.save_artifact(job_id, "extractions", final_extractions)

        # Save result
        result = MagicImportResult(
            job_id=job_id,
            template_name=job.template_name,
            extractions=final_extractions,
            fields_extracted=len(final_extractions),
            fields_needing_review=fields_needing_review,
            average_confidence=avg_confidence,
            llm_provider=active_provider,
            llm_model=active_model,
            processing_time_seconds=processing_time,
            llm_tokens_used=llm_tokens_used,
            llm_prompt_tokens=llm_prompt_tokens,
            llm_completion_tokens=llm_completion_tokens,
            llm_called=llm_called,
            mismatch_suspected=mismatch_suspected,
            mismatch_reasons=mismatch_reasons,
            validation_result=validation_result,
            template_version_used=job.template_version,
            unmapped_findings=unmapped_findings,
            quality_metrics=quality_metrics,
        )
        job_manager.save_result(result)

        # Mark job as done
        job_manager.update_job_status(
            job_id,
            JobStatus.DONE,
            progress=1.0,
            progress_message=f"Extracted {len(final_extractions)} fields ({fields_needing_review} need review)",
        )
        job_manager.append_to_audit_log(
            job_id, "job_complete",
            {
                "fields_extracted": len(final_extractions),
                "fields_needing_review": fields_needing_review,
                "avg_confidence": round(avg_confidence, 3),
                "processing_time_seconds": round(processing_time, 2),
            }
        )

        logger.info(
            "Job %s complete: %d fields, %.1f%% avg confidence, %.1fs",
            job_id,
            len(final_extractions),
            avg_confidence * 100,
            processing_time,
        )

        # Record metrics
        record_magic_import_job(status="success", template_name=job.template_name)
        magic_import_job_duration_seconds.labels(
            template_name=job.template_name
        ).observe(processing_time)

        return {
            "job_id": job_id,
            "status": "done",
            "fields_extracted": len(final_extractions),
            "fields_needing_review": fields_needing_review,
            "average_confidence": avg_confidence,
            "processing_time_seconds": processing_time,
            "tables_found": table_result.total_tables,
            "consistency_warnings": len(consistency_warnings),
            "two_pass_mode": use_two_pass,
        }

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job_manager.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
        )
        job_manager.append_to_audit_log(job_id, "job_failed", {"error": str(e)})

        # Record failure metrics
        processing_time = time.time() - start_time
        record_magic_import_job(status="failed", template_name=job.template_name)
        magic_import_job_duration_seconds.labels(
            template_name=job.template_name
        ).observe(processing_time)

        return {"error": str(e), "job_id": job_id}


def _build_unmapped_findings(
    hints: list,
    tables: list,
    extractions: list[FieldExtraction],
) -> list[UnmappedFinding]:
    """Collect values from tables that do not map to any extraction hints."""
    if not tables:
        return []

    from app.services.magic_import.table_extractor import TableExtractor

    table_extractor = TableExtractor()

    def tokenize(text: str) -> set[str]:
        return {t for t in re.split(r"[^a-zA-Z0-9]+", (text or "").lower()) if t}

    hint_tokens: dict[str, set[str]] = {}
    for hint in hints:
        tokens = set()
        tokens.update(tokenize(hint.label))
        tokens.update(tokenize(hint.path))
        tokens.update(tokenize(" ".join(hint.keywords or [])))
        hint_tokens[hint.path] = tokens

    extracted_values = {str(e.value_raw).strip().lower() for e in extractions if e.value_raw}
    seen: set[tuple[str, int, str]] = set()
    findings: list[UnmappedFinding] = []

    def match_hint(label: str) -> list[str]:
        label_tokens = tokenize(label)
        scored: list[tuple[int, str]] = []
        for path, tokens in hint_tokens.items():
            score = len(label_tokens & tokens)
            if score > 0:
                scored.append((score, path))
        scored.sort(reverse=True)
        return [path for _, path in scored[:3]]

    def is_mapped(label: str) -> bool:
        return len(match_hint(label)) > 0

    for table in tables:
        if table.cols == 2:
            for key, value, confidence in table_extractor.get_key_value_pairs(table):
                if is_mapped(key) or value.lower() in extracted_values:
                    continue
                signature = (value.lower(), table.page, key.lower())
                if signature in seen:
                    continue
                seen.add(signature)
                findings.append(
                    UnmappedFinding(
                        value=value,
                        evidence=EvidenceRef(
                            page=table.page,
                            quote=value,
                            boxes=[table.bbox],
                            method="TEXT",
                            locator_score=0.6,
                        ),
                        suggested_paths=match_hint(key),
                        confidence=confidence,
                        source="table",
                        context=key,
                    )
                )
        else:
            rows = table_extractor.get_table_rows(table)
            data_rows = rows[1:] if table.headers else rows
            for col_idx, header in enumerate(table.headers):
                header_text = (header or "").strip()
                if not header_text:
                    continue
                if is_mapped(header_text):
                    continue
                for row in data_rows:
                    if col_idx >= len(row):
                        continue
                    value = (row[col_idx] or "").strip()
                    if not value:
                        continue
                    if value.lower() in extracted_values:
                        continue
                    signature = (value.lower(), table.page, header_text.lower())
                    if signature in seen:
                        continue
                    seen.add(signature)
                    findings.append(
                        UnmappedFinding(
                            value=value,
                            evidence=EvidenceRef(
                                page=table.page,
                                quote=value,
                                boxes=[table.bbox],
                                method="TEXT",
                                locator_score=0.6,
                            ),
                            suggested_paths=match_hint(header_text),
                            confidence=0.6,
                            source="table",
                            context=header_text,
                        )
                    )

    return findings


def _compute_mismatch_diagnostics(
    hints: list,
    extractions: list[FieldExtraction],
    retrieval_diagnostics: list[dict] | None,
    llm_called: bool,
) -> tuple[bool, list[str]]:
    """Heuristically detect template/document mismatch."""
    reasons: list[str] = []

    if llm_called:
        if not extractions:
            reasons.append("llm_returned_no_fields")
        else:
            non_empty = [e for e in extractions if str(e.value_raw).strip()]
            if not non_empty:
                reasons.append("all_fields_empty")

        if extractions and all(e.evidence is None for e in extractions):
            reasons.append("no_evidence_localized")

    if retrieval_diagnostics:
        total = len(retrieval_diagnostics)
        matched = 0
        for diag in retrieval_diagnostics:
            if diag.get("match_count", 0) > 0 or diag.get("anchor_match_count", 0) > 0:
                matched += 1
        if total > 0:
            match_rate = matched / total
            if matched == 0:
                reasons.append("no_keyword_matches")
            elif match_rate < 0.15:
                reasons.append("low_keyword_match_rate")

    mismatch_suspected = llm_called and bool(reasons)
    return mismatch_suspected, reasons


@shared_task(name="magic_import.cleanup_expired")
def cleanup_expired_jobs() -> dict:
    """Periodic task to clean up expired jobs."""
    from app.services.magic_import.job_manager import JobManager

    job_manager = JobManager()
    deleted = job_manager.cleanup_expired_jobs()
    return {"deleted_count": deleted}
