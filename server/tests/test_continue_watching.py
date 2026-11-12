import base64
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from watch_progress_service.catalog import load_videos
from watch_progress_service.continue_watching import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    InvalidArgumentError,
    clamp_page_size,
    list_continue_watching,
)
from watch_progress_service.seed import seed

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def add(session, user, video, minutes_ago=0, position=1, finished=False, removed=False):
    await session.execute(
        text(
            "INSERT INTO watch_progress (user_id, video_id, position_s, duration_s, event_time, "
            "session_id, finished, removed) VALUES (:user, :video, :position, 1, :time, 's', "
            ":finished, :removed)"
        ),
        {
            "user": user,
            "video": video,
            "position": position,
            "time": T0 - timedelta(minutes=minutes_ago),
            "finished": finished,
            "removed": removed,
        },
    )


@pytest.fixture
async def videos(session):
    """The seeded catalogue, with an empty watch_progress table (rolled back after the test)."""
    await session.execute(text("TRUNCATE watch_progress, user_tokens, videos"))
    await seed(session)
    await session.execute(text("TRUNCATE watch_progress"))
    return await load_videos(session)


async def row(session, videos, user="alice", page_size=0, page_token=""):
    return await list_continue_watching(session, videos, user, page_size, page_token)


async def test_newest_first_and_only_unfinished_unremoved_rows_of_the_caller(session, videos):
    await add(session, "alice", "bbb-clip-h264", minutes_ago=60)
    await add(session, "alice", "big-buck-bunny", minutes_ago=5)
    await add(session, "alice", "flower", minutes_ago=1, finished=True)
    await add(session, "alice", "bbb-clip-av1", minutes_ago=2, removed=True)
    await add(session, "bob", "flower", minutes_ago=3)

    page = await row(session, videos)

    assert [item.video_id for item in page.items] == ["big-buck-bunny", "bbb-clip-h264"]
    assert page.next_page_token == ""


async def test_items_carry_catalogue_data_and_position(session, videos):
    await add(session, "alice", "big-buck-bunny", minutes_ago=5, position=120)

    (item,) = (await row(session, videos)).items

    assert item.title == "Big Buck Bunny"
    assert item.url == videos["big-buck-bunny"].url
    assert item.position_seconds == 120
    assert item.duration_seconds == 596
    assert item.last_watched == T0 - timedelta(minutes=5)


async def test_empty_row(session, videos):
    page = await row(session, videos, user="nobody")

    assert page.items == []
    assert page.next_page_token == ""


async def test_pages_walk_the_whole_row_without_gaps_or_repeats(session, videos):
    for minutes_ago, video in enumerate(["big-buck-bunny", "bbb-clip-h264", "bbb-clip-av1"]):
        await add(session, "alice", video, minutes_ago=minutes_ago)

    first = await row(session, videos, page_size=1)
    second = await row(session, videos, page_size=1, page_token=first.next_page_token)
    third = await row(session, videos, page_size=1, page_token=second.next_page_token)

    assert [p.items[0].video_id for p in (first, second, third)] == [
        "big-buck-bunny",
        "bbb-clip-h264",
        "bbb-clip-av1",
    ]
    assert first.next_page_token and second.next_page_token
    assert third.next_page_token == ""  # last page


async def test_page_that_exactly_fits_has_no_next_page(session, videos):
    await add(session, "alice", "big-buck-bunny", minutes_ago=1)
    await add(session, "alice", "flower", minutes_ago=2)

    page = await row(session, videos, page_size=2)

    assert len(page.items) == 2
    assert page.next_page_token == ""


async def test_equal_event_times_are_ordered_by_video_id_and_page_boundary_is_exact(
    session, videos
):
    for video in ["flower", "bbb-clip-h264", "bbb-clip-av1"]:
        await add(session, "alice", video, minutes_ago=0)  # all the same event_time

    first = await row(session, videos, page_size=2)
    second = await row(session, videos, page_size=2, page_token=first.next_page_token)

    assert [i.video_id for i in first.items] == ["bbb-clip-av1", "bbb-clip-h264"]
    assert [i.video_id for i in second.items] == ["flower"]


def test_page_size_rules():
    assert clamp_page_size(0) == DEFAULT_PAGE_SIZE == 25
    assert clamp_page_size(10) == 10
    assert clamp_page_size(MAX_PAGE_SIZE) == 100
    assert clamp_page_size(1000) == 100
    with pytest.raises(InvalidArgumentError):
        clamp_page_size(-1)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        base64.urlsafe_b64encode(b"not json").decode(),
        base64.urlsafe_b64encode(b'["only-one-item"]').decode(),
        base64.urlsafe_b64encode(b'["not-a-date", "flower"]').decode(),
    ],
)
async def test_malformed_page_token_is_invalid(session, videos, token):
    with pytest.raises(InvalidArgumentError):
        await row(session, videos, page_token=token)


async def test_negative_page_size_is_invalid(session, videos):
    with pytest.raises(InvalidArgumentError):
        await row(session, videos, page_size=-5)
