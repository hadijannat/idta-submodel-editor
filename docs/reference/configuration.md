# Configuration Reference

Complete environment variable reference for the IDTA Submodel Template Editor.

## Backend

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (development, staging, production) | development |
| `SECRET_KEY` | Secret key for signing | Required in production |
| `GITHUB_TOKEN` | GitHub API token for higher rate limits | Optional |
| `CORS_ORIGINS` | Allowed CORS origins | http://localhost:8080 |
| `CACHE_TTL_HOURS` | Template cache TTL in hours | 24 |
| `MAX_UPLOAD_SIZE_MB` | Maximum upload file size | 50 |
| `PDF_ENABLED` | Enable PDF export | true |

### Authentication (OIDC)

| Variable | Description | Default |
|----------|-------------|---------|
| `OIDC_ENABLED` | Enable OAuth2/OIDC authentication | false |
| `OIDC_ISSUER_URL` | OIDC issuer URL | - |
| `OIDC_AUDIENCE` | OIDC audience | - |

### Caching

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis URL for distributed caching | Optional |

### Semantic Lookup

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

### Dataspace

| Variable | Description | Default |
|----------|-------------|---------|
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `DATASPACE_DEFAULT_ENVIRONMENT` | Default dataspace environment | sandbox |
| `DATASPACE_DEFAULT_EDC_MODE` | Default EDC mode | tractus-x |
| `BASYX_AAS_SERVER_URL` | BaSyx AAS server URL | http://basyx-aas-server:4001 |
| `BASYX_REGISTRY_URL` | BaSyx registry URL | http://basyx-registry:4002 |
| `EDC_CONTROL_PLANE_URL` | EDC control plane URL | http://edc-control-plane:19192 |
| `EDC_DATA_PLANE_URL` | EDC data plane URL | http://edc-data-plane:19291 |
| `DTR_URL` | Digital Twin Registry URL | http://dtr:4003 |
| `VAULT_URL` | Vault URL | http://vault:8200 |
| `VAULT_TOKEN` | Vault token | - |

### Magic Import

| Variable | Description | Default |
|----------|-------------|---------|
| `MAGIC_IMPORT_ENABLED` | Enable Magic Import feature | true |
| `MAGIC_IMPORT_LLM_PROVIDER` | LLM provider (openai, anthropic, local) | openai |
| `MAGIC_IMPORT_LLM_MODEL` | Model name | gpt-4o-mini |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OLLAMA_BASE_URL` | Ollama server URL | http://localhost:11434 |
| `MAGIC_IMPORT_CONFIDENCE_THRESHOLD` | Flag fields below this score | 0.80 |
| `MAGIC_IMPORT_OCR_ENABLED` | Enable OCR fallback | true |
| `MAGIC_IMPORT_OCR_LANGUAGE` | Tesseract language codes | eng+deu |
| `MAGIC_IMPORT_OCR_DPI` | OCR resolution | 300 |
| `MAGIC_IMPORT_MAX_PDF_SIZE_MB` | Maximum PDF file size | 50 |
| `MAGIC_IMPORT_JOB_TTL_HOURS` | Job retention period | 24 |
| `CELERY_BROKER_URL` | Redis URL for Celery broker | redis://localhost:6379/0 |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results | redis://localhost:6379/0 |

## Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | http://localhost:8000 |
