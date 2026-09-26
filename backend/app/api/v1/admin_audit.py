"""Read-only audit log viewer for staff. Newest first, keyset-paginated by id."""

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import DB, StaffUser
from app.models import AuditLog, User
from app.schemas.audit import AuditEntryOut, AuditPageOut
from app.services.quotations import PHT

router = APIRouter(prefix="/admin/audit-log", tags=["admin: audit log"])


@router.get("")
async def list_audit_log(
    user: StaffUser,
    db: DB,
    action: Annotated[
        str | None, Query(max_length=64, description="Action prefix, e.g. login")
    ] = None,
    actor: Annotated[
        str | None, Query(max_length=254, description="Part of the actor's email")
    ] = None,
    date_from: Annotated[date | None, Query(description="Philippine date, inclusive")] = None,
    date_to: Annotated[date | None, Query(description="Philippine date, inclusive")] = None,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPageOut:
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.id.desc())
        .limit(limit + 1)  # one extra row tells us whether another page exists
    )
    # autoescape: a user typing % or _ searches for those characters, not wildcards.
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action.strip().lower(), autoescape=True))
    if actor:
        stmt = stmt.where(User.email.contains(actor.strip().lower(), autoescape=True))
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min, PHT))
    if date_to:
        next_day = datetime.combine(date_to + timedelta(days=1), time.min, PHT)
        stmt = stmt.where(AuditLog.created_at < next_day)
    if before_id:
        stmt = stmt.where(AuditLog.id < before_id)

    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        AuditEntryOut(
            id=entry.id,
            created_at=entry.created_at,
            actor_id=entry.actor_id,
            actor_email=email,
            action=entry.action,
            entity=entry.entity,
            entity_id=entry.entity_id,
            ip=entry.ip,
            details=entry.details,
        )
        for entry, email in rows
    ]
    return AuditPageOut(items=items, next_before_id=items[-1].id if has_more else None)
