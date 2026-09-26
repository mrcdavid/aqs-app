"""Login (Google for customers, password for staff), logout, and current user."""

import logging
from datetime import timedelta

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser
from app.core.rate_limit import limiter
from app.core.security import DUMMY_PASSWORD_HASH, verify_password
from app.models import AuthProvider, Profile, Role, User
from app.schemas.auth import MeOut, StaffLoginIn
from app.services import audit
from app.services.oauth import GoogleIdentityError, oauth, verify_google_identity
from app.services.sessions import (
    clear_session_cookie,
    create_session,
    revoke_session_token,
    set_session_cookie,
    utcnow,
)

logger = logging.getLogger("aqs.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")


async def _me(db: DB, user: User) -> MeOut:
    has_profile = await db.get(Profile, user.id) is not None
    return MeOut(id=user.id, email=user.email, role=user.role, has_profile=has_profile)


def _login_error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().app_origin}/login?error={code}", status_code=303)


# ---------- Google (customers) ----------


@router.get("/google/login")
async def google_login(request: Request) -> Response:
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in not configured")
    # Goes through the frontend origin so the Vite proxy / reverse proxy keeps one origin.
    redirect_uri = f"{s.app_origin}/api/v1/auth/google/callback"
    return await oauth.google.authorize_redirect(
        request, redirect_uri, hd=s.allowed_email_domain, prompt="select_account"
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: DB) -> Response:
    s = get_settings()
    try:
        token = await oauth.google.authorize_access_token(request)
        identity = verify_google_identity(token.get("userinfo") or {}, s.allowed_email_domain)
    except GoogleIdentityError as exc:
        audit.record(db, "login.google.rejected", request=request, details={"reason": str(exc)})
        await db.commit()
        return _login_error_redirect("domain" if str(exc) == "domain_not_allowed" else "google")
    except OAuthError as exc:
        logger.warning("Google OAuth error: %s", exc.error)
        return _login_error_redirect("google")

    user = await db.scalar(select(User).where(User.google_sub == identity.sub))
    if user is None:
        if await db.scalar(select(User.id).where(User.email == identity.email)):
            # Email already belongs to a staff account (or an old Google account). Don't merge.
            audit.record(
                db, "login.google.conflict", request=request, details={"email": identity.email}
            )
            await db.commit()
            return _login_error_redirect("conflict")
        user = User(
            email=identity.email,
            role=Role.USER,
            auth_provider=AuthProvider.GOOGLE,
            google_sub=identity.sub,
        )
        db.add(user)
        await db.flush()
        audit.record(
            db,
            "user.registered",
            request=request,
            actor_id=user.id,
            entity="user",
            entity_id=user.id,
        )
    elif user.email != identity.email:
        user.email = identity.email  # Google account email changed

    if not user.can_log_in:
        audit.record(db, "login.google.disabled", request=request, actor_id=user.id)
        await db.commit()
        return _login_error_redirect("disabled")

    await revoke_session_token(db, request.cookies.get(s.session_cookie_name))
    session_token = await create_session(db, user, request)
    user.last_login_at = utcnow()
    audit.record(db, "login.google.success", request=request, actor_id=user.id)
    await db.commit()

    has_profile = await db.get(Profile, user.id) is not None
    target = "/app/quotations" if has_profile else "/app/profile"
    response = RedirectResponse(f"{s.app_origin}{target}", status_code=303)
    set_session_cookie(response, session_token)
    return response


# ---------- Password (staff) ----------


@router.post("/staff/login")
@limiter.limit("5/minute")
async def staff_login(request: Request, response: Response, body: StaffLoginIn, db: DB) -> MeOut:
    s = get_settings()
    email = body.email.lower()
    now = utcnow()
    user = await db.scalar(select(User).where(User.email == email))

    if user is None or user.auth_provider != AuthProvider.PASSWORD or not user.password_hash:
        verify_password(body.password, DUMMY_PASSWORD_HASH)  # same timing as a real check
        audit.record(
            db,
            "login.staff.failed",
            request=request,
            details={"email": email, "reason": "unknown_account"},
        )
        await db.commit()
        raise INVALID_LOGIN

    if user.locked_until and user.locked_until > now:
        verify_password(body.password, DUMMY_PASSWORD_HASH)
        audit.record(
            db,
            "login.staff.failed",
            request=request,
            actor_id=user.id,
            details={"reason": "locked"},
        )
        await db.commit()
        raise INVALID_LOGIN

    valid, upgraded_hash = verify_password(body.password, user.password_hash)
    if not valid:
        user.failed_login_count += 1
        reason = "bad_password"
        if user.failed_login_count >= s.max_failed_logins:
            user.locked_until = now + timedelta(minutes=s.lockout_minutes)
            user.failed_login_count = 0
            reason = "bad_password_locked"
        audit.record(
            db, "login.staff.failed", request=request, actor_id=user.id, details={"reason": reason}
        )
        await db.commit()
        raise INVALID_LOGIN

    if not user.can_log_in:
        audit.record(
            db,
            "login.staff.failed",
            request=request,
            actor_id=user.id,
            details={"reason": "disabled"},
        )
        await db.commit()
        raise INVALID_LOGIN

    if upgraded_hash:
        user.password_hash = upgraded_hash
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await revoke_session_token(db, request.cookies.get(s.session_cookie_name))
    session_token = await create_session(db, user, request)
    audit.record(db, "login.staff.success", request=request, actor_id=user.id)
    await db.commit()

    set_session_cookie(response, session_token)
    return await _me(db, user)


# ---------- Session ----------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: DB) -> Response:
    token = request.cookies.get(get_settings().session_cookie_name)
    await revoke_session_token(db, token)
    await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.get("/me")
async def me(user: CurrentUser, db: DB) -> MeOut:
    return await _me(db, user)
