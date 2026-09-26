import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    entity: str | None
    entity_id: str | None
    ip: str | None
    details: dict[str, Any]


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    # Pass as `before_id` to get the next (older) page; null when there are no more.
    next_before_id: int | None
