from sqlalchemy import text

from watch_progress_service.seed import DEMO_TOKENS, HISTORY, VIDEOS, seed


async def count(session, table: str) -> int:
    return (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()


async def test_seed_inserts_expected_rows(session) -> None:
    await session.execute(text("TRUNCATE watch_progress, user_tokens, videos"))

    await seed(session)

    assert await count(session, "videos") == len(VIDEOS)
    assert await count(session, "user_tokens") == len(DEMO_TOKENS)
    assert await count(session, "watch_progress") == len(HISTORY)


async def test_seed_is_idempotent(session) -> None:
    await session.execute(text("TRUNCATE watch_progress, user_tokens, videos"))

    await seed(session)
    await seed(session)

    assert await count(session, "videos") == len(VIDEOS)
    assert await count(session, "watch_progress") == len(HISTORY)


async def test_tokens_are_stored_hashed(session) -> None:
    await seed(session)

    stored = (await session.execute(text("SELECT token_hash FROM user_tokens"))).scalars().all()

    assert not set(stored) & set(DEMO_TOKENS.values())
