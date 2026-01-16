"""Helpers for semantic identifier normalization."""

from __future__ import annotations

import re

IRI_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
ECLASS_IRDI_PATTERN = re.compile(r"\d{4}-\d#\d{2}-[A-Z0-9]{3}[A-Z0-9]{3}#\d{3}")
IEC_CDD_PATTERN = re.compile(r"\d{4}/\d///61360_4#[A-Z0-9_]+")


def normalize_identifier(identifier: str) -> tuple[str, str | None]:
    """
    Normalize an identifier into (canonical_id, canonical_iri).

    If the identifier is an IRI, attempts to extract an IRDI-like substring.
    Falls back to the full IRI when no canonical ID can be inferred.
    """
    raw = identifier.strip()
    if not raw:
        return (raw, None)

    if IRI_PATTERN.match(raw):
        extracted = _extract_irdi_like(raw)
        return (extracted or raw, raw)

    return (raw, None)


def _extract_irdi_like(value: str) -> str | None:
    for pattern in (ECLASS_IRDI_PATTERN, IEC_CDD_PATTERN):
        match = pattern.search(value)
        if match:
            return match.group(0)
    # Attempt to use the tail segment as a best-effort fallback.
    tail = value.rstrip("/").split("/")[-1]
    return tail or None
