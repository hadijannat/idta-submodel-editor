# Changelog

All notable changes to IDTA Submodel Editor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Template selection**: the newest release of a template is loaded, including
  patch releases and newer minor versions. Previously the first version folder
  that contained an AASX won, which was an older file for most templates.
- **Multi-part templates**: every part of a multi-part folder (Digital Battery
  Passport, Safety Instrumented Functions, ...) is listed as its own template,
  and deeply nested templates such as Digital Product Passport Part 1 are found.
- **Template metadata**: IDTA numbers are read from the template file names, so
  they are filled in again for the current repository layout.

- **Export is a submodel instance**: exports had `kind=Template`, kept every
  template qualifier and reused the template's identifier. They now have
  `kind=Instance`, no template-only qualifiers, an identifier of their own and
  `administration.templateId` pointing at the template.

- **Templates are read in full**: Digital Product Passport Part 1 and Digital
  Battery Passport Part 6 could not be opened, and the Bills of Material
  IEC 81346 extension and Capability Description lost elements without notice
  (the former loaded as an empty form). All 66 published templates now open
  with every element.

- **No empty arrays in exports**: the AAS library writes
  `"specificAssetIds": []` for entities, which the JSON schema forbids. Exports
  of templates with entities (Bills of Material, Handover Documentation,
  Purchase Order, ...) now pass the metamodel check.

### Added
- `readWarnings` on the UI schema and a notice above the form when part of a
  template cannot be read or a package holds more submodels than the form shows.
- Validation requires a global asset ID for self-managed entities.

### Changed
- `EXPORT_SUBMODEL_KIND=template` restores the previous export (the template
  with values filled in).
- The editor proposes a `urn:uuid:` identifier for each new instance instead of
  pre-filling the template's identifier.
- Templates are discovered with one repository listing instead of one request
  per directory. The per-directory walk remains as the fallback.
- `GET /api/templates/{name}/versions` lists every release with a display
  `label`; template entries gain `folder`, `part` and `latest_version`.

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
