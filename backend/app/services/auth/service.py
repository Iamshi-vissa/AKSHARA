"""Authentication use-cases: register, login, refresh-token rotation, logout, profile.

Refresh tokens rotate on every use. Each login starts a *family*; presenting a token that was
already rotated (a replay, e.g. a stolen cookie) revokes the whole family, forcing a new login.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthError, ConflictError
from app.core.ids import uuid7
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    needs_rehash,
    new_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.services import audit


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def register(
        self, email: str, password: str, display_name: str | None, client: ClientInfo
    ) -> User:
        user = User(
            email=email.strip(),
            password_hash=hash_password(password),
            display_name=(display_name or "").strip() or None,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "An account with this e-mail already exists.", code="EMAIL_TAKEN"
            ) from exc
        audit.record(self.session, "auth.register", owner_id=user.id, ip=client.ip)
        await self.session.commit()
        return user

    async def login(self, email: str, password: str, client: ClientInfo) -> IssuedTokens:
        user = await self.session.scalar(select(User).where(User.email == email.strip()))
        if not verify_password(password, user.password_hash if user else None) or user is None:
            audit.record(
                self.session,
                "auth.login_failed",
                owner_id=user.id if user else None,
                ip=client.ip,
            )
            await self.session.commit()
            raise AuthError("Incorrect e-mail or password.", code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise AuthError("This account is disabled.", code="ACCOUNT_DISABLED")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        tokens, _ = self._issue(user.id, family_id=uuid7(), client=client)
        audit.record(self.session, "auth.login", owner_id=user.id, ip=client.ip)
        await self.session.commit()
        return tokens

    async def refresh(self, raw_token: str, client: ClientInfo) -> IssuedTokens:
        row = await self.session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(raw_token))
            .with_for_update()
        )
        now = datetime.now(UTC)
        if row is None:
            raise AuthError("Session expired. Please sign in again.", code="INVALID_REFRESH")
        if row.revoked_at is not None:
            # Reuse of a rotated token: assume theft and end every session in the family.
            await self._revoke_family(row.family_id, now)
            audit.record(
                self.session,
                "auth.refresh_reuse_detected",
                owner_id=row.user_id,
                ip=client.ip,
                family_id=str(row.family_id),
            )
            await self.session.commit()
            raise AuthError("Session expired. Please sign in again.", code="REFRESH_REUSED")
        if row.expires_at <= now:
            raise AuthError("Session expired. Please sign in again.", code="REFRESH_EXPIRED")

        user = await self.session.get(User, row.user_id)
        if user is None or not user.is_active:
            raise AuthError("Session expired. Please sign in again.", code="INVALID_REFRESH")

        tokens, new_row_id = self._issue(user.id, family_id=row.family_id, client=client)
        row.revoked_at = now
        row.replaced_by_id = new_row_id
        await self.session.commit()
        return tokens

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        row = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
        if row is None:
            return
        await self._revoke_family(row.family_id, datetime.now(UTC))
        audit.record(self.session, "auth.logout", owner_id=row.user_id)
        await self.session.commit()

    async def update_profile(
        self,
        user: User,
        *,
        display_name: str | None,
        preferred_unit: str | None,
        allow_external_llm: bool | None,
        fields_set: set[str],
    ) -> User:
        if "display_name" in fields_set:
            user.display_name = (display_name or "").strip() or None
        if preferred_unit is not None:
            user.preferred_unit = preferred_unit
        if allow_external_llm is not None and allow_external_llm != user.allow_external_llm:
            user.allow_external_llm = allow_external_llm
            audit.record(
                self.session, "user.llm_consent_changed", owner_id=user.id, value=allow_external_llm
            )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    # ------------------------------------------------------------------------------------
    def _issue(
        self, user_id: uuid.UUID, *, family_id: uuid.UUID, client: ClientInfo
    ) -> tuple[IssuedTokens, uuid.UUID]:
        access, ttl = create_access_token(user_id, self.settings)
        raw = new_refresh_token()
        expires = datetime.now(UTC) + timedelta(seconds=self.settings.refresh_token_ttl_seconds)
        row = RefreshToken(
            id=uuid7(),
            user_id=user_id,
            token_hash=hash_token(raw),
            family_id=family_id,
            expires_at=expires,
            user_agent=(client.user_agent or "")[:300] or None,
            ip=client.ip,
        )
        self.session.add(row)
        tokens = IssuedTokens(
            access_token=access, expires_in=ttl, refresh_token=raw, refresh_expires_at=expires
        )
        return tokens, row.id

    async def _revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
