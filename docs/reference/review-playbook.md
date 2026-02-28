# Review Playbook

This playbook standardizes security/correctness reviews for the IDTA Submodel Editor.

## Scope

- Core stack is always required: backend API, frontend app, export flow, and core docker compose startup.
- Optional modules are reviewed when touched or explicitly requested:
  - Magic Import profile
  - Dataspace profile
  - PLC profile

## Severity Model

- `P0`: exploitable security/data loss/system unusable.
- `P1`: core workflow broken or materially unreliable.
- `P2`: correctness edge cases/performance/maintainability blockers.
- `P3`: docs/polish/cleanup.

## Mandatory Rule

No fix ships without a test.

## Deployment Governance Prerequisite

Repository admins must enforce branch protection/rulesets on the default branch (typically `main`) and any release branches, with required status checks and required pull requests. This playbook assumes those controls are active.

## Baseline Verification

Run before review coding begins. Execute commands from repo root.

```bash
# Integration/E2E context only
docker compose up -d
# ...run integration/e2e checks...
docker compose down

# Backend-only changes
PYTHONPATH=backend pytest backend/tests

# Frontend changes
npm --prefix frontend run lint
npm --prefix frontend run type-check
npm --prefix frontend run test:unit

# Docs/process changes
mkdocs build --strict
```

## Required Review Checks

1. Backend API consistency
- Standardized error envelopes and status mapping.
- Correlation ID propagation.
- Deterministic route registration and OpenAPI behavior.

2. Feature flag behavior
- Disabled features must not execute runtime calls.
- `/api/settings` and `/api/settings/features` must agree on effective runtime flags.

3. Template pipeline
- Fetcher cache + upstream error handling.
- Validation correctness for cardinality/type/reference constraints.

4. Tool registry
- Dependency ordering.
- Stable `/api/tools/manifest` ordering.
- Accurate enabled/initialized reporting.

5. Frontend tool integration
- Wizard steps derived from manifest metadata.
- Fallback behavior when backend manifest unavailable.

6. Security checks
- Upload validation constraints.
- Secret handling and production guardrails.
- External call timeouts/error handling.

## Test Matrix

- Scoped baseline:
  - Backend changed: `PYTHONPATH=backend pytest backend/tests`
  - Frontend changed: `npm --prefix frontend run lint`
  - Frontend changed: `npm --prefix frontend run type-check`
  - Frontend changed: `npm --prefix frontend run test:unit`
  - Docs or `.github` process files changed: `mkdocs build --strict`
  - Runtime integration or contracts changed: run docker compose + E2E smoke
- Optional, only when affected:
  - `E2E_PROFILE=magic-import npm --prefix frontend run test:e2e`
  - `E2E_PROFILE=dataspace npm --prefix frontend run test:e2e`
  - `E2E_PROFILE=plc npm --prefix frontend run test:e2e`

## Delivery Requirements

Each review cycle must produce:

1. `REVIEW_REPORT.md` with prioritized findings.
2. Small, theme-focused PRs.
3. Tests for each fix/enhancement.
4. Updated docs for behavior or contract changes.
