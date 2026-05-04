"""Tests for dataspace certificate management."""

from pathlib import Path

from app.services.dataspace.identity.cert_manager import CertManager


def test_self_signed_certificate_can_be_reloaded_and_validated(tmp_path: Path):
    manager = CertManager(cert_dir=tmp_path)
    created = manager.create_self_signed_certificate(
        name="client",
        common_name="client.example.test",
        organization="Example Org",
    )

    reloaded = CertManager(cert_dir=tmp_path)
    loaded = reloaded.load_certificate(
        name="client",
        cert_path=Path(created["cert_path"]),
        key_path=Path(created["key_path"]),
    )

    assert "CN=client.example.test" in loaded["subject"]
    assert loaded["key_path"] == created["key_path"]
    valid, errors = reloaded.validate_certificate("client")
    assert valid is True
    assert errors == []
    assert reloaded.get_mtls_context("client") == {
        "cert": created["cert_path"],
        "key": created["key_path"],
    }


def test_certificate_validation_rejects_mismatched_private_key(tmp_path: Path):
    manager = CertManager(cert_dir=tmp_path)
    first = manager.create_self_signed_certificate("first", "first.example.test")
    second = manager.create_self_signed_certificate("second", "second.example.test")

    reloaded = CertManager(cert_dir=tmp_path)
    reloaded.load_certificate(
        name="mismatch",
        cert_path=Path(first["cert_path"]),
        key_path=Path(second["key_path"]),
    )

    valid, errors = reloaded.validate_certificate("mismatch")

    assert valid is False
    assert "Private key does not match certificate" in errors
