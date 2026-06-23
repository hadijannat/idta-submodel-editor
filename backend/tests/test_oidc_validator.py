from datetime import datetime, timedelta, timezone
import json

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.dependencies import OIDCValidator


def _settings():
    return type(
        "S",
        (),
        {
            "oidc_issuer_url": "https://issuer.example.test",
            "oidc_audience": "idta-editor",
        },
    )()


def _rs256_token_and_jwk(*, audience: str = "idta-editor") -> tuple[str, dict]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-key"
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-123",
            "aud": audience,
            "iss": "https://issuer.example.test",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    return token, jwk


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


@pytest.mark.asyncio
async def test_oidc_validator_accepts_rs256_token(monkeypatch):
    validator = OIDCValidator(_settings())
    token, jwk = _rs256_token_and_jwk()

    async def fake_jwks():
        return {"keys": [jwk]}

    monkeypatch.setattr(validator, "_get_jwks", fake_jwks)

    payload = await validator.validate_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert payload["sub"] == "user-123"


@pytest.mark.asyncio
async def test_oidc_validator_rejects_rs256_token_with_wrong_audience(monkeypatch):
    validator = OIDCValidator(_settings())
    token, jwk = _rs256_token_and_jwk(audience="other-client")

    async def fake_jwks():
        return {"keys": [jwk]}

    monkeypatch.setattr(validator, "_get_jwks", fake_jwks)

    with pytest.raises(HTTPException) as exc_info:
        await validator.validate_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert exc_info.value.status_code == 401
