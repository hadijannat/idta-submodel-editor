# Changelog

All notable changes to IDTA Submodel Editor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Forms show the requirements of the template: enumerations as dropdowns, allowed ranges, patterns, required languages, either/or groups, value formats, definitions and specification notes
- Format standards named in the specification text (ISO 3166-1, ISO 639, ISO 4217, ISO 8601, IEC 61406, RFC 2046 …) are recognised and checked as warnings
- Notes, examples and page references from the specification PDF are added to the fields
- Template list shows IDTA number, newest release and every part of multi-part templates; a release can be selected by full version
- Specification PDF, JSON and AASX of a release can be opened from the editor
- `TEMPLATE_REPO_DIR` serves templates from a local checkout of the template repository for offline installations
- Fields that still hold example values from the template are marked and can be cleared at once

### Fixed
- The oldest release of a template was loaded instead of the newest
- Only the first part of multi-part templates could be opened
- Value types were emitted as Python class names, so date, number and boolean fields were rendered as text inputs
- `SMT/SMT/Cardinality` qualifiers were ignored, making optional elements mandatory
- Lists declared `[0..1]` or `[1]` could hold only one item
- Export failed after adding an item to a list of collections
- `xs:duration` values could not be exported
- Packages declaring internal parts as external relationship targets could not be opened
- List items were named after SDK placeholders that changed on every request
- Exported AASX packages referenced supplementary files with upper-case letters in their names by a lower-cased name, so conformance checks reported a relationship with a non-existing target

## [1.0.0] - 2025-01-27

### Added
- **Universal Template Editing**: Metamodel-driven editor for any IDTA submodel template
- **Core Pipeline**: Fetcher → Parser → Hydrator → Validation architecture
- **Semantic Lookup**: ECLASS/IEC CDD dictionary search with offline indices
- **Smart Mapper**: CSV/XLSX bulk import with semantic-aware auto-mapping
- **PCF Calculator**: Carbon Footprint calculation with IDTA 02023 validation
- **Passport Mode**: Digital Product Passport visualization
- **Magic Import**: PDF-to-AAS extraction with LLM providers (OpenAI/Anthropic/Ollama)
- **Dataspace Connector**: Manufacturing-X / Catena-X integration
- **Tool Registry**: Plugin interface with auto-discovery and lifecycle management
- **Export Formats**: AASX packages, JSON files, PDF reports
- **Docker Compose**: One-command deployment with optional profiles

### Infrastructure
- FastAPI backend with Eclipse BaSyx SDK 2.0.0
- React 18 frontend with TypeScript
- Kubernetes manifests with Kustomize overlays
- Comprehensive test suite with conformance validation

[1.0.0]: https://github.com/hadijannat/idta-submodel-editor/releases/tag/v1.0.0
