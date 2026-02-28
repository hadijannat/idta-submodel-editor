# API Endpoints Reference

Swagger UI is available at `/api/docs` and ReDoc at `/api/redoc` when backend `ENV != production`.

## Security Model

- If `OIDC_ENABLED=false`, API routes are effectively unauthenticated by default.
- In `ENV=production`, startup requires `OIDC_ENABLED=true` unless `ALLOW_INSECURE_PROD_AUTH=true` is explicitly set.
- If `OIDC_ENABLED=true`, bearer-token authentication is enforced on routes that depend on current-user validation.
- `PUT /api/settings/features` requires admin privileges when `ENV != development`.
- Expose `/health*` and `/metrics` only on private networks or behind gateway auth/allowlists.

## Health and Observability

| Endpoint | Description |
|---|---|
| `GET /health` | Basic health check |
| `GET /health/liveness` | Liveness probe |
| `GET /health/readiness` | Readiness probe |
| `GET /health/startup` | Startup probe |
| `GET /metrics` | Prometheus metrics |

Security note: these endpoints should be treated as operational surfaces, not public internet endpoints.

## Public Settings

| Endpoint | Description |
|---|---|
| `GET /api/settings` | Public frontend settings (`mnestix_enabled`, `dataspace_enabled`, `magic_import_enabled`, etc.) |

## Templates

| Endpoint | Description |
|---|---|
| `GET /api/templates` | List templates (`status=published|deprecated|all`) |
| `GET /api/templates/{template_name}` | Get template metadata |
| `GET /api/templates/{template_name}/versions` | List versions for a template |
| `POST /api/templates/refresh` | Refresh template cache |
| `DELETE /api/templates/{template_name}/cache` | Clear cached template payload |

## Editor

| Endpoint | Description |
|---|---|
| `GET /api/editor/templates/{template_name}/schema` | Get UI schema for template |
| `GET /api/editor/templates/{template_name}/schema?version={version}` | Get schema for explicit version (optional query parameter) |
| `POST /api/editor/hydrate/{template_name}` | Hydrate to AASX |
| `POST /api/editor/hydrate/{template_name}/json` | Hydrate to JSON |
| `POST /api/editor/upload` | Upload and parse AASX |
| `POST /api/editor/validate/{template_name}` | Validate submitted form data |
| `GET /api/editor/templates/local` | List locally uploaded templates |
| `POST /api/editor/templates/local` | Upload local template |
| `DELETE /api/editor/templates/local/{template_name}` | Delete local template |

## Export

| Endpoint | Description |
|---|---|
| `POST /api/export/{template_name}` | Export template data (`format=aasx|json|pdf`) |
| `GET /api/export/{template_name}/preview` | Template preview |
| `POST /api/export/batch` | Batch export ZIP |

## Conformance

| Endpoint | Description | Auth |
|---|---|---|
| `POST /api/conformance/check` | Run AAS conformance check on uploaded AASX/JSON artifacts | Bearer token when OIDC is enabled |

## Template Operations

| Endpoint | Description |
|---|---|
| `POST /api/template-ops/import` | Import AASX as local template |
| `POST /api/template-ops/diff` | Structural diff between template versions |
| `POST /api/template-ops/migrate` | Migration plan generation |
| `POST /api/template-ops/validate` | Validate template data against schema constraints |
| `POST /api/template-ops/schema-digest` | Compute schema digest |
| `POST /api/template-ops/migrate-recipe` | Migrate Smart Mapper recipe |
| `POST /api/template-ops/migrate-form` | Migrate saved form data |
| `POST /api/template-ops/check-mismatch` | Detect version/schema mismatch |

## Tools Registry

| Endpoint | Description | Auth |
|---|---|---|
| `GET /api/tools` | List tools with metadata | No per-route auth dependency; protect at gateway/network level |
| `GET /api/tools/health` | Overall tool health | No per-route auth dependency; protect at gateway/network level |
| `GET /api/tools/manifest` | Tool manifest used by frontend (includes `schema_version`, `disabled_reason`) | No per-route auth dependency; protect at gateway/network level |
| `GET /api/tools/{tool_id}` | Tool capability report | No per-route auth dependency; protect at gateway/network level |
| `GET /api/tools/{tool_id}/health` | Tool-specific health | No per-route auth dependency; protect at gateway/network level |
| `GET /api/tools/{tool_id}/capabilities` | Tool capabilities details | No per-route auth dependency; protect at gateway/network level |

