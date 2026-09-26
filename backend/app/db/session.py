"""Async engine and a FastAPI dependency that yields one DB session per request."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    # Tests run each case on its own event loop; pooled asyncpg connections can't cross loops.
    **({"poolclass": NullPool} if _settings.environment == "test" else {}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
