"""
Tool registry and plugin interface for the IDTA Submodel Editor.

This package provides a unified framework for tool registration, lifecycle
management, and dynamic loading. Tools integrate with the core pipeline
(fetcher → parser → hydrator → validation) through standardized interfaces.
"""

from app.services.tools.base import BaseTool, ToolMetadata
from app.services.tools.context import ToolContext
from app.services.tools.registry import ToolRegistry

__all__ = [
    "BaseTool",
    "ToolMetadata",
    "ToolContext",
    "ToolRegistry",
]
