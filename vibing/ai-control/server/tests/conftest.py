import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from aicontrol.config import Settings
from aicontrol.db.models import Base, Computer, ComputerKind, User
from aicontrol.db.security import hash_secret
from aicontrol.db.session import get_session
from aicontrol.main import create_app


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def gateway_context(tmp_path: Path) -> Iterator[tuple[TestClient, FastAPI, str, str]]:
    database_path = tmp_path / "gateway.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    async def initialize_database() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            user = User(username="gateway-owner")
            session.add(user)
            await session.flush()
            session.add(
                Computer(
                    id="device-1",
                    owner_user_id=user.id,
                    label="Gateway turtle",
                    kind=ComputerKind.COMPUTER,
                    device_secret_hash=hash_secret("correct-secret"),
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(initialize_database())
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app(
        Settings(
            _env_file=None,
            database_url=database_url,
            max_ws_message_bytes=4096,
            hello_timeout_s=0.15,
            heartbeat_interval_s=1,
            heartbeat_timeout_s=0.35,
        )
    )
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, app, database_url, "device-1"
    asyncio.run(engine.dispose())
