"""
Schemas for AAS export conformance checks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConformanceIssue(BaseModel):
    """Normalized conformance issue."""

    level: str = Field(description="Issue level (error/warning/info)")
    message: str = Field(description="Issue message")


class ConformanceCheckResponse(BaseModel):
    """Response for conformance checks."""

    passed: bool = Field(description="True if the artifact passed conformance checks")
    errors: list[ConformanceIssue] = Field(default_factory=list)
    warnings: list[ConformanceIssue] = Field(default_factory=list)
    engine_version: str | None = Field(default=None, description="aas-test-engines version")
    duration_ms: int = Field(description="Execution time in milliseconds")
    format: str = Field(description="Input format validated (aasx/json)")
