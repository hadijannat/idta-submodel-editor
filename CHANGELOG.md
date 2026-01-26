# Changelog

All notable changes to IDTA Submodel Editor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
