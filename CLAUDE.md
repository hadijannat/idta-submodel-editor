# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Universal IDTA Submodel Template Editor - a metamodel-driven application for editing any IDTA submodel template without code modifications. Uses Eclipse BaSyx Python SDK 2.0.0, FastAPI, and React 18+ with TypeScript.

## Development Commands

### Backend (Python/FastAPI)

```bash
# Run all tests
PYTHONPATH=backend pytest backend/tests

# Run a single test file
PYTHONPATH=backend pytest backend/tests/test_parser.py

# Run a single test function
PYTHONPATH=backend pytest backend/tests/test_parser.py::test_parse_property -v

# Run tests in a subdirectory (e.g., PCF tests)
PYTHONPATH=backend pytest backend/tests/pcf/

# Start development server
cd backend && uvicorn app.main:app --reload --port 8000
```

### Frontend (React/TypeScript)

```bash
cd frontend

npm run dev          # Dev server on :8080
npm run lint         # ESLint (fails on warnings)
npm run type-check   # TypeScript check (tsc --noEmit)
npm run build        # Production build
npm run test:unit    # Run all Vitest tests

# Run specific test file
npx vitest run src/components/PassportMode/__tests__/PassportView.integration.test.tsx
```

### Full Stack

```bash
docker-compose up                    # Start full stack
docker-compose --profile auth up     # With Keycloak authentication
docker-compose --profile magic-import up  # With Magic Import (Celery + Redis)
docker-compose --profile dataspace up     # With Dataspace (BaSyx, EDC, DTR, Vault)
docker-compose --profile dataspace --profile plc up  # Dataspace + PLC4X Bridge
```

## Architecture

The application follows a **three-pipeline architecture**:

```
Fetcher → Parser → Hydrator → Validation
```

1. **Fetcher** (`backend/app/services/fetcher.py`): Discovers and caches IDTA templates from GitHub (`admin-shell-io/submodel-templates`) and local templates (`./templates/local`)

2. **Parser** (`backend/app/services/parser.py`): Transforms Eclipse BaSyx AAS objects → UI-agnostic JSON schema. Recursively handles nested SubmodelElementCollections/Lists, extracts semantic info from ConceptDescriptions, resolves cardinality from Qualifiers

3. **Hydrator** (`backend/app/services/hydrator.py`): Reconstitutes complete AAS objects from form data, preserving metadata (Qualifiers, EmbeddedDataSpecifications, semantic IDs)

4. **Validation** (`backend/app/services/validation.py`): Shared validation logic enforced on hydrate/export endpoints

### Feature-Specific Subsystems

- **Semantic Lookup** (`backend/app/services/semantic/`): ECLASS/IEC CDD dictionary search with offline indices (JSON/CSV/SQLite) and optional online ECLASS webservice (mTLS). Provider pattern: `provider_base.py` → `offline_provider.py` | `eclass_online_provider.py`

- **Smart Mapper** (`backend/app/services/mapper/`): CSV/XLSX bulk import with column profiling, semantic-aware auto-mapping, transformation options, and recipe persistence

- **PCF Calculator** (`backend/app/services/pcf/`): Carbon Footprint calculation with emission factor database (`emission_factors.py`), CO₂e calculator (`calculator.py`), IDTA 02023 validator (`validator.py`), and activity list injection (`activity_list.py`)

- **Passport Mode** (`frontend/src/components/PassportMode/`): WYSIWYG Digital Product Passport visualization with template-specific cards (Nameplate, PCF, Generic). Uses registry-based detection and schema-indexed value extraction

- **Magic Import** (`backend/app/services/magic_import/`): PDF-to-AAS extraction pipeline with LLM providers (OpenAI/Anthropic/Ollama), OCR fallback, BM25 retrieval, evidence localization, and confidence scoring. Provider factory: `llm/factory.py` → `openai_provider.py` | `anthropic_provider.py` | `local_provider.py`. Background jobs via Celery + Redis

- **Dataspace Connector** (`backend/app/services/dataspace/`): Manufacturing-X / Catena-X dataspace integration. Manages connections, publications, and ODRL policies for sovereign data exchange. Key subsystems:
  - `connection_manager.py`: Connection lifecycle (create/connect/disconnect), state persistence
  - `publisher.py`: Submodel publication orchestration (hydrate → BaSyx → DTR → EDC)
  - `registry/basyx_client.py`: Eclipse BaSyx AAS Server API client
  - `registry/dtr_client.py`: Catena-X Digital Twin Registry client
  - `edc/tractus_x_client.py`: Tractus-X EDC Management API client
  - `edc/aas_extension_client.py`: EDC AAS Extension client for direct AAS integration
  - `policy/odrl_builder.py`: Fluent ODRL policy builder with Catena-X profile
  - `policy/engine.py`: Policy validation and evaluation
  - `policy/templates.py`: Pre-built policy templates (unrestricted, membership, BPN-restricted)
  - `identity/cert_manager.py`: Certificate management for mTLS
  - `identity/vault_client.py`: HashiCorp Vault integration for secrets
  - `health.py`: Component health checking
  - `tasks.py`: Celery tasks for async onboarding and publication
  - `providers/`: Environment-specific adapters (sandbox, catena-x)

