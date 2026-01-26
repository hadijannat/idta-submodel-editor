"""
FastAPI dependency injection setup.

Provides factory functions for service instances used across routes.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService, PDFExportService
from app.services.parser import ParserService
from app.services.semantic import SemanticService
from app.services.mapper import MapperService
from app.services.tools.registry import ToolRegistry
from app.services.tools.registry import get_tool_registry as _get_tool_registry

# Security scheme for JWT authentication
security = HTTPBearer(auto_error=False)


@lru_cache
def get_fetcher() -> TemplateFetcherService:
    """Get cached fetcher service instance."""
    settings = get_settings()
    return TemplateFetcherService(
        github_token=settings.github_token,
        cache_dir=settings.cache_dir,
        cache_ttl_hours=settings.cache_ttl_hours,
    )


@lru_cache
def get_parser() -> ParserService:
    """Get cached parser service instance."""
    return ParserService()


@lru_cache
def get_hydrator() -> HydratorService:
    """Get cached hydrator service instance."""
    return HydratorService()


@lru_cache
def get_semantic_service() -> SemanticService:
    """Get cached semantic service instance."""
    return SemanticService()


@lru_cache
def get_mapper_service() -> MapperService:
    """Get cached mapper service instance."""
    return MapperService(
        fetcher=get_fetcher(),
        parser=get_parser(),
        hydrator=get_hydrator(),
        pdf_service=get_pdf_service(),
        semantic_service=get_semantic_service(),
    )

def get_pdf_service() -> PDFExportService | None:
    """
    Get PDF export service if enabled and dependencies available.

    Returns None if PDF export is disabled or dependencies are missing.
    """
    settings = get_settings()
    if not settings.pdf_enabled:
        return None

    try:
        return PDFExportService()
    except ImportError:
        return None


def get_tool_registry() -> ToolRegistry:
    """
    Get the tool registry instance.

    The registry is initialized during app startup and provides access
    to all registered tools and their capabilities.

    Returns:
        The global ToolRegistry instance

    Raises:
        RuntimeError: If the registry hasn't been initialized
    """
    return _get_tool_registry()


class OIDCValidator:
    """
    OIDC token validator for JWT authentication.

    Validates tokens against the configured OIDC provider.
    """

    def __init__(self, settings: Settings):
        self.issuer = settings.oidc_issuer_url
        self.audience = settings.oidc_audience
        self._jwks_cache = None

    def _select_jwk(self, jwks: dict, kid: str | None) -> dict | None:
        """Select a JWK from a JWKS payload by key id."""
        if not isinstance(jwks, dict):
            return None
        keys = jwks.get("keys") or []
        if not isinstance(keys, list) or not keys:
            return None
        if kid:
            for key in keys:
                if isinstance(key, dict) and key.get("kid") == kid:
                    return key
            return None
        if len(keys) == 1 and isinstance(keys[0], dict):
            return keys[0]
        return None

    async def _get_jwks(self) -> dict:
        """Fetch and cache JWKS from the OIDC provider."""
        if self._jwks_cache:
            return self._jwks_cache

        import httpx

        async with httpx.AsyncClient() as client:
            # Get OpenID configuration
            well_known_url = f"{self.issuer}/.well-known/openid-configuration"
            config_response = await client.get(well_known_url, timeout=10.0)
            config_response.raise_for_status()
            config = config_response.json()

            # Get JWKS
            jwks_response = await client.get(config["jwks_uri"], timeout=10.0)
            jwks_response.raise_for_status()
            self._jwks_cache = jwks_response.json()

        return self._jwks_cache

    async def validate_token(
        self,
        credentials: HTTPAuthorizationCredentials | None,
    ) -> dict:
        """
        Validate a JWT token.

        Args:
            credentials: HTTP authorization credentials

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or missing
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            import jwt
            from jwt.exceptions import InvalidTokenError
            from jwt.algorithms import RSAAlgorithm

            token = credentials.credentials
            jwks = await self._get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid") if isinstance(unverified_header, dict) else None
            jwk = self._select_jwk(jwks, kid)
            if jwk is None:
                raise InvalidTokenError("Unable to find matching JWK for token")
            signing_key = RSAAlgorithm.from_jwk(jwk)

            # Decode and validate the token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
            return payload

        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )


@lru_cache
def get_oidc_validator() -> OIDCValidator | None:
    """Get OIDC validator if authentication is enabled."""
    settings = get_settings()
    if not settings.oidc_enabled:
        return None
    return OIDCValidator(settings)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(security)
    ] = None,
    validator: Annotated[OIDCValidator | None, Depends(get_oidc_validator)] = None,
) -> dict | None:
    """
    Get the current authenticated user.

    Returns None if authentication is disabled.
    """
    if validator is None:
        return None  # Auth disabled

    return await validator.validate_token(credentials)


class PermissionChecker:
    """
    Permission checker for role-based access control.

    Use as a dependency to require specific permissions on endpoints.
    """

    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions

    async def __call__(
        self,
        user: Annotated[dict | None, Depends(get_current_user)],
    ) -> bool:
        """Check if the user has required permissions."""
        if user is None:
            # Auth disabled, allow all
            return True

        user_permissions = user.get("permissions", [])
        user_roles = user.get("roles", [])

        for perm in self.required_permissions:
            # Check direct permissions
            if perm in user_permissions:
                continue

            # Check role-based permissions
            if any(f"role:{perm}" in role for role in user_roles):
                continue

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{perm}' required",
            )

        return True


# Common permission dependencies
require_read = PermissionChecker(["submodel:read"])
require_write = PermissionChecker(["submodel:write"])
require_admin = PermissionChecker(["admin"])
