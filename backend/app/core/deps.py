"""FastAPI dependencies for the DB session, the current user, and role checks.

Usage:
    async def route(user: CurrentUser, db: DB): ...
    async def admin_route(user: StaffUser, db: DB): ...
    async def owner_route(user: Annotated[User, Depends(require_role(Role.SUPER_ADMIN))]): ...
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Role, User
from app.services.sessions import resolve_session

DB = Annotated[AsyncSession, Depends(get_db)]

NOT_AUTHENTICATED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


async def get_current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise NOT_AUTHENTICATED
    resolved = await resolve_session(db, token)
    if resolved is None:
        raise NOT_AUTHENTICATED
    session, user = resolved
    request.state.session_id = session.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[User], Awaitable[User]]:
    allowed = frozenset(roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        return user

    return dependency


StaffUser = Annotated[User, Depends(require_role(Role.ADMIN, Role.SUPER_ADMIN))]
SuperAdminUser = Annotated[User, Depends(require_role(Role.SUPER_ADMIN))]
CustomerUser = Annotated[User, Depends(require_role(Role.USER))]
