# 6. Frontend Design Specification

Status: draft for maintainer review.

This document says how the interface is built so that it meets the requirements
of document 2 inside the scope of document 1. Document 2 states *what* must be
true; this one states *how the interface makes it true*. Where a requirement of
document 2 is implemented here, its identifier is given.

## How to read the evidence

| Label | Meaning |
|---|---|
| **Audit** | Measured on this repository on 2026-11-10 at commit `15a9bc4` |
| **Competitor** | Taken from a competitor's public documentation, release notes or source code in November 2026. No competing tool was tried hands-on |
| **Vendor claim** | A competitor's own description that could not be checked |
| **Demand** | Stated in published literature, standards guidance or public issue trackers |
| **Judgement** | A design choice of this document without external evidence |

"Every feature competitors offer" is treated as an inventory, not as a build
list. Section 4 lists each competitor capability with a decision: **Adopt**,
**Adapt**, **Integrate** (hand over to another tool) or **Out of scope**, with
the reason. Building everything would contradict the non-goals of document 1
and repeat the pattern the audit found: more surface than can be verified.

## 1. Users and journeys

| User (document 1) | Main journey | Screens used |
|---|---|---|
| Product data engineer, not an AAS expert | Pick a template, fill the required fields with guidance, export a file the customer accepts | Catalogue, Workspace in guided mode, Review |
| Battery passport author | Fill several parts for one product under one identity, export one package | Catalogue (collection view), Workspace, Review |
| AAS integrator or developer | Inspect structure, semantic identifiers and raw output; reopen and correct files; compare template releases | Workspace in expert mode, Import, Compare |
| Catalogue owner with many products | Fill one template for many products from a spreadsheet | Batch |
| Template author or reviewer | See what a template demands and whether it is conformant | Catalogue, Compare, Conformance page |

## 2. Design principles

1. **The template is the single source of truth.** Field, label, help, input
   control, validation rule and export mapping all derive from the same form
   schema node. No rule is written twice.
2. **Required first, complete later.** A user reaches a valid file through the
   mandatory fields alone; everything else is reachable but not in the way.
3. **Nothing invalid looks valid.** An unresolved mandatory block, an untouched
   example value or a sample data set is shown as such (audit: a mandatory
   address block rendered with zero fields and passed validation).
4. **No lost work.** Every change is stored; every exported file can be opened
   again.
5. **Say what the tool is.** Status labels, engine version and template release
   are visible where a decision depends on them.
6. **One interface, two depths.** Guided and expert mode show the same data.
7. **Usable without a mouse and without a network.**

## 3. Information architecture

The current interface is one 1,270-line component with eight hard-coded wizard
steps, two of which (spreadsheet mapping, PDF import) every user passes through
(audit). It is replaced by routed screens.

```text
/                         Catalogue
/t/:template              Template detail (releases, documents, conformance)
/w/:draft                 Workspace: outline | form | context panel
/w/:draft/review          Review and export
/import                   Open an existing AASX or JSON file
/compare/:template        Compare two releases, migrate a draft
/batch/:template          Fill many instances from a spreadsheet
/drafts                   Drafts on this device
/conformance              Published conformance table (document 4)
/settings                 Language, mode, template snapshot, providers
```

Tools that assist filling (semantic lookup, PDF import, PCF entry aid) open in
the context panel of the Workspace. They are never steps.

### 3.1 Catalogue

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-CAT-1 | Cards show title, IDTA number, newest release, number of releases, conformance badge, and a marker for available specification PDF | Audit (present except badge) | — |
| FE-CAT-2 | Search matches name, title, IDTA number and semantic identifier | Audit: "02003" finds nothing | UX-3 |
| FE-CAT-3 | Filters: status (published, deprecated), domain tag, "has required fields under N", conformance result | Judgement; Demand: template discovery is a documented need | — |
| FE-CAT-4 | Collections group multi-part templates (battery passport parts 1 to 7) and start one draft set under one identity | Demand: battery passport from 18 February 2027 | ID-4, TPL-5 |
| FE-CAT-5 | Template detail lists all releases with dates, links to the PDF, JSON and AASX, the conformance row and a "compare releases" action | Competitor: none found for compare | MIG-4 |
| FE-CAT-6 | The active template snapshot and its upstream commit are shown in the footer; an update is an explicit action | ADR-005 | OPS-1 |

