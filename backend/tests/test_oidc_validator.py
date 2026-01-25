import pytest

from app.dependencies import OIDCValidator


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.mark.asyncio
async def test_oidc_validator_selects_matching_jwk():
    validator = OIDCValidator(type("S", (), {"oidc_issuer_url": "", "oidc_audience": ""})())
    jwks = {
        "keys": [
            {"kid": "a", "kty": "RSA", "n": "abc", "e": "AQAB"},
            {"kid": "b", "kty": "RSA", "n": "def", "e": "AQAB"},
        ]
    }

    assert validator._select_jwk(jwks, "b")["kid"] == "b"
    assert validator._select_jwk(jwks, "missing") is None
    assert validator._select_jwk(jwks, None) is None

    single = {"keys": [{"kid": "only", "kty": "RSA", "n": "abc", "e": "AQAB"}]}
    assert validator._select_jwk(single, None)["kid"] == "only"
