import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from aicontrol.config import get_settings
from alembic import command


async def table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
    await engine.dispose()
    return names


def test_initial_migration_up_down_and_no_drift(tmp_path, monkeypatch) -> None:
    database_file = tmp_path / "migration-test.db"
    monkeypatch.setenv("AIC_DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    try:
        command.upgrade(config, "head")
        names = asyncio.run(table_names(f"sqlite+aiosqlite:///{database_file.as_posix()}"))
        assert "users" in names
        assert "computers" in names
        assert "goal_steps" in names
        command.check(config)
        command.downgrade(config, "base")
        names = asyncio.run(table_names(f"sqlite+aiosqlite:///{database_file.as_posix()}"))
        assert "users" not in names
    finally:
        get_settings.cache_clear()
