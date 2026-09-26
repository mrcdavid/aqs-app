"""User management. Staff can view; only super_admin can change anything.

Rules:
- Nobody changes their own account here (no self-lockout; the acting super_admin always stays
  active, so at least one super_admin always remains).
- Deletes are soft (deleted_at + is_active=false); audit history keeps pointing at the user.
- Disabling, deleting, changing role or resetting a password signs the user out everywhere.
"""

import uuid
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select

from app.core.config import get_settings
from app.core.deps import DB, StaffUser, SuperAdminUser
from app.core.security import hash_password, password_problems
from app.models import AuthProvider, AuthSession, Profile, Role, User
from app.schemas.users import (
    ActiveSessionOut,
    PasswordResetIn,
    StaffCreateIn,
    UserRowOut,
    UserUpdateIn,
)
from app.services import audit
from app.services.sessions import revoke_user_sessions, utcnow

router = APIRouter(prefix="/admin", tags=["admin: users"])

LIST_LIMIT = 500


def _active_session_filter():  # noqa: ANN202 - SQLAlchemy expression
    """Sessions not yet expired by the absolute or the role's idle timeout."""
    s = get_settings()
    now = utcnow()
    return and_(
        AuthSession.expires_at > now,
        or_(
            and_(
                User.role == Role.USER,
                AuthSession.last_seen_at > now - timedelta(minutes=s.user_idle_minutes),
            ),
            and_(
                User.role != Role.USER,
                AuthSession.last_seen_at > now - timedelta(minutes=s.staff_idle_minutes),
            ),
        ),
    )


async def _rows(db: DB, *conditions) -> list[UserRowOut]:  # noqa: ANN002
    sessions = (
        select(
            AuthSession.user_id,
            func.count().label("active"),
            func.max(AuthSession.last_seen_at).label("last_seen"),
        )
        .join(User, User.id == AuthSession.user_id)
        .where(_active_session_filter())
        .group_by(AuthSession.user_id)
        .subquery()
    )
    stmt = (
        select(User, Profile.full_name, Profile.city, sessions.c.active, sessions.c.last_seen)
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(sessions, sessions.c.user_id == User.id)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .limit(LIST_LIMIT)
    )
    now = utcnow()
    return [
        UserRowOut(
            id=u.id,
            email=u.email,
            role=u.role,
            auth_provider=u.auth_provider,
            full_name=full_name,
            city=city,
            is_active=u.is_active,
            deleted_at=u.deleted_at,
            locked=bool(u.locked_until and u.locked_until > now),
            last_login_at=u.last_login_at,
            created_at=u.created_at,
            active_sessions=active or 0,
            last_seen_at=last_seen,
        )
        for u, full_name, city, active, last_seen in (await db.execute(stmt)).all()
    ]


async def _row(db: DB, user_id: uuid.UUID) -> UserRowOut:
    return (await _rows(db, User.id == user_id))[0]


async def _target(db: DB, actor: User, user_id: uuid.UUID) -> User:
    target = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == actor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't change your own account here")
    if target.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This account has been deleted")
    return target


def _check_password(password: str, email: str) -> None:
    if problems := password_problems(password, email):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Password " + "; ".join(problems)
        )


# ---------- read (all staff) ----------


@router.get("/users")
async def list_users(
    user: StaffUser,
    db: DB,
    kind: Literal["customers", "staff", "deleted", "all"] = "customers",
    q: Annotated[str | None, Query(max_length=254)] = None,
) -> list[UserRowOut]:
    conditions = []
    if kind == "customers":
        conditions += [User.role == Role.USER, User.deleted_at.is_(None)]
    elif kind == "staff":
        conditions += [User.role != Role.USER, User.deleted_at.is_(None)]
    elif kind == "deleted":
        conditions.append(User.deleted_at.is_not(None))
    if q:
        term = q.strip().lower()
        conditions.append(
            or_(
                User.email.contains(term, autoescape=True),
                func.lower(Profile.full_name).contains(term, autoescape=True),
            )
        )
    return await _rows(db, *conditions)


