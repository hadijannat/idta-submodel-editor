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
            dpp_enabled=False,
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
                assert initial_public.json()["magic_import_enabled"] is True
                assert initial_public.json()["dpp_enabled"] is False

                update = client.put(
                    "/api/settings/features",
                    json={"dataspace_enabled": True},
                )
                assert update.status_code == 200
                assert update.json()["dataspace_enabled"] is True

                effective_public = client.get("/api/settings")
                assert effective_public.status_code == 200
                assert effective_public.json()["dataspace_enabled"] is True


def test_settings_defaults_keep_prototype_tools_disabled(monkeypatch):
    monkeypatch.delenv("DPP_ENABLED", raising=False)
    monkeypatch.delenv("MNESTIX_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.dpp_enabled is False
    assert settings.mnestix_enabled is False


def test_public_settings_default_response_hides_disabled_integrations(monkeypatch):
    monkeypatch.delenv("DPP_ENABLED", raising=False)
    monkeypatch.delenv("MNESTIX_ENABLED", raising=False)

    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(_env_file=None, settings_storage_dir=Path(tmp_dir))

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.services.settings_service.get_settings", return_value=settings),
            patch("app.routers.settings.get_settings", return_value=settings),
        ):
            app = create_application()
            with TestClient(app) as client:
                response = client.get("/api/settings")
                assert response.status_code == 200
                payload = response.json()
                assert payload["dpp_enabled"] is False
                assert payload["mnestix_enabled"] is False
                assert payload["mnestix_url"] is None
                assert payload["basyx_registry_url"] is None


def test_public_settings_falls_back_to_env_flag_when_storage_lookup_fails():
    settings = Settings(
        dataspace_enabled=True,
        dpp_enabled=True,
    )

    with (
        patch("app.main.get_settings", return_value=settings),
        patch("app.services.settings_service.get_settings", return_value=settings),
        patch("app.routers.settings.get_settings", return_value=settings),
        patch(
            "app.services.settings_service._get_feature_flags_path",
            side_effect=OSError("settings storage unavailable"),
        ),
    ):
        app = create_application()
        with TestClient(app) as client:
            response = client.get("/api/settings")
            assert response.status_code == 200
            payload = response.json()
            assert payload["dataspace_enabled"] is True
            assert payload["magic_import_enabled"] is True
            assert payload["dpp_enabled"] is True


def test_feature_flag_update_requires_admin_auth_outside_development():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(
            env="production",
            allow_insecure_prod_auth=True,
            secret_key="production-secret-key-with-32chars-min",
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
                response = client.put(
                    "/api/settings/features",
                    json={"dataspace_enabled": True},
                )
                assert response.status_code == 401


def test_public_settings_reflects_magic_import_env_flag():
    settings = Settings(
        magic_import_enabled=False,
        dataspace_enabled=False,
        dpp_enabled=True,
    )

    with (
        patch("app.main.get_settings", return_value=settings),
        patch("app.services.settings_service.get_settings", return_value=settings),
        patch("app.routers.settings.get_settings", return_value=settings),
    ):
        app = create_application()
        with TestClient(app) as client:
            response = client.get("/api/settings")
            assert response.status_code == 200
            payload = response.json()
            assert payload["magic_import_enabled"] is False
            assert payload["dataspace_enabled"] is False
            assert payload["dpp_enabled"] is True
