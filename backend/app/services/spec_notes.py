"""
Requirements from the specification PDF, matched to the elements of a form.

The AASX/JSON of a template is the source of truth for its structure. The
specification PDF adds what the package often lacks: explanatory notes,
constraints written in prose, example values and the page where an element
is specified. This service extracts those per-element rows (see
``spec_pdf``), caches the result next to the template cache, and matches the
rows to the elements of the parsed UI schema.

Everything here is guidance for the person filling in the form. It never
changes validation, and a missing or unreadable PDF simply yields no notes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.services.fetcher import TemplateFetcherService
from app.services.spec_pdf import SpecDocument, SpecElement, extract_spec_document
from app.services.template_repo import RepoFile

logger = logging.getLogger(__name__)

# Bump when the extraction heuristics change so cached results are rebuilt.
_EXTRACTOR_VERSION = 1

_locks: dict[str, asyncio.Lock] = {}


def _cache_path(cache_dir: Path, file: RepoFile) -> Path:
    key = hashlib.md5(file.path.encode()).hexdigest()
    revision = (file.sha or "nosha")[:16]
    return cache_dir / f"{key}-{revision}-v{_EXTRACTOR_VERSION}.spec.json"


async def load_spec_document(
    fetcher: TemplateFetcherService, pdf: RepoFile
) -> SpecDocument:
    """Extract the specification rows of a PDF, using the disk cache."""
    cache_file = _cache_path(fetcher.cache_dir, pdf)
    lock = _locks.setdefault(str(cache_file), asyncio.Lock())
    async with lock:
        if cache_file.exists():
            try:
                return SpecDocument.from_dict(json.loads(cache_file.read_text()))
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Ignoring unreadable specification cache %s", cache_file)

        pdf_bytes = await fetcher.fetch_repo_file(pdf)
        document = await asyncio.to_thread(extract_spec_document, pdf_bytes)
        try:
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(document.to_dict()))
            tmp.replace(cache_file)
        except OSError as exc:
            logger.warning("Could not cache specification notes: %s", exc)
        return document


def _compatible(spec: SpecElement, schema_elem: dict[str, Any]) -> bool:
    """Reject matches where the specification row describes another element type."""
    if not spec.sme_type:
        return True
    model_type = schema_elem.get("modelType")
    if spec.sme_type == model_type:
        return True
    containers = {"SubmodelElementCollection", "SubmodelElementList", "Entity"}
    # Lists and collections are used interchangeably across template versions.
    return spec.sme_type in containers and model_type in containers


def match_spec_to_schema(
    document: SpecDocument, schema: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """
    Match specification rows to schema elements.

    Returns ``(notes, matched, total)`` where ``notes`` maps the idShort path
    of an element (list items share the path of their list) to its
    specification entry.
    """
    notes: dict[str, dict[str, Any]] = {}
    counters = {"matched": 0, "total": 0}

    def visit(element: dict[str, Any], parent_id: str | None, path: str) -> None:
        id_short = element.get("idShort") or ""
        counters["total"] += 1
        spec = document.lookup(id_short, parent=parent_id) if id_short else None
        if spec is not None and _compatible(spec, element):
            counters["matched"] += 1
            template_cardinality = element.get("cardinality")
            entry = {
                "idShort": id_short,
                "cardinality": spec.cardinality,
                "templateCardinality": template_cardinality,
                "notes": list(spec.notes),
                "example": spec.example,
                "description": spec.description,
                "page": spec.page,
            }
            notes.setdefault(path, entry)

        for key in ("elements", "statements"):
            for child in element.get(key) or []:
                child_id = child.get("idShort") or ""
                visit(child, id_short, f"{path}.{child_id}" if path else child_id)

        if element.get("modelType") == "SubmodelElementList":
            item = element.get("itemTemplate") or next(iter(element.get("items") or []), None)
            # List items have no idShort of their own; their children are
            # specified in the table of the list (or of its item collection).
            for key in ("elements", "statements"):
                for child in (item or {}).get(key) or []:
                    child_id = child.get("idShort") or ""
                    visit(child, id_short, f"{path}.{child_id}" if path else child_id)

    for element in schema.get("elements") or []:
        root_id = element.get("idShort") or ""
        visit(element, schema.get("idShort"), root_id)

    return notes, counters["matched"], counters["total"]


async def get_specification_notes(
    fetcher: TemplateFetcherService,
    schema: dict[str, Any],
    template_path: str,
) -> dict[str, Any]:
    """Specification notes for the elements of a template schema."""
    empty: dict[str, Any] = {
        "available": False,
        "document": None,
        "pageCount": None,
        "matched": 0,
        "total": 0,
        "notes": {},
    }
    resolved = await fetcher.resolve_in_index(template_path)
    if resolved is None or resolved.version.pdf is None:
        return empty

    pdf = resolved.version.pdf
    document = await load_spec_document(fetcher, pdf)
    notes, matched, total = match_spec_to_schema(document, schema)
    return {
        "available": bool(document.elements),
        "document": {"name": pdf.name, "path": pdf.path, "size": pdf.size},
        "pageCount": document.page_count,
        "matched": matched,
        "total": total,
        "notes": notes,
    }
