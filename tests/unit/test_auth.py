import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import jwt
import pytest
from fastapi import HTTPException

from app.core.auth import InvalidTokenError, get_current_user, verify_cognito_token


@patch("app.core.auth._get_jwks_client")
@patch("app.core.auth.jwt.decode")
def test_verify_cognito_token_returns_claims_when_valid(mock_decode, mock_get_client):
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_decode.return_value = {"sub": "user-sub-1", "email": "ana@example.com", "token_use": "id"}

    claims = verify_cognito_token("fake.jwt.token")

    assert claims["sub"] == "user-sub-1"
    assert claims["token_use"] == "id"


@patch("app.core.auth._get_jwks_client")
@patch("app.core.auth.jwt.decode")
def test_verify_cognito_token_rejects_access_token(mock_decode, mock_get_client):
    # Un access_token no trae los datos de usuario que necesitamos —
    # solo aceptamos id_token.
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_decode.return_value = {"sub": "user-sub-1", "token_use": "access"}

    with pytest.raises(InvalidTokenError, match="id_token"):
        verify_cognito_token("fake.jwt.token")


@patch("app.core.auth._get_jwks_client")
@patch("app.core.auth.jwt.decode")
def test_verify_cognito_token_raises_on_invalid_signature(mock_decode, mock_get_client):
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_decode.side_effect = jwt.InvalidSignatureError("firma inválida")

    with pytest.raises(InvalidTokenError):
        verify_cognito_token("fake.jwt.token")


@pytest.mark.asyncio
@patch("app.core.auth.verify_cognito_token")
async def test_get_current_user_returns_user_when_token_and_lookup_succeed(mock_verify):
    mock_verify.return_value = {"sub": "cognito-sub-1"}
    mock_user = MagicMock()
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user))

    result = await get_current_user(authorization="Bearer valid.token.here", db=db)

    assert result is mock_user


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_authorization_header():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="", db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_non_bearer_header():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Token abc123", db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@patch("app.core.auth.verify_cognito_token")
async def test_get_current_user_rejects_invalid_token(mock_verify):
    mock_verify.side_effect = InvalidTokenError("expirado")
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Bearer bad.token", db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@patch("app.core.auth.verify_cognito_token")
async def test_get_current_user_rejects_when_no_local_user_linked(mock_verify):
    # El token es válido pero ningún User local tiene ese cognito_id —
    # el usuario existe en Cognito pero no está vinculado a ningún negocio.
    mock_verify.return_value = {"sub": "cognito-sub-huerfano"}
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Bearer valid.token.here", db=db)

    assert exc_info.value.status_code == 403