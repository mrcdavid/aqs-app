"""Server-side sessions: create, resolve (with idle/absolute expiry), revoke."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_token, new_session_token
from app.models import AuthSession, User

# Don't write last_seen_at on every request; once a minute is precise enough.
LAST_SEEN_RESOLUTION = timedelta(seconds=60)


def utcnow() -> datetime:
    return datetime.now(UTC)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def idle_timeout(user: User) -> timedelta:
    s = get_settings()
    return timedelta(minutes=s.staff_idle_minutes if user.is_staff else s.user_idle_minutes)


async def create_session(db: AsyncSession, user: User, request: Request) -> str:
    """Adds a session row (caller commits) and returns the raw token for the cookie."""
    token = new_session_token()
    now = utcnow()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            last_seen_at=now,
            expires_at=now + timedelta(days=get_settings().session_absolute_days),
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        )
    )
    return token


async def resolve_session(db: AsyncSession, token: str) -> tuple[AuthSession, User] | None:
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == hash_token(token))
        )
    ).one_or_none()
    if row is None:
        return None
    session, user = row

    now = utcnow()
    expired = now >= session.expires_at or now - session.last_seen_at > idle_timeout(user)
    if expired or not user.can_log_in:
        await db.delete(session)
        await db.commit()
        return None

    if now - session.last_seen_at > LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        await db.commit()
    return session, user


async def revoke_session_token(db: AsyncSession, token: str | None) -> None:
    if token:
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))


async def revoke_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        token,
        max_age=s.session_absolute_days * 24 * 3600,
        httponly=True,
        secure=s.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.session_cookie_name, path="/", secure=s.secure_cookies, httponly=True, samesite="lax"
    )
