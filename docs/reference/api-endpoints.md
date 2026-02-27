# API Endpoints Reference

Swagger UI is available at `/api/docs` and ReDoc at `/api/redoc` when backend `ENV != production`.

## Health and Observability

| Endpoint | Description |
|---|---|
| `GET /health` | Basic health check |
| `GET /health/liveness` | Liveness probe |
| `GET /health/readiness` | Readiness probe |
| `GET /health/startup` | Startup probe |
| `GET /metrics` | Prometheus metrics |

## Public Settings

| Endpoint | Description |
|---|---|
| `GET /api/settings` | Public frontend settings (`mnestix_enabled`, `mnestix_url`, `dataspace_enabled`, etc.) |

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
| `GET /api/editor/templates/{template_name}/schema/{version}` | Get schema for explicit version |
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

| Endpoint | Description |
|---|---|
| `GET /api/tools` | List tools with metadata |
| `GET /api/tools/health` | Overall tool health |
| `GET /api/tools/manifest` | Tool manifest used by frontend |
| `GET /api/tools/{tool_id}` | Tool capability report |
| `GET /api/tools/{tool_id}/health` | Tool-specific health |
| `GET /api/tools/{tool_id}/capabilities` | Tool capabilities details |

## Settings Management

| Endpoint | Description |
|---|---|
| `GET /api/settings/llm` | Get active provider/model configuration (keys masked) |
| `PUT /api/settings/llm` | Update provider/model/threshold/OCR settings |
| `POST /api/settings/llm/validate` | Validate provider credentials without saving |
| `GET /api/settings/llm/models/{provider}` | List provider models |
| `DELETE /api/settings/llm/api-key/{provider}` | Remove stored API key |
| `GET /api/settings/features` | Read runtime feature flags |
| `PUT /api/settings/features` | Update runtime feature flags |

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

| Endpoint | Description |
|---|---|
| `POST /api/dataspace/connections` | Create connection |
| `GET /api/dataspace/connections` | List connections |
| `GET /api/dataspace/connections/{connection_id}` | Connection details/status |
| `GET /api/dataspace/connections/{connection_id}/self-description` | Connector self-description |
| `DELETE /api/dataspace/connections/{connection_id}` | Disconnect |
| `POST /api/dataspace/connections/{connection_id}/reconnect` | Reconnect |

### Publications

| Endpoint | Description |
|---|---|
| `POST /api/dataspace/publications` | Publish submodel |
| `GET /api/dataspace/publications` | List publications |
| `GET /api/dataspace/publications/{publication_id}` | Publication details |
| `PUT /api/dataspace/publications/{publication_id}` | Update publication |
| `DELETE /api/dataspace/publications/{publication_id}` | Unpublish |

### Policies

| Endpoint | Description |
|---|---|
| `GET /api/dataspace/policies/templates` | Policy templates |
| `POST /api/dataspace/policies/preview` | Preview ODRL |
| `POST /api/dataspace/policies` | Create policy |
| `GET /api/dataspace/policies/{policy_id}` | Get policy |
| `PUT /api/dataspace/policies/{policy_id}` | Update policy |
| `DELETE /api/dataspace/policies/{policy_id}` | Delete policy |

### Catalog, Negotiation, Transfers, Audit

| Endpoint | Description |
|---|---|
| `GET /api/dataspace/health` | Dataspace health summary |
| `GET /api/dataspace/environments` | Available environments |
| `GET /api/dataspace/edc-modes` | Available EDC modes |
| `POST /api/dataspace/catalog/search` | Search catalog |
| `GET /api/dataspace/catalog/{connection_id}/providers` | List known providers for a connection |
| `POST /api/dataspace/catalog/{connection_id}/providers` | Add a known provider for a connection |
| `POST /api/dataspace/catalog/negotiate` | Direct negotiation request |
| `GET /api/dataspace/catalog/negotiations/{negotiation_id}` | Negotiation status |
| `POST /api/dataspace/transfers` | Start transfer |
| `GET /api/dataspace/transfers` | List transfers |
| `GET /api/dataspace/transfers/{transfer_id}` | Transfer status |
| `GET /api/dataspace/transfers/{transfer_id}/edr` | Transfer EDR details |
| `POST /api/dataspace/transfers/{transfer_id}/terminate` | Terminate transfer |
| `GET /api/dataspace/audit` | List audit entries |
| `GET /api/dataspace/audit/{entry_id}` | Get audit entry |
