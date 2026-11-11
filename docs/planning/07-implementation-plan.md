# 7. Implementation Plan

Status: draft for maintainer review.

This plan turns documents 1 to 6 into ordered work. It has six phases. Each
phase lists its steps, the acceptance criteria that say the work is correct,
and one acceptance gate that decides whether the phase is finished. Phases 0 to
4 are the milestones M0 to M4 of the roadmap (document 5). Phase 5 collects what
the roadmap leaves unscheduled and ends with the definition of the finished
tool.

Requirement identifiers (EXP-1, FE-WS-1 and so on) point to documents 2 and 6.
File paths are those of the repository at commit `938ecc7`.

## Working rules for every phase

| Rule | Content |
|---|---|
| Unit of work | One step is one pull request. A step that needs more than about 600 changed lines is split |
| Order inside a step | Write the failing acceptance test first, then the change, then the docs |
| Definition of done for a step | Its tests pass in CI; no existing test is skipped or deleted to get there; docs and status labels match the behaviour; the changelog has an entry |
| Review | A human reads every pull request before merge. Automated review is an addition, not a replacement |
| Stable features | A feature is labelled Stable only when a test runs its main action without mocks (TEST-1) |
| Dependencies | Decision records (document 3) named in a phase are accepted before its first step starts |

## How a gate works

1. **Automated part.** Every listed check is a CI job or a script with a stored
   result. A gate cannot pass on a local run.
2. **Manual part.** Each manual item names what to do and what to observe. The
   result is written down with date, commit and the person who checked.
3. **Evidence.** The gate record is a file `docs/releases/gate-phase-N.md` with
   links to the CI run, the conformance result and the manual notes. It is
   committed with the release.
4. **Decision.** The maintainer passes the gate only if every item is met. There
   are two outcomes: *pass*, then tag the release; or *not passed*, then the
   open items become the first steps of the continued phase.
5. **Waivers.** A P0 item cannot be waived. A P1 or P2 item can be moved to the
   next phase once, with the reason in the gate record and the item added to
   that phase's criteria. Blocking conformance classes (document 4) are never
   waived from phase 2 on.
6. **Regression rule.** Every gate includes all automated checks of the earlier
   gates.

---

## Phase 0: Clean base (v1.0.1, target November 2026)

**Goal.** The repository tells the truth about itself and has no stale work
waiting. No behaviour changes.

**Entry.** Documents 1 to 7 merged; the maintainer has decided the feature
targets of document 1.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 0.1 | Merge or close every open dependency update; fix what breaks | 27 open pull requests | — |
| 0.2 | Mock the GitHub call in `test_404_returns_error_response_format` | `backend/tests/test_error_handling.py` | TEST-7 |
| 0.3 | Add a `status` field to the tool manifest and set it for each tool | `backend/app/services/tools/base.py`, `builtin/*.py`, `frontend/src/tools/manifest.ts` | ADR-004, DOC-2 |
| 0.4 | Show the status label in the interface next to each tool | `frontend/src/tools/ToolShell.tsx` | DOC-2 |
| 0.5 | Remove from the default build what document 1 marks Removed: knowledge index, DPP Builder panel, SAMM converter, and dataspace publishing if so decided. Code leaves the default route registration; history keeps it | `backend/app/main.py`, `backend/app/routers/`, `frontend/src/components/` | Document 1 |
| 0.6 | Fix the endpoints that fail on missing names and stay in the product: template import (`FileType.JSON`), OPC UA export by template (`fetcher.get_template`) | `backend/app/routers/template_ops.py`, `opcua.py`, `backend/app/utils/upload_security.py` | RT-4 |
| 0.7 | Rewrite README, feature pages and tool descriptions to the claims policy; delete unreferenced images; mark Semantic Lookup and PCF data as sample data | `README.md`, `docs/features/`, `docs/` | Document 1 |
| 0.8 | Correct the changelog date of 1.0.0, set repository topics, mark TR-017 with its requirement (RT-5) | `CHANGELOG.md`, `REVIEW_REPORT.md` | DOC-4 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P0-A1 | The backend suite passes with outbound network blocked | CI job with network disabled |
| P0-A2 | No open dependency pull request is older than 14 days | Repository query in the gate record |
| P0-A3 | Every tool in `/api/tools/manifest` has a status, and the interface shows it | API test; browser test |
| P0-A4 | No route of a Removed feature is registered; no docs page describes one | Route-list test; docs build check |
| P0-A5 | `POST /api/template-ops/import` accepts AASX and JSON; OPC UA export by template returns 200 for a sample of five templates | API tests without mocks |
| P0-A6 | README and docs contain none of: "compliant", "production", "30+", "I4AAS", "ESPR compliance" outside the non-claims section | Text check in CI |
| P0-A7 | Docs build passes in strict mode with no unreferenced image | `docs` workflow |