# ---------- changes (super_admin only) ----------


@router.post("/users/staff", status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: StaffCreateIn, actor: SuperAdminUser, db: DB, request: Request
) -> UserRowOut:
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    _check_password(body.password, email)
    user = User(
        email=email,
        role=Role(body.role),
        auth_provider=AuthProvider.PASSWORD,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    audit.record(
        db,
        "user.created",
        request=request,
        actor_id=actor.id,
        entity="user",
        entity_id=user.id,
        details={"email": email, "role": body.role},
    )
    await db.commit()
    return await _row(db, user.id)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID, body: UserUpdateIn, actor: SuperAdminUser, db: DB, request: Request
) -> UserRowOut:
    target = await _target(db, actor, user_id)
    sign_out = False

    if body.role is not None and body.role != target.role:
        if target.auth_provider != AuthProvider.PASSWORD:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Customer accounts can't become staff; create a staff account instead",
            )
        audit.record(
            db,
            "user.role_changed",
            request=request,
            actor_id=actor.id,
            entity="user",
            entity_id=target.id,
            details={"changes": {"role": [target.role, body.role]}},
        )
        target.role = Role(body.role)
        sign_out = True  # new role takes effect on the next login

    if body.is_active is not None and body.is_active != target.is_active:
        target.is_active = body.is_active
        if body.is_active:
            target.failed_login_count = 0
            target.locked_until = None
        else:
            sign_out = True
        audit.record(
            db,
            "user.enabled" if body.is_active else "user.disabled",
            request=request,
            actor_id=actor.id,
            entity="user",
            entity_id=target.id,
        )

    if sign_out:
        await revoke_user_sessions(db, target.id)
    await db.commit()
    return await _row(db, target.id)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID, actor: SuperAdminUser, db: DB, request: Request
) -> UserRowOut:
    target = await _target(db, actor, user_id)
    target.is_active = False
    target.deleted_at = utcnow()
    await revoke_user_sessions(db, target.id)
    audit.record(
        db,
        "user.deleted",
        request=request,
        actor_id=actor.id,
        entity="user",
        entity_id=target.id,
        details={"email": target.email, "role": target.role},
    )
    await db.commit()
    return await _row(db, target.id)


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: uuid.UUID, body: PasswordResetIn, actor: SuperAdminUser, db: DB, request: Request
) -> UserRowOut:
    target = await _target(db, actor, user_id)
    if target.auth_provider != AuthProvider.PASSWORD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Customers sign in with Google; no password"
        )
    _check_password(body.password, target.email)
    target.password_hash = hash_password(body.password)
    target.failed_login_count = 0
    target.locked_until = None
    await revoke_user_sessions(db, target.id)
    audit.record(
        db,
        "user.password_reset",
        request=request,
        actor_id=actor.id,
        entity="user",
        entity_id=target.id,
    )
    await db.commit()
    return await _row(db, target.id)


@router.post("/users/{user_id}/sign-out")
async def sign_out_everywhere(
    user_id: uuid.UUID, actor: SuperAdminUser, db: DB, request: Request
) -> UserRowOut:
    target = await _target(db, actor, user_id)
    await revoke_user_sessions(db, target.id)
    audit.record(
        db,
        "user.signed_out",
        request=request,
        actor_id=actor.id,
        entity="user",
        entity_id=target.id,
    )
    await db.commit()
    return await _row(db, target.id)


@router.get("/sessions")
async def active_sessions(actor: SuperAdminUser, db: DB) -> list[ActiveSessionOut]:
    rows = (
        await db.execute(
            select(AuthSession, User.email, User.role)
            .join(User, User.id == AuthSession.user_id)
            .where(_active_session_filter())
            .order_by(AuthSession.last_seen_at.desc())
            .limit(LIST_LIMIT)
        )
    ).all()
    return [
        ActiveSessionOut(
            id=s.id,
            user_id=s.user_id,
            email=email,
            role=role,
            ip=s.ip,
            user_agent=s.user_agent,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
        )
        for s, email, role in rows
    ]
