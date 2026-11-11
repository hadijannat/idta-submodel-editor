# 1. Product Scope and Feature Status

Status: draft for maintainer review.

## Positioning

> The standards-faithful way to fill, validate and export any IDTA submodel
> template in a browser, with public proof that every published template passes
> through it into a conformant file.

The editor competes on template fidelity, not on breadth. Other tools host,
publish and visualise Asset Administration Shells. This one makes sure the
submodel is right before it gets there.

## Users

| User | Situation | What they need from the tool |
|---|---|---|
| Product data engineer at a component manufacturer | Has to deliver a Digital Nameplate, Technical Data or Handover Documentation submodel and is not an AAS expert | A guided form, clear validation, a file the customer's system accepts |
| Battery passport author | Has to produce the IDTA 02035 parts before 18 February 2027 | Current templates, conformant export, the same identity across all parts |
| AAS integrator or developer | Builds pipelines or products on IDTA templates | A reader that opens every published template, a validator, a form schema and a diff they can call from code |
| Template author or reviewer | Maintains or evaluates IDTA templates | A per-template conformance result and a diff between releases |

## The core job

1. Choose a template at its newest release.
2. Fill it in a form generated from the template, with the definition, format
   and specification page of each field at hand.
3. Validate the entries against the rules the template declares.
4. Export a conformant AASX or JSON file, and a PDF report.
5. Reopen that file later, change it, export again.
6. Carry the data forward when the template gets a new release.

Steps 1 to 4 work today for JSON export on most templates, not all: in the
baseline 70 of 74 templates exported and 63 of those 70 passed the conformance
check. Steps 5 and 6 do not work; see document 2.

## In scope

- Form generation for every published IDTA template without per-template code.
- Validation against template qualifiers and the AAS metamodel.
- AASX, JSON and PDF export, and a built-in conformance check.
- Import of existing submodels for editing.
- Template release diff and migration of filled data.
- Filling many instances of one template from a spreadsheet.
- A library, a command-line interface and an HTTP API for the same functions.
- Upload of a finished submodel to an AAS repository through the Part 2 API.

## Non-goals

| Not this tool | Use instead |
|---|---|
| AAS repository, registry or discovery service | BaSyx, FA³ST, Mnestix |
| Viewing and browsing shells | BaSyx AAS Web UI, Mnestix Browser |
| Authoring new submodel templates | AASX Package Explorer |
| Catena-X participation: connector, identity, certified data exchange | Tractus-X Industry Core Hub, a certified connector |
| Digital Product Passport platform: identifiers, data carriers, hosting, access rights | A DPP platform; the editor supplies the submodels |
| Verified product carbon footprints | An LCA tool with licensed data and verification |
| SAMM aspect model tooling | ESMF SDK |
| Multi-tenant SaaS | Out of scope; the tool is self-hosted for one team |

## Status labels

| Label | Meaning | Rule |
|---|---|---|
| **Stable** | The main action completes on real templates and is covered by a test that runs it without mocks | May be advertised in the README |
| **Experimental** | Real code that works for a narrow case or needs external services | Off by default, labelled in the interface and the docs, no compatibility promise |
| **Sample data** | The feature works, the bundled data is a demonstration set | Labelled wherever the data is shown |
| **Removed** | Taken out of the default build and the docs | May return through a decision record |

## Feature status

"Baseline" is what the audit of 2026-11-10 measured. "Target" is the status this
document proposes. The step to reach it is in document 2 or 5.

| Feature | Baseline | Target | Condition for the target |
|---|---|---|---|
| Template discovery and form | Works on 74 of 74 entries | Stable | Entry-template gaps closed (TPL requirements) |
| Validation | Works; numeric types of the `xs:long` family unchecked | Stable | VAL requirements |
| JSON export | 63 of 70 pass; all 7 failures inherited from upstream | Stable | Identity and clean-output requirements |
| AASX export | 53 of 70 pass before #391; concept descriptions missing | Stable | EXP requirements, re-measured |
| PDF report | Works | Stable | — |
| Conformance check | Works | Stable | — |
| Import and re-edit | Not available in the interface | Stable | RT requirements |
| Drafts | Not functional | Stable | DRF requirements |
| Template diff | Works | Stable | Version picker in the interface |
| Data migration between releases | Patch level only | Stable for patch level, Experimental above | MIG requirements |
| Smart Mapper | Single row in the interface; auto-suggest weak | Stable | MAP requirements |
| Passport Mode | Preview; image export empty | Experimental, named "Preview" | Fix export |
| Semantic Lookup | Six sample entries | Sample data | Index builder repaired |
| PCF calculator | Arithmetic on 21 sample factors | Experimental, named "PCF entry aid" | Export gate narrowed; factors with open licence only |
| Magic Import | Does not run through the API | Experimental | Runs in process without a worker; measured accuracy published |
| Dataspace publishing, Policy Builder | Publish path not connected | Removed; replaced by repository upload | ADR-006 |
| DPP Builder | Placeholder | Removed | Returns only on IDTA 02099-1 and 02035 |
| SAMM converter | Fails on 65 of 66 templates | Removed | ADR-006 |
| Template Knowledge Index | Not buildable | Removed | — |
| OPC UA converter | Direct export works at about 72 % coverage | Experimental, API only | "I4AAS" wording removed |
| PLC4X bridge | Prototype service | Moved to its own repository | ADR-007 |

## Claims policy

A statement in the README, the docs or a tool description is allowed only if a
test or the conformance table backs it. In particular:

- No "compliant", "conformant" or "production" wording for a feature that is not
  Stable.
- No standard is named as implemented (ISO 14067, I4AAS, ESPR, Catena-X) unless
  the feature's output is checked against it.
- Counts ("30+ protocols", "all templates") are generated or tested, never typed.
- Bundled sample data is called sample data wherever it appears.

## Open decisions for the maintainer

1. Accept or change the proposed target of each feature above.
2. Remove dataspace publishing from this repository, or keep it behind a flag as
   an Experimental demonstration.
3. Keep one repository for the product. Several related repositories under the
   same account currently split search visibility.
