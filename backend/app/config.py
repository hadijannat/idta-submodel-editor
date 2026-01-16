"""
Application configuration using Pydantic Settings.

Supports environment variables and .env files for configuration.
"""

from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production", min_length=32)

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # CORS
    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:5173"]

    # GitHub API
    github_token: str | None = None
    github_repo: str = "admin-shell-io/submodel-templates"
    github_api_version: str = "2022-11-28"

    # Caching
    cache_dir: Path = Path("./cache/templates")
    cache_ttl_hours: int = 24

    # Semantic dictionary lookup
    semantic_enabled: bool = True
    semantic_prefer_iri: bool = True
    semantic_embed_concept_descriptions: bool = False
    semantic_eclass_offline_enabled: bool = True
    semantic_iec_cdd_offline_enabled: bool = True
    semantic_eclass_online_enabled: bool = False
    semantic_cache_ttl_seconds: int = 86400
    semantic_cache_max_entries: int = 512
    semantic_search_rate_limit_per_min: int = 60
    semantic_resolve_rate_limit_per_min: int = 120
    semantic_index_dir: Path = Path("./cache/semantic")
    eclass_index_path: Path = Path("./cache/semantic/eclass.json")
    iec_cdd_index_path: Path = Path("./cache/semantic/iec_cdd.json")

    # ECLASS online provider
    eclass_api_base: str = ""
    eclass_search_url: str | None = None
    eclass_resolve_url: str | None = None
    eclass_cert_path: Path | None = None
    eclass_key_path: Path | None = None
    eclass_cert_password: str | None = None

    # File upload limits
    max_upload_size_mb: int = 50

    # OAuth2/OIDC
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""
    oidc_audience: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    # Redis (for distributed caching)
    redis_url: str | None = None

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # PDF generation
    pdf_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            value = v.strip()
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("cache_dir", mode="before")
    @classmethod
    def parse_cache_dir(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v

    @field_validator(
        "semantic_index_dir",
        "eclass_index_path",
        "iec_cdd_index_path",
        mode="before",
    )
    @classmethod
    def parse_semantic_paths(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v

    @field_validator("eclass_cert_path", "eclass_key_path", mode="before")
    @classmethod
    def parse_cert_paths(cls, v):
        if isinstance(v, str) and v.strip():
            return Path(v)
        return None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
