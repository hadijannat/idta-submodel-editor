# 2. Core Requirements

Status: draft for maintainer review.

Each requirement has an identifier, a statement that can be true or false, an
acceptance test, and the baseline measured on 2026-11-10 at commit `15a9bc4`.
"All templates" means every published and deprecated entry of the IDTA template
repository that the editor lists. Priority: **P0** blocks the next release,
**P1** blocks the battery passport release, **P2** follows.

## Export

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| EXP-1 | P0 | An exported AASX passes `aas-test-engines` for every template whose upstream file passes | Conformance job (document 4): zero results classed "editor defect" | 53 of 70 pass; 13 failures caused by the editor, addressed by #391 and not yet re-measured |
| EXP-2 | P0 | An exported AASX contains every ConceptDescription the template package contains | For each template, the set of ConceptDescription identifiers equals the upstream set, and each description is equal in content | 23 exported against 3,529 upstream; JSON export keeps all |
| EXP-3 | P1 | AASX export writes an XML payload by default and a JSON payload on request | Both variants open with the BaSyx Python SDK and pass the engine | JSON payload only |
| EXP-4 | P0 | Every form the validator accepts can be exported | For each template, generated valid data exports with HTTP 200 | 4 templates validate and then fail at export |
| EXP-5 | P0 | An export contains no untouched template example value and no empty optional element | Export of a required-only form contains neither | 2,371 empty optional elements across the corpus; examples exported |
| EXP-6 | P1 | The PCF check applies only when the user has used the PCF aid | Battery Passport part 3 and Carbon Footprint 0.9 export with all fields filled | Both return HTTP 422 |
| EXP-7 | P2 | A finished submodel can be uploaded to an AAS repository through the Part 2 API | Upload to a BaSyx repository in a CI service container, then read back | Not available |

## Identity

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| ID-1 | P0 | The user sets the AAS identifier, the global asset identifier and the asset kind before export | The exported AAS identifier, global asset identifier and asset kind each equal the value the user entered | 68 of 71 exported shells keep the template's identifiers |
| ID-2 | P0 | The exported shell, asset and submodel do not carry the identifiers of the template's shell, asset and submodel. Semantic identifiers and ConceptDescription identifiers stay as the template defines them | The AAS identifier, global asset identifier and submodel identifier of the export each differ from those in the upstream package | Fails |
| ID-3 | P0 | The exported submodel has kind `Instance` and a new identifier, proposed by the editor and editable | Check in the conformance job | Kind is correct; identifier handling to be verified |
| ID-4 | P1 | Several submodels can be exported under one shell | One AASX with battery passport parts 1 to 7 under one AAS passes the engine | One submodel per export |

## Import and round trip

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| RT-1 | P0 | An AASX or JSON file exported by the editor can be opened in the interface, changed and exported again | Browser test: export, reopen, change one value, export; the two files differ only in that value | No import in the interface; JSON rejected by the API |
| RT-2 | P1 | A submodel made by another tool opens if its semantic identifier matches a known template | Fixtures exported from AASX Package Explorer and BaSyx open with their values in place | Not available |
| RT-3 | P1 | Elements of an imported file that the template does not know are kept and reported | Import, export, compare: no element lost | Not available |
| RT-4 | P0 | `POST /api/template-ops/import` accepts AASX and JSON | API test with both file types | Returns HTTP 500 |
| RT-5 | P2 | A package with several submodels lets the user choose which one to edit | Browser test with the MTP template | Only the first is shown |

## Drafts

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| DRF-1 | P0 | Every change is saved locally within 2 seconds | Browser test: type, wait 2 s, reload | Nothing saved in the first 30 seconds |
| DRF-2 | P0 | After a reload the user is offered the draft and returns to the same step with the same entries | Browser test | A stored draft is never offered |
| DRF-3 | P1 | Drafts are listed per template and can be deleted | Browser test | Not available |

