# Semantic Dictionary Lookup + Resolver

Attach standardized semantic identifiers (ECLASS / IEC CDD) to SubmodelElements. This is especially important for "generic frame" templates (e.g., Technical Data) where users must define domain-specific properties and need correct semantics.

![Semantic Lookup Live Demo](../semantic/semantic-lookup-live-demo.gif)

## Goal

Enable users to search, select, and apply standardized semantic identifiers while preserving metadata and keeping the Fetcher → Parser → Hydrator → Validation pipeline intact.

## Why Semantic Lookup Matters

1. **AAS semantics are required for interoperability** - matching strategies and ID examples
2. **IDTA submodel context stresses dictionaries** like ECLASS and IEC CDD
3. **ECLASS access is certificate-authenticated and costed per IRDI** → caching + throttling are required
4. **Dictionary data types can suggest correct AAS element type/valueType** (e.g., STRING_TRANSLATABLE)

## Features (MVP)

- **Semantic Search UI**: search box + provider/kind/language filters, results list, details drawer, apply-to-field
- **Backend semantic service**: `/api/semantic/providers`, `/api/semantic/search`, `/api/semantic/resolve`, `/api/semantic/apply-preview`
- **ECLASS provider**: offline index + optional online webservice (mTLS, rate-limited)
- **IEC CDD provider**: offline index first, pluggable for future APIs
- **Resolver**: given semanticId, show label/definition from available providers

### Out of Scope (Initially)

- Global ConceptDescription registry sync
- ECLASS↔IEC CDD reconciliation
- Bundling licensed datasets in the repo

## Apply Logic

- Prefer IRI when available, otherwise IRDI string
- Apply preview suggests element type/valueType based on dictionary datatype
- Optional ConceptDescription embedding at export time (configurable)

## Offline Index

The offline index supports JSON/CSV and SQLite FTS. See: [indexing.md](../semantic/indexing.md)

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SEMANTIC_ENABLED` | Enable semantic lookup | true |
| `SEMANTIC_PREFER_IRI` | Prefer IRI when available | true |
| `SEMANTIC_ECLASS_OFFLINE_ENABLED` | Enable ECLASS offline index | true |
| `SEMANTIC_IEC_CDD_OFFLINE_ENABLED` | Enable IEC CDD offline index | true |
| `SEMANTIC_ECLASS_ONLINE_ENABLED` | Enable ECLASS online webservice | false |
| `ECLASS_API_BASE` | ECLASS webservice base URL | - |
| `ECLASS_SEARCH_URL` | Search endpoint (relative or absolute) | - |
| `ECLASS_RESOLVE_URL` | Resolve endpoint (relative or absolute) | - |
| `ECLASS_CERT_PATH` | Client certificate path | - |
| `ECLASS_KEY_PATH` | Client key path | - |
| `SEMANTIC_CACHE_TTL_SECONDS` | Semantic cache TTL (sec) | 86400 |
| `SEMANTIC_SEARCH_RATE_LIMIT_PER_MIN` | Search rate limit | 60 |
| `SEMANTIC_RESOLVE_RATE_LIMIT_PER_MIN` | Resolve rate limit | 120 |
| `ECLASS_INDEX_PATH` | Offline index path (JSON/CSV/SQLite) | ./cache/semantic/eclass.json |
| `IEC_CDD_INDEX_PATH` | Offline index path (JSON/CSV/SQLite) | ./cache/semantic/iec_cdd.json |
| `SEMANTIC_EMBED_CONCEPT_DESCRIPTIONS` | Embed ConceptDescriptions on export | false |

## API Endpoints

- `GET /api/semantic/providers` - List available semantic providers
- `GET /api/semantic/search` - Search semantic dictionaries
- `GET /api/semantic/resolve` - Resolve an ID/IRI to metadata
- `POST /api/semantic/apply-preview` - Suggest semanticId + type warnings
