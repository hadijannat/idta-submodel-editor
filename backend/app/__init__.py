# IDTA Submodel Editor Backend
"""
Universal IDTA Submodel Template Editor Backend

This package implements a metamodel-driven approach for editing any IDTA submodel
template without code modifications. It uses Eclipse BaSyx Python SDK 2.0.0 for
AAS Metamodel v3.0.1 compliance.

Architecture:
- Fetcher Service: GitHub API integration with caching
- Parser Service: AAS-to-UI schema transformation
- Hydrator Service: UI-to-AAS reconstitution preserving metadata
"""

__version__ = "1.0.0"
