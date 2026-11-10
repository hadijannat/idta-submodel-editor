# Template Requirements and Form Generation

When a template is selected, the editor generates its form from three sources
that IDTA publishes for every template release:

| Source | What the editor takes from it |
|---|---|
| **AASX package** | Structure of the submodel, value types, qualifiers, ConceptDescriptions |
| **JSON serialization** | Same content as the package; offered for download next to it |
| **Specification PDF** | Notes, constraints written in prose, example values and the page where each element is specified |

The package is the source of truth for structure and for everything that is
enforced. The PDF adds guidance for the person filling in the form.

## Which release is used

The upstream repository keeps templates as
`<status>/<Template>/<major>/<minor>[/<patch>]/…`, and a release folder can
contain newer patch folders next to its own files. The editor reads the whole
repository layout once and resolves, for every template:

- the **newest release** (for example `3.0.3`, not the `3.0` it patches),
- the template package of that release, preferring the template over filled
  samples and over the variant for AAS metamodel V3.1,
- the JSON and the specification PDF that belong to it. Patch releases often
  ship no PDF; the PDF of the same `major.minor` line is used then.

Multi-part templates such as *Digital Battery Passport* are listed with one
entry per part. Their names join template and part with `~`, for example
`Digital Battery Passport~7_Circularity`.

A specific release can be requested with `version=3.0.2` (or `3/0/2`). A single
number (`version=3`) selects the newest release of that major line.

The *Configure Instance* step shows the release in use, the template file and
a link to the specification PDF, and warns when a newer release exists.

## Requirements read from the template package

### Qualifiers

Published templates spell qualifier types inconsistently (`SMT/Cardinality`,
`Cardinality`, `Multiplicity`, `SMT/SMT/Cardinality`, `SMT/AllowedValue1`).
Types are matched by family.

| Qualifier | Effect in the form | Validation |
|---|---|---|
| `SMT/Cardinality`, `Cardinality`, `Multiplicity` | Required marker, optional hint | Error when a required value is missing |
| `SMT/AllowedValue` (enumeration such as `pass;fail`) | Dropdown | Error when the value is not listed |
| `SMT/AllowedValue` (regular expression) | Pattern shown as constraint | Error when the value does not match |
| `SMT/AllowedRange` | `min`/`max` on the input | Error when out of range |
| `SMT/RequiredLang` | Required languages listed first | Error when a required translation is missing |
| `SMT/EitherOr` | Constraint shown on each alternative | Error when none of the alternatives is provided |
| `SMT/ExampleValue`, `ExampleValue` | Placeholder and example line | Warning while the example is still in the field |
| `SMT/DefaultValue`, `SMT/InitialValue` | Shown as constraint | — |
| `SMT/AccessMode` (read only) | Read-only input | — |
| `FormChoices`, `enumeration` | Suggestions (free text stays possible) | Warning when the value is not listed |
| `FormInfo`, `Note`, `Comment`, `Constraint` | Shown as notes | — |
| `unit` | Unit next to the label | — |

### ConceptDescriptions (IEC 61360)

| Attribute | Effect |
|---|---|
| Preferred name | Field label when it differs from the idShort |
| Definition | Shown as the description of the field; the element's own description (which carries the specification notes in IDTA templates) is shown as notes |
| Value list | Suggestions with their value IDs; warning when the value is not listed |
| Value format (`X..10`, `NR1..7`) | Shown as constraint; warning when a text is longer than allowed |
| Unit | Unit next to the label |

### Value types

XSD value types select the input control (date picker, number input,
checkbox) and are checked on validation, including the bounds of the integer
types and the lexical form of `xs:duration` and `xs:gYearMonth`.

### Lists

The cardinality of a SubmodelElementList states how often the list itself
occurs, not how many items it holds. A list declared `[0..1]` therefore
accepts any number of items unless its item declares a bound.

## Format standards recognised in the specification text

Many requirements are stated only in prose, in the description of an element
and in the notes of the PDF: *"Country codes defined accord. to DIN EN ISO
3166-1 alpha-2 codes"*. The editor recognises these statements and attaches a
format hint to the field.

