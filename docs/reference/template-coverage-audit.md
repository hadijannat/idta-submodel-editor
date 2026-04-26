# Template Coverage Audit

The IDTA template coverage audit is a manual verification script for the full
template editing pipeline. It lists published and deprecated IDTA templates,
fetches each AASX, parses the UI schema, generates frontend-shaped form data,
validates defaults and required synthetic data, hydrates back to AASX and JSON,
reparses the hydrated AASX, and reports coverage/preservation metrics.

Run it from the repository root:

```bash
PYTHONPATH=backend python backend/scripts/audit_template_coverage.py \
  --statuses published deprecated \
  --output tmp/template-audit/idta-template-coverage.json \
  --summary tmp/template-audit/idta-template-coverage.md
```

Useful smoke-run controls:

```bash
PYTHONPATH=backend python backend/scripts/audit_template_coverage.py \
  --statuses published deprecated \
  --max-templates 3 \
  --concurrency 4 \
  --no-fail \
  --output tmp/template-audit/smoke.json \
  --summary tmp/template-audit/smoke.md
```

## Scope And Outputs

- Published and deprecated templates are included by default.
- Local templates are excluded so the audit does not depend on workstation
  state.
- Reports and the audit-specific template cache are constrained to
  `tmp/template-audit/`, which is gitignored.
- `GITHUB_TOKEN` can be provided through existing backend settings to reduce
  GitHub rate-limit pressure.

Generated files:

- `tmp/template-audit/idta-template-coverage.json`: full machine-readable
  report.
- `tmp/template-audit/idta-template-coverage.md`: human-readable summary.
- `tmp/template-audit/cache/templates/`: audit-only AASX cache.

## Exit Codes

- `0`: audit completed without failing policy checks, or `--no-fail` was used.
- `1`: at least one policy failure occurred.
- `2`: command-line output paths were outside `tmp/template-audit/`.

The default policy continues through all selected templates and exits nonzero
when a fetched template cannot parse, hydrate, or reparse; when an unknown
`modelType` is found; or when required common/type-specific UI metadata is not
emitted.

## Reported Metrics

- Pipeline rates: listed, fetched, parsed, validated, hydrated AASX, hydrated
  JSON, and reparsed.
- Element coverage: recursive schema node count, counts by `modelType`,
  editable renderer coverage, known read-only coverage, and unknown model
  types.
- Metadata coverage: emitted and non-empty rates for common and type-specific
  UI keys.
- Contract coverage: default form generation, backend validation, required
  synthetic form generation, and required validation.
- Preservation checks: model type counts, semantic IDs, qualifiers,
  supplementary files, and nested structure after hydrate/reparse.

## Operational Notes

This audit is intentionally not CI-gated because it uses the live
`admin-shell-io/submodel-templates` repository and can be slow or rate-limited.
Use `--template`, `--max-templates`, and `--no-fail` for local diagnosis, then
run the full default command before relying on coverage results for a release.
