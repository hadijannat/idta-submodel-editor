"""Semantic provider error types."""


class SemanticProviderError(RuntimeError):
    """Base error for semantic providers."""


class SemanticRateLimitError(SemanticProviderError):
    """Raised when a provider hits a rate limit."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after
