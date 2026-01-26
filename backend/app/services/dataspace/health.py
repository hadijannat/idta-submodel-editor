"""
Health checking for dataspace connections.

Provides health checks for all dataspace components:
- Digital Twin Registry connectivity
- EDC Connector availability
- Identity provider status
"""

from __future__ import annotations

import logging
import time
from typing import Any
from datetime import datetime, timezone

from app.services.dataspace.models import (
    ConnectionState,
    HealthCheckResult,
)

logger = logging.getLogger(__name__)


class DataspaceHealthChecker:
    """
    Health checker for dataspace connections.

    Verifies connectivity to all dataspace components and reports status.
    """

    def check_connection(
        self,
        connection: ConnectionState,
        secrets: dict[str, Any] | None = None,
    ) -> list[HealthCheckResult]:
        """
        Run all health checks for a connection.

        Args:
            connection: Connection state to check

        Returns:
            List of health check results for each component
        """
        results = []

        # Check DTR connectivity
        if connection.dtr_url:
            results.append(self._check_dtr(connection, secrets))

        # Check EDC connectivity
        if connection.edc_url:
            results.append(self._check_edc(connection, secrets))

        # Check provider URL
        if connection.provider_url:
            results.append(self._check_provider(connection, secrets))

        return results

    def _check_dtr(
        self,
        connection: ConnectionState,
        secrets: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """
        Check Digital Twin Registry health.

        Args:
            connection: Connection with DTR URL

        Returns:
            Health check result for DTR
        """
        start_time = time.time()

        try:
            headers = {}
            token = (secrets or {}).get("dtr_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            healthy, message, latency_ms = self._probe_endpoint(
                connection.dtr_url,
                headers=headers,
            )
            return HealthCheckResult(
                component="dtr",
                healthy=healthy,
                latency_ms=latency_ms,
                message=message,
                checked_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning("DTR health check failed: %s", e)

            return HealthCheckResult(
                component="dtr",
                healthy=False,
                latency_ms=latency_ms,
                message=str(e),
                checked_at=datetime.now(timezone.utc),
            )

    def _check_edc(
        self,
        connection: ConnectionState,
        secrets: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """
        Check EDC Connector health.

        Args:
            connection: Connection with EDC URL

        Returns:
            Health check result for EDC
        """
        start_time = time.time()

        try:
            headers = {}
            api_key = (secrets or {}).get("edc_api_key")
            if api_key:
                headers["X-Api-Key"] = api_key

            healthy, message, latency_ms = self._probe_endpoint(
                connection.edc_url,
                headers=headers,
            )
            return HealthCheckResult(
                component="edc",
                healthy=healthy,
                latency_ms=latency_ms,
                message=message,
                checked_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning("EDC health check failed: %s", e)

            return HealthCheckResult(
                component="edc",
                healthy=False,
                latency_ms=latency_ms,
                message=str(e),
                checked_at=datetime.now(timezone.utc),
            )

    def _check_provider(
        self,
        connection: ConnectionState,
        secrets: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """
        Check dataspace provider health.

        Args:
            connection: Connection with provider URL

        Returns:
            Health check result for provider
        """
        start_time = time.time()

        try:
            headers = {}
            token = (secrets or {}).get("provider_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            healthy, message, latency_ms = self._probe_endpoint(
                connection.provider_url,
                headers=headers,
            )
            return HealthCheckResult(
                component="provider",
                healthy=healthy,
                latency_ms=latency_ms,
                message=message,
                checked_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning("Provider health check failed: %s", e)

            return HealthCheckResult(
                component="provider",
                healthy=False,
                latency_ms=latency_ms,
                message=str(e),
                checked_at=datetime.now(timezone.utc),
            )

    def check_all(self, connections: list[ConnectionState]) -> dict[str, list[HealthCheckResult]]:
        """
        Run health checks for multiple connections.

        Args:
            connections: List of connections to check

        Returns:
            Dictionary mapping connection_id to health check results
        """
        results = {}

        for connection in connections:
            try:
                results[connection.connection_id] = self.check_connection(connection)
            except Exception as e:
                logger.exception(
                    "Health check failed for connection %s",
                    connection.connection_id,
                )
                results[connection.connection_id] = [
                    HealthCheckResult(
                        component="overall",
                        healthy=False,
                        message=f"Health check error: {e}",
                        checked_at=datetime.now(timezone.utc),
                    )
                ]

        return results

    def _probe_endpoint(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, str | None, float]:
        """
        Probe a health endpoint and return status.

        Returns:
            (healthy, message, latency_ms)
        """
        import httpx

        if not base_url:
            return False, "Missing endpoint URL", 0.0

        candidates = []
        base = base_url.rstrip("/")
        if not base.endswith("/health") and not base.endswith("/actuator/health"):
            candidates.extend([f"{base}/health", f"{base}/actuator/health"])
        candidates.append(base)

        last_error = None
        for url in candidates:
            start_time = time.time()
            try:
                with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                    response = client.get(url, headers=headers)
                latency_ms = (time.time() - start_time) * 1000
                if response.status_code < 400:
                    return True, f"OK ({response.status_code})", latency_ms
                last_error = f"HTTP {response.status_code}"
            except httpx.HTTPError as e:
                latency_ms = (time.time() - start_time) * 1000
                last_error = str(e)
        return False, last_error or "Health check failed", latency_ms