### Gate 0

- [ ] P0-A1 to P0-A7 pass on the release commit.
- [ ] All existing CI jobs are green: `backend`, `backend-typecheck`, `backend-lint`, `frontend-lint`, `frontend-typecheck`, `frontend-test`, `frontend-build`, `aas-conformance`, `e2e-smoke`.
- [ ] Manual: a person follows the README from a clean checkout to a Digital Nameplate export and notes every step that does not match.
- [ ] Release notes list what was removed and why.

---

## Phase 1: Correct export (v1.1, target December 2026)

**Goal.** Every file the editor writes is conformant, carries the user's
identity and loses nothing, and CI proves it for every template.

**Entry.** Gate 0 passed. ADR-001 and ADR-005 accepted.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 1.1 | Extend the audit script into the conformance job: run upstream checks, validate, export through the HTTP API, check exports, compare read-back, check identity; emit `conformance.json` | `backend/scripts/audit_template_coverage.py`, new `backend/scripts/conformance/` | Document 4 |
| 1.2 | Implement result classes, the allow-list file and the rule that the list can only shrink | `backend/scripts/conformance/classify.py`, `conformance-allowlist.yml` | Document 4 |
| 1.3 | Run the job for profile `required` on every pull request and make it a required check; pin the engine version in a constraints file | `.github/workflows/ci.yml` (replace `aas-conformance`) | TEST-2 |
| 1.4 | Generate `docs/reference/conformance.md` and the README badge from the result | `backend/scripts/conformance/render.py`, `docs` workflow | Document 4 |
| 1.5 | Write every referenced ConceptDescription into AASX | `backend/app/services/hydrator.py`, `backend/app/utils/aasx_writer.py` | EXP-2 |
| 1.6 | Write an XML payload by default; keep JSON as an option; merge the two writer classes into one | `backend/app/utils/aasx_writer.py`, `backend/app/routers/export.py` | ADR-001, EXP-3 (option exposed in phase 3) |
| 1.7 | Check every XSD value type in the validator; make validator and exporter share one type table | `backend/app/services/validation.py`, `backend/app/utils/xsd_mapping.py` | VAL-1, EXP-4 |
| 1.8 | Fix the four templates that validate and then fail at export, including reference values | `validation.py`, `hydrator.py` | EXP-4 |
| 1.9 | Leave out untouched examples and empty optional elements on export | `hydrator.py` | EXP-5 |
| 1.10 | Apply the PCF check only when the PCF aid was used | `backend/app/routers/export.py`, `backend/app/services/pcf/validator.py` | EXP-6 |
| 1.11 | Add identity to the form data contract and the exporter: AAS identifier, global asset identifier, asset kind, submodel identifier, with a proposal pattern | `backend/app/schemas/form_data.py`, `hydrator.py` | ID-1, ID-2, ID-3 |
| 1.12 | Add the identity header to the existing form | `frontend/src/App.tsx`, new `frontend/src/components/Identity/` | FE-ID-1, FE-ID-2 |
| 1.13 | Ship a pinned template snapshot with the image and make it the default source; show snapshot and commit in the interface; add the weekly update workflow | `backend/app/services/fetcher.py`, `backend/Dockerfile`, `.github/workflows/fixtures-refresh.yml` | ADR-005, OPS-1 |
| 1.14 | Extend type checking to the whole backend and make it blocking; fix the reported errors | `backend/mypy.ini`, `ci.yml` | TEST-3 |
| 1.15 | Add HTTP-level tests for the editor and export routers on real templates | `backend/tests/` | TEST-1 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P1-A1 | Conformance job, profile `required`: no result in class `editor-defect`, `data-loss`, `identity`, `validation-reject` or `not-exportable`, except allow-list entries that name a phase 2 requirement (TPL-1, TPL-2, TPL-3) | Conformance job |
| P1-A2 | For every template, the ConceptDescriptions in the AASX export equal the upstream set by identifier and content | Conformance job, step 8 |
| P1-A3 | Exported AAS identifier, asset identifier and asset kind equal the entered values; none equals the template's | Conformance job, step 9; API test |
| P1-A4 | An export of a required-only form contains no example value and no empty optional element | Conformance job |
| P1-A5 | Battery Passport part 3 and Carbon Footprint 0.9 export with all fields filled | API test |
| P1-A6 | With outbound network blocked, the application lists, renders and exports every template | CI job with network disabled |
| P1-A7 | Type checking covers all of `backend/app` and blocks merges | `backend-typecheck` |
| P1-A8 | The conformance table is published on the docs site and names snapshot commit, editor commit and engine version | Docs build; page check |
| P1-A9 | Every defect class `upstream-defect` has a text block ready for an upstream issue | Artefact of the conformance job |

