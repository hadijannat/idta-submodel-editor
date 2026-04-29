# Configuration Reference

This page lists runtime configuration for backend and frontend components.

For quick local startup, use the [repository README](https://github.com/hadijannat/idta-submodel-editor/blob/main/README.md). For API behavior, see [API Endpoints Reference](api-endpoints.md).

## Backend

### Core Settings

| Variable | Description | Default |
|---|---|---|
| `ENV` | Runtime environment (`development`, `staging`, `production`) | `development` |
| `DEBUG` | Enable debug behaviors | `false` |
| `SECRET_KEY` | Signing/encryption secret | **Required for all non-local environments (no safe default)** |
| `HOST` | Bind address | `0.0.0.0` |
| `PORT` | Backend port | `8000` |
| `WORKERS` | Worker count for process managers | `4` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array or comma-separated string) | `http://localhost:8080,http://localhost:5173` |
| `MAX_UPLOAD_SIZE_MB` | Upload size limit | `50` |
| `PDF_ENABLED` | Enable PDF export | `true` |

### Template Sources and Caching

| Variable | Description | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub API token for higher rate limits | unset |
| `GITHUB_REPO` | Template source repository | `admin-shell-io/submodel-templates` |
| `GITHUB_TEMPLATE_REF` | Git ref for templates | `main` |
| `CACHE_DIR` | Template cache directory | `./cache/templates` |
| `CACHE_TTL_HOURS` | Template cache TTL | `24` |
| `MAPPER_CACHE_DIR` | Mapper cache directory | `./cache/mapper` |
| `LOCAL_TEMPLATES_ENABLED` | Enable custom local templates | `true` |
| `LOCAL_TEMPLATES_DIR` | Local template directory | `./templates/local` |
| `REDIS_URL` | Optional Redis endpoint for distributed caching | unset |

### Authentication (OIDC)

| Variable | Description | Default |
|---|---|---|
| `OIDC_ENABLED` | Enable token validation and auth enforcement | `false` |
| `ALLOW_INSECURE_PROD_AUTH` | Allow startup without OIDC in production (escape hatch) | `false` |
| `OIDC_ISSUER_URL` | OIDC issuer URL | unset |
| `OIDC_AUDIENCE` | Expected audience | unset |
| `OIDC_CLIENT_ID` | OIDC client ID | unset |
| `OIDC_CLIENT_SECRET` | OIDC client secret | unset |

Notes:
- If `OIDC_ENABLED=false`, user checks resolve to anonymous and permission checks allow requests.
- In `ENV=production`, backend startup fails unless `OIDC_ENABLED=true` or `ALLOW_INSECURE_PROD_AUTH=true`.
- Running Keycloak via compose profile does not by itself enforce auth.
- Keycloak host port defaults to `8081` (`KEYCLOAK_HOST_PORT`) to avoid frontend collisions on `8080`.

### Semantic Lookup

| Variable | Description | Default |
|---|---|---|
| `SEMANTIC_ENABLED` | Enable semantic dictionary features | `true` |
| `SEMANTIC_PREFER_IRI` | Prefer IRI values when available | `true` |
| `SEMANTIC_EMBED_CONCEPT_DESCRIPTIONS` | Embed concept descriptions in exported payloads | `false` |
| `SEMANTIC_ECLASS_OFFLINE_ENABLED` | Use offline ECLASS index | `true` |
| `SEMANTIC_IEC_CDD_OFFLINE_ENABLED` | Use offline IEC CDD index | `true` |
| `SEMANTIC_ECLASS_ONLINE_ENABLED` | Enable ECLASS web-service calls | `false` |
| `SEMANTIC_CACHE_TTL_SECONDS` | Semantic cache TTL | `86400` |
| `SEMANTIC_SEARCH_RATE_LIMIT_PER_MIN` | Search rate limit per minute | `60` |
| `SEMANTIC_RESOLVE_RATE_LIMIT_PER_MIN` | Resolve rate limit per minute | `120` |
| `SEMANTIC_INDEX_DIR` | Semantic index directory | `./cache/semantic` |
| `ECLASS_INDEX_PATH` | ECLASS offline index path | `./cache/semantic/eclass.json` |
| `IEC_CDD_INDEX_PATH` | IEC CDD offline index path | `./cache/semantic/iec_cdd.json` |
| `ECLASS_API_BASE` | ECLASS API base URL | unset |
| `ECLASS_SEARCH_URL` | ECLASS search endpoint | unset |
| `ECLASS_RESOLVE_URL` | ECLASS resolve endpoint | unset |
| `ECLASS_CERT_PATH` | Client certificate path | unset |
| `ECLASS_KEY_PATH` | Client key path | unset |
| `ECLASS_CERT_PASSWORD` | Certificate passphrase | unset |

### Magic Import and LLM Settings

| Variable | Description | Default |
|---|---|---|
| `MAGIC_IMPORT_ENABLED` | Enable Magic Import APIs | `true` |
| `MAGIC_IMPORT_LLM_PROVIDER` | Provider (`openai`, `anthropic`, `openrouter`, `local`) | `openai` |
| `MAGIC_IMPORT_LLM_MODEL` | Active LLM model | `gpt-5.5` |
| `OPENAI_API_KEY` | OpenAI API key | unset |
| `ANTHROPIC_API_KEY` | Anthropic API key | unset |
| `OPENROUTER_API_KEY` | OpenRouter API key | unset |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible base URL | unset |
| `OLLAMA_BASE_URL` | Local Ollama URL | `http://localhost:11434` |
| `SETTINGS_STORAGE_DIR` | Encrypted settings store path | `./cache/settings` |
| `SETTINGS_ENCRYPTION_KEY` | Fernet key for encrypting stored provider secrets | unset (auto-generated at runtime if missing) |
| `MAGIC_IMPORT_CONFIDENCE_THRESHOLD` | Confidence threshold | `0.80` |
| `MAGIC_IMPORT_OCR_ENABLED` | Enable OCR fallback | `true` |
| `MAGIC_IMPORT_OCR_LANGUAGE` | OCR language bundle | `eng+deu` |
| `MAGIC_IMPORT_OCR_DPI` | OCR resolution | `300` |
| `MAGIC_IMPORT_MAX_PDF_SIZE_MB` | Max PDF size | `50` |
| `MAGIC_IMPORT_JOB_TTL_HOURS` | Job retention time | `24` |
| `MAGIC_IMPORT_VALIDATION_MODE` | Validation mode (`warn`, `strict`, `off`) | `warn` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://localhost:6379/0` |

