# Universal IDTA Submodel Template Editor

A metamodel-driven application for editing any IDTA submodel template without code modifications. Built with Eclipse BaSyx Python SDK 2.0.0, FastAPI, and React 18+ with TypeScript.

<p align="center">
  <a href="https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml"><img src="https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"/></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose"/></a>
  <a href="https://github.com/hadijannat/idta-submodel-editor/tags"><img src="https://img.shields.io/badge/version-1.0.0-2F80ED" alt="Version"/></a>
  <a href="https://github.com/hadijannat"><img src="https://img.shields.io/badge/Author-Hadi%20Jannatabadi-blue" alt="Author"/></a>
  <a href="https://www.iat.rwth-aachen.de/"><img src="https://img.shields.io/badge/RWTH-IAT-green" alt="RWTH Aachen"/></a>
</p>

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

To disable optional features explicitly:
```bash
MAGIC_IMPORT_ENABLED=false DATASPACE_ENABLED=false docker-compose up
```

---

## Features

### Core Editing

- **Universal Editing** — Edit any IDTA template through the same interface
- **Metadata Preservation** — Qualifiers, EmbeddedDataSpecifications, and semantic IDs preserved
- **Multiple Export Formats** — AASX packages, JSON files, or PDF reports
- **Recursive Rendering** — Handles nested SubmodelElementCollections and Lists
- **Validation** — Client-side and server-side validation with cardinality enforcement

### Data Import

- **[Smart Mapper](docs/features/smart-mapper.md)** — CSV/XLSX bulk import with column profiling and reusable recipes
- **[Magic Import](docs/features/magic-import.md)** — PDF-to-AAS extraction with LLM and OCR support
  - **Confidence Scoring** — 4-signal hybrid scoring (LLM, Localizer, OCR, Rules) with structured reason codes
  - **Document Intelligence** — Auto-detection of text/scanned/mixed PDFs with 70+ engineering unit normalization
  - **Validation & Provenance** — Schema validation, field evidence display, batch approve/reject operations
  - **Visual Feedback** — Color-coded PDF highlights (green/yellow/red) based on extraction confidence

### Template Management

- **[Template Operations](docs/features/template-ops.md)** — Import, diff, migrate, and validate templates
  - **Version Comparison** — Structural diff between template versions with breaking change detection
  - **Recipe Migration** — Auto-migrate Smart Mapper recipes when templates change
  - **Form Data Migration** — Migrate in-progress form data to new template versions
  - **Three-Phase Algorithm** — Exact path match → Semantic ID match → Fuzzy matching with confidence scores

### Visualization

- **[Passport Mode](docs/features/passport-mode.md)** — Digital Product Passport visualization with template-specific cards
- **AAS Browser** — Embedded Mnestix integration for exploring published AAS instances

### Industry Integration

