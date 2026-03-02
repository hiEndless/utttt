from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

JWT_ISSUER = os.getenv("JWT_ISSUER", "utaker-myapi")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "utaker-web")
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", "utaker-dev-signing-key")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> str:
    now = int(datetime.now(tz=timezone.utc).timestamp())
    exp = now + 60 * 60
    return jwt.encode(
        {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": user_id,
            "iat": now,
            "exp": exp,
        },
        JWT_SIGNING_KEY,
        algorithm=JWT_ALG,
    )


def verify_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            JWT_SIGNING_KEY,
            algorithms=[JWT_ALG],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token")

    return str(sub)


def get_current_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> str:
    if not creds:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return verify_access_token(creds.credentials)