Security/operations note:
- For HA, multi-replica, or ephemeral-storage deployments, set a stable `SETTINGS_ENCRYPTION_KEY` explicitly to avoid losing access to previously encrypted provider credentials after restart/reschedule.

### Template Knowledge

| Variable | Description | Default |
|---|---|---|
| `TEMPLATE_KNOWLEDGE_ENABLED` | Enable template knowledge indexing | `true` |
| `TEMPLATE_KNOWLEDGE_EMBEDDING_MODEL` | Embedding model name | `nomic-embed-text` |
| `TEMPLATE_KNOWLEDGE_AUTO_BUILD` | Build knowledge index on startup | `false` |

### Dataspace and Integration

| Variable | Description | Default |
|---|---|---|
| `DATASPACE_ENABLED` | Enable dataspace endpoints and workflows | `false` |
| `DATASPACE_CACHE_DIR` | Dataspace cache directory | `./cache/dataspace` |
| `DATASPACE_DEFAULT_ENVIRONMENT` | Default target environment | `sandbox` |
| `DATASPACE_DEFAULT_EDC_MODE` | Default EDC mode (`tractus-x`, `aas-extension`) | `tractus-x` |
| `BASYX_AAS_SERVER_URL` | BaSyx AAS Server URL | `http://basyx-aas-server:4001` |
| `BASYX_REGISTRY_URL` | BaSyx Registry URL | `http://basyx-registry:4002` |
| `EDC_CONTROL_PLANE_URL` | EDC control plane URL | `http://edc-control-plane:19192` |
| `EDC_DATA_PLANE_URL` | EDC data plane URL | `http://edc-data-plane:19291` |
| `EDC_API_KEY` | EDC API key | unset |
| `EDC_AAS_EXTENSION_URL` | Alternate AAS extension URL | unset |
| `DTR_URL` | Digital Twin Registry URL | `http://dtr:4003` |
| `VAULT_URL` | Vault URL | `http://vault:8200` |
| `VAULT_TOKEN` | Vault token | unset |
| `CATENA_X_PORTAL_URL` | Catena-X portal URL | unset |
| `CATENA_X_BPN` | Business Partner Number | unset |
| `PLC4X_BRIDGE_ENABLED` | Enable PLC4X bridge integration | `false` |
| `PLC4X_BRIDGE_URL` | PLC4X bridge URL | unset |
| `MNESTIX_ENABLED` | Enable Mnestix browser integration in the app UI | `false` |
| `MNESTIX_URL` | Browser-accessible Mnestix base URL | `http://mnestix:3000` |
| `MNESTIX_HOST_BIND` | Host interface used by the optional Mnestix compose profile | `127.0.0.1` |
| `MNESTIX_HOST_PORT` | Host port used by the optional Mnestix compose profile | `3001` |

### Feature Flags for Additional Tools

| Variable | Description | Default |
|---|---|---|
| `DPP_ENABLED` | Enable DPP builder | `false` |
| `SAMM_ENABLED` | Enable SAMM converter | `true` |
| `SAMM_DEFAULT_NAMESPACE` | Default SAMM namespace | `org.idta.generated` |
| `OPCUA_BRIDGE_ENABLED` | Enable OPC UA bridge tooling | `true` |
| `OPCUA_DEFAULT_NAMESPACE` | Default OPC UA namespace | `urn:idta:generated:aas` |

## Frontend

| Variable | Description | Default |
|---|---|---|
| `VITE_API_URL` | Backend API base URL | `http://localhost:8000` |
| `VITE_PORT` | Local Vite dev server port | `8080` |
| `VITE_PCF_TOOLS_ENABLED` | Show/hide PCF tools in UI | enabled unless explicitly `false` |
| `VITE_PCF_ACTIVITY_LIST_SEMANTIC_IDS` | Semantic IDs treated as activity-list fields | built-in list |
| `VITE_PCF_ACTIVITY_LIST_IDSHORTS` | `idShort` names treated as activity-list fields | built-in list |

## Compose Profile Notes

- `docker compose up` starts backend, frontend, and Redis.
- `--profile magic-import` adds a Celery worker.
- `--profile dataspace` adds dataspace infrastructure.
- `--profile dataspace --profile mnestix` additionally starts Mnestix on `127.0.0.1:3001`; set `MNESTIX_ENABLED=true` to expose the AAS Browser in the app UI.
- `--profile plc` adds PLC4X bridge plus required BaSyx services.
- `--profile auth` adds Keycloak, but auth is only enforced when OIDC backend settings are enabled.
- Auth profile can run alongside frontend; Keycloak maps to host `8081` by default.

### Compose Host-Port Overrides

| Variable | Description | Default |
|---|---|---|
| `KEYCLOAK_HOST_PORT` | Host port mapped to Keycloak container `8080` | `8081` |
| `VAULT_HOST_PORT` | Host port mapped to Vault container `8200` | `8200` |
