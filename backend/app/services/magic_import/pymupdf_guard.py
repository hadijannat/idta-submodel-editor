"""Runtime guard for PyMuPDF-backed untrusted PDF processing."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.config import Settings, get_settings


UNSAFE_MUPDF_MAX = (1, 27, 2)


class UnsafePyMuPDFError(RuntimeError):
    """Raised when production PDF parsing would use an unsafe PyMuPDF build."""


@dataclass(frozen=True)
class PyMuPDFSafety:
    is_safe: bool
    reason: str
    pymupdf_version: str | None
    mupdf_version: str | None


def _parse_version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    parts = [int(part) for part in re.findall(r"\d+", value)[:3]]
    if len(parts) < 3:
        return None
    return tuple(parts)


def assess_pymupdf_safety() -> PyMuPDFSafety:
    """Assess whether the installed PyMuPDF embeds a MuPDF build past CVE-2026-3308."""
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        return PyMuPDFSafety(
            is_safe=False,
            reason=f"PyMuPDF version could not be inspected: {exc}",
            pymupdf_version=None,
            mupdf_version=None,
        )

    pymupdf_version = getattr(fitz, "VersionBind", None) or getattr(
        fitz, "pymupdf_version", None
    )
    mupdf_version = getattr(fitz, "VersionFitz", None) or getattr(
        fitz, "mupdf_version", None
    )
    parsed_mupdf = _parse_version(mupdf_version)

    if parsed_mupdf is None:
        return PyMuPDFSafety(
            is_safe=False,
            reason="MuPDF version could not be inspected",
            pymupdf_version=str(pymupdf_version) if pymupdf_version else None,
            mupdf_version=str(mupdf_version) if mupdf_version else None,
        )

    if parsed_mupdf <= UNSAFE_MUPDF_MAX:
        return PyMuPDFSafety(
            is_safe=False,
            reason=(
                f"MuPDF {mupdf_version} is at or below the vulnerable "
                "CVE-2026-3308 range for untrusted PDF parsing"
            ),
            pymupdf_version=str(pymupdf_version) if pymupdf_version else None,
            mupdf_version=str(mupdf_version) if mupdf_version else None,
        )

    return PyMuPDFSafety(
        is_safe=True,
        reason=f"MuPDF {mupdf_version} is newer than the known vulnerable range",
        pymupdf_version=str(pymupdf_version) if pymupdf_version else None,
        mupdf_version=str(mupdf_version) if mupdf_version else None,
    )


def assert_pymupdf_allowed(settings: Settings | None = None) -> None:
    """Fail closed for production Magic Import PDF parsing unless explicitly allowed."""
    settings = settings or get_settings()
    if settings.env != "production" or settings.magic_import_allow_vulnerable_pymupdf:
        return

    safety = assess_pymupdf_safety()
    if safety.is_safe:
        return

    detail = (
        "Magic Import PDF processing is disabled in production because the "
        "installed PyMuPDF/MuPDF build is vulnerable or unknown. "
        "Upgrade to a PyMuPDF build with the MuPDF CVE-2026-3308 fix, run PDF "
        "processing in a hardened sandbox, or set "
        "MAGIC_IMPORT_ALLOW_VULNERABLE_PYMUPDF=true only after accepting that risk."
    )
    versions = []
    if safety.pymupdf_version:
        versions.append(f"PyMuPDF {safety.pymupdf_version}")
    if safety.mupdf_version:
        versions.append(f"MuPDF {safety.mupdf_version}")
    if versions:
        detail = f"{detail} Detected {' / '.join(versions)}."
    raise UnsafePyMuPDFError(detail)
