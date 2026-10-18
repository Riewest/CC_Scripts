from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aicontrol.config import get_settings


def async_database_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def make_engine(database_url: str | None = None):
    url = async_database_url(database_url or get_settings().database_url)
    options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url.endswith(":memory:") else {}
    return create_async_engine(url, pool_pre_ping=True, **options)


engine = make_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
