from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.storage import BlobStorage
from app.core.config import Settings
from app.core.errors import AuthError, RateLimitedError
from app.core.filesafety import SafetyLimits
from app.core.ratelimit import RateLimiter
from app.core.security import decode_access_token
from app.db.models import User
from app.services.auth.service import ClientInfo


@dataclass
class AppState:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    storage: BlobStorage
    rate_limiter: RateLimiter
    redis: Redis | None


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.akshara
    return state


StateDep = Annotated[AppState, Depends(get_state)]


def get_settings_dep(state: StateDep) -> Settings:
    return state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_session(state: StateDep) -> AsyncIterator[AsyncSession]:
    async with state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_storage(state: StateDep) -> BlobStorage:
    return state.storage


StorageDep = Annotated[BlobStorage, Depends(get_storage)]


def get_limits(settings: SettingsDep) -> SafetyLimits:
    return SafetyLimits(
        max_bytes=settings.max_upload_bytes,
        max_uncompressed_bytes=settings.max_ooxml_uncompressed_bytes,
        max_entries=settings.max_ooxml_entries,
        max_compression_ratio=settings.max_compression_ratio,
    )


LimitsDep = Annotated[SafetyLimits, Depends(get_limits)]


def client_info(request: Request) -> ClientInfo:
    ip = request.client.host if request.client else None
    return ClientInfo(ip=ip, user_agent=request.headers.get("user-agent"))


ClientDep = Annotated[ClientInfo, Depends(client_info)]

_bearer = HTTPBearer(auto_error=False)


async def current_user(
    session: SessionDep,
    settings: SettingsDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthError("Sign in to continue.", code="UNAUTHENTICATED")
    user_id = decode_access_token(creds.credentials, settings)
    if user_id is None:
        raise AuthError("Your session has expired.", code="TOKEN_INVALID")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("Your session has expired.", code="TOKEN_INVALID")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def rate_limit(scope: str, per_minute_setting: str = "login_rate_limit_per_minute"):  # type: ignore[no-untyped-def]
    async def _dep(state: StateDep, client: ClientDep) -> None:
        limit = int(getattr(state.settings, per_minute_setting))
        if not await state.rate_limiter.hit(f"{scope}:{client.ip}", limit, 60):
            raise RateLimitedError("Too many attempts. Please wait a minute and try again.")

    return Depends(_dep)


def parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
