# Adoption Roadmap PR Batches

This file captures the implementation split for the 8-10 week repo-only roadmap as 5 small, theme-focused PRs.

## PR-1: Compose/Profile Fixes + Onboarding Docs

Scope:
- Compose profile correctness and startup friction removal
- `docker compose` command standardization
- E2E profile startup reliability fixes

Files:
- `docker-compose.yaml`
- `README.md`
- `docs/reference/configuration.md`
- `docs/features/dataspace-publishing.md`
- `docs/features/plc4x-bridge.md`
- `docs/index.md`
- `docs/pcf/README.md`
- `.github/workflows/e2e-tests.yml`
- `frontend/e2e/global-setup.ts`
- `frontend/e2e/helpers/docker-health.ts`
- `frontend/e2e/pages/template-selector.page.ts`
- `frontend/e2e/suites/suite-06-magic-import/pdf-upload.spec.ts`
- `frontend/e2e/suites/suite-08-passport-mode/nameplate-card.spec.ts`
- `frontend/e2e/suites/suite-09-dataspace/connection-onboarding.spec.ts`
- `frontend/e2e/suites/suite-09-dataspace/policy-builder.spec.ts`
- `frontend/playwright.config.ts`
- `frontend/src/components/MagicImport/index.tsx`
- `frontend/src/components/MagicImport/MagicImportPanel.tsx`
- `frontend/src/components/MagicImport/PdfViewer.tsx`
- `frontend/src/components/MagicImport/ExtractionReviewTable.tsx`
- `frontend/src/components/MagicImport/ProvenancePanel.tsx`
- `frontend/src/tools/index.ts`

Validation:
- `E2E_PROFILE=default npx playwright test --project=chromium`
- `E2E_PROFILE=magic-import npx playwright test --project=chromium`
- `VAULT_HOST_PORT=18200 E2E_PROFILE=dataspace npx playwright test --project=chromium`
- `VAULT_HOST_PORT=18200 E2E_PROFILE=plc npx playwright test --project=chromium`

## PR-2: Conformance API + Export Integration

Scope:
- Add `POST /api/conformance/check`
- Add frontend verify/export conformance rendering
- Add CI fixture policy for protected branches

Files:
- `backend/app/routers/conformance.py`
- `backend/app/services/conformance.py`
- `backend/app/schemas/conformance.py`
- `backend/app/routers/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/tests/test_conformance_router.py`
- `backend/tests/test_conformance_service.py`
- `.github/workflows/ci.yml`
- `frontend/src/services/api.ts`
- `frontend/src/hooks/useSubmodelForm.ts`
- `frontend/src/components/ExportPanel/index.tsx`
- `docs/reference/api-endpoints.md`

Validation:
- `PYTHONPATH=backend pytest backend/tests/test_conformance_service.py backend/tests/test_conformance_router.py`
- `npm --prefix frontend run test:unit -- ExportPanel`
- `npm --prefix frontend run type-check`

## PR-3: Magic Import Preview/Redaction + Audit Workflow

Scope:
- Add `POST /api/magic-import/jobs/preview`
- Support snippet override submission for extraction jobs
- Expose review-first snippet editing/removal before LLM call

Files:
- `backend/app/routers/magic_import.py`
- `backend/app/schemas/magic_import.py`
- `backend/app/services/magic_import/tasks.py`
- `backend/app/services/magic_import/job_manager.py`
- `backend/tests/magic_import/test_preview_router.py`
- `frontend/src/services/magicImportApi.ts`
- `frontend/src/components/MagicImport/useMagicImport.ts`
- `frontend/src/components/MagicImport/MagicImportPanel.tsx`
- `frontend/src/components/MagicImport/MagicImport.css`
- `docs/features/magic-import.md`

Validation:
- `PYTHONPATH=backend pytest backend/tests/magic_import/test_preview_router.py backend/tests/magic_import/test_audit_report.py backend/tests/magic_import/test_confidence_regression.py`
- `npm --prefix frontend run test:unit -- MagicImport`

## PR-4: Element-Type Cliff Reduction

Scope:
- Blob editable path (upload/download/content type)
- RelationshipElement editing support
- AnnotatedRelationshipElement annotation editing support
- Operation rationale hint retained (read-only)

Files:
- `frontend/src/components/AASRenderer/BlobField.tsx`
- `frontend/src/components/AASRenderer/index.tsx`
- `frontend/src/hooks/useSubmodelForm.ts`
- `docs/reference/element-types.md`

Validation:
- `npm --prefix frontend run type-check`
- `npm --prefix frontend run test:unit`

## PR-5: Production Guardrails + Manifest Contract + Contributor Onboarding

Scope:
- Production startup guardrails (`OIDC_ENABLED` or explicit insecure override)
- Public settings include effective `magic_import_enabled`
- Tool manifest contract includes `schema_version` and `disabled_reason`
- Contributor onboarding updates (`CONTRIBUTING.md`, `.devcontainer`, `REVIEW_REPORT.md`)

Files:
- `backend/app/config.py`
- `backend/app/services/settings_service.py`
- `backend/app/routers/tools.py`
- `backend/app/services/tools/base.py`
- `backend/app/services/tools/registry.py`
- `backend/tests/test_config_security.py`
- `backend/tests/test_public_settings.py`
- `backend/tests/tools/test_registry.py`
- `backend/tests/tools/test_router.py`
- `frontend/src/App.tsx`
- `frontend/src/tools/types.ts`
- `frontend/src/tools/index.ts`
- `frontend/src/services/api.ts`
- `frontend/src/services/__tests__/api.public-settings.test.ts`
- `frontend/src/components/MnestixBrowser/__tests__/MnestixBrowser.test.tsx`
- `CONTRIBUTING.md`
- `.devcontainer/devcontainer.json`
- `.github/pull_request_template.md`
- `REVIEW_REPORT.md`
- `docs/reference/review-playbook.md`

Validation:
- `PYTHONPATH=backend pytest backend/tests/test_config_security.py backend/tests/test_public_settings.py backend/tests/tools/test_registry.py backend/tests/tools/test_router.py`
- `npm --prefix frontend run lint && npm --prefix frontend run type-check && npm --prefix frontend run test:unit`
- `mkdocs build --strict`
