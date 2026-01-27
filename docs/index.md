# Universal IDTA Submodel Template Editor

A metamodel-driven application for editing any IDTA submodel template without code modifications. Built with Eclipse BaSyx Python SDK 2.0.0, FastAPI, and React 18+ with TypeScript.

---

## Quick Start

```bash
# Start the application
docker-compose up

# Open http://localhost:8080
# Select a template → Fill the form → Export as AASX/JSON/PDF
```

**That's it!** The editor auto-discovers templates from the [IDTA repository](https://github.com/admin-shell-io/submodel-templates).

### URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| AAS Browser (Mnestix) | http://localhost:3000 |

### Minimal Reproducible Demo

The core template editing functionality works **without external API keys**:

```bash
# 1. Start the application
docker-compose up

# 2. Open the editor
open http://localhost:8080

# 3. Complete a sample workflow:
#    - Select "Digital Nameplate" template
#    - Fill in manufacturer name and product designation
#    - Click "Export" → Download AASX file
#    - Validate: the downloaded .aasx contains your data
```

**Optional features requiring setup:**

- **Magic Import** (PDF extraction): Configure via UI or set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`
- **Dataspace Publishing**: Requires Manufacturing-X infrastructure
- **Online Semantic Lookup**: Requires ECLASS webservice credentials
- **PLC4X Bridge**: Requires industrial PLC connectivity

---

## Features

### Core Editing

- **Universal Editing** — Edit any IDTA template through the same interface
- **Metadata Preservation** — Qualifiers, EmbeddedDataSpecifications, and semantic IDs preserved
- **Multiple Export Formats** — AASX packages, JSON files, or PDF reports
- **Recursive Rendering** — Handles nested SubmodelElementCollections and Lists
- **Validation** — Client-side and server-side validation with cardinality enforcement

### Data Import

- **[Smart Mapper](features/smart-mapper.md)** — CSV/XLSX bulk import with column profiling and reusable recipes
- **[Magic Import](features/magic-import.md)** — PDF-to-AAS extraction with LLM and OCR support
    - **In-App Configuration** — Configure LLM providers via UI with encrypted API key storage
    - **Confidence Scoring** — 4-signal hybrid scoring (LLM, Localizer, OCR, Rules) with structured reason codes
    - **Document Intelligence** — Auto-detection of text/scanned/mixed PDFs with 70+ engineering unit normalization
    - **Validation & Provenance** — Schema validation, field evidence display, batch approve/reject operations
    - **Visual Feedback** — Color-coded PDF highlights (green/yellow/red) based on extraction confidence

### Template Management

- **[Template Operations](features/template-ops.md)** — Import, diff, migrate, and validate templates
    - **Version Comparison** — Structural diff between template versions with breaking change detection
    - **Recipe Migration** — Auto-migrate Smart Mapper recipes when templates change
    - **Form Data Migration** — Migrate in-progress form data to new template versions
    - **Three-Phase Algorithm** — Exact path match → Semantic ID match → Fuzzy matching with confidence scores

### Visualization

- **[Passport Mode](features/passport-mode.md)** — Digital Product Passport visualization with template-specific cards
- **AAS Browser** — Embedded Mnestix integration for exploring published AAS instances

### Industry Integration

- **[Semantic Lookup](features/semantic-lookup.md)** — Search ECLASS/IEC CDD dictionaries and attach semantic identifiers
- **[PCF Calculator](features/pcf-calculator.md)** — Carbon footprint calculation with IDTA 02023 validation
- **[PLC4X Bridge](features/plc4x-bridge.md)** — Real-time shopfloor data integration via Apache PLC4X (30+ industrial protocols)

### Dataspace Publishing

- **[Dataspace Connector](features/dataspace-publishing.md)** — Manufacturing-X / Catena-X connectivity
    - **Policy Builder** — Visual ODRL policy construction with pre-built templates
    - **Multiple Environments** — Sandbox, Catena-X Test, Catena-X Production
    - **EDC Modes** — Tractus-X EDC or AAS Extension mode
    - **Contract Negotiation** — Full EDC contract workflow with asset/policy/agreement management
    - **Audit Logging** — Track all dataspace operations

---

## Architecture

```
Fetcher → Parser → Hydrator → Validation
```

1. **Fetcher** — Discovers and caches IDTA templates from GitHub and local directories
2. **Parser** — Transforms AAS structures into UI-agnostic JSON schema
3. **Hydrator** — Reconstitutes complete AAS objects from form data
4. **Validation** — Enforces constraints on hydrate/export endpoints

### Tool Registry

The application uses a pluggable **Tool Registry** system for extensibility:

```
app.services.tools/
├── registry.py       # Auto-discovery and lifecycle management
├── base.py           # BaseTool interface with metadata
├── context.py        # Shared context for all tools
├── capabilities.py   # Dependency graph validation
└── builtin/          # Built-in tool implementations
```

**Key Features:**

- **Auto-Discovery** — Tools discovered at startup from Python packages
- **Lazy Loading** — Frontend components loaded on demand
- **Feature Flags** — Enable/disable tools via configuration
- **Health Checking** — Per-tool health status monitoring
- **Dependency Management** — Tools can declare dependencies on other tools
- **Categories** — `core`, `import`, `export`, `integration`, `analytics`

---

## Deployment

### Docker Compose Profiles

```bash
# Core stack
docker-compose up

