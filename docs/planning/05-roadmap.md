# 5. Roadmap and Release Plan

Status: draft for maintainer review. Dates are proposals for one maintainer and
move with capacity; the order does not.

## Principles

1. Correctness of the core before any new feature.
2. A milestone is done when its exit criteria pass in CI, not when the code is
   merged.
3. Every milestone ends in a tagged release with notes.
4. Nothing is advertised before it is Stable (document 1).

## Fixed external date

The EU battery passport obligation applies from **18 February 2027**. Milestone 3
must be released before it, with enough margin for users to try it.

## Milestones

### M0 — Clean base (v1.0.1, November 2026)

No new behaviour. Makes the repository tell the truth.

- Merge or close the open dependency updates.
- Apply the status labels of document 1 to the README, the docs and the tool
  manifest (ADR-004); remove claims the code does not back (claims policy).
- Remove the Template Knowledge Index, the DPP Builder panel and the SAMM
  converter from the default build (pending acceptance of document 1).
- Fix the one test that needs the public internet (TEST-7).
- Correct the changelog date of 1.0.0; set repository topics.

Exit: docs build passes; the README lists no feature above its status; the test
suite passes offline.

### M1 — Correct export (v1.1, December 2026)

Requirements: EXP-1, EXP-2, EXP-4, EXP-5, EXP-6, ID-1, ID-2, ID-3, VAL-1,
RT-4, OPS-1, TEST-1, TEST-2, TEST-3. Decisions: ADR-001, ADR-005.

- Conformance job of document 4 for profile `required`, blocking, with the
  generated public table.
- Concept descriptions in AASX; XML payload.
- Identity step in the wizard.
- Validator and exporter agree on every template.
- Pinned template snapshot as default source.

Exit: no template in a blocking class except entries on the allow-list that
belong to M2; the conformance table is published on the docs site.

### M2 — Complete entry templates and round trip (v1.2, January 2027)

Requirements: TPL-1, TPL-2, TPL-3, RT-1, RT-3, DRF-1, DRF-2, VAL-2, VAL-3,
UX-1, UX-3, API-4, TEST-4, TEST-6, DOC-1. Decisions: ADR-002, ADR-003.

- Referenced templates resolved; free elements with name, type and unit; file
  upload into the package.
- Open an exported file, edit, export again; drafts that restore.
- Qualifier test matrix.
- Conformance profile `full`.

Exit: a browser test fills a complete Digital Nameplate with address, a
Technical Data submodel with three named properties and a Handover
Documentation with one document, exports, reopens and re-exports each; the
allow-list is empty.

### M3 — Battery passport (v1.3, release by 1 February 2027)

Requirements: TPL-4, TPL-5, ID-4, EXP-3, MIG-1, MIG-2, MIG-4, OPS-5.

- All parts of IDTA 02035 and IDTA 02099-1 under one shell, in one AASX.
- A worked example in the repository and the docs, run in CI.
- Patch-level migration visible in the interface, because these templates are
  new and will receive bug-fix releases.
- Quick start verified in CI.

Exit: the worked example passes the engine and loads into a BaSyx repository
container; a user can move a filled part from one bug-fix release to the next.

### M4 — Building blocks (v2.0, second quarter of 2027)

Requirements: API-1, API-2, API-3, API-5, EXP-7, MAP-1 to MAP-3, MIG-3 (the
diff recognises renamed and moved elements), OPS-2 to OPS-4. Decisions: ADR-006, ADR-007, ADR-008.

- Core library on PyPI, command-line tool, CI action.
- Versioned form schema with its own specification page.
- Upload to an AAS repository through the Part 2 API.
- One row per submodel from a spreadsheet, with batch export.
- Login in the interface and authentication on every data operation.

Exit: a ten-line script outside the repository exports a nameplate; a second
project consumes the form schema; batch export of 100 rows passes the engine.

### Later, not scheduled

- Magic Import as Stable, after TEST-8 gives it a measured accuracy figure.
- Migration of filled data across major releases, which builds on the diff of
  MIG-3 from M4 and needs MIG-5.
- Interface in German (UX-6), accessibility to WCAG 2.1 AA (UX-4).
- Derivation of the DPP value-only JSON from a filled IDTA 02099-1 submodel.
- Support for metamodel 3.1 and 3.2 packages once the engine checks them.

## Release rules

- Cadence: a release at each milestone, and a patch release whenever the
  template snapshot changes or a blocking conformance class is fixed.
- Versioning: semantic. A change of the form schema format or of the library
  interface is a major or minor change and is named in the notes.
- Each release attaches the conformance result and names the template snapshot.
- Release checklist: conformance green on every profile that exists at that
  milestone (M0: the existing `aas-conformance` job; M1: profile `required`;
  from M2 on: all profiles); docs walkthrough
  (DOC-1); changelog; tag; container images; PyPI from M4 on.

## Adoption steps tied to milestones

| After | Step |
|---|---|
| M0 | Consolidate related repositories into this one or link them from one place |
| M1 | Report every `upstream-defect` to the template repository, with the generated text block |
| M1 | Offer the reader's package repairs to the BaSyx Python SDK |
| M2 | List the tool in the IDTA AAS Solutions Hub; put a public demo instance online. The demo keeps no visitor data on the server: template upload, local templates, server-side jobs and every add-on that stores files are switched off, and drafts stay in the visitor's browser. Authentication in M4 does not separate visitors, so these functions stay off in the demo after M4 as well |
| M2 | Label starter issues; document the architecture for contributors |
| M3 | Publish the battery passport worked example as a tutorial |
| M4 | Submit a tool paper; propose the form schema to the BaSyx and Mnestix projects as an input format |

## Risks

| Risk | Effect | Response |
|---|---|---|
| One maintainer | Dates slip | The order holds; M3 scope shrinks to parts 1 to 3 and DPP part 1 before M2 scope does |
| Battery passport templates change before February | Rework | Snapshot updates through the weekly job; patch-level migration is in M3 for this reason |
| BaSyx generalises its creation wizard to any template | The form alone no longer differentiates | The public conformance table, migration and the library are the lead; reach M1 and M2 first |
| Large, fast merges reintroduce defects | Regressions like the lost export fix | The conformance job blocks merges; a human review before every merge |
| Removing features disappoints existing users | Complaints | Announce in the M0 notes; removed code stays in history and can return through a decision record |
| The engine lags behind the metamodel | Passes that mean less over time | State the engine version and its limits in the table; add the repository round-trip check |

## What "done" looks like

The tool is not finished when it has every feature. It is finished, for a given
release, when the conformance table has no blocking entry, every Stable feature
has an unmocked test, and the docs describe what the interface does. Those three
checks are the definition this plan works toward.
