"""Server entry point: `python -m watch_progress_service.server`."""

import asyncio
import logging
import signal

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from watchprogress.v1 import watch_progress_pb2 as pb
from watchprogress.v1 import watch_progress_pb2_grpc as pb_grpc

from watch_progress_service.auth.interceptor import AuthInterceptor
from watch_progress_service.auth.tokens import load_tokens
from watch_progress_service.catalog import Video, load_videos
from watch_progress_service.config import Config, load_config
from watch_progress_service.db import create_engine, create_session_factory
from watch_progress_service.logging_interceptor import LoggingInterceptor
from watch_progress_service.servicer import WatchProgressServicer

log = logging.getLogger(__name__)

SERVICE_NAME = pb.DESCRIPTOR.services_by_name["WatchProgressService"].full_name


def build_server(
    tokens: dict[str, str],
    videos: dict[str, Video],
    sessions: async_sessionmaker[AsyncSession],
) -> grpc.aio.Server:
    """A server with every service registered, not yet bound to a port or started."""
    # The first interceptor is the outermost: logging sees the result of the auth check.
    server = grpc.aio.server(interceptors=[LoggingInterceptor(), AuthInterceptor(tokens)])
    pb_grpc.add_WatchProgressServiceServicer_to_server(
        WatchProgressServicer(sessions, videos), server
    )

    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)  # overall server health
    health_servicer.set(SERVICE_NAME, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    # Reflection lets grpcurl list and call methods without the .proto file.
    reflection.enable_server_reflection(
        (SERVICE_NAME, health.SERVICE_NAME, reflection.SERVICE_NAME), server
    )
    return server


async def serve(config: Config) -> None:
    engine = create_engine(config.database_url)
    sessions = create_session_factory(engine)
    async with sessions() as session:  # tokens and videos are read once, at startup
        tokens = await load_tokens(session)
        videos = await load_videos(session)
    log.info("loaded %d tokens and %d videos", len(tokens), len(videos))

    server = build_server(tokens, videos, sessions)
    server.add_insecure_port(f"[::]:{config.port}")
    await server.start()
    log.info("listening on port %d", config.port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    log.info("shutting down")
    await server.stop(grace=5)  # let in-flight calls finish
    await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(serve(load_config()))


if __name__ == "__main__":
    main()
