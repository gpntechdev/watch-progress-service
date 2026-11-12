import logging

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
from sqlalchemy import text
from watchprogress.v1 import watch_progress_pb2 as pb
from watchprogress.v1 import watch_progress_pb2_grpc as pb_grpc

from watch_progress_service import servicer
from watch_progress_service.auth.tokens import load_tokens
from watch_progress_service.catalog import load_videos
from watch_progress_service.seed import DEMO_TOKENS, seed
from watch_progress_service.server import SERVICE_NAME, build_server

ALICE = (("authorization", f"Bearer {DEMO_TOKENS['alice']}"),)


@pytest.fixture
async def channel(session_factory):
    """A real server (all interceptors and services) over the seeded, rolled-back database."""
    async with session_factory() as session:
        await session.execute(text("TRUNCATE watch_progress, user_tokens, videos"))
        await seed(session)
        tokens = await load_tokens(session)
        videos = await load_videos(session)
    server = build_server(tokens, videos, session_factory)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        yield channel
    await server.stop(None)


def stub(channel):
    return pb_grpc.WatchProgressServiceStub(channel)


async def test_list_returns_the_seeded_row_newest_first(channel) -> None:
    response = await stub(channel).ListContinueWatching(
        pb.ListContinueWatchingRequest(), metadata=ALICE, timeout=5
    )

    assert [item.video_id for item in response.items] == ["big-buck-bunny", "bbb-clip-h264"]
    first = response.items[0]
    assert (first.title, first.position_seconds, first.duration_seconds) == (
        "Big Buck Bunny",
        120,
        596,
    )
    assert first.last_watched.seconds > 0
    assert response.next_page_token == ""


async def test_pagination_through_the_api(channel) -> None:
    request = pb.ListContinueWatchingRequest(page_size=1)
    page1 = await stub(channel).ListContinueWatching(request, metadata=ALICE, timeout=5)
    request.page_token = page1.next_page_token
    page2 = await stub(channel).ListContinueWatching(request, metadata=ALICE, timeout=5)

    assert [i.video_id for i in page1.items] == ["big-buck-bunny"]
    assert [i.video_id for i in page2.items] == ["bbb-clip-h264"]
    assert page2.next_page_token == ""


async def test_each_user_gets_their_own_row(channel) -> None:
    bob = (("authorization", f"Bearer {DEMO_TOKENS['bob']}"),)

    response = await stub(channel).ListContinueWatching(
        pb.ListContinueWatchingRequest(), metadata=bob, timeout=5
    )

    assert [item.video_id for item in response.items] == ["big-buck-bunny"]
    assert response.items[0].position_seconds == 100


@pytest.mark.parametrize(
    "request_message",
    [
        pb.ListContinueWatchingRequest(page_size=-1),
        pb.ListContinueWatchingRequest(page_token="garbage"),
    ],
)
async def test_bad_arguments_are_invalid_argument(channel, request_message) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub(channel).ListContinueWatching(request_message, metadata=ALICE, timeout=5)

    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def test_no_token_is_unauthenticated(channel) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub(channel).ListContinueWatching(pb.ListContinueWatchingRequest(), timeout=5)

    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_rpcs_not_built_yet_are_unimplemented(channel) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub(channel).GetProgress(pb.GetProgressRequest(), metadata=ALICE, timeout=5)

    assert error.value.code() == grpc.StatusCode.UNIMPLEMENTED


async def test_default_deadline_applies_when_the_client_sets_none(channel, monkeypatch) -> None:
    async def too_slow(*args):
        import asyncio

        await asyncio.sleep(10)

    monkeypatch.setattr(servicer, "DEFAULT_DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(servicer, "list_continue_watching", too_slow)

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub(channel).ListContinueWatching(pb.ListContinueWatchingRequest(), metadata=ALICE)

    assert error.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


async def test_health_works_without_a_token(channel) -> None:
    health = health_pb2_grpc.HealthStub(channel)

    overall = await health.Check(health_pb2.HealthCheckRequest(), timeout=5)
    ours = await health.Check(health_pb2.HealthCheckRequest(service=SERVICE_NAME), timeout=5)

    assert overall.status == ours.status == health_pb2.HealthCheckResponse.SERVING


async def test_reflection_lists_our_service_without_a_token(channel) -> None:
    reflection = reflection_pb2_grpc.ServerReflectionStub(channel)

    async def requests():
        yield reflection_pb2.ServerReflectionRequest(list_services="")

    names = []
    async for response in reflection.ServerReflectionInfo(requests(), timeout=5):
        names += [s.name for s in response.list_services_response.service]

    assert SERVICE_NAME in names


async def test_each_rpc_is_logged_without_the_token(channel, caplog) -> None:
    caplog.set_level(logging.INFO, logger="watch_progress_service.rpc")

    await stub(channel).ListContinueWatching(
        pb.ListContinueWatchingRequest(), metadata=ALICE, timeout=5
    )
    with pytest.raises(grpc.aio.AioRpcError):
        await stub(channel).ListContinueWatching(pb.ListContinueWatchingRequest(), timeout=5)

    lines = [r.getMessage() for r in caplog.records]
    assert any("ListContinueWatching user=alice status=OK" in line for line in lines)
    assert any("user=- status=UNAUTHENTICATED" in line for line in lines)
    assert not any(DEMO_TOKENS["alice"] in line for line in lines)
