"""The signed-in customer's own profile. There is no user id in the URL, so no IDOR risk."""

from fastapi import APIRouter, HTTPException, Request, status

from app.core.deps import DB, CustomerUser
from app.models import Profile
from app.schemas.profile import ProfileIn, ProfileOut
from app.services import audit

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(user: CustomerUser, db: DB) -> ProfileOut:
    profile = await db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not set up yet")
    return ProfileOut.model_validate(profile)


@router.put("")
async def upsert_profile(
    body: ProfileIn, user: CustomerUser, db: DB, request: Request
) -> ProfileOut:
    profile = await db.get(Profile, user.id)
    created = profile is None
    if profile is None:
        profile = Profile(user_id=user.id, **body.model_dump())
        db.add(profile)
    else:
        for field, value in body.model_dump().items():
            setattr(profile, field, value)
    audit.record(
        db,
        "profile.created" if created else "profile.updated",
        request=request,
        actor_id=user.id,
        entity="profile",
        entity_id=user.id,
    )
    await db.commit()
    return ProfileOut.model_validate(profile)
