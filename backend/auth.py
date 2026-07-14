import os
import secrets
from typing import Optional
from fastapi import Header, HTTPException

# Read keys on import (app initialization phase)
GATEWAY_MASTER_KEY = os.getenv("GATEWAY_MASTER_KEY", "").strip()
GATEWAY_ADMIN_KEY = os.getenv("GATEWAY_ADMIN_KEY", "").strip()

# Enforce fail-closed secure startup
if not GATEWAY_MASTER_KEY:
    raise RuntimeError(
        "GATEWAY_MASTER_KEY is required; refusing to start insecurely."
    )

if not GATEWAY_ADMIN_KEY:
    raise RuntimeError(
        "GATEWAY_ADMIN_KEY is required; refusing to start insecurely."
    )

if GATEWAY_MASTER_KEY == GATEWAY_ADMIN_KEY:
    raise RuntimeError(
        "Gateway and admin keys must be different."
    )


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, separator, token = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token.strip()


def require_gateway_auth(authorization: Optional[str] = Header(None)) -> None:
    token = extract_bearer_token(authorization)
    if not secrets.compare_digest(token, GATEWAY_MASTER_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin_auth(authorization: Optional[str] = Header(None)) -> None:
    token = extract_bearer_token(authorization)
    if not secrets.compare_digest(token, GATEWAY_ADMIN_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
