from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.semantic.eclass_online_provider import EclassOnlineProvider


def _build_provider(
    tmp_path: Path,
    *,
    with_key: bool,
    cert_password: str | None = None,
) -> tuple[EclassOnlineProvider, Path, Path | None]:
    cert_path = tmp_path / "client-cert.pem"
    cert_path.write_text("placeholder cert")

    key_path = None
    if with_key:
        key_path = tmp_path / "client-key.pem"
        key_path.write_text("placeholder key")

    provider = EclassOnlineProvider(
        base_url="https://example.com",
        search_url="/search",
        resolve_url="/resolve",
        cert_path=cert_path,
        key_path=key_path,
        cert_password=cert_password,
        enabled=True,
        cache_ttl_seconds=60,
        cache_max_entries=10,
        search_rate_limit=100,
        resolve_rate_limit=100,
        timeout_seconds=5.0,
    )
    return provider, cert_path, key_path


@pytest.mark.asyncio
async def test_request_json_uses_ssl_context_with_cert_and_key(tmp_path: Path):
    provider, cert_path, key_path = _build_provider(
        tmp_path, with_key=True, cert_password="secret"
    )
    assert key_path is not None

    mock_context = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"ok": True}

    with patch(
        "app.services.semantic.eclass_online_provider.ssl.create_default_context",
        return_value=mock_context,
    ) as mock_create_context:
        with patch(
            "app.services.semantic.eclass_online_provider.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            payload = await provider._request_json(
                "https://example.com/search", params={"q": "torque"}
            )

    assert payload == {"ok": True}
    mock_create_context.assert_called_once_with()
    mock_context.load_cert_chain.assert_called_once_with(
        certfile=str(cert_path),
        keyfile=str(key_path),
        password="secret",
    )
    mock_client_class.assert_called_once_with(timeout=5.0, verify=mock_context)
    mock_client.get.assert_awaited_once_with(
        "https://example.com/search", params={"q": "torque"}
    )


@pytest.mark.asyncio
async def test_request_json_uses_ssl_context_with_cert_only(tmp_path: Path):
    provider, cert_path, key_path = _build_provider(tmp_path, with_key=False)
    assert key_path is None

    mock_context = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"ok": True}

    with patch(
        "app.services.semantic.eclass_online_provider.ssl.create_default_context",
        return_value=mock_context,
    ) as mock_create_context:
        with patch(
            "app.services.semantic.eclass_online_provider.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            payload = await provider._request_json(
                "https://example.com/resolve", params={"id": "123"}
            )

    assert payload == {"ok": True}
    mock_create_context.assert_called_once_with()
    mock_context.load_cert_chain.assert_called_once_with(
        certfile=str(cert_path),
        keyfile=None,
        password=None,
    )
    mock_client_class.assert_called_once_with(timeout=5.0, verify=mock_context)
    mock_client.get.assert_awaited_once_with(
        "https://example.com/resolve", params={"id": "123"}
    )


@pytest.mark.asyncio
async def test_request_json_uses_default_tls_verification_without_client_cert():
    provider = EclassOnlineProvider(
        base_url="https://example.com",
        search_url="/search",
        resolve_url="/resolve",
        cert_path=None,
        key_path=None,
        cert_password=None,
        enabled=True,
        cache_ttl_seconds=60,
        cache_max_entries=10,
        search_rate_limit=100,
        resolve_rate_limit=100,
        timeout_seconds=5.0,
    )

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"ok": True}

    with patch(
        "app.services.semantic.eclass_online_provider.ssl.create_default_context"
    ) as mock_create_context:
        with patch(
            "app.services.semantic.eclass_online_provider.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            payload = await provider._request_json(
                "https://example.com/search", params={"q": "no-cert"}
            )

    assert payload == {"ok": True}
    mock_create_context.assert_not_called()
    mock_client_class.assert_called_once_with(timeout=5.0, verify=True)
    mock_client.get.assert_awaited_once_with(
        "https://example.com/search", params={"q": "no-cert"}
    )