### Gate 1

- [ ] P1-A1 to P1-A9 pass on the release commit; Gate 0 automated checks still pass.
- [ ] The conformance job is a required status check on `main`.
- [ ] Manual: the Digital Nameplate, Technical Data and Carbon Footprint exports (AASX with XML payload) are loaded into a BaSyx AAS environment container and read back without error.
- [ ] Manual: the same three files open in AASX Package Explorer with their supplementary files and concept descriptions.
- [ ] Upstream issues are filed for every `upstream-defect`, and their links are in the conformance table.
- [ ] The allow-list contains only entries for TPL-1, TPL-2 and TPL-3.

---

## Phase 2: Complete authoring and round trip (v1.2, target January 2027)

**Goal.** A user can produce a complete Digital Nameplate, Technical Data and
Handover Documentation submodel, come back later, and continue.

**Entry.** Gate 1 passed. ADR-002 and ADR-003 accepted. The investigation named
in ADR-002 (how many templates use referenced templates and free elements) is
done and recorded.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 2.1 | Version the form schema and document it; generate frontend types from it; add the contract test | `backend/app/schemas/ui_schema.py`, `frontend/src/types/ui-schema.ts`, `docs/reference/` | API-3 (first part) |
| 2.2 | Resolve referenced templates in the parser; record the origin of each resolved part; block export when a mandatory block is unresolved | `backend/app/services/parser.py`, `fetcher.py`, new `backend/app/data/template_references.yml` | TPL-1 |
| 2.3 | Add the free-element node type to schema, validator and exporter | `parser.py`, `validation.py`, `hydrator.py` | TPL-2 |
| 2.4 | Accept file uploads per draft, store them, and write them into the package | `backend/app/routers/editor.py`, `hydrator.py`, `backend/app/utils/upload_security.py` | TPL-3 |
| 2.5 | Unify the error format and status codes across all routers | `backend/app/errors.py`, `backend/app/routers/` | API-4 |
| 2.6 | Import of AASX and JSON produced by the editor: detect template and release, return form data and an import report, keep unknown elements | `backend/app/routers/editor.py`, new `backend/app/services/importer.py` | RT-1, RT-3 |
| 2.7 | Introduce the application shell and routes around the existing form; split `App.tsx` | `frontend/src/app/`, `frontend/src/features/` | Document 6, §3 and §8 |
| 2.8 | Build the Workspace: outline with completion state and search, virtualised form, context panel with problems list | `frontend/src/features/workspace/` | FE-WS-1 to FE-WS-10, FE-WS-13, FE-WS-14; UX-1, UX-2, VAL-3 |
| 2.9 | Add the controls for free elements, resolved blocks and file upload | `frontend/src/form/controls/` | Document 6, §3.3 |
| 2.10 | Replace draft storage: save every change, list drafts, restore on return, save and load a draft file | `frontend/src/hooks/useDraftAutoSave.ts`, `frontend/src/features/drafts/` | DRF-1, DRF-2, DRF-3, FE-DR-1 to FE-DR-3 |
| 2.11 | Build the import screen and the review screen | `frontend/src/features/import/`, `frontend/src/features/review/` | FE-IM-1, FE-IM-2, FE-EX-1, FE-EX-2, FE-EX-4, FE-EX-7 |
| 2.12 | Catalogue search by IDTA number and semantic identifier; conformance badge on cards | `frontend/src/features/catalogue/` | UX-3, FE-CAT-1, FE-CAT-2 |
| 2.13 | Write the qualifier test matrix: one accepted and one rejected value per qualifier on a real template | `backend/tests/test_qualifier_matrix.py` | VAL-2 |
| 2.14 | Add conformance profile `full` (every element, repeated items, uploaded files, free elements) | `backend/scripts/conformance/` | Document 4 |
| 2.15 | Browser tests for the three journeys without skips, run on every pull request; generate docs screenshots from them | `frontend/e2e/`, `.github/workflows/` | TEST-6, DOC-3 |
| 2.16 | Raise router coverage and add the thresholds | `backend/tests/`, `ci.yml` | TEST-4 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P2-A1 | Digital Nameplate shows the address fields; a form without address fails validation; the exported address validates | Browser test; conformance job |
| P2-A2 | Three free properties in Technical Data export under the names, value types and units the user gave | Browser test; read-back comparison |
| P2-A3 | A PDF uploaded in Handover Documentation is in the AASX, referenced by its File element, and passes the engine | Browser test; conformance profile `full` |
| P2-A4 | Export, reopen, change one value, export: the two files differ in that value only | Browser test with file comparison |
| P2-A5 | Reload during editing returns to the same field with all entries; a draft file moves a draft to another browser profile | Browser test |
| P2-A6 | Every qualifier in document 6, §3.4, that the backend reads has a passing accept and reject test | `test_qualifier_matrix.py` |
| P2-A7 | Conformance job, profiles `required` and `full`: no blocking class; the allow-list is empty | Conformance job |
| P2-A8 | Asset Interfaces Description: any field is reachable in at most three actions through outline or search; median input latency on Purchase Order at most 50 ms in the production build | Browser test; performance job |
| P2-A9 | Every error response has the unified format and a correct status code | Contract test over all routes |
| P2-A10 | Coverage of `routers/editor.py` and `routers/export.py` at least 80 %; the core browser suite contains no skip | CI thresholds |
| P2-A11 | A click on a problem focuses its field; server messages use labels, not paths | Browser test |

