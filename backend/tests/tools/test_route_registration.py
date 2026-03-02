"""Regression tests for tool route registration lifecycle."""

from collections import Counter

from fastapi.testclient import TestClient

from app.main import create_application
from app.routers.tools import get_registry


def _route_duplicates(app) -> list[tuple[tuple[str, str], int]]:
    """Return duplicate (method, path) route entries."""
    keys = [
        (method, route.path)
        for route in app.routes
        for method in (route.methods or set())
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    ]
    counts = Counter(keys)
    return [(key, count) for key, count in counts.items() if count > 1]


def _route_occurrences(app, *, path: str, method: str) -> int:
    return sum(
        1
        for route in app.routes
        if route.path == path and method in (route.methods or set())
    )


def test_tool_routes_not_duplicated_after_startup():
    """Tool routers should be included exactly once across app lifecycle."""
    app = create_application()

    assert _route_duplicates(app) == []

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert _route_duplicates(app) == []


def test_route_count_stable_across_startup_and_openapi():
    """Startup and OpenAPI generation should not register routes repeatedly."""
    app = create_application()
    manifest_count_before = _route_occurrences(
        app,
        path="/api/tools/manifest",
        method="GET",
    )
    tools_count_before = _route_occurrences(app, path="/api/tools", method="GET")

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert _route_duplicates(app) == []
        schema = app.openapi()
        assert "paths" in schema
        assert _route_duplicates(app) == []
        assert _route_occurrences(app, path="/api/tools/manifest", method="GET") == (
            manifest_count_before
        )
        assert _route_occurrences(app, path="/api/tools", method="GET") == (
            tools_count_before
        )


def test_metrics_route_exposed_and_scrapeable():
    """Metrics route should be mounted once and return Prometheus text output."""
    app = create_application()
    metrics_count_before = _route_occurrences(app, path="/metrics", method="GET")

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "idta_submodel_editor_info" in response.text
        assert _route_duplicates(app) == []
        assert _route_occurrences(app, path="/metrics", method="GET") == (
            metrics_count_before
        )


def test_tool_registry_bootstrapped_before_lifespan_startup():
    """Global tool registry should be available before lifespan startup runs."""
    create_application()

    registry = get_registry()
    payload = registry.get_tool_manifest()
    assert isinstance(payload, list)
    assert payload
    assert all(item["initialized"] is False for item in payload)
