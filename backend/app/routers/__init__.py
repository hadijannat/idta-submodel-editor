"""
FastAPI routers for the IDTA Submodel Editor.
"""

from app.routers import editor, export, templates, semantic

__all__ = ["templates", "editor", "export", "semantic"]
