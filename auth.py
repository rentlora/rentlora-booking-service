"""Cognito-based auth. Validates the Cognito ID token (RS256, verified against the
user pool's JWKS) and just-in-time provisions a local User row keyed by email, so
the rest of the app keeps using the integer User.id (FK'd from bookings/properties).
Self-contained: reads the pool/client ids from SSM via the pod's IRSA role."""

import os
from typing import Optional

import boto3
import jwt
from database import get_db
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from models import User
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

security = HTTPBearer(auto_error=False)
_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
_ENV = os.getenv("ENV", "local")


def _load_cognito():
    """Resolve pool/client ids from SSM and build a cached JWKS client. Returns None
    (rather than crashing the service at import) if config can't be read."""
    if _ENV not in ("dev", "prod"):
        return None
    try:
        ssm = boto3.client("ssm", region_name=_REGION)
        pool_id = ssm.get_parameter(Name=f"/rentlora/{_ENV}/cognito-user-pool-id")["Parameter"]["Value"]
        client_id = ssm.get_parameter(Name=f"/rentlora/{_ENV}/cognito-client-id")["Parameter"]["Value"]
    except Exception:
        return None
    issuer = f"https://cognito-idp.{_REGION}.amazonaws.com/{pool_id}"
    return {
        "pool_id": pool_id,
        "client_id": client_id,
        "issuer": issuer,
        "jwks": PyJWKClient(f"{issuer}/.well-known/jwks.json"),
    }


_COGNITO = _load_cognito()


def cognito_public_config() -> dict:
    """Non-secret ids the SPA needs to talk to Cognito (served via /auth/config)."""
    if not _COGNITO:
        return {}
    return {"userPoolId": _COGNITO["pool_id"], "clientId": _COGNITO["client_id"], "region": _REGION}


def _verify(token: str) -> dict:
    if not _COGNITO:
        raise HTTPException(status_code=500, detail="Cognito not configured")
    try:
        key = _COGNITO["jwks"].get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=_COGNITO["client_id"],
            issuer=_COGNITO["issuer"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if claims.get("token_use") != "id":
        raise HTTPException(status_code=401, detail="ID token required")
    return claims


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    claims = _verify(creds.credentials)
    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="Token missing email")

    user = await db.scalar(select(User).where(User.email == email))
    if user:
        return user

    # First time we see this Cognito user → create the local row. Role from the
    # cognito:groups claim (admin/host/user), default "user".
    groups = claims.get("cognito:groups") or []
    user = User(
        name=claims.get("name") or email.split("@")[0],
        email=email,
        password_hash="cognito",  # password is managed by Cognito, not locally
        role=groups[0] if groups else "user",
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        # Concurrent create from another service — re-fetch the winner.
        await db.rollback()
        user = await db.scalar(select(User).where(User.email == email))
    return user