## Key Data Flow

1. **Template Selection** → `GET /api/templates` → Fetcher returns available templates
2. **Load Schema** → `GET /api/editor/templates/{name}/schema` → Parser outputs UI schema
3. **Form Rendering** → `AASRenderer` component recursively renders form from schema
4. **Validation** → `POST /api/editor/validate/{name}` → Server-side validation
5. **Export** → `POST /api/export/{name}?format=aasx|json|pdf` → Hydrator + export

## Frontend Key Components

- `frontend/src/components/AASRenderer/` - Recursive form renderer with per-element-type fields (Property, Collection, List, File, Range, etc.)
- `frontend/src/hooks/useSubmodelForm.ts` - Main form logic: generates Zod schemas from UI schema, manages validation state, handles export
- `frontend/src/components/SmartMapper/` - CSV/XLSX mapping UI with drag-and-drop
- `frontend/src/components/PCFPanel/` - PCF declaration, CO₂e calculator, IDTA 02023 validator
- `frontend/src/components/PassportMode/cards/` - Template-specific passport card renderers
- `frontend/src/components/MagicImport/` - PDF upload, extraction review table, confidence badges, PDF viewer with evidence highlighting
- `frontend/src/components/DataspaceConnector/` - Dataspace connection management:
  - `DataspaceConnectorPanel.tsx` - Main panel with connection workflow tabs
  - `EnvironmentSelector.tsx` - Environment picker (sandbox, catena-x-test, catena-x-prod)
  - `EDCModeSelector.tsx` - EDC mode selection (tractus-x, aas-extension)
  - `ConnectionStatus.tsx` - Real-time connection status display
  - `OnboardingWizard.tsx` - Step-by-step onboarding flow
  - `PublicationManager.tsx` - Manage published submodels
  - `useDataspace.ts` / `usePublications.ts` - React hooks for API integration
- `frontend/src/components/PolicyBuilder/` - Visual ODRL policy construction:
  - `PolicyBuilder.tsx` - Main policy builder interface
  - `AccessLevelPicker.tsx` - Access type selection (public, membership, restricted)
  - `PartnerSelector.tsx` - BPN partner allow-list editor
  - `ElementSelector.tsx` - Submodel element selection for partial policies
  - `PolicyPreview.tsx` - ODRL JSON preview with syntax highlighting

## Backend Key Services

- `backend/app/services/` - Core business logic (fetcher, parser, hydrator, validation)
- `backend/app/routers/` - FastAPI endpoints: templates, editor, export, semantic, mapper, pcf, magic_import, dataspace
- `backend/app/schemas/` - Pydantic v2 models

## Testing

Backend tests use pytest with shared fixtures in `backend/tests/conftest.py`. Conformance fixtures in `backend/tests/fixtures/` are validated against `aas-test-engines`. Domain-specific tests organized by feature: `tests/pcf/`, `tests/semantic/`, `tests/mapper/`, `tests/magic_import/`, `tests/dataspace/`.

### Dataspace Tests

```bash
# Run all dataspace tests
PYTHONPATH=backend pytest backend/tests/dataspace/

# Run specific dataspace test modules
PYTHONPATH=backend pytest backend/tests/dataspace/test_policy.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_registry_clients.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_edc_clients.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_connection_manager.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_publisher.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_router.py -v
PYTHONPATH=backend pytest backend/tests/dataspace/test_tasks.py -v
```

Frontend uses Vitest with React Testing Library. Tests colocated in `__tests__` directories.

## Configuration

Backend uses Pydantic Settings (`backend/app/config.py`) with environment variable parsing. Key vars:
- `ENV`: development|staging|production
- `GITHUB_TOKEN`: For higher API rate limits
- `LOCAL_TEMPLATES_ENABLED` / `LOCAL_TEMPLATES_DIR`: Custom AASX templates
- `SEMANTIC_*`: Dictionary lookup config
- `OIDC_*`: Authentication setup
- `MAGIC_IMPORT_*`: PDF extraction settings (LLM provider, OCR, confidence threshold)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OLLAMA_BASE_URL`: LLM credentials
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`: Background job config

### Dataspace Configuration

