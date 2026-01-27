# Template Operations

Manage template versions, compare schemas, and migrate data when templates change.

## Overview

Template Operations provides tools for:

- **Version Comparison** — Structural diff between template versions with breaking change detection
- **Recipe Migration** — Auto-migrate Smart Mapper recipes when templates change
- **Form Data Migration** — Migrate in-progress form data to new template versions
- **Local Template Import** — Import custom AASX files as local templates

---

## Version Comparison

Compare two template versions to identify structural differences:

```
Template A (v2.0.0)          Template B (v2.1.0)
├── ManufacturerName         ├── ManufacturerName
├── ProductDesignation       ├── ProductDesignation
└── SerialNumber             ├── SerialNumber
                             └── BatchNumber (NEW)
```

### Diff Categories

| Category | Description |
|----------|-------------|
| `added` | New elements in the target version |
| `removed` | Elements no longer present |
| `modified` | Elements with changed type, cardinality, or semanticId |
| `renamed` | Elements with same semanticId but different path |

### API Usage

```bash
curl -X POST /api/template-ops/diff \
  -H "Content-Type: application/json" \
  -d '{
    "source_template": "DigitalNameplate",
    "source_version": "2.0.0",
    "target_template": "DigitalNameplate",
    "target_version": "2.1.0"
  }'
```

---

## Three-Phase Migration Algorithm

When migrating data between template versions, the system uses a three-phase matching algorithm:

### Phase 1: Exact Path Match

Elements with identical JSON paths (e.g., `Nameplate.ManufacturerName`) are matched directly.

### Phase 2: Semantic ID Match

Elements with the same `semanticId` are matched regardless of path changes. This handles renamed or reorganized elements.

### Phase 3: Fuzzy Matching

For remaining unmatched elements, the system applies:

- Path similarity (Levenshtein distance)
- Label/idShort similarity
- Type compatibility scoring

Each fuzzy match includes a confidence score (0.0-1.0).

---

## Recipe Migration

When a Smart Mapper recipe references a template that has been updated, migrate the recipe to the new schema:

```bash
curl -X POST /api/template-ops/migrate/recipe \
  -H "Content-Type: application/json" \
  -d '{
    "recipe_name": "my-csv-mapping",
    "target_template": "DigitalNameplate",
    "target_version": "2.1.0"
  }'
```

### Migration Report

```json
{
  "migrated_mappings": 15,
  "exact_matches": 12,
  "semantic_matches": 2,
  "fuzzy_matches": 1,
  "unmapped": 0,
  "warnings": [
    {
      "original_path": "Nameplate.OldField",
      "matched_path": "Nameplate.NewField",
      "confidence": 0.85,
      "reason": "fuzzy_match"
    }
  ]
}
```

---

## Form Data Migration

Migrate in-progress form data when switching template versions:

```bash
curl -X POST /api/template-ops/migrate/form-data \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": { ... },
    "source_template": "DigitalNameplate",
    "source_version": "2.0.0",
    "target_template": "DigitalNameplate",
    "target_version": "2.1.0"
  }'
```

### Response

```json
{
  "migrated_data": { ... },
  "migration_report": {
    "total_fields": 20,
    "migrated": 18,
    "dropped": 1,
    "new_required": 1
  },
  "warnings": [...]
}
```

---

## Version Mismatch Detection

Check if saved form data or recipes are compatible with the current template version:

```bash
curl -X POST /api/template-ops/check-mismatch \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "DigitalNameplate",
    "schema_digest": "abc123..."
  }'
```

---

## Local Template Import

Import custom AASX templates for local use:

```bash
curl -X POST /api/template-ops/import \
  -F "file=@custom-template.aasx" \
  -F "name=MyCustomTemplate"
```

Imported templates are stored in `LOCAL_TEMPLATES_DIR` (default: `./templates/local`).

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_TEMPLATES_ENABLED` | Enable local templates | true |
| `LOCAL_TEMPLATES_DIR` | Directory for local AASX files | ./templates/local |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/template-ops/diff` | Compare two template versions |
| POST | `/api/template-ops/import` | Import AASX as local template |
| POST | `/api/template-ops/migrate/recipe` | Migrate Smart Mapper recipe |
| POST | `/api/template-ops/migrate/form-data` | Migrate form data |
| POST | `/api/template-ops/check-mismatch` | Check version mismatch |
| POST | `/api/template-ops/digest` | Compute schema digest |

---

## See Also

- [Smart Mapper](smart-mapper.md) — Uses recipes that can be migrated
- [Configuration Reference](../reference/configuration.md)
