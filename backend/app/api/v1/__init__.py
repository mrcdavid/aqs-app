from fastapi import APIRouter

from app.api.v1 import (
    admin_audit,
    admin_catalog,
    admin_dashboard,
    admin_quotations,
    admin_users,
    auth,
    health,
    profile,
    quotations,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(quotations.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_quotations.router)
api_router.include_router(admin_audit.router)
api_router.include_router(admin_dashboard.router)
api_router.include_router(admin_users.router)