```bash
# Feature flag
DATASPACE_ENABLED=true
DATASPACE_CACHE_DIR=./cache/dataspace
DATASPACE_DEFAULT_ENVIRONMENT=sandbox  # sandbox|catena-x-test|catena-x-prod
DATASPACE_DEFAULT_EDC_MODE=tractus-x   # tractus-x|aas-extension

# BaSyx AAS Server
BASYX_AAS_SERVER_URL=http://basyx-aas-server:4001
BASYX_REGISTRY_URL=http://basyx-registry:4002

# EDC Tractus-X
EDC_CONTROL_PLANE_URL=http://edc-control-plane:19192
EDC_DATA_PLANE_URL=http://edc-data-plane:19291
EDC_API_KEY=your-api-key

# EDC AAS Extension (alternative mode)
EDC_AAS_EXTENSION_URL=http://edc-aas:8080

# Digital Twin Registry (Catena-X)
DTR_URL=http://dtr:4003

# HashiCorp Vault (secrets)
VAULT_URL=http://vault:8200
VAULT_TOKEN=dev-root-token

# Catena-X specific
CATENA_X_PORTAL_URL=https://portal.catena-x.net
CATENA_X_BPN=BPNL000000000001

# PLC4X Bridge
PLC4X_BRIDGE_ENABLED=false
PLC4X_BRIDGE_URL=http://plc4x-bridge:8090

# Mnestix AAS Browser
MNESTIX_ENABLED=true
MNESTIX_URL=http://mnestix:3000
```

Frontend uses Vite with `VITE_API_URL` env var (defaults to `http://localhost:8000`).

## Dataspace API Endpoints

All endpoints under `/api/dataspace/*` require `DATASPACE_ENABLED=true`.

### Connection Management
- `POST /api/dataspace/connections` - Start dataspace onboarding
- `GET /api/dataspace/connections` - List all connections
- `GET /api/dataspace/connections/{id}` - Get connection status with health checks
- `DELETE /api/dataspace/connections/{id}` - Disconnect from dataspace
- `POST /api/dataspace/connections/{id}/reconnect` - Reconnect failed connection

### Publication Management
- `POST /api/dataspace/publications` - Publish submodel to dataspace
- `GET /api/dataspace/publications` - List publications (filter by connection, template, status)
- `GET /api/dataspace/publications/{id}` - Get publication details
- `PUT /api/dataspace/publications/{id}` - Update published submodel
- `DELETE /api/dataspace/publications/{id}` - Unpublish submodel

### Policy Management
- `GET /api/dataspace/policies/templates` - Get pre-built policy templates
- `POST /api/dataspace/policies/preview` - Preview ODRL from policy config
- `POST /api/dataspace/policies` - Create new policy
- `GET /api/dataspace/policies/{id}` - Get policy details
- `PUT /api/dataspace/policies/{id}` - Update policy
- `DELETE /api/dataspace/policies/{id}` - Delete policy

### Health & Discovery
- `GET /api/dataspace/health` - Check dataspace component health
- `GET /api/dataspace/environments` - List available environments
- `GET /api/dataspace/edc-modes` - List available EDC connector modes

## PLC4X Bridge

The PLC4X Bridge (`plc4x-bridge/`) is a Java/Spring Boot microservice that bridges industrial PLCs to the BaSyx AAS Server, enabling real-time shopfloor data integration.

### Architecture
- `PlcReader.java` - PLC4X protocol-agnostic tag reading
- `ContinuousReader.java` - Scheduled polling with configurable intervals
- `AasUpdater.java` - BaSyx submodel property updates
- `PlcController.java` - REST API for connection management and tag mapping

### Supported Protocols
Via Apache PLC4X: Modbus TCP/RTU, OPC UA, S7 (Siemens), EtherNet/IP, BACnet, and 30+ others

### Configuration
```bash
PLC_CONNECTION_STRING=s7://192.168.1.10    # PLC4X connection string
PLC_READ_INTERVAL=1000                      # Polling interval (ms)
BASYX_AAS_SERVER_URL=http://basyx-aas-server:4001
MAPPING_UPDATE_MODE=ON_CHANGE              # ON_CHANGE|ALWAYS
MAPPING_CHANGE_THRESHOLD=0.01              # Deadband for ON_CHANGE mode
```

### API Endpoints
- `GET /api/plc/status` - Connection status
- `POST /api/plc/connect` - Connect to PLC
- `POST /api/plc/disconnect` - Disconnect from PLC
- `GET /api/plc/tags` - List discovered tags
- `POST /api/plc/mappings` - Configure tag-to-submodel mappings
- `GET /api/plc/readings` - Get current tag values

## Kubernetes Deployment

Kubernetes manifests use Kustomize with base/overlay structure.

### Structure
```
kubernetes/
├── base/
│   ├── kustomization.yaml
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── pvc.yaml
│   └── dataspace/           # Dataspace profile
│       ├── kustomization.yaml
│       ├── dataspace-configmap.yaml
│       ├── dataspace-secrets.yaml
│       ├── dataspace-pvc.yaml
│       ├── postgres-deployment.yaml
│       ├── vault-deployment.yaml
│       ├── basyx-deployment.yaml
│       ├── dtr-deployment.yaml
│       ├── edc-control-deployment.yaml
│       ├── edc-data-deployment.yaml
│       └── mnestix-deployment.yaml
└── overlays/
    ├── development/
    │   └── kustomization.yaml
    └── production/
        └── kustomization.yaml
```

### Deployment Commands
```bash
# Base deployment (no dataspace)
kubectl apply -k kubernetes/overlays/development

# With dataspace components
kubectl apply -k kubernetes/base/dataspace
kubectl apply -k kubernetes/overlays/development
```
