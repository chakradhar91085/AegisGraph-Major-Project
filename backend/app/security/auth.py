"""
AegisGraph — authentication.

The frontend signs users in with Clerk and sends the Clerk session token as
`Authorization: Bearer <token>`. We verify its signature against Clerk's
public keys, then look the user's role up server-side. A client can never
choose its own role or identity.
"""
import asyncio
import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

from app.core.config import settings
from app.security.policy import ROLE_POLICIES

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


@dataclass(frozen=True)
class User:
    user_id: str
    role: str
    # Present only if the Clerk session token is customized to include it.
    email: str | None = None


def _signing_key(token: str):
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{settings.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json")
    return _jwks_client.get_signing_key_from_jwt(token).key


def _role_for(user_id: str) -> str:
    for pair in settings.SECURITY_USER_ROLES.split(","):
        uid, _, role = pair.partition(":")
        if uid.strip() == user_id and role.strip() in ROLE_POLICIES:
            return role.strip()
    return "Standard"


def display_name(user_id: str | None) -> str | None:
    """Friendly label for a Clerk user id from SECURITY_USER_NAMES ("id:Name,..."), or None."""
    for pair in settings.SECURITY_USER_NAMES.split(","):
        uid, _, name = pair.partition(":")
        if user_id and uid.strip() == user_id and name.strip():
            return name.strip()
    return None


async def current_user(request: Request) -> User:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not settings.CLERK_ISSUER:
        raise HTTPException(status_code=503, detail="Authentication is not configured on the server")

    try:
        key = await asyncio.to_thread(_signing_key, token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER.rstrip("/"),
            options={"require": ["exp", "sub"]},
            leeway=10,
        )
    except Exception as e:  # bad signature, expired, wrong issuer, or JWKS unreachable
        logger.warning(f"Rejected token: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if claims.get("azp") and claims["azp"] not in allowed_origins:
        raise HTTPException(status_code=401, detail="Token was issued for a different app")

    return User(user_id=claims["sub"], role=_role_for(claims["sub"]), email=claims.get("email"))


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "Auditor":
        raise HTTPException(status_code=403, detail="Auditor role required")
    return user
