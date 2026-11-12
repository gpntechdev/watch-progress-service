import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from watch_progress_service.config import load_config
from watch_progress_service.db import create_engine, create_session_factory


@pytest.fixture
async def session():
    """A session on the local database (`make up && make migrate`) that is rolled back."""
    engine = create_engine(load_config().database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except OSError:
        await engine.dispose()
        pytest.skip("PostgreSQL is not running (make up)")
    async with create_session_factory(engine)() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def session_factory():
    """Session factory whose sessions all share one rolled-back transaction, so a test can
    seed data and run server code against it without committing anything."""
    engine = create_engine(load_config().database_url)
    try:
        connection = await engine.connect()
    except OSError:
        await engine.dispose()
        pytest.skip("PostgreSQL is not running (make up)")
    transaction = await connection.begin()
    factory = async_sessionmaker(
        connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    yield factory
    await transaction.rollback()
    await connection.close()
    await engine.dispose()
