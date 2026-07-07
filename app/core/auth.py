import jwt
from jwt import PyJWKClient
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# Cacheado a nivel de módulo: PyJWKClient ya cachea internamente las claves
# públicas (JWKS) de Cognito, así que reutilizamos la misma instancia entre
# peticiones en vez de volver a pedirlas cada vez.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = (
            f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
        )
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


class InvalidTokenError(Exception):
    # Cualquier fallo de verificación (firma, emisor, audiencia, expirado,
    # o el tipo de token equivocado) se normaliza a esta excepción, para que
    # quien la use no tenga que conocer los detalles internos de PyJWT.
    pass


def verify_cognito_token(token: str) -> dict:
    """Verifica firma, emisor, audiencia y expiración de un id_token emitido
    por el User Pool de Cognito configurado. Devuelve los claims si es
    válido, o lanza InvalidTokenError si no."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,
            issuer=(
                f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
                f"{settings.cognito_user_pool_id}"
            ),
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    # Cognito emite tanto id_token como access_token; solo el id_token trae
    # los datos del usuario (email, sub) que necesitamos, así que rechazamos
    # explícitamente si alguien manda el access_token por error.
    if claims.get("token_use") != "id":
        raise InvalidTokenError("Se esperaba un id_token, no un access_token")

    return claims


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Dependencia de FastAPI para proteger endpoints: valida el header
    # Authorization, verifica el token contra Cognito, y resuelve el
    # User local (por cognito_id) al que pertenece — así el resto del
    # endpoint ya trabaja con el negocio correcto sin fiarse de nada que
    # mande el cliente.
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Falta el header Authorization: Bearer <token>",
        )

    token = authorization.removeprefix("Bearer ")
    try:
        claims = verify_cognito_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido: {exc}") from exc

    cognito_id = claims.get("sub")
    result = await db.execute(select(User).where(User.cognito_id == cognito_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="Este usuario de Cognito no está vinculado a ningún negocio todavía.",
        )
    return user