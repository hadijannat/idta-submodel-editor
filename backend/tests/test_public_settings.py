"""Tests for the public settings endpoint contract."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_application


def test_public_settings_reflect_effective_dataspace_flag():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(
            dataspace_enabled=False,
            settings_storage_dir=Path(tmp_dir),
        )

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.services.settings_service.get_settings", return_value=settings),
            patch("app.routers.settings.get_settings", return_value=settings),
        ):
            app = create_application()
            with TestClient(app) as client:
                initial_public = client.get("/api/settings")
                assert initial_public.status_code == 200
                assert initial_public.json()["dataspace_enabled"] is False
                assert "dpp_enabled" in initial_public.json()

                update = client.put(
                    "/api/settings/features",
                    json={"dataspace_enabled": True},
                )
                assert update.status_code == 200
                assert update.json()["dataspace_enabled"] is True

                effective_public = client.get("/api/settings")
                assert effective_public.status_code == 200
                assert effective_public.json()["dataspace_enabled"] is True
