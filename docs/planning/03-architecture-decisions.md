# 3. Architecture Decisions

Status: all records are **Proposed**. A record becomes *Accepted* when the
maintainer agrees, and is then not edited again; a later record supersedes it.

| Record | Decision in one line |
|---|---|
| [ADR-001](#adr-001-aasx-payload-format) | AASX exports carry XML by default, JSON on request, always with concept descriptions |
| [ADR-002](#adr-002-drop-in-templates-and-free-elements) | Referenced templates are resolved at parse time; free elements become a first-class form type |
| [ADR-003](#adr-003-persistence) | Drafts in the browser, server state in SQLite, no tenant model |
| [ADR-004](#adr-004-tool-registry) | Keep the in-tree manifest, add a status field, drop the plug-in claim |
| [ADR-005](#adr-005-template-source) | A pinned snapshot ships with the release; GitHub is an update channel |
| [ADR-006](#adr-006-publishing-and-samm) | Upload through the AAS Part 2 API replaces dataspace publishing; SAMM conversion is removed |
| [ADR-007](#adr-007-package-layout) | One installable core package with optional extras; the PLC bridge moves out |
| [ADR-008](#adr-008-background-work) | Long tasks run in process by default; Celery is optional |

---

## ADR-001: AASX payload format

**Context.** Exported AASX packages carry a JSON payload and drop almost all
concept descriptions (23 exported against 3,529 in the upstream packages). The
reference desktop editor has an open defect report about JSON-carrying packages
that load without their supplementary files. The IDTA templates themselves are
published with XML payloads.

**Decision.** The exporter writes an XML payload by default and offers JSON as
an option. Both include every concept description of the source package that
the exported submodel references, plus the ones the user added through semantic
lookup. One writer class owns all package-level corrections; the two existing
corrections (`ConformantAASXWriter`, `NormalizingAASXWriter`) merge into it.

**Consequences.** Exports open in tools that expect XML. Package size grows.
The conformance job checks both variants. If the BaSyx SDK fixes the underlying
writer behaviour, the corrections are removed and the fix is taken from
upstream.

**Alternatives.** JSON only: keeps the code as it is and the interoperability
risk. XML only: removes a format that API users ask for.

---

## ADR-002: Drop-in templates and free elements

**Context.** Two patterns of the IDTA templates defeat a form that mirrors the
template file one to one. Some collections are empty in the file and are to be
filled with the structure of another template (the address block of the Digital
Nameplate). Some elements stand for "any property" and must receive a name, a
type and a unit from the user (Technical Data).

**Decision.**

1. The parser resolves a referenced template when it builds the form schema. It
   finds the target by semantic identifier in the template index. A small
   curated table covers the cases where the template files do not name the
   target unambiguously. The schema records where each resolved part came from.
2. If a target cannot be resolved, the form shows that fact and blocks export
   for a mandatory block, instead of presenting an empty section as valid.
3. The form schema gains a node type for free elements. Its editor asks for
   idShort, display name, model type, value type, unit and semantic identifier,
   and the exporter writes the element under that idShort.

**Consequences.** The form schema format changes and gets a version number
(requirement API-3). The curated table needs upkeep when templates change; the
conformance job reports unresolved references per template, so gaps are
visible.

**Open point.** A short investigation must confirm how many templates use each
pattern before the schema change is designed in detail.

---

## ADR-003: Persistence

**Context.** Drafts live in browser storage and are not restored. Server state
(jobs, mapping recipes, audit records) lives in JSON files without locking. The
application has no login in the interface and no tenant model.

**Decision.**

- Drafts stay in the browser (IndexedDB), written on every change and offered
  on return. This needs no server state and works for the single-user case.
- Server state moves to SQLite through one storage module with migrations. The
  module's interface allows PostgreSQL later without changes to callers.
- The product stays self-hosted for one team. Authentication protects the
  instance; there is no separation between tenants.

**Consequences.** Drafts do not follow the user to another browser. Server-side
drafts become possible once the login exists (requirement OPS-2) and are not
planned before that.

**Alternatives.** PostgreSQL from the start: adds a service to the two-minute
quick start. Keeping JSON files: parallel writes can corrupt state.

---

## ADR-004: Tool registry

**Context.** The backend discovers tools from one hard-coded package and serves
a manifest; the frontend maps tool identifiers to components in a static table.
No third party can add a tool without changing the repository. Several
registered tools have no interface.

**Decision.** Keep the manifest as an in-tree mechanism and describe it as such.
Add a `status` field per tool with the labels of document 1 (`stable`,
`experimental`, `sample-data`). The interface, the README table and the docs
read the label from the manifest. A tool without an interface is not listed in
the wizard. A plug-in interface for third parties is not built until someone
asks for one.

**Consequences.** One place decides what users are told about a feature. Dead
registration code (`registerComponent` without callers) is removed.

---

## ADR-005: Template source

**Context.** By default the editor reads templates from the GitHub API. Without
that access the template list fails. Results then depend on the day a user
starts the tool, and a new upstream release can change behaviour without a
release of the editor.

**Decision.** Each release of the editor ships a pinned snapshot of the template
repository (the newest release of each template plus the older releases needed
for migration), identified by the upstream commit. The snapshot is what the
conformance job tested. Updating from GitHub is an explicit action in the
interface and the CLI, and the interface shows which snapshot is in use. The
IDTA template repository API is evaluated as a second update channel.

**Consequences.** The editor works offline and reproducibly. The image grows by
the size of the snapshot. A scheduled workflow opens a pull request when
upstream changes, with the new conformance result attached, so a template
release reaches users through a tested release of the editor.

**Alternatives.** Live GitHub only: current behaviour and its failure mode.
Local mirror only as an option: already exists and is not the default.

---

## ADR-006: Publishing and SAMM

**Context.** The dataspace publishing path does not execute. It checks the
logged-in user and the owner of a connection, but it has no dataspace identity:
no wallet, no credentials and no participant identifier handling, which the
Catena-X network requires. It targets connector versions that the Catena-X network has since
replaced. Applications that exchange data in that network need certification
per ecosystem release. The Tractus-X Industry Core Hub already automates twin
and connector registration. The SAMM converter fails on 65 of 66 templates,
while the ESMF SDK maintains converters in both directions.

**Decision.**

- Remove the dataspace publishing feature, the policy builder and the bundled
  connector stack from the default build and the docs.
- Add one publishing function: upload the finished submodel, and optionally its
  shell, to an AAS repository through the Part 2 API (requirement EXP-7). From
  there the user's own infrastructure registers and shares it.
- Document the path to Catena-X with the Industry Core Hub as a how-to.
- Remove the SAMM converter and link to the ESMF SDK.

**Consequences.** About a sixth of the backend code leaves the repository. The
product no longer shows a Catena-X button. It gains a publishing function that
can be tested in CI against a real repository container.

**Alternative.** Keep dataspace publishing behind a flag as an Experimental
demonstration. This keeps the code and its maintenance cost; choose it only if
the demonstration has an audience.

---

## ADR-007: Package layout

**Context.** The core pipeline is about 17 % of the backend code. Magic Import
and dataspace together are about 38 %. All dependencies install together, the
core functions cannot be imported outside the application, and a Java service
lives in the same repository.

**Decision.**

```text
idta_smt/            core library: reader, index, form schema, validation,
                     export, diff, migration. No web framework.
idta_smt/cli         command line on top of the library
app/                 FastAPI application on top of the library
app/tools/<name>/    one package per add-on, installed through an extra:
                     [mapper], [magic-import], [pcf], [opcua]
frontend/            unchanged location; one folder per tool
```

Rules: the library imports nothing from `app`; an add-on imports the library
and never another add-on; an import-linter contract in CI enforces both. The
PLC4X bridge moves to its own repository. The library is published to PyPI.

**Consequences.** A developer can install and call the core in one line, which
is the route to reuse by other projects. The move is mechanical but touches most
imports, so it is done in one pull request per package with the tests green at
each step.

---

## ADR-008: Background work

**Context.** Magic Import needs a Celery worker and Redis. Without them, the
fallback fails inside the running event loop, so a first-time user gets an
error from the first upload. Dataspace tasks have the same dependency.

**Decision.** Long-running work goes through one small job interface with two
back ends: an in-process runner (thread pool, state in SQLite), which is the
default, and Celery, which is optional for larger installations. The default
`docker compose up` needs no worker and no Redis. Request handlers never start
an event loop.

**Consequences.** Every add-on works on the core profile. Jobs do not survive a
restart in the default back end; the interface says so and offers a retry.
