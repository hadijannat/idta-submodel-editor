"""Security guardrail tests for settings validation."""

from pathlib import Path

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "secret_key",
    [
        "change-me-in-production-please-update",
        " development-secret-key-change-in-production ",
        "change-this-to-a-secure-random-string-in-production",
    ],
)
def test_production_rejects_known_insecure_secret_keys(secret_key: str):
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(env="production", secret_key=secret_key)


@pytest.mark.parametrize(
    "ref",
    ["/main", "main/", "-main", "main@{1}", "main..x", "main//x", "feature.lock/x"],
)
def test_github_template_ref_rejects_unsafe_patterns(ref: str):
    with pytest.raises(ValueError, match="Invalid git ref"):
        Settings(github_template_ref=ref)


@pytest.mark.parametrize("ref", ["main", "release/1.2.3", "feature-x", "a" * 40])
def test_github_template_ref_accepts_safe_patterns(ref: str):
    settings = Settings(github_template_ref=ref)
    assert settings.github_template_ref == ref


def test_github_template_ref_defaults_to_main_when_blank():
    settings = Settings(github_template_ref="   ")
    assert settings.github_template_ref == "main"


def test_production_requires_oidc_or_explicit_insecure_override():
    with pytest.raises(ValueError, match="OIDC_ENABLED"):
        Settings(
            env="production",
            secret_key="secure-secret-key-with-at-least-32-characters",
            oidc_enabled=False,
            allow_insecure_prod_auth=False,
        )


def test_production_allows_explicit_insecure_override():
    settings = Settings(
        env="production",
        secret_key="secure-secret-key-with-at-least-32-characters",
        oidc_enabled=False,
        allow_insecure_prod_auth=True,
    )
    assert settings.allow_insecure_prod_auth is True


def test_production_allows_oidc_enabled():
    settings = Settings(
        env="production",
        secret_key="secure-secret-key-with-at-least-32-characters",
        oidc_enabled=True,
    )
    assert settings.oidc_enabled is True


def test_env_parses_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173")

    settings = Settings()

    assert settings.cors_origins == [
        "http://localhost:8080",
        "http://localhost:5173",
    ]


def test_env_parses_json_cors_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["https://editor.example.com", "https://api.example.com"]',
    )

    settings = Settings()

    assert settings.cors_origins == [
        "https://editor.example.com",
        "https://api.example.com",
    ]


def test_env_parses_boolean_and_path_values(monkeypatch, tmp_path):
    cache_dir = tmp_path / "template-cache"
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("MAGIC_IMPORT_ENABLED", "false")
    monkeypatch.setenv("CACHE_DIR", str(cache_dir))

    settings = Settings()

    assert settings.debug is True
    assert settings.magic_import_enabled is False
    assert settings.cache_dir == Path(cache_dir)


def test_env_production_requires_oidc_or_explicit_insecure_override(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "secure-secret-key-with-at-least-32-characters")
    monkeypatch.setenv("OIDC_ENABLED", "false")
    monkeypatch.setenv("ALLOW_INSECURE_PROD_AUTH", "false")

    with pytest.raises(ValueError, match="OIDC_ENABLED"):
        Settings()
