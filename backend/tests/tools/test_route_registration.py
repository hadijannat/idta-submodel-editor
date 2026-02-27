"""Regression tests for tool route registration lifecycle."""

from collections import Counter

from fastapi.testclient import TestClient

from app.main import create_application


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
    count_before = len(app.routes)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        count_after_startup = len(app.routes)
        assert count_after_startup == count_before

        openapi = client.get("/api/openapi.json")
        assert openapi.status_code == 200
        count_after_openapi = len(app.routes)
        assert count_after_openapi == count_before

        tool_manifest_routes = [
            route
            for route in app.routes
            if route.path == "/api/tools/manifest" and "GET" in (route.methods or set())
        ]
        assert len(tool_manifest_routes) == 1
