# 4. Conformance Specification

Status: draft for maintainer review.

## Purpose

The editor's central claim is that every published IDTA template passes through
it into a conformant file. This document defines how that claim is tested, how
the result is classified, and how it is published. The published table is part
of the product: it tells a user which templates to trust, and it tells template
maintainers which upstream files have defects.

## Corpus

- Every published and deprecated entry of `admin-shell-io/submodel-templates`,
  each at its newest release. Baseline: 66 published, 8 deprecated.
- The corpus is the pinned snapshot of ADR-005. The upstream commit is recorded
  in the result.
- Template parts (for example battery passport parts 1 to 7) are separate rows.

## Pipeline per template

| Step | Action | Recorded |
|---|---|---|
| 1 | Read the upstream AASX with the editor's reader | Success; repairs applied by the reader |
| 2 | Check the upstream AASX and JSON with the engine | Pass or fail with messages |
| 3 | Build the form schema | Node count; element types; unresolved template references; free elements |
| 4 | Generate form data for each fill profile | Number of values set |
| 5 | Validate the form data | Accepted or rejected with messages |
| 6 | Export AASX (XML payload), AASX (JSON payload) and JSON | HTTP status; duration |
| 7 | Check every export with the engine | Pass or fail with messages |
| 8 | Read each export back and compare with the form data | Values lost or changed; concept description identifiers and contents against upstream |
| 9 | Check identity | Shell, asset and submodel identifiers differ from the template's and equal the entered values; kind `Instance` |

Steps 5 to 7 run through the HTTP API, not by calling services directly, so the
routers are under test as well (requirement TEST-1).

## Fill profiles

| Profile | Content | Purpose |
|---|---|---|
| `required` | Only mandatory elements, with generated values that satisfy type, range, allowed values and required languages | The smallest valid submodel |
| `full` | Every element once, repeatable elements twice, one uploaded file per File element, free elements with a generated name and type | Exercises optional structure, lists and supplementary files |
| `examples` | The template's own example values, unchanged | Shows whether the template's examples satisfy its own rules |

The generator is deterministic: the same snapshot and seed give the same data.

## Engine

- `aas-test-engines`, at one exact version that this job installs from a
  constraints file. `backend/requirements.txt` allows a range, so the job pins
  its own version, and a change of that version is a reviewed change with the
  new result attached. The baseline used 1.0.3.
- Known limits, stated in the published table:
  - The engine checks metamodel 3.0. A file in the 3.1 XML namespace is reported
    as failing for that reason alone; such results are classed `engine-limit`.
    In the baseline this applied to 25 of 31 upstream AASX failures.
  - The engine has template-specific checks for two templates. For all others a
    pass means metamodel conformance, not conformance to the template.
- Conformance to the template itself is covered by steps 5 and 8 and by the
  qualifier tests of requirement VAL-2.

## Result classes

| Class | Meaning | Effect in CI |
|---|---|---|
| `pass` | Export passes the engine and the read-back comparison | — |
| `upstream-defect` | Every engine message on the export also occurs on the upstream file | Allowed; listed with a link to the upstream issue |
| `engine-limit` | Failure caused by a documented limit of the engine | Allowed; listed |
| `editor-defect` | The export has at least one engine message that the upstream file does not have | **Blocks the merge** |
| `validation-reject` | The validator rejects generated data that satisfies the template's rules | **Blocks the merge** |
| `not-exportable` | Validation accepts the data and export fails | **Blocks the merge** |
| `data-loss` | Read-back differs from the form data, or concept descriptions are missing | **Blocks the merge** |
| `identity` | The shell, asset or submodel identifier is the template's or differs from the entered value, or the submodel kind is not `Instance` | **Blocks the merge** |

Messages are compared one by one. An export whose messages include both
inherited and new ones is an `editor-defect`: the job blocks on every message
that cannot be attributed to the upstream file. A template can carry several
classes, and any blocking class blocks.

During the transition, known failures of a blocking class are listed in an
allow-list file with the requirement that will remove them. The job fails on
any failure that is not on the list and on any list entry that now passes, so
the list can only shrink.

## Baseline (2026-11-10, commit `15a9bc4`, profile `required`)

| Measure | Result |
|---|---|
| Templates read | 74 of 74 |
| Templates exported | 70 of 74 (4 `not-exportable`) |
| JSON exports passing | 63 of 70; all 7 failures `upstream-defect` |
| AASX exports passing | 53 of 70; 13 `editor-defect`, addressed by #391 and not re-measured |
| Concept descriptions in AASX exports | 23 of 3,529 (`data-loss`) |
| Shells keeping template identifiers | 68 of 71 (`identity`) |

The `full` and `examples` profiles have no baseline.

## Outputs

1. `conformance.json`: one record per template and profile with every recorded
   field, the snapshot commit, the editor commit and the engine version.
2. `docs/reference/conformance.md`: the public table, generated from the JSON
   and never edited by hand.

   | Template | IDTA | Release | Upstream | JSON | AASX (XML) | AASX (JSON) | Notes |
   |---|---|---|---|---|---|---|---|

3. A summary line for the README and a badge: templates passing out of total.
4. For each `upstream-defect`, a text block ready to file as an upstream issue.

## Where it runs

| Trigger | Scope | Blocking |
|---|---|---|
| Pull request | All templates, profile `required`; profile `full` for templates whose code paths changed | Yes |
| Push to `main` | All templates, all profiles; regenerate the table | Yes |
| Scheduled, weekly | Newest upstream commit instead of the snapshot | No; opens a pull request that updates the snapshot with the new result |
| Release | All templates, all profiles; result attached to the release | Yes |

Baseline timings suggest the job is cheap: schema generation takes at most
0.6 s per template and export about 50 ms.

## Relation to existing files

- `backend/scripts/audit_template_coverage.py` covers steps 1, 3, 4 and part of
  8. It is extended, not replaced, and gains steps 2, 5 to 7 and 9.
- `backend/scripts/export_conformance_sample.py` and the committed fixtures of
  the `aas-conformance` job are superseded once the full job blocks merges.
- `docs/reference/template-coverage-audit.md` is merged into the generated
  reference page.

## Interoperability beyond the engine

A pass from one engine does not show that other tools accept the file. For each
release, the `full` export of Digital Nameplate, Technical Data, Handover
Documentation and battery passport part 1 is loaded into a BaSyx repository in
a CI service container and read back. Loading into AASX Package Explorer is a
manual release check until it can be automated.