## Entry templates

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| TPL-1 | P0 | A collection that a template leaves empty and fills by reference to another template shows the fields of that template | Digital Nameplate: `AddressInformation` shows its fields and a form without address fails validation | "Address Information (0 fields)"; form validates |
| TPL-2 | P0 | An element the template declares as free (arbitrary idShort) gets a name, a value type, a unit and a semantic identifier from the user | Technical Data: three named, typed properties export under their names | Exported as `ArbitraryProperty`, `ArbitraryProperty__01__`, all `xs:string` |
| TPL-3 | P0 | A File element accepts an upload, and the file is in the exported AASX | Handover Documentation: an uploaded PDF is in the package and referenced | No upload control |
| TPL-4 | P1 | A reference field offers the possible targets inside the submodel and accepts an external reference | Browser test on Hierarchical Structures | Free text only |
| TPL-5 | P1 | Battery passport parts 1 to 7 and DPP part 1 (IDTA 02035, 02099-1) fill, validate and export without workaround | Worked example in the repository, run in CI | Part 3 blocked by EXP-6; AASX parts 1 to 3 failed before #391 |

## Validation

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| VAL-1 | P0 | Every XSD value type the metamodel allows is checked for lexical form and range | Unit test per type; a non-numeric value in an `xs:long` field is rejected | `xs:long`, `xs:short` and the unsigned types are unchecked (169 nodes) |
| VAL-2 | P0 | Each qualifier the editor reads has a test with one accepted and one rejected value on a real template: cardinality, allowed values, allowed range, either-or, required language, default and example | Test matrix over the qualifier list | Only cardinality and types are shown to be enforced |
| VAL-3 | P1 | A validation message names the field by its label and takes the user to it | Browser test: click on a message focuses the field | Plain idShort paths, not linked |
| VAL-4 | P1 | The user chooses whether format rules from the specification text are warnings or errors | Setting, covered by an API test | Warnings only |
| VAL-5 | P2 | The validator runs on a file without the form (see API-2) | CLI test | Not available |

## Migration

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| MIG-1 | P0 | Migration never fails with a server error; what cannot be moved is reported per element | Run over every pair of consecutive releases in the template repository | Fails on every major-version pair tried |
| MIG-2 | P1 | Data moves between patch releases without loss | Fill, migrate, compare, for every patch pair | 30 of 30 on the pairs tried |
| MIG-3 | P1 | The diff recognises renamed and moved elements | Digital Nameplate 2.0 to 3.0: known moves are reported as moves | Reported as removed plus added |
| MIG-4 | P1 | The interface lets the user pick two releases of one template | Browser test | Not available |
| MIG-5 | P2 | Diff, migration plan and recipe use one matching algorithm | One confidence value per element pair | Two algorithms with different values |

## Spreadsheet mapping

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| MAP-1 | P1 | Column suggestions tolerate spacing, case, separators and the template's labels in English and German | At least 6 of 7 columns of the demo file are suggested correctly | 0 of 7 |
| MAP-2 | P1 | One row produces one submodel, and all rows export as one archive | 100-row file yields 100 files that pass the engine | No output in the interface |
| MAP-3 | P1 | Columns map into lists of collections | Markings of the Digital Nameplate from grouped rows | Path rejected by the tool's own validator |
| MAP-4 | P2 | Files in Latin-1 and Windows-1252 are read | API test | HTTP 500 |
| MAP-5 | P2 | Every control is reachable at 1280 px width | Browser test | "Run mapping" is off-screen at 1440 and 1920 px |

## Usability

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| UX-1 | P1 | Large forms have an outline, expand-all and search by label or idShort | Browser test on Asset Interfaces Description | 182 clicks to open every section |
| UX-2 | P1 | Typing in the largest form responds within 50 ms (median, production build) | Performance test on Purchase Order | 158 ms |
| UX-3 | P1 | Template search finds by IDTA number | "02006" finds Digital Nameplate | Name and title only |
| UX-4 | P2 | Text contrast meets WCAG 2.1 AA, and dialogs keep the focus inside | Automated accessibility check in CI | Secondary text at 2.15:1 and 3.8:1 |
| UX-5 | P2 | The layout holds at any nesting depth the templates use | Screenshot test on Interface Connector | Breaks at depth 12 |
| UX-6 | P2 | The interface is available in English and German | Language switch covered by a browser test | English only |