### Gate 2

- [ ] P2-A1 to P2-A11 pass on the release commit; Gate 0 and Gate 1 automated checks still pass.
- [ ] The allow-list file is empty and stays a required check.
- [ ] Manual: a person who has not worked on the code completes Digital Nameplate, Technical Data and Handover Documentation from the docs alone; time to a valid export and every point of confusion are recorded.
- [ ] Manual: the three `full` exports load into BaSyx and AASX Package Explorer with files and concept descriptions.
- [ ] Docs walkthrough: every statement in the feature pages is checked against the interface (DOC-1).
- [ ] The tool is submitted to the IDTA AAS Solutions Hub and a demo instance is online with server-side storage switched off; the restrictions are verified on the deployed instance.

---

## Phase 3: Battery passport (v1.3, release by 1 February 2027)

**Goal.** All parts of the battery passport and the DPP metadata template can be
filled for one product, exported as one package, and carried across template
bug-fix releases.

**Entry.** Gate 2 passed. The template snapshot contains the current releases
of IDTA 02035 parts 1 to 7 and IDTA 02099-1.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 3.1 | Draft sets: several submodels under one identity; export one package with a choice of submodels | `backend/app/services/hydrator.py`, `frontend/src/features/review/` | ID-4, FE-EX-5 |
| 3.2 | Collections in the catalogue that start a draft set | `frontend/src/features/catalogue/` | FE-CAT-4 |
| 3.3 | Reference picker for elements inside the submodel and for external references | `frontend/src/form/controls/ReferenceField.tsx` | TPL-4 |
| 3.4 | Expose the payload choice (XML, JSON) and XML file export in review | `backend/app/routers/export.py`, review screen | EXP-3, FE-EX-3 |
| 3.5 | Make migration total: no server error on any pair of consecutive releases; report per element what moved and what could not | `backend/app/services/template_ops/migration_service.py` | MIG-1 |
| 3.6 | Run patch-level migration over every patch pair in the snapshot as a test | `backend/tests/template_ops/` | MIG-2 |
| 3.7 | Release picker and "newer release available" notice with review of changes | `frontend/src/features/compare/`, Workspace | MIG-4, FE-MG-3 |
| 3.8 | Open files made by other tools when the semantic identifier matches a known template | `backend/app/services/importer.py` | RT-2 |
| 3.9 | Setting for format rules as warnings or errors | `backend/app/services/format_rules.py`, Settings | VAL-4 |
| 3.10 | Worked example: fixture data for one battery, a script that fills all parts, a tutorial page | `examples/battery-passport/`, `docs/` | TPL-5 |
| 3.11 | CI job that starts the stack with `docker compose up` and runs the worked example | `ci.yml` | OPS-5 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P3-A1 | The worked example produces one AASX with parts 1 to 7 and DPP part 1 under one shell that passes the engine | CI job |
| P3-A2 | Each of the eight submodels passes conformance profiles `required` and `full` | Conformance job |
| P3-A3 | Migration over every pair of consecutive releases in the snapshot returns a report and never a server error | Test over the snapshot |
| P3-A4 | For every patch-level pair, migrated data equals the original for all elements present in both releases | Test over the snapshot |
| P3-A5 | A draft on an older release shows the notice, and the user can review and apply the migration in the interface | Browser test |
| P3-A6 | Fixtures exported from AASX Package Explorer and BaSyx for Digital Nameplate open with their values in place | API test with committed fixtures |
| P3-A7 | `docker compose up` on a clean runner serves a working editor within 120 s | CI job |

