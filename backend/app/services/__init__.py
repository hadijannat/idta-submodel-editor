"""
Backend services for the IDTA Submodel Editor.

Three-pipeline architecture:
- Fetcher: Template discovery and GitHub caching
- Parser: AAS-to-UI schema transformation
- Hydrator: UI-to-AAS reconstitution
"""

from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService

__all__ = ["TemplateFetcherService", "ParserService", "HydratorService"]