## Settings Management

| Endpoint | Description | Auth |
|---|---|---|
| `GET /api/settings/llm` | Get active provider/model configuration (keys masked) | Bearer token when OIDC is enabled |
| `PUT /api/settings/llm` | Update provider/model/threshold/OCR settings | Bearer token when OIDC is enabled |
| `POST /api/settings/llm/validate` | Validate provider credentials without saving | Bearer token when OIDC is enabled |
| `GET /api/settings/llm/models/{provider}` | List provider models | Bearer token when OIDC is enabled |
| `DELETE /api/settings/llm/api-key/{provider}` | Remove stored API key | Bearer token when OIDC is enabled |
| `GET /api/settings/features` | Read runtime feature flags | Bearer token when OIDC is enabled |
| `PUT /api/settings/features` | Update runtime feature flags | Admin required when `ENV != development` (and OIDC enabled) |

## Semantic Lookup

| Endpoint | Description |
|---|---|
| `GET /api/semantic/providers` | List semantic providers |
| `GET /api/semantic/search` | Search dictionaries |
| `GET /api/semantic/resolve` | Resolve semantic ID/IRI |
| `POST /api/semantic/apply-preview` | Preview semantic application to fields |
| `POST /api/semantic/batch-resolve` | Resolve multiple semantic IDs |

## Smart Mapper

| Endpoint | Description |
|---|---|
| `POST /api/mapper/profile` | Profile CSV/XLSX columns |
| `POST /api/mapper/auto-suggest` | Suggest field mappings |
| `POST /api/mapper/run` | Execute mapping |
| `GET /api/mapper/recipes` | List recipes |
| `POST /api/mapper/recipes` | Save recipe |
| `GET /api/mapper/recipes/{name}` | Get recipe |
| `DELETE /api/mapper/recipes/{name}` | Delete recipe |

## Magic Import

| Endpoint | Description |
|---|---|
| `POST /api/magic-import/jobs/preview` | Preview snippets/token estimate before extraction |
| `POST /api/magic-import/jobs` | Create extraction job |
| `GET /api/magic-import/jobs` | List jobs |
| `GET /api/magic-import/jobs/{job_id}` | Job status |
| `GET /api/magic-import/jobs/{job_id}/result` | Extraction result |
| `POST /api/magic-import/jobs/{job_id}/reextract` | Re-run extraction |
| `GET /api/magic-import/jobs/{job_id}/pdf` | Download uploaded PDF |
| `DELETE /api/magic-import/jobs/{job_id}` | Delete job and artifacts |
| `GET /api/magic-import/jobs/{job_id}/quality-metrics` | Quality metrics |
| `GET /api/magic-import/jobs/{job_id}/audit-report` | Download JSON/PDF audit report |
| `GET /api/magic-import/jobs/{job_id}/audit-report/preview` | Audit report preview |
| `POST /api/magic-import/jobs/{job_id}/corrections` | Submit manual correction outcomes |
| `GET /api/magic-import/analytics/correction-rates` | Aggregated correction analytics |
| `GET /api/magic-import/provider-status` | Quick provider status |
| `GET /api/magic-import/providers/info` | Provider capability details |
| `POST /api/magic-import/providers/select` | Select active provider |
| `POST /api/magic-import/health` | Trigger health check |

## Template Knowledge

| Endpoint | Description |
|---|---|
| `GET /api/knowledge/status` | Index status |
| `GET /api/knowledge/templates` | List indexed templates |
| `GET /api/knowledge/templates/{idta_number}` | Template metadata |
| `GET /api/knowledge/templates/{idta_number}/fields` | Field list for template |
| `POST /api/knowledge/search/semantic` | Semantic similarity search |
| `POST /api/knowledge/recommend` | Semantic recommendation |
| `GET /api/knowledge/fields/by-semantic-id/{semantic_id}` | Fields by semantic ID |
| `GET /api/knowledge/keywords/{idta_number}/{path}` | Keyword extraction for field path |

## PCF