### Gate 3

- [ ] P3-A1 to P3-A7 pass on the release commit; all earlier automated checks still pass.
- [ ] Manual: the worked-example package loads into a BaSyx AAS environment and every submodel is readable there.
- [ ] Manual: a second person follows the battery passport tutorial to the end without help.
- [ ] The release is tagged no later than 1 February 2027. If the date is at risk, scope is cut in this order: parts 4 to 7, then RT-2, then VAL-4. Parts 1 to 3 and DPP part 1 are not cut.
- [ ] The release notes state plainly that the tool supplies submodels and does not establish conformance with the Battery Regulation.

---

## Phase 4: Building blocks and batch (v2.0, target second quarter of 2027)

**Goal.** Developers can use the core without the application, catalogue owners
can fill many products at once, and a team can run the tool safely.

**Entry.** Gate 3 passed. ADR-006, ADR-007 and ADR-008 accepted.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 4.1 | Extract the core into a package without web framework imports, one module per pull request; add the import-rule check | new `idta_smt/` from `backend/app/services/{fetcher,parser,validation,hydrator,template_ops}`, `backend/app/utils/` | ADR-007, API-1 |
| 4.2 | Command-line tool: `list`, `schema`, `validate`, `export`, `diff`, `migrate` | `idta_smt/cli/` | API-2, VAL-5 |
| 4.3 | Publish to PyPI from the release workflow; freeze the form schema as version 1 with its specification page | release workflow, `docs/reference/` | API-1, API-3 |
| 4.4 | CI action that validates submodel files in a repository | new `action.yml` | API-5 |
| 4.5 | Job interface with an in-process runner as default and Celery as option; no event loop started in request handlers | `backend/app/services/jobs/`, `backend/celery_app.py` | ADR-008 |
| 4.6 | Move server state to SQLite behind one storage module with migrations | `backend/app/services/storage/` | ADR-003, OPS-7 |
| 4.7 | Upload to an AAS repository through the Part 2 API; target in Settings | `backend/app/services/publish/`, review screen | EXP-7, FE-EX-6 |
| 4.8 | Mapper: tolerant column suggestions in English and German, encodings, lists of collections | `backend/app/services/mapper/` | MAP-1, MAP-3, MAP-4 |
| 4.9 | Batch screen: mapping grid, dry run, one row per submodel, archive export with report | `frontend/src/features/batch/` | MAP-2, MAP-5, FE-BA-1 to FE-BA-7 |
| 4.10 | Compare screen with moved and renamed elements | `migration_service.py`, `frontend/src/features/compare/` | MIG-3, FE-MG-1, FE-MG-2 |
| 4.11 | Authentication on every data operation; login, logout and session expiry in the interface | `backend/app/dependencies.py`, routers, `frontend/src/app/` | OPS-2, FE-SEC-4 |
| 4.12 | Rate limits, upload and unpacked-size limits; schema parsing off the request thread, with caching | `backend/app/main.py`, `upload_security.py`, `parser.py` | OPS-3, OPS-4 |
| 4.13 | Bundle the PDF library, add the content security policy, add consent for sending text to a model provider | `frontend/`, web server config | FE-SEC-1 to FE-SEC-3 |
| 4.14 | Every frontend file of a Stable feature loaded by a test | `frontend/src/**/__tests__/` | TEST-5 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P4-A1 | In a fresh environment, `pip install` of the package and a script of at most ten lines export a conformant Digital Nameplate | CI job outside the repository tree |
| P4-A2 | The package imports nothing from the web application | Import-rule check |
| P4-A3 | Each CLI command works on all templates of the snapshot; `validate` returns a non-zero exit code on an invalid file | CLI tests |
| P4-A4 | A submodel uploaded to a BaSyx repository in a CI service container is read back identical | CI job |
| P4-A5 | A 100-row spreadsheet yields 100 files that pass the engine, and rows with errors are reported before export | Browser test; conformance check on the archive |
| P4-A6 | At least 6 of 7 columns of the demo file are suggested correctly, in English and in German headers | Mapper test |
| P4-A7 | Digital Nameplate 2.0 to 3.0: the known moved elements are reported as moved | Diff test |
| P4-A8 | With authentication on, every data route returns 401 without a token | Route test over all routes |
| P4-A9 | An archive that unpacks beyond the limit is rejected with peak memory under 300 MB; the health endpoint stays under 50 ms during 8 parallel large schema requests | Load tests |
| P4-A10 | A browser test that fails on any request to another origin passes for every screen | Browser test |
| P4-A11 | All add-ons work on the default compose profile without a worker or Redis | CI job |
| P4-A12 | No file of a Stable feature is missing from the coverage report | Coverage check |

