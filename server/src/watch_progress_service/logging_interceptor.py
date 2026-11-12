"""Logs one structured line per RPC: method, user, status and duration. Never the token."""

import asyncio
import logging
import time

import grpc

from watch_progress_service.auth.interceptor import PUBLIC_PREFIXES, current_user
from watch_progress_service.handlers import replace_behavior

log = logging.getLogger("watch_progress_service.rpc")


class LoggingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        handler = await continuation(handler_call_details)
        method = handler_call_details.method
        # Health probes and reflection are frequent and uninteresting: not logged.
        if handler is None or method.startswith(PUBLIC_PREFIXES):
            return handler

        def wrap(inner):
            async def run(request, context):
                start = time.perf_counter()
                code = grpc.StatusCode.OK
                try:
                    return await inner(request, context)
                except asyncio.CancelledError:
                    code = grpc.StatusCode.CANCELLED
                    raise
                except BaseException:
                    # context.abort(...) sets the code before raising; anything else is a bug.
                    code = context.code() or grpc.StatusCode.UNKNOWN
                    raise
                finally:
                    # current_user was set by the auth interceptor inside this same call.
                    log.info(
                        "rpc method=%s user=%s status=%s duration_ms=%.1f",
                        method,
                        current_user.get("-"),
                        code.name,
                        (time.perf_counter() - start) * 1000,
                    )

            return run

        return replace_behavior(handler, wrap)
