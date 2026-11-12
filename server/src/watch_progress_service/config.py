"""Server settings, read from environment variables (defaults match .env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    redis_url: str  # not used until Phase 2
    port: int


def load_config() -> Config:
    return Config(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://watch:watch@127.0.0.1:5432/watchprogress",
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        port=int(os.environ.get("PORT", "50051")),
    )
