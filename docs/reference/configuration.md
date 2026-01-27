# Configuration Reference

Complete environment variable reference for the IDTA Submodel Template Editor.

---

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

### Local Templates

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_TEMPLATES_ENABLED` | Enable custom local templates | true |
| `LOCAL_TEMPLATES_DIR` | Directory for local AASX files | ./templates/local |

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

---

## Semantic Lookup

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

---

## Magic Import

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
| `MAGIC_IMPORT_VALIDATION_MODE` | Validation strictness (strict/warn/off) | warn |
| `CELERY_BROKER_URL` | Redis URL for Celery broker | redis://localhost:6379/0 |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results | redis://localhost:6379/0 |

---

## Dataspace

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `DATASPACE_CACHE_DIR` | Cache directory for dataspace | ./cache/dataspace |
| `DATASPACE_DEFAULT_ENVIRONMENT` | Default environment (sandbox/catena-x-test/catena-x-prod) | sandbox |
| `DATASPACE_DEFAULT_EDC_MODE` | Default EDC mode (tractus-x/aas-extension) | tractus-x |

### Eclipse BaSyx

| Variable | Description | Default |
|----------|-------------|---------|
| `BASYX_AAS_SERVER_URL` | BaSyx AAS server URL | http://basyx-aas-server:4001 |
| `BASYX_REGISTRY_URL` | BaSyx registry URL | http://basyx-registry:4002 |

### Tractus-X EDC

| Variable | Description | Default |
|----------|-------------|---------|
| `EDC_CONTROL_PLANE_URL` | EDC control plane URL | http://edc-control-plane:19192 |
| `EDC_DATA_PLANE_URL` | EDC data plane URL | http://edc-data-plane:19291 |
| `EDC_API_KEY` | EDC Management API key | - |

### EDC AAS Extension

| Variable | Description | Default |
|----------|-------------|---------|
| `EDC_AAS_EXTENSION_URL` | EDC AAS Extension URL (alternative mode) | - |

### Digital Twin Registry

| Variable | Description | Default |
|----------|-------------|---------|
| `DTR_URL` | Digital Twin Registry URL | http://dtr:4003 |

### HashiCorp Vault

| Variable | Description | Default |
|----------|-------------|---------|
| `VAULT_URL` | Vault URL | http://vault:8200 |
| `VAULT_TOKEN` | Vault access token | - |

### Catena-X Specific

| Variable | Description | Default |
|----------|-------------|---------|
| `CATENA_X_PORTAL_URL` | Catena-X Portal URL | https://portal.catena-x.net |
| `CATENA_X_BPN` | Business Partner Number | - |

---

## PLC4X Bridge

### Backend Integration

| Variable | Description | Default |
|----------|-------------|---------|
| `PLC4X_BRIDGE_ENABLED` | Enable PLC bridge feature | false |
| `PLC4X_BRIDGE_URL` | PLC4X Bridge microservice URL | http://plc4x-bridge:8090 |

### Bridge Configuration (application.yml)

These settings are configured in the PLC4X Bridge's `application.yml`:

| Property | Description | Default |
|----------|-------------|---------|
| `plc.connection-string` | PLC4X connection string (e.g., `s7://192.168.1.10`) | - |
| `plc.read-interval` | Polling interval in milliseconds | 1000 |
| `mapping.update-mode` | Update mode (ON_CHANGE/ALWAYS) | ON_CHANGE |
| `mapping.change-threshold` | Deadband for ON_CHANGE mode | 0.01 |
| `basyx.aas-server.url` | BaSyx AAS Server URL | http://basyx-aas-server:4001 |

---

## Mnestix (AAS Browser)

| Variable | Description | Default |
|----------|-------------|---------|
| `MNESTIX_ENABLED` | Enable AAS Browser integration | true |
| `MNESTIX_URL` | Mnestix instance URL | http://mnestix:3000 |

---

## Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | http://localhost:8000 |

---

## Feature Toggles Summary

Quick reference for enabling/disabling major features:

| Feature | Variable | Default |
|---------|----------|---------|
| Magic Import | `MAGIC_IMPORT_ENABLED` | true |
| Dataspace | `DATASPACE_ENABLED` | false |
| PLC4X Bridge | `PLC4X_BRIDGE_ENABLED` | false |
| AAS Browser | `MNESTIX_ENABLED` | true |
| Local Templates | `LOCAL_TEMPLATES_ENABLED` | true |
| Semantic Lookup | `SEMANTIC_ENABLED` | true |
| Authentication | `OIDC_ENABLED` | false |
| PDF Export | `PDF_ENABLED` | true |
