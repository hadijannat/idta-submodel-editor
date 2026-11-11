# Planning Documents

These seven documents define what the editor is meant to be, what "done" means for
its core, which design decisions the refactoring depends on, how correctness is
proven, in which order the work ships, and how the interface is built.

| # | Document | Settles |
|---|---|---|
| 1 | [Product scope and feature status](01-product-scope.md) | Who the tool is for, its one core job, non-goals, and the status of every feature |
| 2 | [Core requirements](02-core-requirements.md) | Measurable requirements with acceptance tests, and the test strategy |
| 3 | [Architecture decisions](03-architecture-decisions.md) | The design choices that shape the refactoring |
| 4 | [Conformance specification](04-conformance-specification.md) | What is checked per template and how CI publishes the result |
| 5 | [Roadmap and release plan](05-roadmap.md) | Milestones, release cadence and exit criteria |
| 6 | [Frontend design specification](06-frontend-design-specification.md) | Screens, field behaviour, competitor capability decisions, accessibility and the compliance matrix |
| 7 | [Implementation plan](07-implementation-plan.md) | Six phases with ordered steps, acceptance criteria and one acceptance gate each, ending in the definition of the finished tool |

## Status

All seven are **drafts for maintainer review**. Decisions in document 3 are marked
*Proposed* until accepted. Dates in document 5 are proposals.

## Baseline

Figures quoted as "baseline" come from an audit of commit `15a9bc4` on 2026-11-10
against the IDTA template repository in its state of 2026-10-29 (66 published and
8 deprecated template entries). The audit read all 74 entries and filled each
with generated required-only data. 70 of them could be exported; 4 could not.
The 70 exports were checked with `aas-test-engines` 1.0.3.

One fix has landed since: #391 corrects the relationship targets of supplementary
files in exported AASX packages, the cause of 13 of the 17 AASX failures in the
baseline. The AASX figures have not been re-measured after #391; the first run of
the conformance job described in document 4 replaces them.

## Maintenance

- A requirement changes only together with its acceptance test.
- A feature changes status only in document 1, and the README and the tool
  manifest follow it.
- A decision record is never edited after acceptance. A new record supersedes it.