### Gate 4

- [ ] P4-A1 to P4-A12 pass on the release commit; all earlier automated checks still pass.
- [ ] Manual: a developer outside the project uses the library or CLI from the published docs and reports what was unclear.
- [ ] Manual: security review of authentication, upload handling and the content security policy, with findings recorded and P0 or P1 findings fixed.
- [ ] The form schema version 1 is published, and a breaking change policy is stated.
- [ ] The package is on PyPI and the action is usable from another repository.

---

## Phase 5: Complete product (v2.x, from the third quarter of 2027)

**Goal.** Close every remaining requirement and replace the remaining
assumptions with measurements.

**Entry.** Gate 4 passed.

### Steps

| # | Step | Where | Requirement |
|---|---|---|---|
| 5.1 | Accessibility: contrast, focus handling, ARIA patterns, zoom; automated check per screen | `frontend/src/ui/`, `frontend/e2e/` | UX-4, FE-A11Y-1 to FE-A11Y-6 |
| 5.2 | Interface in German from one message catalogue | `frontend/src/` | UX-6 |
| 5.3 | Layout for any nesting depth; small-screen layouts | `frontend/src/features/workspace/` | UX-5, Document 6 §6.3 |
| 5.4 | Selection of a submodel in packages with several | importer, import screen | RT-5 |
| 5.5 | One matching algorithm for diff, plan and recipe; migration of filled data across major releases with decisions by the user | `migration_service.py`, compare screen | MIG-5 |
| 5.6 | PDF import: run in process, build a set of real datasheets with reviewed reference values, publish accuracy; label Stable only if the published figure meets a threshold the maintainer sets beforehand | `backend/app/services/magic_import/`, `backend/tests/fixtures/magic_import/` | TEST-8 |
| 5.7 | Semantic lookup on a real, user-supplied dictionary index; repair the index builder | `backend/scripts/semantic_import.py`, `backend/app/services/semantic/` | Document 1 |
| 5.8 | Derive the DPP value-only JSON from a filled IDTA 02099-1 submodel | `idta_smt/` | Roadmap, later list |
| 5.9 | Kubernetes manifests that start with the settings they ship | `kubernetes/`, CI job | OPS-6 |
| 5.10 | Usability tests as planned in document 6, with the findings turned into issues and the top findings fixed | — | Document 6 §9 |
| 5.11 | Support for the newer metamodel versions once the engine checks them | reader, exporter, conformance job | Document 4 |

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| P5-A1 | No violation at WCAG 2.1 level AA in the automated check on any screen; a manual screen-reader pass of the three journeys completes | CI job; manual record |
| P5-A2 | Every user-visible string exists in English and German; a browser test runs the nameplate journey in German | Catalogue check; browser test |
| P5-A3 | Interface Connector renders without overlap at its deepest level | Screenshot test |
| P5-A4 | The MTP package lets the user choose among its submodels | Browser test |
| P5-A5 | Migration across the major releases of Digital Nameplate, Technical Data and Carbon Footprint completes with a report and no server error | Tests |
| P5-A6 | The accuracy of PDF import on the reference set is published with method, data set size and model; the status label matches the rule in step 5.6 | Benchmark job; docs page |
| P5-A7 | The Kubernetes manifests start in a local cluster in CI | CI job |
| P5-A8 | In the usability tests, at least 8 of 10 participants reach a valid Digital Nameplate export without help | Test record |

