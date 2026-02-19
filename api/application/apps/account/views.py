from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import urllib.parse
import urllib.request
import uuid
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .models import OAuthLoginSession, OAuthToken, User, UserIdentity

load_dotenv()

app = APIRouter()

PROVIDER_BASE_URL = os.getenv("PROVIDER_BASE_URL",
                              "http://localhost:9000")  # 认证提供方（OAuth Provider）服务的基础地址，用于拼接 token/userinfo 等接口 URL
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "utaker-client")  # OAuth 客户端 ID（client_id），用于向认证提供方标识当前应用
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET",
                                "utaker-secret")  # OAuth 客户端密钥（client_secret），用于与提供方交换/刷新令牌时进行客户端认证

PROVIDER_JWT_SIGNING_KEY = os.getenv("PROVIDER_JWT_SIGNING_KEY", "provider-dev-signing-key")
PROVIDER_JWT_ISSUER = os.getenv("PROVIDER_JWT_ISSUER",
                                "http://localhost:9000")  # 认证提供方签发的 JWT 的签发者（iss）声明，用于校验 provider token 的来源是否可信

JWT_ISSUER = os.getenv("JWT_ISSUER", "utaker-myapi")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "utaker-web")
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", os.getenv("JWT_SECRET", "utaker-dev-signing-key"))
JWT_ALG = os.getenv("JWT_ALG", "HS256")

PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_ENTERPRISE = "enterprise"

PLAN_FEATURES: dict[str, set[str]] = {
    PLAN_FREE: {"feature:basic"},
    PLAN_PRO: {"feature:basic", "feature:export"},
    PLAN_ENTERPRISE: {"feature:basic", "feature:export", "feature:admin"},
}

bearer = HTTPBearer(auto_error=False)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def _ensure_single_user_by_email(email: str) -> Optional[User]:
    normalized = _normalize_email(email)
    if not normalized:
        return None

    users = await User.filter(email__iexact=normalized).order_by("created_at", "id")
    if not users:
        return None

    primary = users[0]
    if len(users) == 1:
        if primary.email != normalized:
            primary.email = normalized
            await primary.save(update_fields=["email", "updated_at"])
        return primary

    await primary.fetch_related("identities", "oauth_tokens")
    primary_tokens_by_provider: dict[str, OAuthToken] = {t.provider: t for t in primary.oauth_tokens}

    for dupe in users[1:]:
        await dupe.fetch_related("identities", "oauth_tokens")

        for ident in dupe.identities:
            existing = await UserIdentity.get_or_none(provider=ident.provider, provider_subject=ident.provider_subject)
            if existing and existing.user_id != primary.id:
                await ident.delete()
                continue
            ident.user = primary
            await ident.save()

        for token in dupe.oauth_tokens:
            existing_token = primary_tokens_by_provider.get(token.provider)
            if not existing_token:
                token.user = primary
                await token.save()
                primary_tokens_by_provider[token.provider] = token
                continue

            should_replace = False
            if token.updated_at and existing_token.updated_at:
                should_replace = token.updated_at > existing_token.updated_at

            if should_replace:
                existing_token.access_token = token.access_token
                existing_token.refresh_token = token.refresh_token
                existing_token.app_refresh_token = token.app_refresh_token
                existing_token.scope = token.scope
                existing_token.expires_at = token.expires_at
                await existing_token.save()

            await token.delete()

        await dupe.delete()

    if primary.email != normalized:
        primary.email = normalized
        await primary.save(update_fields=["email", "updated_at"])

    return primary


class ExchangeRequest(BaseModel):
    code: str
    login_id: str


class ExchangeResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CreateLoginSessionRequest(BaseModel):
    code_verifier: str
    state: str = Field(..., max_length=128)
    redirect_uri: str


class CreateLoginSessionResponse(BaseModel):
    login_id: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    plan: str
    plan_expires_at: Optional[str] = None
    features: list[str]


class MeResponse(BaseModel):
    user: UserOut


def normalize_plan(plan: str) -> str:
    p = (plan or "").strip().lower()
    if p in PLAN_FEATURES:
        return p
    return PLAN_FREE


def is_plan_expired(plan: str, plan_expires_at: Optional[datetime]) -> bool:
    if normalize_plan(plan) == PLAN_FREE:
        return False
    if not plan_expires_at:
        return True
    now = datetime.now(timezone.utc)
    if plan_expires_at.tzinfo is None:
        plan_expires_at = plan_expires_at.replace(tzinfo=timezone.utc)
    return plan_expires_at <= now


def features_for_plan(plan: str) -> set[str]:
    return PLAN_FEATURES.get(normalize_plan(plan), PLAN_FEATURES[PLAN_FREE])


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


