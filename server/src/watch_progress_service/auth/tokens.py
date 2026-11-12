"""Tokens: hashing, and the token-hash -> user-id map held in memory."""

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def hash_token(token: str) -> str:
    """Only the SHA-256 hash of a token is ever stored."""
    return hashlib.sha256(token.encode()).hexdigest()


async def load_tokens(session: AsyncSession) -> dict[str, str]:
    """Read `user_tokens` once, at startup. Returns {token_hash: user_id}."""
    rows = await session.execute(text("SELECT token_hash, user_id FROM user_tokens"))
    return {token_hash: user_id for token_hash, user_id in rows}


def find_user(tokens: dict[str, str], token: str) -> str | None:
    """The user a presented token belongs to, or None. No database call."""
    return tokens.get(hash_token(token))
