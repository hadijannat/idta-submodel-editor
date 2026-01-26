# Universal IDTA Submodel Template Editor

A metamodel-driven application for editing any IDTA submodel template without code modifications. Built with Eclipse BaSyx Python SDK 2.0.0, FastAPI, and React 18+ with TypeScript.

<p align="center">
  <a href="https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml"><img src="https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"/></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose"/></a>
  <a href="https://github.com/hadijannat/idta-submodel-editor/tags"><img src="https://img.shields.io/badge/version-1.0.0-2F80ED" alt="Version"/></a>
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

---

## Features

- **[Semantic Lookup](docs/features/semantic-lookup.md)** — Search ECLASS/IEC CDD dictionaries and attach semantic identifiers
- **[Smart Mapper](docs/features/smart-mapper.md)** — CSV/XLSX bulk import with column profiling and reusable recipes
- **[PCF Calculator](docs/features/pcf-calculator.md)** — Carbon footprint calculation with IDTA 02023 validation
- **[Passport Mode](docs/features/passport-mode.md)** — Digital Product Passport visualization
- **[Magic Import](docs/features/magic-import.md)** — PDF-to-AAS extraction with LLM and OCR support
  - **Confidence Scoring** — 4-signal hybrid scoring (LLM, Localizer, OCR, Rules) with structured reason codes
  - **Document Intelligence** — Auto-detection of text/scanned/mixed PDFs with 70+ engineering unit normalization
  - **Validation & Provenance** — Schema validation, field evidence display, batch approve/reject operations
  - **Visual Feedback** — Color-coded PDF highlights (green/yellow/red) based on extraction confidence
- **[Dataspace Publishing](docs/features/dataspace-publishing.md)** — Manufacturing-X / Catena-X connectivity

### Core Capabilities

- **Universal Editing** — Edit any IDTA template through the same interface
- **Metadata Preservation** — Qualifiers, EmbeddedDataSpecifications, and semantic IDs preserved
- **Multiple Export Formats** — AASX packages, JSON files, or PDF reports
- **Recursive Rendering** — Handles nested SubmodelElementCollections and Lists
- **Validation** — Client-side and server-side validation with cardinality enforcement

---

## Architecture

```
Fetcher → Parser → Hydrator → Validation
```

1. **Fetcher** — Discovers and caches IDTA templates from GitHub
2. **Parser** — Transforms AAS structures into UI-agnostic JSON schema
3. **Hydrator** — Reconstitutes complete AAS objects from form data
4. **Validation** — Enforces constraints on hydrate/export endpoints

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

## Deployment

### Docker Compose Profiles

```bash
# Core stack
docker-compose up

# With authentication (Keycloak)
docker-compose --profile auth up

# With Magic Import (Celery + Redis)
docker-compose --profile magic-import up

# With Dataspace (BaSyx, EDC, DTR, Vault)
docker-compose --profile dataspace up
```

### Kubernetes

```bash
kubectl apply -k kubernetes/overlays/production
```

---

## Configuration

Key environment variables (see [full reference](docs/reference/configuration.md)):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | development / staging / production | development |
| `GITHUB_TOKEN` | GitHub API token (higher rate limits) | - |
| `VITE_API_URL` | Backend URL for frontend | http://localhost:8000 |
| `OIDC_ENABLED` | Enable authentication | false |
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `MAGIC_IMPORT_LLM_PROVIDER` | LLM provider (openai/anthropic/local) | openai |
| `MAGIC_IMPORT_VALIDATION_MODE` | Validation strictness (strict/warn/off) | warn |

---

## Technology Stack

**Backend**: Python 3.11+ · FastAPI · Eclipse BaSyx SDK 2.0.0 · Pydantic v2 · Celery + Redis

**Frontend**: React 18 · TypeScript · React Hook Form · Zod · Vite

**Infrastructure**: Docker · Kubernetes · Redis · Keycloak

---

## Project Structure

```
idta-submodel-editor/
├── backend/
│   ├── app/
│   │   ├── services/          # Core: fetcher, parser, hydrator, validation
│   │   │   ├── pcf/           # Carbon footprint calculator
│   │   │   ├── semantic/      # Dictionary lookup
│   │   │   ├── mapper/        # CSV/XLSX import
│   │   │   ├── magic_import/  # PDF extraction
│   │   │   └── dataspace/     # Catena-X connector
│   │   └── routers/           # API endpoints
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/        # React components
│       │   ├── AASRenderer/   # Form renderer
│       │   ├── PassportMode/  # DPP visualization
│       │   ├── MagicImport/   # PDF extraction UI
│       │   └── SmartMapper/   # Bulk import
│       └── hooks/             # useSubmodelForm, etc.
├── docs/
│   ├── features/              # Feature documentation
│   └── reference/             # Configuration, API, element types
├── kubernetes/
│   ├── base/
│   └── overlays/
└── docker-compose.yaml
```

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

## License

MIT License

## Acknowledgments

- [IDTA](https://industrialdigitaltwin.org/) — Submodel template specifications
- [Eclipse BaSyx](https://www.eclipse.org/basyx/) — AAS SDK
- [admin-shell-io](https://github.com/admin-shell-io/submodel-templates) — Template repository