async def ensure_plan_not_expired(user: User) -> User:
    plan = normalize_plan(user.plan)
    if is_plan_expired(plan, user.plan_expires_at):
        user.plan = PLAN_FREE
        user.plan_expires_at = None
        user.updated_at = datetime.now(timezone.utc)
        await user.save(update_fields=["plan", "plan_expires_at", "updated_at"])
    return user


def require_feature(feature_key: str):
    async def _dep(user_id: str = Depends(get_current_user_id)) -> User:
        user = await User.get(id=user_id)
        user = await ensure_plan_not_expired(user)
        features = features_for_plan(user.plan)
        if feature_key not in features:
            raise HTTPException(status_code=403, detail="feature not allowed")
        return user

    return _dep


async def _provider_exchange_code(code: str, code_verifier: str, redirect_uri: str) -> dict:
    token_url = f"{PROVIDER_BASE_URL}/oauth/token"
    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"provider token exchange failed: request error: {str(e)}")

    if status != 200:
        raise HTTPException(status_code=400, detail=f"provider token exchange failed: {status} {body}")

    import json

    return json.loads(body)


def _decode_provider_access_token(access_token: str) -> dict:
    try:
        payload = jwt.decode(
            access_token,
            PROVIDER_JWT_SIGNING_KEY,
            algorithms=["HS256"],
            audience=OAUTH_CLIENT_ID,
            issuer=PROVIDER_JWT_ISSUER,
        )
    except Exception:
        raise HTTPException(status_code=400, detail="invalid provider access_token")

    return payload


