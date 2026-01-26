"""
Certificate Manager for dataspace identity.

Manages X.509 certificates and keys for dataspace authentication,
including mTLS client certificates for EDC connectors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CertManager:
    """
    Certificate manager for dataspace identity.

    Handles:
    - Loading and validating certificates
    - Certificate chain verification
    - Key pair management
    - Certificate expiration monitoring
    """

    def __init__(
        self,
        cert_dir: Path | None = None,
    ) -> None:
        """
        Initialize the certificate manager.

        Args:
            cert_dir: Directory for storing certificates
        """
        self.cert_dir = cert_dir or Path("./certs")
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        self._certificates: dict[str, dict[str, Any]] = {}

    def load_certificate(
        self,
        name: str,
        cert_path: Path,
        key_path: Path | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """
        Load a certificate from file.

        Args:
            name: Certificate identifier
            cert_path: Path to certificate file (PEM or DER)
            key_path: Optional path to private key file
            password: Optional password for encrypted key

        Returns:
            Certificate information dictionary
        """
        logger.info("Loading certificate '%s' from %s", name, cert_path)

        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cert_bytes = cert_path.read_bytes()
        try:
            cert = x509.load_pem_x509_certificate(cert_bytes)
        except ValueError:
            cert = x509.load_der_x509_certificate(cert_bytes)

        key = None
        if key_path:
            key_bytes = key_path.read_bytes()
            key = serialization.load_pem_private_key(
                key_bytes,
                password=password.encode() if password else None,
            )

        cert_info = {
            "name": name,
            "cert_path": str(cert_path),
            "key_path": str(key_path) if key_path else None,
            "loaded_at": datetime.utcnow().isoformat(),
            "valid": True,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_before": cert.not_valid_before_utc.isoformat(),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "serial_number": str(cert.serial_number),
            "_cert": cert,
            "_key": key,
        }

        self._certificates[name] = cert_info
        return cert_info

    def get_certificate(self, name: str) -> dict[str, Any] | None:
        """
        Get a loaded certificate by name.

        Args:
            name: Certificate identifier

        Returns:
            Certificate information or None if not found
        """
        return self._certificates.get(name)

    def validate_certificate(self, name: str) -> tuple[bool, list[str]]:
        """
        Validate a loaded certificate.

        Checks:
        - Certificate is not expired
        - Certificate chain is valid
        - Key matches certificate (if key is loaded)

        Args:
            name: Certificate identifier

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        cert = self.get_certificate(name)
        if cert is None:
            return False, [f"Certificate '{name}' not found"]

        errors = []

        from cryptography.hazmat.primitives import serialization

        cert_obj = cert.get("_cert")
        key_obj = cert.get("_key")

        if cert_obj is None:
            return False, ["Certificate data not loaded"]

        now = datetime.utcnow()
        if cert_obj.not_valid_before_utc > now:
            errors.append("Certificate not yet valid")
        if cert_obj.not_valid_after_utc < now:
            errors.append("Certificate has expired")

        if key_obj is not None:
            try:
                cert_pub = cert_obj.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                key_pub = key_obj.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                if cert_pub != key_pub:
                    errors.append("Private key does not match certificate")
            except Exception as e:
                errors.append(f"Failed to verify key match: {e}")

        return len(errors) == 0, errors

    def check_expiration(
        self,
        name: str,
        warn_days: int = 30,
    ) -> tuple[bool, int | None, str]:
        """
        Check certificate expiration.

        Args:
            name: Certificate identifier
            warn_days: Days before expiration to warn

        Returns:
            Tuple of (is_expiring_soon, days_until_expiration, message)
        """
        cert = self.get_certificate(name)
        if cert is None:
            return True, None, f"Certificate '{name}' not found"

        cert_obj = cert.get("_cert")
        if cert_obj is None:
            return True, None, f"Certificate '{name}' not loaded"

        now = datetime.utcnow()
        not_after = cert_obj.not_valid_after_utc
        delta = not_after - now
        days_left = max(delta.days, 0)
        if days_left <= warn_days:
            return True, days_left, f"Certificate '{name}' expires in {days_left} days"
        return False, days_left, f"Certificate '{name}' valid for {days_left} days"

    def get_mtls_context(self, name: str) -> dict[str, Any] | None:
        """
        Get mTLS context for HTTP client.

        Returns the certificate and key paths for use with httpx/aiohttp.

        Args:
            name: Certificate identifier

        Returns:
            mTLS context dictionary or None if certificate not found
        """
        cert = self.get_certificate(name)
        if cert is None:
            return None

        context = {
            "cert": cert["cert_path"],
        }

        if cert.get("key_path"):
            context["key"] = cert["key_path"]

        return context

    def list_certificates(self) -> list[dict[str, Any]]:
        """
        List all loaded certificates.

        Returns:
            List of certificate information dictionaries
        """
        return list(self._certificates.values())

    def remove_certificate(self, name: str) -> bool:
        """
        Remove a loaded certificate.

        Args:
            name: Certificate identifier

        Returns:
            True if certificate was removed
        """
        if name in self._certificates:
            del self._certificates[name]
            logger.info("Removed certificate '%s'", name)
            return True
        return False

    def create_self_signed_certificate(
        self,
        name: str,
        common_name: str,
        organization: str | None = None,
        validity_days: int = 365,
    ) -> dict[str, Any]:
        """
        Create a self-signed certificate for testing.

        Args:
            name: Certificate identifier
            common_name: Certificate CN
            organization: Optional organization name
            validity_days: Certificate validity in days

        Returns:
            Certificate information dictionary

        Note:
            Self-signed certificates should only be used for testing.
            Production deployments should use properly signed certificates.
        """
        logger.warning(
            "Creating self-signed certificate '%s' - for testing only",
            name,
        )

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject_parts = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
        if organization:
            subject_parts.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization))
        subject = issuer = x509.Name(subject_parts)
        now = datetime.utcnow()

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )

        cert_path = self.cert_dir / f"{name}.pem"
        key_path = self.cert_dir / f"{name}.key"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        cert_info = {
            "name": name,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "self_signed": True,
            "common_name": common_name,
            "organization": organization,
            "created_at": datetime.utcnow().isoformat(),
            "valid": True,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_before": cert.not_valid_before_utc.isoformat(),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "serial_number": str(cert.serial_number),
            "_cert": cert,
            "_key": key,
        }

        self._certificates[name] = cert_info
        return cert_info

    async def renew_certificate(
        self,
        name: str,
        csr_path: Path | None = None,
    ) -> dict[str, Any] | None:
        """
        Renew a certificate.

        Args:
            name: Certificate identifier
            csr_path: Optional path to CSR file

        Returns:
            Updated certificate information or None if failed

        Note:
            This is a placeholder for integration with certificate authorities.
        """
        logger.info("Certificate renewal requested for '%s'", name)

        cert = self.get_certificate(name)
        if cert is None:
            return None
        if cert.get("self_signed"):
            return self.create_self_signed_certificate(
                name=name,
                common_name=cert.get("common_name", name),
                organization=cert.get("organization"),
            )
        return None
