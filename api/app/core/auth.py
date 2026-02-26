from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Header, HTTPException

from app.core.config import settings


@dataclass
class CurrentUser:
    user_id: str
    role: str = "user"
    email: str | None = None


def _decode_token(token: str) -> dict[str, Any]:
    if settings.jwt_secret:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    if settings.jwt_jwks_url:
        jwk_client = jwt.PyJWKClient(settings.jwt_jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[settings.jwt_algorithm],
            audience=(settings.jwt_audience or None),
            issuer=(settings.jwt_issuer or None),
            options={"verify_aud": bool(settings.jwt_audience)},
        )
    raise HTTPException(status_code=401, detail="JWT verification is not configured")


def get_current_user(
    authorization: str = Header(default="", alias="Authorization"),
    x_user_id: str = Header(default="", alias="X-User-Id"),
    x_user_role: str = Header(default="", alias="X-User-Role"),
) -> CurrentUser:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        try:
            payload = _decode_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
        user_id = str(payload.get("sub") or payload.get("user_id") or "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing subject")
        role = str(payload.get("role") or settings.default_user_role)
        email = payload.get("email")
        return CurrentUser(user_id=user_id, role=role, email=(str(email) if email else None))

    if settings.allow_dev_auth and x_user_id:
        role = x_user_role or settings.default_user_role
        return CurrentUser(user_id=x_user_id, role=role)

    raise HTTPException(status_code=401, detail="Authentication required")


def require_admin(user: CurrentUser) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
