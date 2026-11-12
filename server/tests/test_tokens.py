from watch_progress_service.auth.tokens import find_user, hash_token, load_tokens
from watch_progress_service.seed import DEMO_TOKENS, seed


def test_hash_is_deterministic_and_hides_the_token() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert "abc" not in hash_token("abc")
    assert len(hash_token("abc")) == 64  # hex SHA-256


def test_find_user() -> None:
    tokens = {hash_token("secret"): "alice"}

    assert find_user(tokens, "secret") == "alice"
    assert find_user(tokens, "wrong") is None
    assert find_user(tokens, "") is None


async def test_load_tokens_maps_every_demo_token(session) -> None:
    await seed(session)

    tokens = await load_tokens(session)

    for user_id, token in DEMO_TOKENS.items():
        assert find_user(tokens, token) == user_id
