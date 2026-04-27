"""Regression tests for PDF export dependency compatibility behavior."""

from __future__ import annotations

from importlib.metadata import version as package_version
from pathlib import Path
import sys
import types

from app.services.hydrator import PDFExportService


class _FakeTemplate:
    def __init__(self) -> None:
        self.render_calls = []

    def render(self, **kwargs) -> str:
        self.render_calls.append(kwargs)
        return "<html><body>ok</body></html>"


class _FakeEnvironment:
    def __init__(self, loader) -> None:
        self.loader = loader
        self._template = _FakeTemplate()

    def get_template(self, template_name: str) -> _FakeTemplate:
        assert template_name == "pdf_report.html"
        return self._template


class _FakeHTML:
    def __init__(self, string: str) -> None:
        self.string = string

    def write_pdf(self) -> bytes:
        return b"%PDF-FAKE"


def _install_fake_pdf_modules(monkeypatch, pdf_class: type) -> types.SimpleNamespace:
    fake_jinja2 = types.ModuleType("jinja2")
    fake_jinja2.Environment = _FakeEnvironment
    fake_jinja2.FileSystemLoader = lambda template_dir: template_dir

    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasy_pdf = types.SimpleNamespace(pydyf=types.SimpleNamespace(PDF=pdf_class))
    fake_weasyprint.HTML = _FakeHTML
    fake_weasyprint.pdf = fake_weasy_pdf

    fake_pydyf = types.ModuleType("pydyf")
    fake_pydyf.PDF = pdf_class

    monkeypatch.setitem(sys.modules, "jinja2", fake_jinja2)
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)
    monkeypatch.setitem(sys.modules, "pydyf", fake_pydyf)

    return fake_weasy_pdf


def test_generate_pdf_adds_compat_shim_for_noarg_pydyf(monkeypatch) -> None:
    class NoArgPDF:
        def __init__(self) -> None:
            self.version = None
            self.identifier = None

    fake_weasy_pdf = _install_fake_pdf_modules(monkeypatch, NoArgPDF)
    service = PDFExportService(template_dir="app/templates")

    result = service.generate_pdf({"elements": []}, "pdf_report.html")

    assert result == b"%PDF-FAKE"
    assert fake_weasy_pdf.pydyf.PDF is not NoArgPDF

    compat_pdf = fake_weasy_pdf.pydyf.PDF("1.7", b"id-123")
    assert compat_pdf.version == b"1.7"
    assert compat_pdf.identifier == b"id-123"


def test_generate_pdf_keeps_constructor_when_pydyf_has_args(monkeypatch) -> None:
    class ArgPDF:
        def __init__(self, version: bytes = b"1.7", identifier=None) -> None:
            self.version = version
            self.identifier = identifier

    fake_weasy_pdf = _install_fake_pdf_modules(monkeypatch, ArgPDF)
    service = PDFExportService(template_dir="app/templates")

    result = service.generate_pdf({"elements": []}, "pdf_report.html")

    assert result == b"%PDF-FAKE"
    assert fake_weasy_pdf.pydyf.PDF is ArgPDF


def test_generate_pdf_with_real_pydyf_012_contract() -> None:
    """Exercise the installed WeasyPrint/pydyf integration, not just fakes."""

    from packaging.version import Version
    from weasyprint import pdf as weasy_pdf

    pydyf_version = Version(package_version("pydyf"))
    assert Version("0.12.1") <= pydyf_version < Version("0.13")

    original_pdf_class = weasy_pdf.pydyf.PDF
    try:
        template_dir = Path(__file__).resolve().parents[1] / "app" / "templates"
        pdf_bytes = PDFExportService(template_dir=str(template_dir)).generate_pdf(
            {"elements": []},
            "pdf_report.html",
        )
    finally:
        weasy_pdf.pydyf.PDF = original_pdf_class

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000
    assert b"%%EOF" in pdf_bytes[-128:]
