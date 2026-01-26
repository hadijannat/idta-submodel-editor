"""
Template Operations Tool.

Provides template import, diff, migration planning, and validation
diagnostics for the tool registry.
"""

from typing import ClassVar

from app.services.tools.base import BaseTool, ToolMetadata


class TemplateOpsTool(BaseTool):
    """
    Template Operations tool for the IDTA Submodel Editor.

    Provides:
    - Import existing AASX/JSON as local templates
    - Diff template versions to detect changes
    - Generate migration plans with auto-mappings
    - Comprehensive validation diagnostics
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="template-ops",
        name="Template Operations",
        description="Import, diff, migrate, and validate submodel templates",
        version="1.0.0",
        category="core",
        wizard_step=None,  # Utility tool, not a wizard step
        feature_flag=None,
        requires_auth=False,
        dependencies=[],
    )

    async def initialize(self) -> None:
        """Initialize the template operations tool."""
        # No special initialization needed
        pass

    async def shutdown(self) -> None:
        """Shutdown the template operations tool."""
        pass

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if template operations are available."""
        try:
            # Verify fetcher and parser are available via context
            fetcher = self.context.fetcher
            parser = self.context.parser
            if fetcher and parser:
                return True, None
            return False, "Fetcher or parser service not available"
        except Exception as e:
            return False, str(e)

    def get_router(self):
        """Return the template ops router."""
        from app.routers.template_ops import router
        return router

    def get_capabilities(self) -> dict:
        """Return capabilities provided by this tool."""
        return {
            "import": {
                "description": "Import AASX/JSON files as local templates",
                "formats": ["aasx", "json"],
            },
            "diff": {
                "description": "Compare two template versions",
                "detects": ["added", "removed", "modified", "cardinality_changes", "semantic_changes"],
            },
            "migrate": {
                "description": "Generate migration plans between template versions",
                "strategies": ["exact_match", "semantic_match", "fuzzy_match"],
            },
            "validate": {
                "description": "Run comprehensive validation diagnostics",
                "checks": ["semantic_ids", "cardinality", "value_types", "conformance"],
            },
        }


# Mark for auto-discovery
tool_class = TemplateOpsTool
