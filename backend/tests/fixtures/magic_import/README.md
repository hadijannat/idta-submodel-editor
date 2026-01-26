# Magic Import Test Fixtures

This directory contains golden fixtures for regression testing the Magic Import PDF extraction pipeline.

## Directory Structure

```
magic_import/
├── README.md                      # This file
├── nameplate_text.pdf             # Clean text PDF (add manually)
├── nameplate_text_expected.json   # Expected extractions
├── techspec_tables.pdf            # Table-heavy document (add manually)
├── techspec_tables_expected.json  # Expected extractions
├── scanned_ocr.pdf                # Scanned document (add manually)
├── scanned_ocr_expected.json      # Expected extractions
└── multicolumn.pdf                # Complex layout (add manually)
```

## Expected JSON Schema

Each `*_expected.json` file defines:

```json
{
  "description": "Human-readable description",
  "template_name": "IDTA template to use",
  "min_confidence_threshold": 0.75,
  "expected_extractions": [
    {
      "path": "idShortPath of field",
      "expected_value": "Expected extracted value",
      "expected_unit": "Optional expected unit",
      "expected_confidence_min": 0.80,
      "expected_evidence": {
        "page": 0,
        "quote_contains": "Text that should appear in evidence"
      }
    }
  ],
  "expected_classification": {
    "doc_type": "text|scanned|mixed",
    "has_tables": false,
    "quality_score_min": 0.7
  }
}
```

## Adding New Fixtures

1. Add the PDF file to this directory
2. Create a corresponding `*_expected.json` with expected extractions
3. Run the extraction manually to verify expectations
4. Update confidence thresholds based on actual results

## Regression Testing

Tests in `test_confidence_regression.py` use these fixtures to:
- Verify extractions match expected values
- Ensure confidence scores don't drop more than 10%
- Detect if evidence localization breaks
- Track extraction quality over time

## Notes

- PDF files are not committed to git (add to .gitignore if needed)
- Expected JSONs define the "ground truth" for testing
- Confidence thresholds should be set conservatively
- Update fixtures when intentional changes are made
