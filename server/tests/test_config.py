from watch_progress_service.config import load_config


def test_defaults(monkeypatch) -> None:
    for name in ("DATABASE_URL", "REDIS_URL", "PORT"):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.database_url.startswith("postgresql+asyncpg://")
    assert config.redis_url == "redis://127.0.0.1:6379/0"
    assert config.port == 50051


def test_environment_overrides_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    monkeypatch.setenv("PORT", "9000")

    config = load_config()

    assert config.database_url == "postgresql+asyncpg://u:p@db:5432/x"
    assert config.port == 9000
