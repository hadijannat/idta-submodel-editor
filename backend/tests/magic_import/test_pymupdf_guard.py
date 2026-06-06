"""Tests for PyMuPDF production safety guard."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.config import Settings
from app.services.magic_import.pymupdf_guard import (
    UnsafePyMuPDFError,
    assert_pymupdf_allowed,
    assess_pymupdf_safety,
)


def _production_settings(**overrides) -> Settings:
    values = {
        "env": "production",
        "secret_key": "secure-secret-key-with-at-least-32-characters",
        "oidc_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_assess_pymupdf_safety_flags_current_vulnerable_mupdf():
    fake_fitz = SimpleNamespace(VersionBind="1.27.2.3", VersionFitz="1.27.2")

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        safety = assess_pymupdf_safety()

    assert safety.is_safe is False
    assert safety.pymupdf_version == "1.27.2.3"
    assert safety.mupdf_version == "1.27.2"
    assert "CVE-2026-3308" in safety.reason


def test_pymupdf_guard_blocks_vulnerable_mupdf_in_production():
    fake_fitz = SimpleNamespace(VersionBind="1.27.2.3", VersionFitz="1.27.2")

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        with pytest.raises(UnsafePyMuPDFError, match="Magic Import PDF processing"):
            assert_pymupdf_allowed(_production_settings())


def test_pymupdf_guard_allows_explicit_production_override():
    fake_fitz = SimpleNamespace(VersionBind="1.27.2.3", VersionFitz="1.27.2")

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        assert_pymupdf_allowed(
            _production_settings(magic_import_allow_vulnerable_pymupdf=True)
        )


def test_pymupdf_guard_allows_future_patched_mupdf_in_production():
    fake_fitz = SimpleNamespace(VersionBind="1.27.3", VersionFitz="1.27.3")

    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        assert_pymupdf_allowed(_production_settings())
