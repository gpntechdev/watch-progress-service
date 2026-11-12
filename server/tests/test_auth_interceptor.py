import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from watchprogress.v1 import watch_progress_pb2 as pb
from watchprogress.v1 import watch_progress_pb2_grpc as pb_grpc

from watch_progress_service.auth.interceptor import AuthInterceptor, current_user
from watch_progress_service.auth.tokens import hash_token


class FakeService(pb_grpc.WatchProgressServiceServicer):
    """Answers with the user the interceptor found, so tests can see what the handler got."""

    async def ListContinueWatching(self, request, context):
        return pb.ListContinueWatchingResponse(next_page_token=current_user.get())

    async def StreamProgress(self, request_iterator, context):
        count = 0
        async for _ in request_iterator:
            count += 1
        return pb.StreamProgressSummary(events_accepted=count)


@pytest.fixture
async def channel():
    tokens = {hash_token("alice-token"): "alice", hash_token("bob-token"): "bob"}
    server = grpc.aio.server(interceptors=[AuthInterceptor(tokens)])
    pb_grpc.add_WatchProgressServiceServicer_to_server(FakeService(), server)
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        yield channel
    await server.stop(None)


def bearer(token: str):
    return (("authorization", f"Bearer {token}"),)


async def list_row(channel, metadata=None):
    stub = pb_grpc.WatchProgressServiceStub(channel)
    return await stub.ListContinueWatching(
        pb.ListContinueWatchingRequest(), metadata=metadata, timeout=5
    )


async def test_valid_token_reaches_handler_with_the_users_id(channel) -> None:
    assert (await list_row(channel, bearer("alice-token"))).next_page_token == "alice"
    assert (await list_row(channel, bearer("bob-token"))).next_page_token == "bob"


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        bearer("wrong-token"),
        (("authorization", "alice-token"),),  # no "Bearer" scheme
        (("authorization", "Bearer "),),  # empty token
    ],
)
async def test_missing_or_bad_token_is_unauthenticated(channel, metadata) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await list_row(channel, metadata)

    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_scheme_is_case_insensitive(channel) -> None:
    metadata = (("authorization", "bearer alice-token"),)

    assert (await list_row(channel, metadata)).next_page_token == "alice"


async def test_stream_is_checked_once_when_it_opens(channel) -> None:
    stub = pb_grpc.WatchProgressServiceStub(channel)

    async def events():
        for _ in range(3):
            yield pb.ProgressEvent(video_id="flower")

    summary = await stub.StreamProgress(events(), metadata=bearer("alice-token"), timeout=5)
    assert summary.events_accepted == 3

    with pytest.raises(grpc.aio.AioRpcError) as error:
        await stub.StreamProgress(events(), timeout=5)
    assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_health_check_needs_no_token(channel) -> None:
    stub = health_pb2_grpc.HealthStub(channel)

    response = await stub.Check(health_pb2.HealthCheckRequest(), timeout=5)

    assert response.status == health_pb2.HealthCheckResponse.SERVING
