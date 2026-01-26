"""
FastAPI routers for the IDTA Submodel Editor.
"""

from app.routers import editor, export, templates, semantic, mapper, pcf, tools

__all__ = ["templates", "editor", "export", "semantic", "mapper", "pcf", "tools"]