| Recognised from | Hint |
|---|---|
| "ISO 3166", "country code" | ISO 3166-1 alpha-2 (or alpha-3) country code, with the country list as suggestions |
| "ISO 639", "language code" | ISO 639 language code |
| "ISO 4217", "three-letter ISO currency code" | ISO 4217 currency code |
| "ISO 8601", "YYYY-MM-DD", "P[n]Y[n]M…" | ISO 8601 date, date-time, duration or time zone |
| "IEC 61406", "DIN SPEC 91406" | Identification link (http/https URL) |
| "RFC 2046", "MIME type" | Media type |
| Value type `xs:anyURI`, names such as `…Uri`, `…Url` | URI / URL |
| Names such as `EmailAddress`, `TelephoneNumber`, `GTIN`, `YearOf…`, `…UUID` | E-mail, phone number, GTIN (with check digit), year, UUID |

Every standard a text refers to (ISO, IEC, DIN, EN, RFC, VDI …) is also shown
as a chip next to the field.

Format hints are **advisory**: a value that does not follow the recognised
format produces a warning, never a blocking error, because the wording of a
specification is not a formal constraint.

Enumerations written as `IRDI (label), IRDI (label)` in a description — the
way IDTA specifications list ECLASS value lists — are offered as suggestions,
and the label of the selected identifier is shown below the input.

## Requirements read from the specification PDF

IDTA specifications describe every element in tables with the columns
*idShort*, *semanticId / description*, *value type / example* and
*cardinality*. The editor extracts these rows and matches them to the
elements of the form. For each matched field it adds:

- the notes of the specification, where the package carries none,
- an example value, where the package carries none,
- a link that opens the PDF on the page of the element,
- a remark when the cardinality printed in the PDF differs from the one
  declared in the package.

Extraction runs in the background the first time a release is opened (a few
seconds) and is cached. It is guidance only: validation is driven by the
package, and a missing or unreadable PDF simply yields no notes. Older,
Word-generated specifications are read less completely than the current
AsciiDoc-generated ones.

## Example values

Values in a template (`"Muster AG"`, `DE`, `2022-01-01`) illustrate the
expected format; they are not data about the user's product. The editor
therefore:

- marks every field that still holds the template's example,
- shows how many fields are affected and offers **Clear example values**,
- reports unchanged examples as warnings on validation,
- starts new list items empty instead of copying the examples of the first
  item.

Files uploaded for editing (kind *Instance*) are not treated this way.

## Offline and air-gapped installations

Set `TEMPLATE_REPO_DIR` to a checkout of
[admin-shell-io/submodel-templates](https://github.com/admin-shell-io/submodel-templates)
to serve templates, JSON and PDFs from disk without contacting GitHub:

```bash
git clone --depth 1 https://github.com/admin-shell-io/submodel-templates.git /srv/submodel-templates
TEMPLATE_REPO_DIR=/srv/submodel-templates uvicorn app.main:app
```

With Docker Compose the checkout has to be mounted into the backend
container and the setting has to name the path inside the container. Add a
`docker-compose.override.yaml` next to `docker-compose.yaml`:

```yaml
services:
  backend:
    environment:
      - TEMPLATE_REPO_DIR=/srv/submodel-templates
    volumes:
      - /path/on/host/submodel-templates:/srv/submodel-templates:ro
```

A directory without a `published` or `deprecated` folder is ignored with a
warning in the log, and templates are loaded from GitHub instead.

Without a mirror the repository layout is read with a single GitHub API
request and files are downloaded from `raw.githubusercontent.com`, which does
not count against the API rate limit. The layout is saved to disk and reused
when GitHub cannot be reached.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/templates` | Templates and template parts with `latest_version`, `versions`, `group`, `part`, `has_specification` |
| `GET /api/templates/{name}/versions` | Releases of a template, newest first |
| `GET /api/templates/{name}/documents/{specification\|json\|aasx}` | Download a document of a release |
| `GET /api/editor/templates/{name}/schema` | UI schema with requirements per element and the resolved release in `template` |
| `GET /api/editor/templates/{name}/specification-notes` | Requirements read from the PDF, keyed by idShort path |

## Known limits

- Elements other than lists that a template allows several times
  (`[0..*]` / `[1..*]` on a collection or property) are rendered once. Adding
  further occurrences in the form is not supported yet.
- Packages that contain several submodels are edited one submodel at a time;
  the submodel referenced by the shell is used.
- `SMT/AllowedIdShort` and `EditIdShort` are read and exposed in the schema
  but idShorts cannot be edited in the form.
