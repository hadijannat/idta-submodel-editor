"""ECLASS webservice provider (optional)."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.schemas.semantic import SemanticEntry, SemanticKind
from app.services.semantic.cache import TTLCache
from app.services.semantic.errors import SemanticRateLimitError
from app.services.semantic.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class EclassOnlineProvider:
    """Optional ECLASS webservice provider.

    This provider expects configurable endpoints that return normalized entries.
    """

    def __init__(
        self,
        base_url: str,
        search_url: str | None,
        resolve_url: str | None,
        cert_path: Path | None,
        key_path: Path | None,
        cert_password: str | None,
        enabled: bool,
        cache_ttl_seconds: int,
        cache_max_entries: int,
        search_rate_limit: int,
        resolve_rate_limit: int,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.id = "eclass_online"
        self.label = "ECLASS (webservice)"
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._search_url = search_url
        self._resolve_url = resolve_url
        self._cert_path = cert_path
        self._key_path = key_path
        self._cert_password = cert_password
        self._enabled = enabled
        self._timeout = timeout_seconds
        self._status_reason: str | None = None

        self._search_cache: TTLCache[str, tuple[list[SemanticEntry], int]] = TTLCache(
            maxsize=cache_max_entries, ttl_seconds=cache_ttl_seconds
        )
        self._resolve_cache: TTLCache[str, SemanticEntry] = TTLCache(
            maxsize=cache_max_entries, ttl_seconds=cache_ttl_seconds
        )
        self._search_rate = RateLimiter(search_rate_limit)
        self._resolve_rate = RateLimiter(resolve_rate_limit)

        self._validate_config()

    def status(self) -> tuple[str, str | None]:
        if not self._enabled:
            return ("disabled", self._status_reason or "disabled by configuration")
        return ("ready", None)

    async def search(
        self,
        q: str,
        kind: SemanticKind | None,
        lang: str,
        limit: int,
        offset: int,
    ) -> tuple[list[SemanticEntry], int]:
        if not self._enabled:
            return ([], 0)

        if not self._search_rate.allow():
            raise SemanticRateLimitError(
                "ECLASS search rate limit exceeded",
                retry_after=self._search_rate.retry_after(),
            )

        cache_key = f"{q}:{kind}:{lang}:{limit}:{offset}"
        cached = self._search_cache.get(cache_key)
        if cached:
            return cached

        url = self._format_url(self._search_url, q=q, kind=kind, lang=lang, limit=limit, offset=offset)
        payload = await self._request_json(url, params={"q": q, "kind": kind, "lang": lang, "limit": limit, "offset": offset})

        results, total = _parse_search_payload(payload, provider_id=self.id, lang=lang)
        self._search_cache.set(cache_key, (results, total))
        return results, total

    async def resolve(self, identifier: str, lang: str) -> SemanticEntry | None:
        if not self._enabled:
            return None

        if not self._resolve_rate.allow():
            raise SemanticRateLimitError(
                "ECLASS resolve rate limit exceeded",
                retry_after=self._resolve_rate.retry_after(),
            )

        cache_key = f"{identifier}:{lang}"
        cached = self._resolve_cache.get(cache_key)
        if cached:
            return cached

        url = self._format_url(self._resolve_url, identifier=identifier, lang=lang)
        payload = await self._request_json(url, params={"id": identifier, "lang": lang})
        entry = _parse_resolve_payload(payload, provider_id=self.id, lang=lang)
        if entry:
            self._resolve_cache.set(cache_key, entry)
        return entry

    def _validate_config(self) -> None:
        if not self._enabled:
            self._status_reason = "disabled by configuration"
            return

        if not self._base_url:
            self._enabled = False
            self._status_reason = "missing ECLASS base URL"
            return

        if not self._search_url and not self._resolve_url:
            self._enabled = False
            self._status_reason = "missing search/resolve endpoint"
            return

        if not self._cert_path or not self._cert_path.exists():
            self._enabled = False
            self._status_reason = "missing ECLASS client certificate"
            return

        if self._key_path and not self._key_path.exists():
            self._enabled = False
            self._status_reason = "missing ECLASS client key"
            return

    def _format_url(self, template: str | None, **kwargs) -> str:
        if not template:
            raise SemanticRateLimitError("ECLASS endpoint not configured")
        url = template.format(**{k: v for k, v in kwargs.items() if v is not None})
        if url.startswith("/"):
            return f"{self._base_url}{url}"
        if url.startswith("http"):
            return url
        return f"{self._base_url}/{url}"

    async def _request_json(self, url: str, params: dict | None = None):
        cert = None
        if self._cert_path:
            if self._key_path:
                cert = (str(self._cert_path), str(self._key_path))
            else:
                cert = str(self._cert_path)

        async with httpx.AsyncClient(timeout=self._timeout, cert=cert) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()


def _parse_search_payload(payload: object, provider_id: str, lang: str) -> tuple[list[SemanticEntry], int]:
    if isinstance(payload, dict):
        results_raw = payload.get("results") or payload.get("items") or []
        total = payload.get("total") or len(results_raw)
    elif isinstance(payload, list):
        results_raw = payload
        total = len(payload)
    else:
        return ([], 0)

    results = [_map_entry(item, provider_id, lang) for item in results_raw]
    results = [entry for entry in results if entry is not None]
    return results, int(total)


def _parse_resolve_payload(payload: object, provider_id: str, lang: str) -> SemanticEntry | None:
    if isinstance(payload, dict):
        entry_raw = payload.get("entry") or payload
        return _map_entry(entry_raw, provider_id, lang)
    return None


def _map_entry(raw: dict, provider_id: str, lang: str) -> SemanticEntry | None:
    if not isinstance(raw, dict):
        return None
    canonical_id = raw.get("canonicalId") or raw.get("id") or raw.get("irdi")
    if not canonical_id:
        return None

    preferred_name = raw.get("preferredName")
    definition = raw.get("definition")

    return SemanticEntry(
        provider=provider_id,
        kind=raw.get("kind", "property"),
        canonicalId=canonical_id,
        canonicalIri=raw.get("canonicalIri") or raw.get("iri"),
        preferredName=_pick_lang(preferred_name, lang),
        definition=_pick_lang(definition, lang),
        datatypeHint=raw.get("datatypeHint"),
        unitHint=raw.get("unitHint"),
        labels=preferred_name if isinstance(preferred_name, dict) else None,
        definitions=definition if isinstance(definition, dict) else None,
        synonyms=raw.get("synonyms"),
        score=raw.get("score"),
    )


def _pick_lang(value: dict | str | None, lang: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if lang in value:
        return value[lang]
    if "en" in value:
        return value["en"]
    return next(iter(value.values()), None)