@app.post("/auth/login-session", response_model=CreateLoginSessionResponse)
async def create_login_session(req: CreateLoginSessionRequest):
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    try:
        session = await OAuthLoginSession.create(
            code_verifier=req.code_verifier,
            state=req.state,
            redirect_uri=req.redirect_uri,
            expires_at=expires_at,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create login session: {str(e)}")
    return CreateLoginSessionResponse(login_id=str(session.id))


@app.post("/auth/exchange", response_model=ExchangeResponse)
async def exchange(req: ExchangeRequest):
    session = await OAuthLoginSession.get_or_none(id=req.login_id)
    if not session:
        raise HTTPException(status_code=400, detail="invalid login_id")

    now = datetime.now(timezone.utc)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        await session.delete()
        raise HTTPException(status_code=400, detail="login session expired")

    token_data = await _provider_exchange_code(req.code, session.code_verifier, session.redirect_uri)
    await session.delete()

    provider_access_token = token_data.get("access_token")
    if not provider_access_token:
        raise HTTPException(status_code=400, detail="missing provider access_token")

    provider_payload = _decode_provider_access_token(provider_access_token)

    provider = "utaker-provider"
    provider_subject = str(provider_payload.get("sub"))
    provider_email = provider_payload.get("email")
    provider_name = provider_payload.get("name")
    provider_avatar_url = provider_payload.get("avatar_url") or provider_payload.get("picture")
    if provider_avatar_url is not None:
        provider_avatar_url = str(provider_avatar_url).strip()
    else:
        provider_avatar_url = ""

    identity = await UserIdentity.get_or_none(provider=provider, provider_subject=provider_subject).prefetch_related(
        "user")
    if identity:
        user = identity.user
        if provider_email:
            normalized_email = _normalize_email(provider_email)
            if identity.provider_email != normalized_email:
                identity.provider_email = normalized_email
                await identity.save(update_fields=["provider_email", "updated_at"])
            if user.email != normalized_email:
                user.email = normalized_email
            await user.save(update_fields=["email", "updated_at"])
        if provider_name and user.display_name != provider_name:
            user.display_name = provider_name
            await user.save(update_fields=["display_name", "updated_at"])
        if provider_avatar_url != (user.avatar_url or ""):
            user.avatar_url = provider_avatar_url
            await user.save(update_fields=["avatar_url", "updated_at"])
    else:
        if not provider_email:
            raise HTTPException(status_code=400, detail="missing email from provider")
        if not provider_name:
            provider_name = provider_email.split("@", 1)[0]

        normalized_email = _normalize_email(provider_email)
        user = await _ensure_single_user_by_email(normalized_email)
        if not user:
            try:
                user = await User.create(email=normalized_email, display_name=provider_name,
                                         avatar_url=provider_avatar_url)
            except Exception:
                user = await _ensure_single_user_by_email(normalized_email)
                if not user:
                    raise
        else:
            if user.display_name != provider_name and provider_name:
                user.display_name = provider_name
                await user.save(update_fields=["display_name", "updated_at"])
            if provider_avatar_url != (user.avatar_url or ""):
                user.avatar_url = provider_avatar_url
                await user.save(update_fields=["avatar_url", "updated_at"])

        identity_by_email = (
            await UserIdentity.filter(provider=provider, provider_email__iexact=normalized_email)
            .prefetch_related("user")
            .order_by("created_at", "id")
            .first()
        )
        if identity_by_email:
            if identity_by_email.user_id != user.id:
                identity_by_email.user = user
            identity_by_email.provider_subject = provider_subject
            identity_by_email.provider_email = normalized_email
            await identity_by_email.save()
            await UserIdentity.filter(provider=provider, provider_email__iexact=normalized_email).exclude(
                id=identity_by_email.id
            ).delete()
        else:
            try:
                await UserIdentity.create(
                    user=user,
                    provider=provider,
                    provider_subject=provider_subject,
                    provider_email=normalized_email,
                )
            except Exception:
                existing = await UserIdentity.get_or_none(provider=provider, provider_subject=provider_subject)
                if existing:
                    if existing.user_id != user.id:
                        existing.user = user
                    existing.provider_email = normalized_email
                    await existing.save()
                else:
                    raise

    expires_in = token_data.get("expires_in")
    expires_at: Optional[datetime] = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    app_refresh_token = uuid.uuid4().hex

    oauth_token = await OAuthToken.get_or_none(user=user, provider=provider)
    if oauth_token:
        oauth_token.access_token = provider_access_token
        oauth_token.refresh_token = token_data.get("refresh_token")
        oauth_token.app_refresh_token = app_refresh_token
        oauth_token.scope = token_data.get("scope")
        oauth_token.expires_at = expires_at
        await oauth_token.save()
    else:
        await OAuthToken.create(
            user=user,
            provider=provider,
            access_token=provider_access_token,
            refresh_token=token_data.get("refresh_token"),
            app_refresh_token=app_refresh_token,
            scope=token_data.get("scope"),
            expires_at=expires_at,
        )

    if not user.plan:
        user.plan = PLAN_FREE
        await user.save(update_fields=["plan", "updated_at"])

    my_jwt = create_access_token(str(user.id))
    return ExchangeResponse(access_token=my_jwt, refresh_token=app_refresh_token)


@app.post("/auth/refresh", response_model=ExchangeResponse)
async def refresh_token(req: RefreshTokenRequest):
    token_record = await OAuthToken.get_or_none(app_refresh_token=req.refresh_token).prefetch_related("user")
    if not token_record:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    # Optional: Check if provider token is expired and refresh it here
    # For now, we just refresh the app token

    # Generate new refresh token? (Rotating refresh token policy)
    # For simplicity, let's keep the same refresh token or generate new one.
    # Let's rotate it for security.
    new_refresh_token = uuid.uuid4().hex
    token_record.app_refresh_token = new_refresh_token
    await token_record.save(update_fields=["app_refresh_token", "updated_at"])

    new_jwt = create_access_token(str(token_record.user.id))
    return ExchangeResponse(access_token=new_jwt, refresh_token=new_refresh_token)


@app.get("/me", response_model=MeResponse)
async def me(user_id: str = Depends(get_current_user_id)):
    user = await User.get(id=user_id)
    user = await ensure_plan_not_expired(user)
    return MeResponse(
        user={
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url or "",
            "plan": user.plan,
            "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
            "features": sorted(features_for_plan(user.plan)),
        }
    )


@app.get("/export")
async def export_data(user: User = Depends(require_feature("feature:export"))):
    return {"ok": True, "plan": user.plan}


@app.post("/auth/logout")
async def logout(user_id: str = Depends(get_current_user_id)):
    """
    登出接口：
    1. 获取当前用户的 Provider Access Token
    2. 调用 Provider 的 /auth/logout 接口销毁 Provider Session
    3. (可选) 销毁本地 Session (如果是基于 Session 的话，但这里是 JWT，客户端删掉即可)
    """
    user = await User.get_or_none(id=user_id)
    if not user:
        return {"ok": True}

    provider = "utaker-provider"
    oauth_token = await OAuthToken.get_or_none(user=user, provider=provider)

    if oauth_token and oauth_token.access_token:
        # 调用 Provider 登出
        try:
            req = urllib.request.Request(
                f"{PROVIDER_BASE_URL}/auth/logout",
                headers={
                    "Authorization": f"Bearer {oauth_token.access_token}",
                    "Accept": "application/json"
                },
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except Exception as e:
            # 即使 Provider 登出失败，也允许本地登出
            print(f"Provider logout failed: {e}")

        # 可选：删除本地存储的 Provider Token
        await oauth_token.delete()

    return {"ok": True}
