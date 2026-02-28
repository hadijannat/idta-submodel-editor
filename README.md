# Universal IDTA Submodel Template Editor

[![CI](https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/idta-submodel-editor/actions/workflows/ci.yml)
[![Docs](https://github.com/hadijannat/idta-submodel-editor/actions/workflows/docs.yml/badge.svg)](https://github.com/hadijannat/idta-submodel-editor/actions/workflows/docs.yml)
[![Release](https://img.shields.io/github/v/release/hadijannat/idta-submodel-editor)](https://github.com/hadijannat/idta-submodel-editor/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18374723.svg)](https://doi.org/10.5281/zenodo.18374723)

A metamodel-driven application for editing IDTA submodel templates without code changes. It combines a FastAPI backend, a React + TypeScript frontend, and profile-based integrations for Magic Import, Dataspace publishing, and PLC connectivity.

## North-Star Job

Create compliant IDTA submodels quickly, starting from templates, spreadsheets, or PDFs, then export or publish to AAS/dataspace targets.

## What It Does

The editor discovers IDTA templates, renders dynamic forms, validates data, and exports submodels as AASX/JSON/PDF. The core workflow runs locally without external API keys, while advanced capabilities (LLM-assisted extraction, dataspace publication, semantic web services, and PLC bridges) can be enabled incrementally.

## Quick Start (2 Minutes)

```bash
# from repo root
docker compose up
```

Then open `http://localhost:8080`.

### Core URLs

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:8080 | Main UI |
| Backend API | http://localhost:8000 | REST API |
| Swagger UI | http://localhost:8000/api/docs | Available when `ENV != production` |
| Health | http://localhost:8000/health | Basic health/liveness indicator |
| AAS Browser (Mnestix) | http://localhost:3001 | Available with `dataspace` profile |

## Choose Your Path

- [Try It](#try-it-new-users)
- [Contribute](#contribute-developers)
- [Operate](#operate-operators)

## Runtime Profiles

| Profile | Command | What It Adds | Important Notes |
|---|---|---|---|
| Core | `docker compose up` | Backend, frontend, Redis | Core editing works without external API keys; lightest startup path |
| Magic Import Worker | `docker compose --profile magic-import up` | `celery-worker` for async/background jobs | Magic Import feature flag is already enabled in base backend config |
| Dataspace | `docker compose --profile dataspace up` | BaSyx, DTR, Vault, EDC, Postgres, Mnestix | Mnestix is exposed at `http://localhost:3001`; heavy stack, slower first startup |
| PLC Bridge | `docker compose --profile plc up` (or `--profile dataspace --profile plc`) | PLC4X bridge + required BaSyx services | Use standalone for local PLC-to-AAS loop, or combine with dataspace for full connector flow |
| Auth | `OIDC_ENABLED=true OIDC_ISSUER_URL=http://keycloak:8080/realms/idta OIDC_AUDIENCE=idta-editor docker compose --profile auth up backend redis keycloak` | Backend + Redis + Keycloak | Keycloak is mapped to `http://localhost:8081` to avoid frontend port collisions |

## Feature Overview

- [Smart Mapper](docs/features/smart-mapper.md): CSV/XLSX profiling and mapping with reusable recipes.
- [Magic Import](docs/features/magic-import.md): PDF extraction with LLM + OCR, confidence signals, and auditability.
- [Template Operations](docs/features/template-ops.md): import/diff/migrate/validate template versions.
- [Passport Mode](docs/features/passport-mode.md): product passport card-style visualization.
- [Semantic Lookup](docs/features/semantic-lookup.md): dictionary search/resolve workflows.
- [PCF Calculator](docs/features/pcf-calculator.md): CO2e calculations and validation workflows.
- [Dataspace Publishing](docs/features/dataspace-publishing.md): Catena-X / Manufacturing-X integration.
- [PLC4X Bridge](docs/features/plc4x-bridge.md): industrial protocol bridge into AAS infrastructure.

## Try It (New Users)

1. Run `docker compose up`.
2. Open `http://localhost:8080`.
3. Select a template (for example, Digital Nameplate).
4. Fill required fields and export as AASX/JSON/PDF.

## Default Path

1. Start core stack with `docker compose up`.
2. Complete template editing + export flow first.
3. Add optional profiles only when needed:
   - Magic Import worker: `--profile magic-import`
   - Dataspace stack: `--profile dataspace`
   - PLC bridge: `--profile plc` (optionally combine with dataspace)
   - Auth stack: `--profile auth`

## Contribute (Developers)

### Local Development

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Testing

#### Backend

```bash
cd backend
# Option A: full backend suite
pytest tests

# Option B: targeted suites during iteration
pytest tests/dataspace tests/mapper tests/magic_import
```

#### Frontend quality + unit tests

```bash
cd frontend
npm run lint
npm run type-check
npm run build
npm run test:unit
```

#### CI-parity coverage checks (optional)

```bash
# Backend (from repo root)
PYTHONPATH=backend pytest backend/tests --cov=backend/app --cov-report=term-missing

# Frontend (from frontend/)
npm run test:unit -- --coverage
```

#### End-to-end tests (Playwright)

```bash
cd frontend
npx playwright install --with-deps

# Fast local smoke check (CI-like browser target)
npm run test:e2e:smoke -- --project=chromium

# Full default matrix (slower; multiple browser/device projects)
npm run test:e2e

# Optional profile-specific suites
npm run test:e2e:magic-import
npm run test:e2e:dataspace
npm run test:e2e:plc
```

Notes:
- Playwright config does not auto-start services; start backend/frontend first.
- Choose one E2E path per run unless intentionally doing full coverage.
- Useful overrides: `E2E_PROFILE`, `DEMO_BASE_URL`, `VITE_API_URL`, `PW_HEADLESS=false`.

## Operate (Operators)

- Backend health probes:
  - `GET /health`
  - `GET /health/liveness`
  - `GET /health/readiness`
  - `GET /health/startup`
- Metrics endpoint: `GET /metrics`
- Security note: expose `/health*` and `/metrics` only on private networks or behind gateway auth/allowlists.
- Runtime feature flags API: `GET/PUT /api/settings/features`
  - Outside development mode, updating flags requires admin-authenticated context.
- OIDC behavior:
  - If `OIDC_ENABLED=false`, auth checks are effectively bypassed.
  - Enabling Keycloak profile alone does not enforce authentication.

## Architecture Snapshot

```text
Fetcher -> Parser -> Hydrator -> Validation
```

- `Fetcher`: discovers/caches templates from GitHub and local template directories.
- `Parser`: transforms AAS structures into UI schema.
- `Hydrator`: reconstructs AAS payloads from submitted form data.
- `Validation`: enforces constraints before export/hydration.

Tooling model:
- Backend auto-discovers tools and serves `/api/tools/manifest`.
- Frontend maps known tool IDs to React components.
- Unmapped discovered tools render a placeholder panel instead of a full UI.

## Docs Map

- Features overview: [docs/features/README.md](docs/features/README.md)
- Configuration reference: [docs/reference/configuration.md](docs/reference/configuration.md)
- API endpoints reference: [docs/reference/api-endpoints.md](docs/reference/api-endpoints.md)
- Element types reference: [docs/reference/element-types.md](docs/reference/element-types.md)
- Review playbook: [docs/reference/review-playbook.md](docs/reference/review-playbook.md)

## Operations and CI

- CI workflow: [.github/workflows/ci.yml](.github/workflows/ci.yml)
- E2E workflow: [.github/workflows/e2e-tests.yml](.github/workflows/e2e-tests.yml)
- Fixture refresh workflow: [.github/workflows/fixtures-refresh.yml](.github/workflows/fixtures-refresh.yml)
- Docs workflow: [.github/workflows/docs.yml](.github/workflows/docs.yml)

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening PRs.

## Citation

If you use this project in academic work, cite:

```bibtex
@software{jannatabadi2024idta,
  author = {Jannatabadi, Hadi},
  title = {IDTA Submodel Editor},
  year = {2024},
  url = {https://github.com/hadijannat/idta-submodel-editor},
  license = {MIT}
}
```

## License

MIT License. See [LICENSE.txt](LICENSE.txt).
