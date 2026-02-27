"""Tests for template upstream HTTP error mapping."""

import httpx

from app.errors import ErrorCode
from app.routers.templates import _map_upstream_http_error


def _build_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            request=request,
            text=f"upstream status={status_code}",
        )
    )
    with httpx.Client(transport=transport) as client:
        response = client.get("https://api.github.com/repos/example/templates")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    raise AssertionError("Expected HTTPStatusError to be raised")


def test_map_upstream_404_to_upstream_error():
    exc = _build_http_status_error(404)
    mapped = _map_upstream_http_error(exc, fallback_message="fallback")
    assert mapped.code == ErrorCode.UPSTREAM_ERROR
    assert mapped.detail == {
        "error": "fallback",
        "upstream_status": 404,
    }


def test_map_upstream_429_to_rate_limited():
    exc = _build_http_status_error(429)
    mapped = _map_upstream_http_error(exc, fallback_message="fallback")
    assert mapped.code == ErrorCode.UPSTREAM_RATE_LIMITED
    assert mapped.detail == {
        "error": "fallback",
        "upstream_status": 429,
    }


def test_map_upstream_503_to_unavailable():
    exc = _build_http_status_error(503)
    mapped = _map_upstream_http_error(exc, fallback_message="fallback")
    assert mapped.code == ErrorCode.UPSTREAM_UNAVAILABLE
    assert mapped.detail == {
        "error": "fallback",
        "upstream_status": 503,
    }


def test_map_upstream_500_to_generic_upstream_error():
    exc = _build_http_status_error(500)
    mapped = _map_upstream_http_error(exc, fallback_message="fallback")
    assert mapped.code == ErrorCode.UPSTREAM_ERROR
    assert mapped.detail == {
        "error": "fallback",
        "upstream_status": 500,
    }