# With authentication (Keycloak)
docker-compose --profile auth up

# With Magic Import (Celery + Redis for background jobs)
docker-compose --profile magic-import up

# With Dataspace (BaSyx, EDC, DTR, Vault, Mnestix)
docker-compose --profile dataspace up

# With Dataspace + PLC4X Bridge
docker-compose --profile dataspace --profile plc up

# Full stack (all features)
docker-compose --profile auth --profile magic-import --profile dataspace --profile plc up
```

### Kubernetes

```bash
# Base deployment
kubectl apply -k kubernetes/overlays/development

# With dataspace components
kubectl apply -k kubernetes/base/dataspace
kubectl apply -k kubernetes/overlays/production
```

---

## Configuration

Key environment variables (see [full reference](reference/configuration.md)):

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (development/staging/production) | development |
| `GITHUB_TOKEN` | GitHub API token (higher rate limits) | - |
| `VITE_API_URL` | Backend URL for frontend | http://localhost:8000 |
| `OIDC_ENABLED` | Enable authentication | false |
| `LOCAL_TEMPLATES_ENABLED` | Enable custom local templates | true |
| `LOCAL_TEMPLATES_DIR` | Directory for local AASX templates | ./templates/local |

### Feature Toggles

| Variable | Description | Default |
|----------|-------------|---------|
| `MAGIC_IMPORT_ENABLED` | Enable PDF extraction feature | true |
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `PLC4X_BRIDGE_ENABLED` | Enable PLC bridge feature | false |
| `MNESTIX_ENABLED` | Enable AAS Browser integration | true |

---

## Development

### Backend

```bash
cd backend

# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --port 8000

# Test
PYTHONPATH=backend pytest backend/tests

# Test specific subsystems
PYTHONPATH=backend pytest backend/tests/dataspace/
PYTHONPATH=backend pytest backend/tests/mapper/
PYTHONPATH=backend pytest backend/tests/magic_import/
```

### Frontend

```bash
cd frontend

# Setup
npm install

# Run
npm run dev

# Quality checks
npm run lint && npm run type-check
npm run test:unit
```

---

## Technology Stack

**Backend**: Python 3.11+ · FastAPI · Eclipse BaSyx SDK 2.0.0 · Pydantic v2 · Celery + Redis

**Frontend**: React 18 · TypeScript · React Hook Form · Zod · Vite · TanStack Query

**Dataspace**: Eclipse BaSyx · Tractus-X EDC · HashiCorp Vault · Mnestix

**PLC Bridge**: Java 17 · Spring Boot 3.2 · Apache PLC4X

**Infrastructure**: Docker · Kubernetes · Redis · Keycloak · PostgreSQL

---

## Project Structure

```
idta-submodel-editor/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── fetcher.py            # Template discovery
│   │   │   ├── parser.py             # AAS → UI schema
│   │   │   ├── hydrator.py           # Form data → AAS
│   │   │   ├── validation.py         # Constraint enforcement
│   │   │   ├── tools/                # Tool Registry system
│   │   │   ├── template_ops/         # Template operations
│   │   │   ├── mapper/               # Smart Mapper
│   │   │   ├── magic_import/         # PDF extraction
│   │   │   ├── semantic/             # Dictionary lookup
│   │   │   ├── pcf/                  # Carbon footprint
│   │   │   └── dataspace/            # Catena-X connector
│   │   ├── routers/                  # API endpoints
│   │   └── schemas/                  # Pydantic models
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── AASRenderer/          # Form renderer
│       │   ├── PassportMode/         # DPP visualization
│       │   ├── MagicImport/          # PDF extraction UI
│       │   ├── SmartMapper/          # Bulk import
│       │   ├── TemplateOps/          # Template operations UI
│       │   ├── DataspaceConnector/   # Dataspace UI
│       │   └── PolicyBuilder/        # ODRL policy UI
│       ├── tools/                    # Frontend tool registry
│       └── hooks/                    # useSubmodelForm, etc.
├── plc4x-bridge/                     # PLC integration microservice
├── docs/
│   ├── features/                     # Feature documentation
│   └── reference/                    # Configuration, API, element types
├── kubernetes/
│   ├── base/
│   │   └── dataspace/                # Dataspace component manifests
│   └── overlays/
└── docker-compose.yaml
```

---

## Documentation

- [Features Overview](features/README.md)
- [Configuration Reference](reference/configuration.md)
- [API Endpoints](reference/api-endpoints.md)
- [Supported Element Types](reference/element-types.md)

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest` (backend), `npm run lint && npm run type-check` (frontend)
4. Submit a pull request

### CI & Conformance

CI runs backend tests, frontend quality checks, and AAS conformance validation. Conformance fixtures in `backend/tests/fixtures/` are auto-generated via nightly workflow.

---

## License

MIT License

## Acknowledgments

- [IDTA](https://industrialdigitaltwin.org/) — Submodel template specifications
- [Eclipse BaSyx](https://www.eclipse.org/basyx/) — AAS SDK
- [admin-shell-io](https://github.com/admin-shell-io/submodel-templates) — Template repository
- [Tractus-X](https://eclipse-tractusx.github.io/) — EDC connector
- [Mnestix](https://github.com/eclipse-mnestix/mnestix-browser) — AAS Browser
- [Apache PLC4X](https://plc4x.apache.org/) — Industrial protocol library
