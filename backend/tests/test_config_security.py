"""Security guardrail tests for settings validation."""

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