- **[Semantic Lookup](docs/features/semantic-lookup.md)** — Search ECLASS/IEC CDD dictionaries and attach semantic identifiers
- **[PCF Calculator](docs/features/pcf-calculator.md)** — Carbon footprint calculation with IDTA 02023 validation
- **[PLC4X Bridge](#plc4x-bridge)** — Real-time shopfloor data integration via Apache PLC4X (30+ industrial protocols)

### Dataspace Publishing

- **[Dataspace Connector](docs/features/dataspace-publishing.md)** — Manufacturing-X / Catena-X connectivity
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
    ├── smart_mapper_tool.py
    ├── magic_import_tool.py
    ├── dataspace_tool.py
    ├── template_ops_tool.py
    ├── semantic_tool.py
    ├── pcf_tool.py
    └── export_tool.py
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

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (development/staging/production) | development |
| `GITHUB_TOKEN` | GitHub API token (higher rate limits) | - |
| `VITE_API_URL` | Backend URL for frontend | http://localhost:8000 |
| `OIDC_ENABLED` | Enable authentication | false |
| `LOCAL_TEMPLATES_ENABLED` | Enable custom local templates | true |
| `LOCAL_TEMPLATES_DIR` | Directory for local AASX templates | ./templates/local |

### Magic Import Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `MAGIC_IMPORT_ENABLED` | Enable PDF extraction feature | true |
| `MAGIC_IMPORT_LLM_PROVIDER` | LLM provider (openai/anthropic/openrouter/local) | openai |
| `MAGIC_IMPORT_LLM_MODEL` | LLM model name | gpt-4o-mini |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENROUTER_API_KEY` | OpenRouter API key (100+ models) | - |
| `OLLAMA_BASE_URL` | Ollama server URL (for local provider) | http://localhost:11434 |
| `SETTINGS_STORAGE_DIR` | Directory for encrypted settings | ./cache/settings |
| `MAGIC_IMPORT_OCR_ENABLED` | Enable OCR fallback | true |
| `MAGIC_IMPORT_CONFIDENCE_THRESHOLD` | Minimum confidence for auto-accept | 0.80 |
| `CELERY_BROKER_URL` | Redis URL for Celery | redis://localhost:6379/0 |

### Dataspace Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `DATASPACE_DEFAULT_ENVIRONMENT` | Default environment | sandbox |
| `DATASPACE_DEFAULT_EDC_MODE` | EDC connector mode | tractus-x |
| `BASYX_AAS_SERVER_URL` | BaSyx AAS Server | http://basyx-aas-server:4001 |
| `BASYX_REGISTRY_URL` | BaSyx Registry | http://basyx-registry:4002 |
| `EDC_CONTROL_PLANE_URL` | EDC Control Plane | http://edc-control-plane:19192 |
| `EDC_DATA_PLANE_URL` | EDC Data Plane | http://edc-data-plane:19291 |
| `EDC_API_KEY` | EDC Management API key | - |
| `EDC_AAS_EXTENSION_URL` | EDC AAS Extension URL (alternative mode) | - |
| `DTR_URL` | Digital Twin Registry | http://dtr:4003 |
| `VAULT_URL` | HashiCorp Vault | http://vault:8200 |
| `VAULT_TOKEN` | Vault access token | - |
| `CATENA_X_BPN` | Business Partner Number | - |

### PLC4X Bridge Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `PLC4X_BRIDGE_ENABLED` | Enable PLC bridge feature | false |
| `PLC4X_BRIDGE_URL` | PLC4X Bridge microservice URL | - |

PLC4X Bridge is configured via its own `application.yml`:

| Property | Description | Default |
|----------|-------------|---------|
| `plc.connection-string` | PLC4X connection string (e.g., `s7://192.168.1.10`) | - |
| `plc.read-interval` | Polling interval in milliseconds | 1000 |
| `mapping.update-mode` | Update mode (ON_CHANGE/ALWAYS) | ON_CHANGE |
| `mapping.change-threshold` | Deadband for ON_CHANGE mode | 0.01 |
| `basyx.aas-server.url` | BaSyx AAS Server URL | http://basyx-aas-server:4001 |

### Mnestix Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `MNESTIX_ENABLED` | Enable AAS Browser integration | true |
| `MNESTIX_URL` | Mnestix instance URL | http://mnestix:3000 |

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
│   │   │   │   ├── registry.py       # Auto-discovery & lifecycle
│   │   │   │   ├── base.py           # BaseTool interface
│   │   │   │   └── builtin/          # Built-in tools
│   │   │   ├── template_ops/         # Template operations
│   │   │   │   └── migration_service.py
│   │   │   ├── mapper/               # Smart Mapper
│   │   │   ├── magic_import/         # PDF extraction
│   │   │   ├── semantic/             # Dictionary lookup
│   │   │   ├── pcf/                  # Carbon footprint
│   │   │   └── dataspace/            # Catena-X connector
│   │   │       ├── connection_manager.py
│   │   │       ├── publisher.py
│   │   │       ├── registry/         # BaSyx & DTR clients
│   │   │       ├── edc/              # EDC clients
│   │   │       └── policy/           # ODRL policy builder
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
│       │   │   ├── MigrationWizard.tsx
│       │   │   └── VersionDiffView.tsx
│       │   ├── DataspaceConnector/   # Dataspace UI
│       │   └── PolicyBuilder/        # ODRL policy UI
│       ├── tools/                    # Frontend tool registry
│       │   ├── manifest.ts
│       │   ├── ToolShell.tsx
│       │   └── hooks/useTools.ts
│       └── hooks/                    # useSubmodelForm, etc.
├── plc4x-bridge/                     # PLC integration microservice
│   ├── src/main/java/com/idta/plc4x/
│   │   ├── controller/PlcController.java
│   │   └── service/
│   │       ├── PlcReader.java
│   │       ├── ContinuousReader.java
│   │       └── AasUpdater.java
│   └── pom.xml
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

## API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates` | List available templates |
| GET | `/api/editor/templates/{name}/schema` | Get UI schema for template |
| POST | `/api/editor/validate/{name}` | Validate form data |
| POST | `/api/export/{name}` | Export as AASX/JSON/PDF |

### Template Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/template-ops/diff` | Compare two template versions |
| POST | `/api/template-ops/import` | Import AASX as local template |
| POST | `/api/template-ops/migrate/recipe` | Migrate Smart Mapper recipe |
| POST | `/api/template-ops/migrate/form-data` | Migrate form data |
| POST | `/api/template-ops/check-mismatch` | Check version mismatch |
| POST | `/api/template-ops/digest` | Compute schema digest |

### Dataspace

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dataspace/connections` | Start dataspace onboarding |
| GET | `/api/dataspace/connections` | List connections |
| GET | `/api/dataspace/connections/{id}` | Get connection status |
| DELETE | `/api/dataspace/connections/{id}` | Disconnect |
| POST | `/api/dataspace/publications` | Publish submodel |
| GET | `/api/dataspace/publications` | List publications |
| GET | `/api/dataspace/policies/templates` | Get policy templates |
| POST | `/api/dataspace/policies/preview` | Preview ODRL from config |
| GET | `/api/dataspace/health` | Check component health |
| GET | `/api/dataspace/environments` | List available environments |

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tools/manifest` | Get all registered tools |
| GET | `/api/tools/{id}/health` | Check tool health |

---

## PLC4X Bridge

The PLC4X Bridge is a separate Java/Spring Boot microservice that integrates industrial PLCs with the AAS Server.

### Supported Protocols

Via Apache PLC4X: **Modbus TCP/RTU**, **OPC UA**, **S7 (Siemens)**, **EtherNet/IP**, **BACnet**, **ADS (Beckhoff)**, **KNX**, and 30+ others.

### Architecture

```
PLC ──────────► PlcReader ──────────► ContinuousReader ──────────► AasUpdater ──────────► BaSyx
  (Protocol)     (Connect)             (Poll @ interval)           (Update)              (AAS Server)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plc/status` | Get connection status |
| POST | `/api/plc/connect` | Connect to PLC |
| POST | `/api/plc/disconnect` | Disconnect from PLC |
| GET | `/api/plc/tags` | List discovered tags |
| POST | `/api/plc/mappings` | Configure tag-to-AAS mappings |
| GET | `/api/plc/readings` | Get current tag values |

---

## Technology Stack

**Backend**: Python 3.11+ · FastAPI · Eclipse BaSyx SDK 2.0.0 · Pydantic v2 · Celery + Redis

**Frontend**: React 18 · TypeScript · React Hook Form · Zod · Vite · TanStack Query

**Dataspace**: Eclipse BaSyx · Tractus-X EDC · HashiCorp Vault · Mnestix

**PLC Bridge**: Java 17 · Spring Boot 3.2 · Apache PLC4X

**Infrastructure**: Docker · Kubernetes · Redis · Keycloak · PostgreSQL

---

## Documentation

- [Features Overview](docs/features/README.md)
- [Configuration Reference](docs/reference/configuration.md)
- [API Endpoints](docs/reference/api-endpoints.md)
- [Supported Element Types](docs/reference/element-types.md)

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest` (backend), `npm run lint && npm run type-check` (frontend)
4. Submit a pull request

### CI & Conformance

CI runs backend tests, frontend quality checks, and AAS conformance validation. Conformance fixtures in `backend/tests/fixtures/` are auto-generated via nightly workflow.

---

## Citing this Project

If you use this software in academic work, please cite:

```bibtex
@software{jannatabadi2024idta,
  author = {Jannatabadi, Hadi},
  title = {IDTA Submodel Editor},
  year = {2024},
  url = {https://github.com/hadijannat/idta-submodel-editor},
  license = {MIT}
}
```

Or use the "Cite this repository" button on GitHub (generated from CITATION.cff).

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
