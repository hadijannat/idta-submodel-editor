# Magic Import Documentation Assets

This directory contains screenshots and GIFs for the Magic Import feature documentation.

## Required Assets

The following assets are referenced in the main README.md:

| File | Description | Status |
|------|-------------|--------|
| `magic-import-live-demo.gif` | Animated demo showing full extraction workflow | TODO |
| `magic-import-upload.png` | Drag-drop zone for PDF upload and template selection | ✅ Done |
| `magic-import-processing.png` | Progress bar with status message and PDF info (pages, words, OCR) | TODO (extraction too fast to capture) |
| `magic-import-review.png` | Split view: PDF viewer + extraction table with filter tabs | ✅ Done (Danfoss APP 11-13 datasheet) |
| `magic-import-highlight.png` | Click field → PDF evidence highlighted with quote display | ✅ Done |
| `magic-import-edit-value.png` | Inline editing mode with text input | ✅ Done |
| `magic-import-apply.png` | "Apply X Fields to Form" button enabled, ready to apply | ✅ Done |

## Capture Guidelines

When creating these assets:

1. **Live Demo GIF** - Show the full flow:
   - Upload a sample PDF datasheet
   - Select a template (e.g., Digital Nameplate)
   - Show job progress states
   - Review extracted fields in the table
   - Click a field to highlight source in PDF
   - Apply values to the form

2. **Upload Screenshot** - Capture:
   - File upload zone
   - Template selector dropdown
   - "Start Extraction" button

3. **Review Screenshot** - Capture:
   - Extraction review table
   - Confidence badges (green/yellow/red)
   - Edit buttons on low-confidence fields
   - "Apply to Form" button

4. **Highlight Screenshot** - Capture:
   - PDF viewer with highlighted bounding box
   - Corresponding field selected in review table
   - Evidence quote visible

## Tools

Recommended tools for capturing:
- **GIF**: [LICEcap](https://www.cockos.com/licecap/) or [Kap](https://getkap.co/)
- **Screenshots**: macOS Screenshot (Cmd+Shift+4) or browser DevTools
- **Annotation**: [Skitch](https://evernote.com/products/skitch) or Preview.app
