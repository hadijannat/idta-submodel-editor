"""Semantic lookup service coordinating multiple providers."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.schemas.semantic import (
    SemanticApplyPreviewResponse,
    SemanticEntry,
    SemanticKind,
    SemanticProviderInfo,
)
from app.services.semantic.apply import preview_application
from app.services.semantic.normalize import normalize_identifier
from app.services.semantic.offline_provider import OfflineSemanticProvider
from app.services.semantic.sqlite_provider import SQLiteSemanticProvider
from app.services.semantic.provider_base import SemanticProvider
from app.services.semantic.eclass_online_provider import EclassOnlineProvider
from app.services.semantic.errors import SemanticRateLimitError


class SemanticService:
    """Facade for semantic provider search/resolve/apply-preview."""

    def __init__(self) -> None:
        settings = get_settings()

        base_dir = Path(__file__).resolve().parent
        sample_dir = base_dir / "data"

        eclass_path = settings.eclass_index_path
        iec_path = settings.iec_cdd_index_path

        enabled = settings.semantic_enabled
        self._providers: dict[str, SemanticProvider] = {
            "eclass_online": EclassOnlineProvider(
                base_url=settings.eclass_api_base,
                search_url=settings.eclass_search_url,
                resolve_url=settings.eclass_resolve_url,
                cert_path=settings.eclass_cert_path,
                key_path=settings.eclass_key_path,
                cert_password=settings.eclass_cert_password,
                enabled=enabled and settings.semantic_eclass_online_enabled,
                cache_ttl_seconds=settings.semantic_cache_ttl_seconds,
                cache_max_entries=settings.semantic_cache_max_entries,
                search_rate_limit=settings.semantic_search_rate_limit_per_min,
                resolve_rate_limit=settings.semantic_resolve_rate_limit_per_min,
            ),
            "eclass_offline": _build_provider(
                provider_id="eclass_offline",
                label="ECLASS (offline index)",
                path=eclass_path,
                fallback=sample_dir / "eclass_sample.json",
                enabled=enabled and settings.semantic_eclass_offline_enabled,
            ),
            "iec_cdd_offline": _build_provider(
                provider_id="iec_cdd_offline",
                label="IEC CDD (offline index)",
                path=iec_path,
                fallback=sample_dir / "iec_cdd_sample.json",
                enabled=enabled and settings.semantic_iec_cdd_offline_enabled,
            ),
        }

        self._prefer_iri = settings.semantic_prefer_iri

    def providers_info(self) -> list[SemanticProviderInfo]:
        info: list[SemanticProviderInfo] = []
        for provider in self._providers.values():
            status, reason = provider.status()
            info.append(
                SemanticProviderInfo(
                    id=provider.id,
                    label=provider.label,
                    status=status,  # type: ignore[arg-type]
                    reason=reason,
                )
            )
        return info

    async def search(
        self,
        q: str,
        provider: str | None,
        kind: SemanticKind | None,
        lang: str,
        limit: int,
        offset: int,
    ) -> tuple[list[SemanticEntry], int]:
        providers = self._select_providers(provider)

        results: list[SemanticEntry] = []
        total = 0
        for prov in providers:
            try:
                entries, count = await prov.search(q, kind, lang, limit, offset)
            except SemanticRateLimitError:
                if provider:
                    raise
                continue
            except Exception:
                if provider:
                    raise
                continue
            results.extend(entries)
            total += count

        results.sort(key=lambda entry: entry.score or 0, reverse=True)
        return results[:limit], total

    async def resolve(
        self, identifier: str, provider: str | None, lang: str
    ) -> SemanticEntry | None:
        providers = self._select_providers(provider)

        canonical_id, canonical_iri = normalize_identifier(identifier)
        lookup_ids = [identifier.strip(), canonical_id]
        if canonical_iri:
            lookup_ids.append(canonical_iri)

        for prov in providers:
            for lookup in lookup_ids:
                if not lookup:
                    continue
                try:
                    entry = await prov.resolve(lookup, lang)
                except SemanticRateLimitError:
                    if provider:
                        raise
                    continue
                except Exception:
                    if provider:
                        raise
                    continue
                if entry:
                    if canonical_iri and not entry.canonicalIri:
                        entry.canonicalIri = canonical_iri
                    return entry
        return None

    async def apply_preview(
        self,
        identifier: str,
        provider: str | None,
        lang: str,
        element_type: str | None,
        value_type: str | None,
        prefer_iri: bool | None = None,
    ) -> SemanticApplyPreviewResponse | None:
        entry = await self.resolve(identifier, provider, lang)
        if not entry:
            return None

        semantic_id, suggested_element, suggested_value, warnings, notes = (
            preview_application(
                entry,
                element_type,
                value_type,
                prefer_iri if prefer_iri is not None else self._prefer_iri,
            )
        )

        return SemanticApplyPreviewResponse(
            semanticId=semantic_id,
            elementType=suggested_element,
            valueType=suggested_value,
            warnings=warnings,
            notes=notes,
        )

    def _select_providers(self, provider: str | None) -> list[SemanticProvider]:
        if provider:
            selected = self._providers.get(provider)
            return [selected] if selected else []
        return list(self._providers.values())


def _build_provider(
    provider_id: str,
    label: str,
    path: Path,
    fallback: Path,
    enabled: bool,
) -> SemanticProvider:
    if path and path.suffix.lower() == ".sqlite" and path.exists():
        return SQLiteSemanticProvider(
            provider_id=provider_id,
            label=label,
            db_path=path,
            enabled=enabled,
        )
    if path and path.exists() and path.suffix.lower() in (".json", ".csv"):
        return OfflineSemanticProvider(
            provider_id=provider_id,
            label=label,
            data_path=path,
            enabled=enabled,
        )
    return OfflineSemanticProvider(
        provider_id=provider_id,
        label=label,
        data_path=fallback,
        enabled=enabled,
    )
