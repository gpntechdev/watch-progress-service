"""The "Continue watching" row, read from PostgreSQL (docs/DESIGN.md section 7).

Phase 1 reads PostgreSQL only; Phase 2 merges in Redis. No gRPC code here, so it can be
tested without a server.
"""

import base64
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from watch_progress_service.catalog import Video

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class InvalidArgumentError(ValueError):
    """A bad page_size or page_token. The servicer maps this to INVALID_ARGUMENT."""


@dataclass(frozen=True)
class WatchedVideo:
    video_id: str
    title: str
    url: str
    position_seconds: int
    duration_seconds: int
    last_watched: datetime


@dataclass(frozen=True)
class Page:
    items: list[WatchedVideo]
    next_page_token: str  # empty on the last page


def clamp_page_size(page_size: int) -> int:
    """0 (unset) means the default; larger than the maximum is reduced; negative is an error."""
    if page_size < 0:
        raise InvalidArgumentError("page_size must not be negative")
    if page_size == 0:
        return DEFAULT_PAGE_SIZE
    return min(page_size, MAX_PAGE_SIZE)


def encode_page_token(last_watched: datetime, video_id: str) -> str:
    """Opaque cursor: where the last returned item sits in the (event_time, video_id) order."""
    raw = json.dumps([last_watched.isoformat(), video_id])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_page_token(page_token: str) -> tuple[datetime, str]:
    try:
        last_watched, video_id = json.loads(base64.urlsafe_b64decode(page_token))
        return datetime.fromisoformat(last_watched), str(video_id)
    except (ValueError, TypeError):
        raise InvalidArgumentError("malformed page_token") from None


# Newest first, video_id as the tie-break, so the order is total and a page boundary is exact.
# The partial index (user_id, event_time DESC) serves the WHERE and the ORDER BY.
FIRST_PAGE_SQL = text(
    """
    SELECT video_id, position_s, event_time FROM watch_progress
    WHERE user_id = :user_id AND NOT finished AND NOT removed
    ORDER BY event_time DESC, video_id
    LIMIT :limit
    """
)
NEXT_PAGE_SQL = text(
    """
    SELECT video_id, position_s, event_time FROM watch_progress
    WHERE user_id = :user_id AND NOT finished AND NOT removed
      AND (event_time < :after_time OR (event_time = :after_time AND video_id > :after_video))
    ORDER BY event_time DESC, video_id
    LIMIT :limit
    """
)


async def list_continue_watching(
    session: AsyncSession,
    videos: dict[str, Video],
    user_id: str,
    page_size: int,
    page_token: str,
) -> Page:
    size = clamp_page_size(page_size)
    params = {"user_id": user_id, "limit": size + 1}  # one extra row tells us there is a next page
    if page_token:
        after_time, after_video = decode_page_token(page_token)
        params |= {"after_time": after_time, "after_video": after_video}
        rows = (await session.execute(NEXT_PAGE_SQL, params)).all()
    else:
        rows = (await session.execute(FIRST_PAGE_SQL, params)).all()

    has_more = len(rows) > size
    rows = rows[:size]

    items = []
    for row in rows:
        video = videos.get(row.video_id)
        if video is None:  # not in the catalogue loaded at startup (added since); skip it
            continue
        items.append(
            WatchedVideo(
                video_id=video.video_id,
                title=video.title,
                url=video.url,
                position_seconds=row.position_s,
                duration_seconds=video.duration_seconds,
                last_watched=row.event_time,
            )
        )

    next_page_token = ""
    if has_more and rows:
        last = rows[-1]
        next_page_token = encode_page_token(last.event_time, last.video_id)
    return Page(items=items, next_page_token=next_page_token)
