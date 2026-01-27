# API Endpoints Reference

Full API documentation is available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc) when running the backend.

---

## Templates

| Endpoint | Description |
|----------|-------------|
| `GET /api/templates` | List available templates (`status=published\|deprecated\|all`) |
| `GET /api/templates/{name}` | Get template information |
| `GET /api/templates/{name}/versions` | Get template versions |
| `POST /api/templates/refresh` | Refresh template cache |

---

## Editor

| Endpoint | Description |
|----------|-------------|
| `GET /api/editor/templates/{name}/schema` | Get UI schema for a template |
| `POST /api/editor/hydrate/{name}` | Hydrate template with form data (returns AASX) |
| `POST /api/editor/hydrate/{name}/json` | Hydrate template (returns JSON) |
| `POST /api/editor/upload` | Upload and parse an AASX file |
| `POST /api/editor/validate/{name}` | Validate form data |

---

## Export

| Endpoint | Description |
|----------|-------------|
| `POST /api/export/{name}?format=aasx\|json\|pdf` | Export filled submodel |
| `GET /api/export/{name}/preview` | Get template preview |
| `POST /api/export/batch` | Batch export as ZIP |

---

## Template Operations

| Endpoint | Description |
|----------|-------------|
| `POST /api/template-ops/diff` | Compare two template versions |
| `POST /api/template-ops/import` | Import AASX as local template |
| `POST /api/template-ops/migrate/recipe` | Migrate Smart Mapper recipe to new template |
| `POST /api/template-ops/migrate/form-data` | Migrate form data to new template version |
| `POST /api/template-ops/check-mismatch` | Check if saved data matches current schema |
| `POST /api/template-ops/digest` | Compute schema digest for version tracking |

---

## Tools

| Endpoint | Description |
|----------|-------------|
| `GET /api/tools/manifest` | Get all registered tools with metadata |
| `GET /api/tools/{id}/health` | Check individual tool health status |

---

## Dataspace

### Connection Management

| Endpoint | Description |
|----------|-------------|
| `POST /api/dataspace/connections` | Create a dataspace connection (onboarding) |
| `GET /api/dataspace/connections` | List dataspace connections |
| `GET /api/dataspace/connections/{id}` | Connection status + health checks |
| `DELETE /api/dataspace/connections/{id}` | Disconnect from dataspace |
| `POST /api/dataspace/connections/{id}/reconnect` | Reconnect failed connection |

### Publication Management

| Endpoint | Description |
|----------|-------------|
| `POST /api/dataspace/publications` | Publish submodel to dataspace |
| `GET /api/dataspace/publications` | List publications (filter by connection, template, status) |
| `GET /api/dataspace/publications/{id}` | Get publication details |
| `PUT /api/dataspace/publications/{id}` | Update published submodel |
| `DELETE /api/dataspace/publications/{id}` | Unpublish submodel |

### Policy Management

| Endpoint | Description |
|----------|-------------|
| `GET /api/dataspace/policies/templates` | Get pre-built policy templates |
| `POST /api/dataspace/policies/preview` | Preview ODRL from policy config |
| `POST /api/dataspace/policies` | Create new policy |
| `GET /api/dataspace/policies/{id}` | Get policy details |
| `PUT /api/dataspace/policies/{id}` | Update policy |
| `DELETE /api/dataspace/policies/{id}` | Delete policy |

### Health & Discovery

| Endpoint | Description |
|----------|-------------|
| `GET /api/dataspace/health` | Dataspace health status |
| `GET /api/dataspace/environments` | List available dataspace environments |
| `GET /api/dataspace/edc-modes` | List available EDC connector modes |

---

## Semantic

| Endpoint | Description |
|----------|-------------|
| `GET /api/semantic/providers` | List semantic providers |
| `GET /api/semantic/search` | Search semantic dictionaries |
| `GET /api/semantic/resolve` | Resolve ID/IRI to metadata |
| `POST /api/semantic/apply-preview` | Suggest semanticId + type warnings |

---

## Mapper (Smart Mapper)

| Endpoint | Description |
|----------|-------------|
| `POST /api/mapper/profile` | Profile CSV/XLSX headers |
| `POST /api/mapper/auto-suggest` | Auto-suggest column mappings |
| `POST /api/mapper/run` | Run mapping |
| `GET /api/mapper/recipes` | List saved recipes |
| `POST /api/mapper/recipes` | Save recipe |
| `GET /api/mapper/recipes/{name}` | Fetch recipe |
| `DELETE /api/mapper/recipes/{name}` | Delete recipe |

---

## PCF (Carbon Footprint)

| Endpoint | Description |
|----------|-------------|
| `POST /api/pcf/calculate` | Calculate CO₂e emissions |
| `POST /api/pcf/validate` | Validate against IDTA 02023 |
| `GET /api/pcf/factors/search` | Search emission factors |
| `GET /api/pcf/factors/{id}` | Get emission factor |
| `GET /api/pcf/health` | PCF service health |

---

## Magic Import

| Endpoint | Description |
|----------|-------------|
| `POST /api/magic-import/jobs` | Create extraction job |
| `GET /api/magic-import/jobs/{id}` | Get job status |
| `GET /api/magic-import/jobs/{id}/result` | Get extraction results |
| `GET /api/magic-import/jobs/{id}/pdf` | Download PDF |
| `DELETE /api/magic-import/jobs/{id}` | Clean up job |
| `GET /api/magic-import/jobs` | List recent jobs |
| `POST /api/magic-import/health` | Service health check |

---

## PLC4X Bridge

These endpoints are served by the PLC4X Bridge microservice (default port 8090):

| Endpoint | Description |
|----------|-------------|
| `GET /api/plc/status` | Get PLC connection status |
| `POST /api/plc/connect` | Connect to PLC |
| `POST /api/plc/disconnect` | Disconnect from PLC |
| `GET /api/plc/tags` | List discovered PLC tags |
| `POST /api/plc/mappings` | Configure tag-to-AAS mappings |
| `GET /api/plc/readings` | Get current tag values |

---

## Authentication

When `OIDC_ENABLED=true`:

| Endpoint | Description |
|----------|-------------|
| `GET /api/auth/me` | Get current user info |
| `POST /api/auth/logout` | Logout (revoke token) |
