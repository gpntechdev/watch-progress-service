"""The gRPC servicer. Thin: it maps requests to the domain code and errors to status codes.

Only ListContinueWatching is implemented in Phase 1; the other RPCs answer UNIMPLEMENTED.
"""

import asyncio
import logging

import grpc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from watchprogress.v1 import watch_progress_pb2 as pb
from watchprogress.v1 import watch_progress_pb2_grpc as pb_grpc

from watch_progress_service.auth.interceptor import current_user
from watch_progress_service.catalog import Video
from watch_progress_service.continue_watching import (
    InvalidArgumentError,
    WatchedVideo,
    list_continue_watching,
)

log = logging.getLogger(__name__)

# Applied when the client sets no deadline (docs/DESIGN.md section 4).
DEFAULT_DEADLINE_SECONDS = 5.0


def to_proto(item: WatchedVideo) -> pb.VideoProgress:
    progress = pb.VideoProgress(
        video_id=item.video_id,
        title=item.title,
        url=item.url,
        position_seconds=item.position_seconds,
        duration_seconds=item.duration_seconds,
    )
    progress.last_watched.FromDatetime(item.last_watched)
    return progress


class WatchProgressServicer(pb_grpc.WatchProgressServiceServicer):
    def __init__(self, sessions: async_sessionmaker[AsyncSession], videos: dict[str, Video]):
        self._sessions = sessions
        self._videos = videos

    async def ListContinueWatching(self, request, context):
        user_id = current_user.get()  # from the auth metadata, never from the request
        timeout = context.time_remaining()
        if timeout is None:
            timeout = DEFAULT_DEADLINE_SECONDS
        try:
            async with asyncio.timeout(timeout), self._sessions() as session:
                page = await list_continue_watching(
                    session, self._videos, user_id, request.page_size, request.page_token
                )
        except InvalidArgumentError as error:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        except TimeoutError:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "deadline exceeded")
        except (OSError, SQLAlchemyError):
            log.exception("database error")
            await context.abort(grpc.StatusCode.UNAVAILABLE, "database unavailable")

        return pb.ListContinueWatchingResponse(
            items=[to_proto(item) for item in page.items],
            next_page_token=page.next_page_token,
        )