### Gate 5 and the definition of the finished tool

The tool is fully realised when all of the following hold on one release
commit:

- [ ] Every requirement of document 2 has a passing acceptance test, or is listed with a recorded decision not to build it.
- [ ] The conformance table has no blocking entry on any profile, and names every upstream defect with its issue.
- [ ] Every feature labelled Stable has a test of its main action without mocks, and no feature is labelled above what its tests show.
- [ ] P5-A1 to P5-A8 pass; all earlier automated checks still pass.
- [ ] The docs walkthrough finds no statement that the interface does not bear out.
- [ ] The open points of document 6 are closed: usability tests run, legal review obtained, competitor rows marked as vendor claims either confirmed by trial or removed.

After Gate 5 the plan is replaced by ordinary maintenance: a patch release for
every template snapshot update, with the conformance result attached.

---

## Requirement coverage

Every requirement of document 2 has one phase. Where this table assigns a
requirement the roadmap left unscheduled, this plan is the reference.

| Phase | Requirements |
|---|---|
| 0 | TEST-7, DOC-2, DOC-4, RT-4 |
| 1 | EXP-1, EXP-2, EXP-4, EXP-5, EXP-6, ID-1, ID-2, ID-3, VAL-1, OPS-1, TEST-1, TEST-2, TEST-3 |
| 2 | TPL-1, TPL-2, TPL-3, RT-1, RT-3, DRF-1, DRF-2, DRF-3, VAL-2, VAL-3, UX-1, UX-2, UX-3, API-3 (draft), API-4, TEST-4, TEST-6, DOC-1, DOC-3 |
| 3 | TPL-4, TPL-5, ID-4, EXP-3, MIG-1, MIG-2, MIG-4, RT-2, VAL-4, OPS-5 |
| 4 | API-1, API-2, API-3 (version 1), API-5, VAL-5, EXP-7, MAP-1 to MAP-5, MIG-3, OPS-2, OPS-3, OPS-4, OPS-7, TEST-5 |
| 5 | UX-4, UX-5, UX-6, RT-5, MIG-5, OPS-6, TEST-8 |

## What this plan does not contain

- **Effort estimates.** The audits measured the code, not the time to change it.
  Dates are the roadmap's proposals for one maintainer.
- **Visual design.** Wireframes are the next artefact after document 6.
- **Results.** Nothing in this plan has been run. Every criterion is a target
  until its gate record shows the evidence.
