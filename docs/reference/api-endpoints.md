# API Endpoints Reference

Full API documentation is available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc) when running the backend.

## Templates

| Endpoint | Description |
|----------|-------------|
| `GET /api/templates` | List available templates (`status=published\|deprecated\|all`) |
| `GET /api/templates/{name}` | Get template information |
| `GET /api/templates/{name}/versions` | Get template versions |
| `POST /api/templates/refresh` | Refresh template cache |

## Editor

| Endpoint | Description |
|----------|-------------|
| `GET /api/editor/templates/{name}/schema` | Get UI schema for a template |
| `POST /api/editor/hydrate/{name}` | Hydrate template with form data (returns AASX) |
| `POST /api/editor/hydrate/{name}/json` | Hydrate template (returns JSON) |
| `POST /api/editor/upload` | Upload and parse an AASX file |
| `POST /api/editor/validate/{name}` | Validate form data |

## Export

| Endpoint | Description |
|----------|-------------|
| `POST /api/export/{name}?format=aasx\|json\|pdf` | Export filled submodel |
| `GET /api/export/{name}/preview` | Get template preview |
| `POST /api/export/batch` | Batch export as ZIP |

## Dataspace

| Endpoint | Description |
|----------|-------------|
| `POST /api/dataspace/connections` | Create a dataspace connection |
| `GET /api/dataspace/connections` | List dataspace connections |
| `GET /api/dataspace/connections/{id}` | Connection status + health |
| `POST /api/dataspace/publications` | Publish submodel to dataspace |
| `GET /api/dataspace/health` | Dataspace health status |

## Semantic

| Endpoint | Description |
|----------|-------------|
| `GET /api/semantic/providers` | List semantic providers |
| `GET /api/semantic/search` | Search semantic dictionaries |
| `GET /api/semantic/resolve` | Resolve ID/IRI to metadata |
| `POST /api/semantic/apply-preview` | Suggest semanticId + type warnings |

## Mapper

| Endpoint | Description |
|----------|-------------|
| `POST /api/mapper/profile` | Profile CSV/XLSX headers |
| `POST /api/mapper/auto-suggest` | Auto-suggest column mappings |
| `POST /api/mapper/run` | Run mapping |
| `GET /api/mapper/recipes` | List saved recipes |
| `POST /api/mapper/recipes` | Save recipe |
| `GET /api/mapper/recipes/{name}` | Fetch recipe |
| `DELETE /api/mapper/recipes/{name}` | Delete recipe |

## PCF (Carbon Footprint)

| Endpoint | Description |
|----------|-------------|
| `POST /api/pcf/calculate` | Calculate CO₂e emissions |
| `POST /api/pcf/validate` | Validate against IDTA 02023 |
| `GET /api/pcf/factors/search` | Search emission factors |
| `GET /api/pcf/factors/{id}` | Get emission factor |
| `GET /api/pcf/health` | PCF service health |

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