## API, library and command line

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| API-1 | P1 | Reader, form schema, validator, exporter and diff are importable as a Python package without starting the server | `pip install`, then a ten-line script exports a nameplate | Importable only with the application's path set |
| API-2 | P1 | A command-line tool offers `list`, `schema`, `validate`, `export`, `diff`, `migrate` | CLI tests | Not available |
| API-3 | P1 | The form schema is a versioned, documented format | JSON Schema of the format in the repository; contract test | Undocumented |
| API-4 | P1 | Errors use one format and the correct status code on every endpoint | Contract test over all routes | An unknown template returns 404, 400, 200 or 500 depending on the endpoint; upload errors return 200 |
| API-5 | P2 | A CI action validates submodel files in a repository | Example workflow | Not available |

## Operation and security

| ID | P | Requirement | Acceptance test | Baseline |
|---|---|---|---|---|
| OPS-1 | P0 | The editor starts and works without access to the GitHub API | Start with the network blocked; list, fill and export a template | Template list returns HTTP 502 |
| OPS-2 | P1 | With authentication enabled, every operation that reads or writes user data requires a token, and the interface has a login | Route test: no token, HTTP 401 | 53 of 103 operations never check a token; no login |
| OPS-3 | P1 | Rate limits and upload size limits are enforced, including the unpacked size of archives | Load test; archive bomb test | No rate limit; a 404 kB upload reached 1.3 GB of memory |
| OPS-4 | P1 | Parsing a large template does not block other requests | Health endpoint stays under 50 ms during 8 parallel schema requests | 350 ms |
| OPS-5 | P1 | `docker compose up` gives a working editor, and CI proves it | CI job starts the stack and exports a nameplate | Not tested in CI |
| OPS-6 | P2 | The Kubernetes manifests start with the settings they ship | CI job with a local cluster | Rejected by the application's own settings check |
| OPS-7 | P2 | Server state is stored with locking and survives parallel writes | Concurrency test | JSON files without locking |

## Test strategy

The baseline showed 1,774 passing backend tests and 606 passing frontend tests
while several headline features failed when run. Each failure sat behind a mock.
These rules close that gap.

| ID | P | Rule | Check |
|---|---|---|---|
| TEST-1 | P0 | Every Stable feature has at least one test that runs its main action through the HTTP API with no mock inside the application. A feature that lives only in the browser (drafts, ADR-003) has a browser test against the running application instead | Review checklist; list of such tests in the repository |
| TEST-2 | P0 | The conformance job of document 4 blocks merges | Branch protection |
| TEST-3 | P0 | Type checking covers the whole backend and blocks merges | CI; baseline 14 of 171 files, 216 errors when run on all |
| TEST-4 | P1 | Coverage of the editor and export routers is at least 80 %, with a threshold in CI | CI; baseline 36 % and 20 % |
| TEST-5 | P1 | Every frontend file of a Stable feature is loaded by at least one test | Coverage report lists no unloaded file; baseline 53 of 125 unloaded |
| TEST-6 | P1 | The browser tests for the core job run on every pull request and contain no skip | CI; baseline 78 conditional skips |
| TEST-7 | P1 | No test needs the public internet | The suite passes with the network blocked; baseline one failing test |
| TEST-8 | P1 | Magic Import is released only with an accuracy figure measured on real datasheets with reviewed reference values | Benchmark and data set in the repository |

## Documentation

| ID | P | Requirement | Check |
|---|---|---|---|
| DOC-1 | P0 | The docs describe only what the interface offers | Docs review against a browser walkthrough for each release |
| DOC-2 | P0 | Every feature carries its status label from document 1 wherever it appears: README, docs and interface; for a feature without an interface, its API reference page and its OpenAPI description. A Removed feature appears in none of them and is named once in the changelog of the release that removed it | Status comes from the tool manifest; the docs build fails on a page for a tool the manifest does not list |
| DOC-3 | P1 | Every screenshot in the docs is generated by a browser test | Docs build fails on an unreferenced or missing image |
| DOC-4 | P1 | The changelog and the release notes match the tagged releases | Release checklist |
