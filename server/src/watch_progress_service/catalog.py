"""The video catalogue, held in memory so validation needs no database call per request."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    url: str
    duration_seconds: int


async def load_videos(session: AsyncSession) -> dict[str, Video]:
    """Read `videos` once, at startup. Returns {video_id: Video}."""
    rows = await session.execute(text("SELECT video_id, title, url, duration_seconds FROM videos"))
    return {row.video_id: Video(*row) for row in rows}
