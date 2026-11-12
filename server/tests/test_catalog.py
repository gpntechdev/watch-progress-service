from watch_progress_service.catalog import Video, load_videos
from watch_progress_service.seed import VIDEOS, seed


async def test_load_videos_returns_the_seeded_catalogue(session) -> None:
    await seed(session)

    videos = await load_videos(session)

    assert set(videos) == {video_id for video_id, *_ in VIDEOS}
    assert videos["flower"] == Video(
        video_id="flower",
        title="Flower",
        url="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        duration_seconds=5,
    )
