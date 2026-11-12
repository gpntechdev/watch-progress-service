"""`seed-demo`: the catalogue, a few fixed users and a little watch history.

Runs in every environment. The demo tokens are public by design (docs/DESIGN.md section 11).
Safe to run more than once: existing rows are left alone.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from watch_progress_service.auth.tokens import hash_token
from watch_progress_service.config import load_config
from watch_progress_service.db import create_engine, create_session_factory

# Sources: https://github.com/video-commander/public-test-streams (MP4 section). Big Buck Bunny
# is CC-BY (Blender Foundation); flower.mp4 is CC0. Durations are read from the mp4 headers,
# rounded down to whole seconds.
# (video_id, title, url, duration_seconds)
VIDEOS = [
    (
        "big-buck-bunny",
        "Big Buck Bunny",
        "https://uploads.video-commander.com/sample/BigBuckBunny.mp4",
        596,
    ),
    (
        "bbb-clip-h264",
        "Big Buck Bunny, 10 s clip (H.264)",
        "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4",
        10,
    ),
    (
        "bbb-clip-av1",
        "Big Buck Bunny, 10 s clip (AV1)",
        "https://test-videos.co.uk/vids/bigbuckbunny/mp4/av1/360/Big_Buck_Bunny_360_10s_1MB.mp4",
        10,
    ),
    (
        "flower",
        "Flower",
        "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        5,
    ),
]

# user_id -> demo token
DEMO_TOKENS = {
    "alice": "demo-token-alice",
    "bob": "demo-token-bob",
    "carol": "demo-token-carol",
}

# (user_id, video_id, position_s, minutes_ago, finished, removed)
# Alice covers every case the "Continue watching" row must handle.
HISTORY = [
    ("alice", "big-buck-bunny", 120, 5, False, False),  # unfinished, most recent
    ("alice", "bbb-clip-h264", 4, 60, False, False),  # unfinished, older
    ("alice", "flower", 5, 30, True, False),  # finished (>= 90%): not in the row
    ("alice", "bbb-clip-av1", 3, 10, False, True),  # removed: not in the row
    ("bob", "big-buck-bunny", 100, 15, False, False),  # another user's row
]


async def seed(session: AsyncSession) -> None:
    """Insert the demo data. The caller commits."""
    duration = {video_id: seconds for video_id, _, _, seconds in VIDEOS}

    for video_id, title, url, seconds in VIDEOS:
        await session.execute(
            text(
                "INSERT INTO videos (video_id, title, url, duration_seconds) "
                "VALUES (:video_id, :title, :url, :seconds) ON CONFLICT DO NOTHING"
            ),
            {
                "video_id": video_id,
                "title": title,
                "url": url,
                "seconds": seconds,
            },
        )

    for user_id, token in DEMO_TOKENS.items():
        await session.execute(
            text(
                "INSERT INTO user_tokens (token_hash, user_id) "
                "VALUES (:token_hash, :user_id) ON CONFLICT DO NOTHING"
            ),
            {"token_hash": hash_token(token), "user_id": user_id},
        )

    for user_id, video_id, position, minutes_ago, finished, removed in HISTORY:
        await session.execute(
            text(
                "INSERT INTO watch_progress "
                "(user_id, video_id, position_s, duration_s, event_time, session_id, "
                "finished, removed) "
                "VALUES (:user_id, :video_id, :position, :duration, "
                "now() - make_interval(mins => :minutes_ago), :session_id, :finished, :removed) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "user_id": user_id,
                "video_id": video_id,
                "position": position,
                "duration": duration[video_id],
                "minutes_ago": minutes_ago,
                "session_id": f"seed-{user_id}-{video_id}",
                "finished": finished,
                "removed": removed,
            },
        )


async def run() -> None:
    engine = create_engine(load_config().database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        await seed(session)
    await engine.dispose()


def main() -> None:
    asyncio.run(run())
    print("Seeded demo data. Demo tokens:", ", ".join(DEMO_TOKENS.values()))
