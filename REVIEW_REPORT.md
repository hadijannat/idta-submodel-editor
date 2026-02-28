# REVIEW_REPORT

Use this file to record prioritized review findings and remediation status for each review cycle.

## How To Use

- Add one entry per review cycle.
- Prioritize findings with the playbook severity model (`P0`-`P3`).
- Include file paths, impact, and verification evidence.
- Mark findings as resolved only after tests and docs updates are complete.

### Review: 2026-02-28 - PR #51 Deployment/Ops Reliability

- Reviewer(s): Deployment Officer Reviewer (Codex)
- Branch/PR: `pendar/adoption-roadmap-batches` / #51
- Scope: Compose profile correctness, CI guardrails, docs-command consistency, startup ergonomics, protected-branch policy effects
- Summary: Identified one profile-level startup break and three deploy/ops reliability gaps in workflows/docs; all remediated in owned files.

#### Findings

| Severity | ID | Area | File/Path | Description | Fix | Status |
|---|---|---|---|---|---|---|
| P1 | DO-001 | Compose Profiles | `docker-compose.yaml` | `docker compose --profile plc config` failed because `plc4x-bridge` depended on `basyx-aas-server`, but BaSyx services were only in `dataspace` profile. | Added `plc` profile membership to `basyx-aas-server` and `basyx-registry` so PLC profile resolves dependencies. | Resolved |
| P2 | DO-002 | CI Guardrail | `.github/workflows/ci.yml` | Conformance fixture enforcement was hardcoded to `main`, making branch policy brittle and misaligned with non-`main` protected/default branch setups. | Made required-target branches configurable via `CONFORMANCE_REQUIRED_BRANCHES` (repo var), with default-branch fallback. | Resolved |
| P2 | DO-003 | E2E Stability | `.github/workflows/e2e-tests.yml` | Fixed sleeps (`30s`/`120s`) for profile stack startup were timing-sensitive and caused flaky E2E readiness. | Replaced sleeps with `docker compose ... up -d --wait --wait-timeout ...` and added `down --remove-orphans`. | Resolved |
| P3 | DO-004 | Docs Consistency | `docs/features/dataspace-publishing.md` | Dataspace guide still claimed GHCR login was required although compose now uses public image names. | Updated docs to remove GHCR login requirement and align startup commands. | Resolved |

#### Verification

- Backend tests: Not run (scope limited to compose/workflows/docs).
- Frontend tests: Not run (scope limited to compose/workflows/docs).
- E2E/tests: `docker compose config` sanity checks passed for default, `magic-import`, `auth`, `dataspace`, `plc`, and `dataspace+plc` profile combinations.
- Docs: `mkdocs build --strict` passed.

#### Follow-ups

- If additional protected branches are used (for example `release/*`), set repository variable `CONFORMANCE_REQUIRED_BRANCHES` to a comma-separated branch list.

## Template

### Review: <YYYY-MM-DD> - <Scope/PR>

- Reviewer(s):
- Branch/PR:
- Scope:
- Summary:

#### Findings

| Severity | ID | Area | File/Path | Description | Fix | Status |
|---|---|---|---|---|---|---|
| P1 | RPT-001 | Backend | `backend/...` | <what is wrong> | <what was changed> | Open/Resolved |

#### Verification

- Backend tests:
- Frontend tests:
- E2E/tests:
- Docs:

#### Follow-ups

- <remaining risk or deferred work>