### 3.2 Workspace

Three panes on wide screens; outline and context panel become drawers below
1,024 px.

**Outline (left)**

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-WS-1 | Tree of all sections with completion state per node (complete, required missing, has warnings, untouched) | Audit: 182 clicks to open one template | UX-1 |
| FE-WS-2 | Search by label, idShort or semantic identifier jumps to the field | Audit | UX-1 |
| FE-WS-3 | Expand all, collapse all, "show only required", "show only problems" | Audit | UX-1 |
| FE-WS-4 | The outline is virtualised and keyboard navigable (arrow keys, type-ahead) | Audit: lists lack arrow-key navigation | UX-4 |

**Form (centre)**

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-WS-5 | Guided mode shows labels in plain language, required fields first, optional groups collapsed. Expert mode adds idShort, model type, value type, semantic identifier, qualifiers and the path | Demand: expert knowledge is the named adoption barrier; Competitor: tree editors serve experts only | — |
| FE-WS-6 | Each field shows definition, format hint, example and a link to the page of the specification PDF | Audit (present; keep) | — |
| FE-WS-7 | An untouched template example is marked and never counts as filled; one action clears all | Audit (present; keep) | EXP-5 |
| FE-WS-8 | Inline validation on blur; the message names the rule and the expected form | Audit (present; keep) | VAL-3 |
| FE-WS-9 | Typing responds within 50 ms on the largest template; only visible fields are mounted | Audit: 158 ms per key | UX-2 |
| FE-WS-10 | Nested collections indent to a fixed maximum; deeper levels use breadcrumbs instead of further indentation | Audit: layout breaks at depth 12 | UX-5 |
| FE-WS-11 | Undo and redo for value changes and for add, remove and reorder of items | Judgement | — |
| FE-WS-12 | Copy and paste of a collection or list item, within a draft and between drafts | Competitor: BaSyx (JSON clipboard) | — |

**Context panel (right)**

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-WS-13 | Shows the concept description of the focused field: preferred name, definition, unit, data type, value list, source dictionary | Competitor: BaSyx, AASX Package Explorer | — |
| FE-WS-14 | Problems list: every error and warning with label; a click focuses the field | Audit: messages are unlinked idShort paths | VAL-3 |
| FE-WS-15 | Live preview tabs: product card, JSON, element tree | Competitor: BaSyx (JSON and XML viewers, UML panel); audit (card preview exists) | — |
| FE-WS-16 | Assist tools open here against the focused field or section and write only after the user confirms | Audit: PCF "apply" wrote to a wrong path | — |

### 3.3 Field controls

One control per form-schema node type. The mapping is the contract between
parser and interface (requirement API-3).

