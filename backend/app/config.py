"""
Application configuration using Pydantic Settings.

Supports environment variables and .env files for configuration.
"""

from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Annotated, ClassVar, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production-please-update", min_length=32)

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # CORS
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:8080",
        "http://localhost:5173",
    ]

    # GitHub API
    github_token: str | None = None
    github_repo: str = "admin-shell-io/submodel-templates"
    github_api_version: str = "2022-11-28"
    github_template_ref: str = "main"

    # Caching
    cache_dir: Path = Path("./cache/templates")
    cache_ttl_hours: int = 24
    mapper_cache_dir: Path = Path("./cache/mapper")

    # Local templates (custom templates not from GitHub)
    local_templates_enabled: bool = True
    local_templates_dir: Path = Path("./templates/local")

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

    # AASX parsing
    aasx_lenient_name_types: bool = True

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
    allow_insecure_prod_auth: bool = False
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

    # Magic Import - Core
    magic_import_enabled: bool = True
    magic_import_cache_dir: Path = Path("./cache/magic_import")
    magic_import_confidence_threshold: float = 0.80
    magic_import_max_pdf_size_mb: int = 50
    magic_import_job_ttl_hours: int = 24

    # Magic Import - LLM Provider (supports openai, anthropic, openrouter, local)
    magic_import_llm_provider: Literal["openai", "anthropic", "openrouter", "local"] = "openai"
    magic_import_llm_model: str = "gpt-4o-mini"
    magic_import_llm_request_timeout_seconds: float = 60.0
    magic_import_llm_max_retries: int = 2
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Settings encryption key (for storing API keys securely)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    settings_encryption_key: str | None = None
    settings_storage_dir: Path = Path("./cache/settings")

    # Magic Import - OCR (Tesseract)
    magic_import_ocr_enabled: bool = True
    magic_import_ocr_language: str = "eng+deu"
    magic_import_ocr_dpi: int = 300
    magic_import_validation_mode: Literal["warn", "strict", "off"] = "warn"

    # Celery + Redis (for background job processing)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # =========================================================================
    # Template Knowledge System
    # =========================================================================
    template_knowledge_enabled: bool = True
    template_knowledge_embedding_model: str = "nomic-embed-text"
    template_knowledge_auto_build: bool = False  # Auto-build index on startup

    # =========================================================================
    # Dataspace Integration
    # =========================================================================

    # Feature flag and general settings
    dataspace_enabled: bool = False
    dataspace_cache_dir: Path = Path("./cache/dataspace")
    dataspace_default_environment: Literal[
        "sandbox",
        "catena-x-test",
        "catena-x-prod",
        "manufacturing-x",
    ] = "sandbox"
    dataspace_default_edc_mode: Literal["tractus-x", "aas-extension"] = "tractus-x"

    # BaSyx AAS Server
    basyx_aas_server_url: str = "http://basyx-aas-server:4001"
    basyx_registry_url: str = "http://basyx-registry:4002"

    # EDC - Tractus-X
    edc_control_plane_url: str = "http://edc-control-plane:19192"
    edc_data_plane_url: str = "http://edc-data-plane:19291"
    edc_api_key: str | None = None

    # EDC - AAS Extension
    edc_aas_extension_url: str | None = None

    # Digital Twin Registry (DTR)
    dtr_url: str = "http://dtr:4003"

    # Vault (for secrets management)
    vault_url: str = "http://vault:8200"
    vault_token: str | None = None

    # Catena-X specific
    catena_x_portal_url: str | None = None
    catena_x_bpn: str | None = None

    # PLC4X Bridge (industrial protocol integration)
    plc4x_bridge_url: str | None = None
    plc4x_bridge_enabled: bool = False

    # Mnestix (AAS viewer/browser)
    mnestix_enabled: bool = False
    mnestix_url: str = "http://mnestix:3000"

    # =========================================================================
    # DPP (Digital Product Passport) Builder
    # =========================================================================
    dpp_enabled: bool = False

    # =========================================================================
    # SAMM (Semantic Aspect Meta Model) Converter
    # =========================================================================
    samm_enabled: bool = True
    samm_default_namespace: str = "org.idta.generated"

    # =========================================================================
    # OPC UA Bridge (NodeSet import/export)
    # =========================================================================
    opcua_bridge_enabled: bool = True
    opcua_default_namespace: str = "urn:idta:generated:aas"
    _KNOWN_INSECURE_SECRET_KEYS: ClassVar[set[str]] = {
        "change-me-in-production-please-update",
        "development-secret-key-change-in-production",
        "change-this-to-a-secure-random-string-in-production",
        "your-secret-key-here-change-in-production",
    }

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

    @field_validator("github_template_ref", mode="before")
    @classmethod
    def parse_github_template_ref(cls, v: str | None) -> str:
        if v is None:
            return "main"
        if not isinstance(v, str):
            return v
        value = v.strip()
        if not value:
            return "main"
        # Validate Git ref naming convention (branches, tags, commit SHAs)
        if not re.match(r"^[a-zA-Z0-9._/-]+$", value):
            raise ValueError(f"Invalid git ref: {value}")
        if (
            value.startswith("/")
            or value.endswith("/")
            or value.startswith("-")
            or ".." in value
            or "//" in value
            or "@{" in value
            or "\\" in value
        ):
            raise ValueError(f"Invalid git ref path: {value}")
        segments = value.split("/")
        if any(segment.endswith(".lock") for segment in segments):
            raise ValueError(f"Invalid git ref path: {value}")
        return value

    @field_validator(
        "semantic_index_dir",
        "eclass_index_path",
        "iec_cdd_index_path",
        "mapper_cache_dir",
        "local_templates_dir",
        "magic_import_cache_dir",
        "dataspace_cache_dir",
        "settings_storage_dir",
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

    @model_validator(mode="after")
    def validate_security_defaults(self):
        normalized_secret = self.secret_key.strip().lower()
        if self.env == "production" and normalized_secret in self._KNOWN_INSECURE_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY must be overridden in production environments."
            )
        if (
            self.env == "production"
            and not self.oidc_enabled
            and not self.allow_insecure_prod_auth
        ):
            raise ValueError(
                "OIDC_ENABLED must be true in production unless "
                "ALLOW_INSECURE_PROD_AUTH=true is explicitly set."
            )
        return self

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
