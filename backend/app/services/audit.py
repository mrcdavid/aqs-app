"""Write audit log entries. The caller commits, so the entry lands with the change it describes."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.services.sessions import client_ip


def record(
    db: AsyncSession,
    action: str,
    *,
    request: Request | None = None,
    actor_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            actor_id=actor_id,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip=client_ip(request) if request else None,
            details=details or {},
        )
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")  # 100.50 and 100.5 compare equal
    if isinstance(value, uuid.UUID | datetime):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def snapshot(obj: object, fields: list[str]) -> dict[str, Any]:
    """JSON-safe copy of selected attributes, for audit details."""
    return {f: _jsonable(getattr(obj, f)) for f in fields}


def changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """{field: [old, new]} for fields that changed."""
    return {k: [before[k], after[k]] for k in before if before[k] != after.get(k)}
