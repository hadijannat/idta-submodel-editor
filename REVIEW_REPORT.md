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

### Review: 2026-11-10 - Form Generation From Template, JSON And Specification PDF

- Reviewer(s): Claude Code
- Branch/PR: `hadi/charming-curie-risrm6`
- Scope: Template discovery and version selection, AASX-to-form parsing, requirements stated in template JSON and specification PDF, validation, export of filled forms, form UX
- Summary: Measured against all 74 templates of `admin-shell-io/submodel-templates` (66 published entries including template parts, 8 deprecated). 54 of 56 published template folders loaded an outdated release, most requirements a template declares were ignored, and several defects blocked export of ordinary forms. All findings below are remediated except the listed follow-ups.

#### Findings

| Severity | ID | Area | File/Path | Description | Fix | Status |
|---|---|---|---|---|---|---|
| P0 | TR-001 | Template selection | `backend/app/services/fetcher.py` | The first version folder and the shallowest AASX were chosen, so 54 of 56 published templates loaded their oldest release (Digital Nameplate 3.0 instead of 3.0.3, Asset Interfaces Description 1.0 instead of 1.2.1). | New repository index (`template_repo.py`) resolves the newest release; the per-directory fallback searches newest folders first. | Resolved |
| P0 | TR-002 | Export | `backend/app/services/hydrator.py` | Export failed with an AAS constraint violation after adding an item to a list of collections (for example a second marking on the nameplate). | List items are cloned detached from their parent. | Resolved |
| P1 | TR-003 | Parser | `backend/app/services/parser.py` | `valueType` was emitted as a Python class name (`<class 'str'>`), so every Property was a text input, XSD bounds never applied and downstream tools saw unknown types. | XSD names (`xs:date`) are emitted; values are serialized in their lexical form. | Resolved |
| P1 | TR-004 | Requirements | `backend/app/services/parser.py` | Only cardinality was read from qualifiers. Allowed values, ranges, required languages, either/or groups, example and default values, form hints, IEC 61360 value lists and value formats were ignored. | `template_constraints.py` reads them; validation and the form apply them. | Resolved |
| P1 | TR-005 | Requirements | `backend/app/services/parser.py` | Format standards named in specification text (ISO 3166-1, ISO 639, ISO 4217, ISO 8601, IEC 61406, RFC 2046) had no effect. | `format_rules.py` recognises them; mismatches are warnings. | Resolved |
| P1 | TR-006 | Specification PDF | `backend/app/services/fetcher.py` | The PDF and JSON published with a template were never used or offered. | PDF rows are extracted (`spec_pdf.py`), matched to the form (`spec_notes.py`) and shown per field; PDF, JSON and AASX can be opened from the editor. | Resolved |
| P1 | TR-007 | Template selection | `backend/app/services/fetcher.py` | Multi-part templates exposed only their first part (1 of 7 for the Digital Battery Passport); Digital Product Passport could not be opened at all. | Every part is a template entry. | Resolved |
| P1 | TR-008 | Lists | `backend/app/services/validation.py`, `frontend/src/components/AASRenderer/ListField.tsx` | A list declared `[0..1]` or `[1]` was limited to one item, in the form and on validation. | The list's cardinality is no longer used as item bound. | Resolved |
| P1 | TR-009 | Parser | `backend/app/services/parser.py` | `SMT/SMT/Cardinality` (Control Component templates) was not recognised, making optional elements mandatory. | Qualifier types are matched by family. | Resolved |
| P1 | TR-010 | Export | `backend/app/services/hydrator.py` | `xs:duration` values could not be exported: the type was mistaken for a date. | Types are matched by XSD name; remaining XSD types are parsed from their lexical form. | Resolved |
| P1 | TR-011 | UX | `frontend/src/App.tsx` | Example values of the template were pre-filled without any indication and counted as completed required fields. | Example values are marked, counted, reported on validation and can be cleared at once. | Resolved |
| P2 | TR-012 | AASX reader | `backend/app/utils/aasx_reader.py` | Two published packages declare internal parts as external relationship targets and could not be read. | Relationships are repaired on read. | Resolved |
| P2 | TR-013 | Parser | `backend/app/services/parser.py` | List items were named `generated_submodel_list_hack_<id>` with an id that changed on every request. | Stable item names derived from the list. | Resolved |
| P2 | TR-014 | Operations | `backend/app/services/fetcher.py` | Every template fetch needed several GitHub API requests (60 per hour unauthenticated) and nothing worked without GitHub. | One tree request, downloads from raw content, index saved to disk, optional local mirror (`TEMPLATE_REPO_DIR`). | Resolved |
| P2 | TR-015 | UX | `frontend/src/components/AASRenderer` | Labels were raw idShorts, the definition of a concept was hidden whenever an element had notes, semantic controls cluttered every field, IDTA numbers and versions were not shown. | Readable labels, definition plus notes, semantic controls behind a toggle, release information in list and configuration step. | Resolved |
| P2 | TR-016 | Repeatable elements | `frontend/src/components/AASRenderer` | Collections and properties a template allows several times (`[0..*]`, `[1..*]`) outside of lists are rendered once and cannot be added. | Further occurrences can be added and removed in the form (`ElementOccurrences.tsx`). They travel in the element's `occurrences` list, are validated like the element and are exported as siblings with their own idShort (`Phone`, `Phone__01__`; `backend/app/services/occurrences.py`). | Resolved |
| P2 | TR-018 | Export | `backend/app/services/hydrator.py` | Exported AASX packages reference supplementary files by a lower-cased part name while the file is stored under its original mixed-case name (seen with Carbon Footprint 1.0.3), so `aas-test-engines` reports a relationship with a non-existing target. Present before this review. | The BaSyx `AASXWriter` (2.1.0 and 2.2.0) lower-cases the targets of supplementary file relationships. `ConformantAASXWriter` (`backend/app/utils/aasx_writer.py`) writes them with the names the parts are stored under; file names and `File` values keep their case. | Resolved |
| P3 | TR-017 | Multi-submodel packages | `backend/app/services/parser.py` | A package with several submodels (MTP) is edited one submodel at a time. | — | Open |

#### Verification

- Backend tests: `pytest backend/tests` — all pass except `test_404_returns_error_response_format`, which needs live access to the GitHub API and fails identically on the unmodified code in a sandbox without it.
- Frontend tests: `npm run lint`, `npm run type-check`, `npm run test:unit` pass.
- E2E/tests: `backend/scripts/audit_template_coverage.py` against a checkout of the template repository: 74 of 74 templates fetched, parsed, validated with generated required data, exported to AASX and JSON and re-parsed. Default Playwright profile on Chromium against that checkout: 114 passed, 29 skipped, 0 failed. Three page-object selectors and one assertion were adapted (exact template card match, label text, rows of virtualized lists, date picker input).
- Conformance: exports of Digital Nameplate 3.0.3 and Technical Data 2.0.4 filled with required data pass `aas-test-engines`. Carbon Footprint 1.0.3 failed on TR-018; since its fix an unedited export passes and its supplementary file is preserved under its original name (regression test `backend/tests/test_hydrator_supplementary_files.py`). Of the 74 templates exported with required data, 13 AASX exports failed on TR-018 before the fix and none after. Contact Information 1.0.4 is not conformant as published upstream.
- Docs: `docs/features/template-requirements.md` added; configuration, API reference, README and changelog updated.

#### Follow-ups

- TR-017: let the user choose the submodel of a multi-submodel package.
- Specification PDFs generated from Word are read less completely than the AsciiDoc-generated ones; extraction quality per template is reported by the `specification-notes` endpoint (`matched` / `total`).

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
