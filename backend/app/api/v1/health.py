from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Also the first call the frontend makes, so it receives the CSRF cookie."""
    return {"status": "ok"}