| Node | Control | Behaviour |
|---|---|---|
| Property, by value type | Text, number with step and unit, date, date-time, duration, boolean switch, URI | Lexical check for every XSD type (VAL-1) |
| Property with value list | Select or combobox from the allowed values or the IEC 61360 value list | Free entry only if the template allows it |
| MultiLanguageProperty | Language tabs with a completeness marker; required languages are fixed tabs | Missing required language is an error |
| Range | Two inputs with one unit; min ≤ max enforced | — |
| File | Drop zone with upload, type and size check, preview; the file is stored in the package | TPL-3; audit: no upload exists |
| Blob | Upload with content type | — |
| ReferenceElement, RelationshipElement | Picker for elements of this submodel; separate entry for an external reference with key-chain editor in expert mode | TPL-4 |
| Entity | Entity type switch; asset identifier fields; statements as nested form | — |
| SubmodelElementCollection | Section with completion state | — |
| SubmodelElementList | Table for flat items, cards for nested items; add, remove, reorder, duplicate | — |
| Repeatable element outside a list | "Add another" with numbered idShorts on export | Audit (present since #390) |
| Free element (arbitrary idShort) | Editor for idShort, display name, model type, value type, unit, semantic identifier | TPL-2, ADR-002 |
| Referenced template (drop-in) | Fields of the resolved template; if unresolved, a blocking notice | TPL-1, ADR-002 |
| Operation, Capability, BasicEventElement | Read-only summary | Audit: classed read-only |

### 3.4 Template qualifiers in the interface

The IDTA guideline for submodel templates defines the qualifiers a form tool has
to honour. The backend already reads each name below (audit: read in code); the
audit could show enforcement only for cardinality and value types, so every row
needs the test of requirement VAL-2.

| Qualifier | Interface behaviour |
|---|---|
| `SMT/Cardinality` (One, ZeroToOne, ZeroToMany, OneToMany) | Required marker, "add another", minimum count on lists |
| `SMT/EitherOr` | The alternatives are shown as one group with the rule stated; filling one satisfies the group |
| `SMT/AllowedValue` | Select for an enumeration; pattern check with the pattern shown for a regular expression |
| `SMT/AllowedRange` | Minimum and maximum on the input, stated in the hint |
| `SMT/AllowedIdShort` | Constrains the idShort editor of a free element |
| `SMT/RequiredLang` | Fixed language tabs |
| `SMT/InitialValue`, `SMT/DefaultValue` | Pre-filled and marked as default; counts as filled |
| `SMT/ExampleValue` | Shown as placeholder and hint; never exported unless the user confirms it |
| `SMT/AccessMode` | Read-only fields are shown and locked |
| `FormTitle`, `FormInfo`, `FormUrl`, `FormChoices` | Label override, help text, help link, choice list |
| `EditIdShort`, `EditDescription` | Expose the idShort or description editor for that element. Not read by the backend today |

### 3.5 Identity

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-ID-1 | A fixed header of the Workspace holds AAS identifier, global asset identifier, asset kind (Type, Instance, Batch as far as the metamodel version of the export allows) and submodel identifier | Audit: 68 of 71 exports keep template identifiers | ID-1, ID-2 |
| FE-ID-2 | Identifiers are proposed from a pattern set in Settings (for example a company URL prefix plus serial number) and stay editable | Judgement | ID-3 |
| FE-ID-3 | Where a template holds the product URI (Digital Nameplate `URIOfTheProduct`), the header offers to reuse it as asset identifier | Judgement | — |
| FE-ID-4 | A QR code of the asset identifier can be downloaded from the review screen | Competitor: twinviewer (mobile QR viewer), Mnestix (asset identifier search). The current card shows a decorative pattern, not a code (audit) | — |

### 3.6 Review and export

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-EX-1 | Summary: identity, template and release, counts of filled, empty optional, example and default values | Audit | EXP-5 |
| FE-EX-2 | Conformance check runs on the file that will be downloaded and shows engine name and version; failures are listed with the affected element | Audit (check exists) | EXP-1 |
| FE-EX-3 | Formats: AASX with XML payload (default), AASX with JSON payload, JSON, XML, PDF report | Competitor: BaSyx, twinstudio (JSON, XML, AASX); ADR-001 | EXP-3 |
| FE-EX-4 | "Include" options: concept descriptions (on), supplementary files (on), empty optional elements (off) | Audit | EXP-2, EXP-5 |
| FE-EX-5 | Several submodels of one draft set export as one package under one shell, with a choice of which to include | Competitor: BaSyx (choice of submodels on export) | ID-4 |
| FE-EX-6 | "Send to repository": upload to an AAS repository through the Part 2 API, with the target stored in Settings | ADR-006 | EXP-7 |
| FE-EX-7 | The export panel stays in view; a blocked export states the first three reasons and links to the problems list | Audit: panel not sticky | — |

### 3.7 Import, drafts and history

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-IM-1 | Open an AASX, JSON or XML file by drop or file dialog; the matching template and release are detected by semantic identifier | Competitor: BaSyx, AASX Package Explorer, twinstudio; Demand: users ask AASX Package Explorer to work directly with JSON and XML files | RT-1, RT-2 |
| FE-IM-2 | Import report: matched elements, unknown elements kept, values that fail the template, older release detected with an offer to migrate | Judgement | RT-3 |
| FE-IM-3 | A package with several submodels lists them for selection | Audit | RT-5 |
| FE-DR-1 | Every change is stored locally within 2 s; a visible "saved" state | Audit: nothing saved in the first 30 s | DRF-1 |
| FE-DR-2 | Returning users see their drafts first, with template, release, completion and date; resume, duplicate, rename, delete | Audit: stored drafts are never offered | DRF-2, DRF-3 |
| FE-DR-3 | A draft can be saved to and loaded from a file, so work can move between devices without a server | Judgement; ADR-003 | — |

### 3.8 Compare and migrate

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-MG-1 | Pick two releases of one template; side-by-side tree with added, removed, changed, moved and renamed elements, filterable | Competitor: none found; Mnestix removed its comparison in 2.3.0 | MIG-3, MIG-4 |
| FE-MG-2 | Migrate a draft or an imported file: every element is listed as carried over, needs a decision, or cannot be moved; nothing is dropped silently | Audit: migration fails on major releases | MIG-1 |
| FE-MG-3 | A draft on an outdated release shows a notice with "review changes" | Demand: 93 % of published releases have had a bug-fix release | MIG-2 |

### 3.9 Batch from a spreadsheet

| ID | Specification | Source | Doc 2 |
|---|---|---|---|
| FE-BA-1 | Upload CSV or XLSX; choose sheet, header row, encoding and delimiter with a live preview | Audit: Latin-1 fails | MAP-4 |
| FE-BA-2 | Mapping grid: one row per column with suggested field, confidence, transform (trim, decimal comma, date format, unit, value map) and sample result | Audit: 0 of 7 columns suggested; Competitor: AASX Package Explorer table import, vendor mapping layers | MAP-1 |
| FE-BA-3 | Modes: one row per submodel, or rows grouped by a key into list items | Audit | MAP-2, MAP-3 |
| FE-BA-4 | Dry run validates every row and shows a table of rows with errors before anything is exported | Judgement | — |
| FE-BA-5 | Export all valid rows as one archive with a result report; identifiers come from a column or the pattern of FE-ID-2 | Demand: bulk creation from existing data | MAP-2 |
| FE-BA-6 | Mappings are saved as recipes with the template release; a recipe on a newer release shows what changed | Audit (recipes exist) | — |
| FE-BA-7 | All controls are visible at 1,280 px | Audit: "Run mapping" off-screen | MAP-5 |

### 3.10 Assist tools

| Tool | Specification | Status label |
|---|---|---|
| Semantic lookup | Search dictionaries by name or identifier from any field or free element; result shows definition, unit, data type; "apply" sets the semantic identifier and adds the concept description. The data source and its size are named in the dialog | Sample data until a real index is loaded |
| PDF import | Upload, then a review table: proposed value, the quoted source text highlighted in the PDF, confidence, accept or reject per field. Consent notice before any text leaves the instance; provider and model shown. The PDF library is bundled, not loaded from a CDN | Experimental |
| PCF entry aid | Activity table, factor search with source and year, result; writes to the Carbon Footprint fields only after confirmation. States that the result is not a verified footprint | Experimental |
| Product card | Read-only preview and image export with a real QR code | Preview |

## 4. Competitor capability inventory and decisions

| Capability | Offered by | Decision | Where | Reason |
|---|---|---|---|---|
| Guided wizard for common templates | BaSyx (4 steps, 3 templates), AAS Suite, FA³ST CreAItor demo | Adopt, generically | FE-WS-5 | Our form already covers every template; guided mode gives the same ease without per-template code |
| Element-by-element tree editor | AASX Package Explorer, BaSyx, AAS Manager | Adapt | FE-WS-5, FE-WS-15 | Expert mode and the tree preview serve inspection; free restructuring would break template conformance |
| Form presets from qualifiers | AASX Package Explorer (GenericForms) | Adopt | §3.4 | Same qualifiers, read directly from the template |
| Instance validation against any template with qualifiers | twinfix (vendor claim) | Adopt | §3.4, FE-EX-2 | Core of the positioning; needs the proof of VAL-2 |
| Automatic repair of common defects | twinfix (vendor claim), AASX Package Explorer ("fix issue") | Adapt | FE-IM-2 | Offer listed, reversible fixes on import; no silent changes |
| Import of AASX, JSON, XML | BaSyx, twinstudio, AASX Package Explorer | Adopt | FE-IM-1 | Missing today |
| Export with choice of submodels and formats | BaSyx, twinstudio | Adopt | FE-EX-3, FE-EX-5 | — |
| JSON and XML source view, UML view | BaSyx | Adapt | FE-WS-15 | JSON and tree preview; UML is of use to template authors, not to our users |
| JSON clipboard copy and paste | BaSyx | Adopt | FE-WS-12 | — |
| Dedicated viewers per submodel | BaSyx (about 12), Mnestix (about 8), AASX Package Explorer plugins | Adapt | Product card | One generic card plus overrides for nameplate and carbon footprint; viewing is other tools' job |
| Concept description display and editing | BaSyx, AASX Package Explorer, Mnestix | Adopt display; editing in expert mode | FE-WS-13 | — |
| ECLASS and IEC CDD search or import | AASX Package Explorer, AAS Suite (ECLASS) | Adopt | Semantic lookup | Needs licensed data from the user |
| Table and spreadsheet import | AASX Package Explorer, Papyrus, vexplor-aas (CSV bulk fill), vendor mapping tools | Adopt | §3.9 | Demand is strong; our recipes exist |
| Blueprints with mapping rules for machine data | Mnestix, Neoception, twinstudio (coming soon) | Integrate | — | Different job: system-to-system generation. Our batch mode covers files; live sources belong to those tools |
| AI document-to-submodel | FA³ST CreAItor, AAS Manager (handover documentation), Codewerk, twinstudio (classification; mapper coming soon) | Adopt as Experimental | PDF import | Crowded and unproven; keep the review design, publish measured accuracy first |
| Template editor and template publishing | AASX Package Explorer, twinstudio (coming soon) | Out of scope | — | Non-goal: authoring templates |
| Repository, registry and discovery browsing | BaSyx, Mnestix, twinsphere | Integrate | FE-EX-6 | Non-goal; we upload to them |
| Login, roles, access policies | BaSyx (OAuth2, ABAC), twinsphere | Adapt | §6.5 | Login for a self-hosted team instance; no policy management |
| Dataspace and Catena-X modules | BaSyx (CatenaXplorer), twinsphere (EDC), FA³ST | Out of scope | — | ADR-006; certification and identity are outside a form tool |
| PCF calculation | BaSyx module, AAS Suite, HARTING demonstrator | Adapt | PCF entry aid | Entry help only; no claim of a verified footprint |
| DPP view or gateway | BaSyx demo, AAS Suite gateway, Mnestix | Adapt | Product card; later: derive the DPP value-only JSON | Platform functions are out of scope |
| Mobile-optimised viewing, QR entry | Mnestix, twinviewer | Adapt | §6.3, FE-ID-4 | Responsive for review; QR for identity. Filling large forms on a phone is not a goal |
| Embedded REST or OPC UA server, PLC connectivity | AASX Package Explorer, Siemens, FA³ST | Out of scope | — | Non-goal |
| Desktop application | AASX Package Explorer (Windows only), AAS Manager | Out of scope | — | Demand runs the other way: the most-commented AASX Package Explorer issue asks for macOS and Linux |
| Agent access (MCP) | SAP server, BaSyx prototype, AASX Server | Integrate | — | Works against a repository, which we feed |

## 5. Stakeholder demand and how the interface answers it

| Demand | Evidence | Answer |
|---|---|---|
| Creating submodels without expert knowledge | Named as the adoption barrier in several peer-reviewed papers, 2022 to 2026 | Guided mode, plain labels, specification links (FE-WS-5, FE-WS-6) |
| Trustworthy conformance, also where templates themselves have defects | An audit of 51 official templates found violations in 11; the official engine covers two templates specifically | Conformance in review and as a public table, with upstream defects named (FE-EX-2, `/conformance`) |
| Bulk creation from existing product data | Literature and vendor offerings; large catalogues reported by manufacturers | Batch mode (§3.9) |
| Keeping data current when templates change | 93 % of published releases have a bug-fix release; a 2025 review asks for a transformation engine | Compare and migrate (§3.8) |
| Battery passport before 18 February 2027 | Battery Regulation; IDTA 02035 parts 1 to 7 | Collections and one identity (FE-CAT-4, FE-EX-5) |
| Working on any operating system, with plain JSON or XML | Public issues of the reference desktop editor | Browser application; import and export of all three formats |
| Finding and licensing semantic identifiers | Documented pain point | Semantic lookup with user-supplied dictionaries |
| Files that other tools accept | Export defects reported for two major tools | XML payload, concept descriptions, round-trip check against a repository (document 4) |

No user study of authoring tools was found, and none was run for this document.
Section 9 lists the usability tests that would replace these inferences.

## 6. Non-functional specification

### 6.1 Performance budgets

| Measure | Budget | Baseline (audit) |
|---|---|---|
| First form visible after choosing a template | 1.5 s | 1 to 1.5 s on a local mirror |
| Input latency on the largest template, production build | 50 ms median | 158 ms |
| Initial script, compressed | 150 kB; tools load on demand | 158 kB in one chunk |
| Validation round trip | 500 ms | not measured |

Budgets are checked in CI on a fixed runner; a regression of more than 20 %
fails the job.

### 6.2 Accessibility

Target: WCAG 2.1 level AA. Whether a legal duty applies (European Accessibility
Act, public-sector procurement under EN 301 549) has not been checked and needs
legal review; the target stands regardless.

| ID | Specification | Baseline (audit) |
|---|---|---|
| FE-A11Y-1 | Text contrast at least 4.5:1, interface components 3:1 | Secondary text at 2.15:1 and 3.8:1 |
| FE-A11Y-2 | Every function reachable by keyboard; visible focus; dialogs trap and return focus | Dialogs do not trap focus |
| FE-A11Y-3 | Tabs, trees, lists and comboboxes follow the ARIA authoring patterns, including arrow keys | No arrow-key navigation |
| FE-A11Y-4 | Errors are announced and tied to their field; the problems list is a landmark | — |
| FE-A11Y-5 | Works at 200 % zoom and with reduced motion | not tested |
| FE-A11Y-6 | Automated check on every screen in CI; a manual screen-reader pass per release | not present |

### 6.3 Responsive behaviour

| Width | Layout |
|---|---|
| 1,280 px and above | Three panes |
| 768 to 1,279 px | Form with outline and context panel as drawers |
| Below 768 px | Single column; review, drafts, product card and small templates are supported; batch and compare show a notice to use a wider screen |

### 6.4 Language

Interface in English and German from one message catalogue; template content in
the languages the template provides, with the interface language preferred.
Dates and numbers are shown by locale and stored in their lexical XSD form
(requirement UX-6; audit: interface is English only).

### 6.5 Privacy and security

| ID | Specification | Baseline (audit) |
|---|---|---|
| FE-SEC-1 | No request leaves the instance without the user's action: no external fonts, scripts or analytics | PDF library loaded from a CDN |
| FE-SEC-2 | A content security policy without inline scripts and without third-party origins | not present |
| FE-SEC-3 | Sending document text to a language-model provider requires consent per instance, names provider and model, and can be disabled by the operator | not present |
| FE-SEC-4 | With authentication enabled the interface has login, logout and session expiry handling | No login in the interface |
| FE-SEC-5 | Drafts stay in the browser; the interface says so and offers "delete all local data" | — |
| FE-SEC-6 | Uploaded files are checked for type and size before upload and again on the server | Server check exists |

Whether data-protection law or the EU Cyber Resilience Act places duties on the
project depends on who operates an instance and on the project's legal form.
Neither question was examined here.

### 6.6 Browser support

The two newest versions of Chrome, Edge, Firefox and Safari. The browser tests
run on Chromium, Firefox and WebKit for the core journey.

## 7. Compliance matrix

Each rule has a source, the place where the interface satisfies it, and the
check that proves it. A rule without a check is not claimed.

| Rule | Source | Satisfied by | Check |
|---|---|---|---|
| Exports conform to the AAS metamodel | IDTA specification of the AAS, Part 1 | Form schema and exporter | Conformance job (document 4) |
| Package structure | Part 5, AASX package format | Exporter | Conformance job; repository round trip |
| Template structure and qualifiers | The IDTA submodel template and the guideline for templates | §3.3, §3.4 | Qualifier test matrix (VAL-2) |
| Value formats named in specifications (country, language and currency codes, dates, media types) | The standards each template cites | Field hints and checks | Unit tests per format |
| Concept descriptions preserved | Part 1; IEC 61360 data specification | FE-EX-4 | Identifier and content comparison (EXP-2) |
| Battery passport content | IDTA 02035 parts 1 to 7 | Collections | Worked example in CI (TPL-5) |
| Accessibility | WCAG 2.1 AA | §6.2 | Automated and manual checks |
| No third-party data transfer by default | Design rule of this document | FE-SEC-1 to FE-SEC-3 | Browser test that fails on any external request |
| Licences of bundled data | Each data source's terms | Only openly licensed data is bundled; sample data is labelled | Licence file reviewed per release |

**Not claimed by the interface, and stated to the user where relevant:**
conformance with the Battery Regulation or the ESPR (the duty lies with the
economic operator; the tool supplies submodels), a verified product carbon
footprint, Catena-X certification, and conformance with metamodel versions the
engine cannot check yet.

## 8. Frontend architecture

| Topic | Specification |
|---|---|
| Structure | `app/` shell and routes; `features/<screen>/`; `form/` engine (schema types, controls, validation binding); `ui/` primitives; `tools/<name>/` loaded on demand. No feature imports another feature |
| Routing | A router with the paths of section 3; the draft identifier is in the URL so a reload returns to the same place |
| Form state | The existing form library with schema-derived validation stays. One store per draft; fields subscribe to their own value only |
| Rendering | The existing list virtualisation is extended to the whole form and the outline |
| Schema contract | Types generated from the versioned form schema (API-3); a contract test fails when backend and frontend disagree |
| Renderer registry | Controls are looked up by node type; an optional override by semantic identifier allows a special view for a template without changing the engine |
| Design system | Design tokens for colour, spacing and type in one file, with a dark theme; about 12,400 lines of hand-written CSS are reduced to primitives and tokens |
| Messages | One catalogue per language; no user-visible string in components |
| Errors | One error boundary per route; API errors carry the unified format of API-4 and are shown with the action the user can take |
| Tests | Unit tests for controls; one browser test per journey of section 1 against the running backend; visual snapshots of the field catalogue; accessibility check per screen (TEST-5, TEST-6) |
| Documentation | A field catalogue page renders every control in every state; screenshots in the docs are taken from it (DOC-3) |

Migration from the current code is incremental: first the routes and the shell
around the existing form, then the Workspace panes, then one screen per pull
request. The existing field components are kept and moved, not rewritten.

## 9. Open points

1. **Usability tests.** Five sessions each with a product data engineer and an
   integrator on Digital Nameplate, Technical Data and one battery passport
   part, before and after the Workspace change. Measures: time to a valid
   export, errors, places where help was needed.
2. **Legal review** of accessibility duties, data protection for hosted
   instances and the Cyber Resilience Act.
3. **Competitor trials.** The inventory in section 4 rests on documentation;
   hands-on trials of the BaSyx wizard, twinfix and the AAS Suite designer
   would confirm or correct the rows marked as vendor claims.
4. **Design assets.** This document specifies behaviour, not visuals.
   Wireframes for Workspace, Review and Batch are the next artefact.
5. **Order of work.** Proposed mapping to the roadmap: Workspace outline,
   identity header, review and drafts in M2; collections in M3; batch, compare,
   routes for import and the repository upload in M4.
