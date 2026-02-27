"""Security guardrail tests for settings validation."""

import pytest

from app.config import Settings


def test_production_rejects_default_secret_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            env="production",
            secret_key="change-me-in-production-please-update",
        )


def test_github_template_ref_rejects_git_expression():
    with pytest.raises(ValueError, match="Invalid git ref"):
        Settings(github_template_ref="main@{1}")