| Endpoint | Description |
|---|---|
| `POST /api/pcf/calculate` | Calculate emissions |
| `POST /api/pcf/validate` | Validate PCF payload |
| `GET /api/pcf/health` | PCF module health |
| `GET /api/pcf/factors/search` | Search emission factors |
| `GET /api/pcf/factors/{factor_id}` | Get factor details |

## DPP Builder

| Endpoint | Description |
|---|---|
| `POST /api/dpp/packages` | Create package |
| `GET /api/dpp/packages` | List packages |
| `GET /api/dpp/packages/{package_id}` | Get package |
| `PUT /api/dpp/packages/{package_id}` | Update package metadata |
| `DELETE /api/dpp/packages/{package_id}` | Delete package |
| `POST /api/dpp/packages/{package_id}/submodels` | Add submodel |
| `DELETE /api/dpp/packages/{package_id}/submodels/{template_name}` | Remove submodel |
| `POST /api/dpp/packages/{package_id}/validate` | Validate package compliance |
| `POST /api/dpp/packages/{package_id}/export` | Export package |
| `GET /api/dpp/suggested-submodels` | Suggested submodels |
| `GET /api/dpp/compliance-levels` | Compliance level definitions |

## SAMM Converter

| Endpoint | Description |
|---|---|
| `POST /api/samm/import` | Import SAMM payload |
| `POST /api/samm/import/file` | Import SAMM file |
| `POST /api/samm/export` | Export SAMM payload |
| `POST /api/samm/export/download` | Download Turtle file |
| `GET /api/samm/type-mappings` | Type mapping reference |
| `GET /api/samm/supported-formats` | Supported import/export formats |

## OPC UA Bridge

| Endpoint | Description |
|---|---|
| `POST /api/opcua/import` | Import NodeSet payload |
| `POST /api/opcua/import/file` | Import NodeSet file |
| `POST /api/opcua/export` | Export NodeSet payload |
| `POST /api/opcua/export/download` | Download NodeSet file |
| `POST /api/opcua/export/direct` | Direct export from UI schema |
| `GET /api/opcua/type-mappings` | Type mapping reference |
| `GET /api/opcua/supported-types` | Supported NodeSet types |

## Dataspace

### Connections

| Endpoint | Description | Auth |
|---|---|---|
| `POST /api/dataspace/connections` | Create connection | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/connections` | List connections | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/connections/{connection_id}` | Connection details/status | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/connections/{connection_id}/self-description` | Connector self-description | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `DELETE /api/dataspace/connections/{connection_id}` | Disconnect | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/connections/{connection_id}/reconnect` | Reconnect | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |

### Publications

| Endpoint | Description | Auth |
|---|---|---|
| `POST /api/dataspace/publications` | Publish submodel | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/publications` | List publications | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/publications/{publication_id}` | Publication details | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `PUT /api/dataspace/publications/{publication_id}` | Update publication | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `DELETE /api/dataspace/publications/{publication_id}` | Unpublish | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |

### Policies

| Endpoint | Description | Auth |
|---|---|---|
| `GET /api/dataspace/policies/templates` | Policy templates | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/policies/preview` | Preview ODRL | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/policies` | Create policy | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/policies/{policy_id}` | Get policy | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `PUT /api/dataspace/policies/{policy_id}` | Update policy | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `DELETE /api/dataspace/policies/{policy_id}` | Delete policy | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |

### Catalog, Negotiation, Transfers, Audit

| Endpoint | Description | Auth |
|---|---|---|
| `GET /api/dataspace/health` | Dataspace health summary | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/environments` | Available environments | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/edc-modes` | Available EDC modes | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/catalog/search` | Search catalog | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/catalog/{connection_id}/providers` | List known providers for a connection | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/catalog/{connection_id}/providers` | Add a known provider for a connection | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/catalog/negotiate` | Direct negotiation request | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/catalog/negotiations/{negotiation_id}` | Negotiation status | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/transfers` | Start transfer | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/transfers` | List transfers | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/transfers/{transfer_id}` | Transfer status | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/transfers/{transfer_id}/edr` | Transfer EDR details | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `POST /api/dataspace/transfers/{transfer_id}/terminate` | Terminate transfer | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/audit` | List audit entries | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
| `GET /api/dataspace/audit/{entry_id}` | Get audit entry | Bearer token when OIDC is enabled; ownership checks apply to resource-scoped operations |
