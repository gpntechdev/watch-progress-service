"""Auth interceptor: maps the `authorization` token to a user ID before a handler runs.

The user ID reaches the handler through `current_user`, never through the request body
(docs/DESIGN.md section 4). For streams the token is checked once, when the stream opens.
"""

from contextvars import ContextVar

import grpc

from watch_progress_service.auth.tokens import find_user
from watch_progress_service.handlers import replace_behavior

# Set by the interceptor just before the handler runs; read it with `current_user.get()`.
current_user: ContextVar[str] = ContextVar("current_user")

# Health checks and reflection need no token (probes, `grpcurl list`).
PUBLIC_PREFIXES = (
    "/grpc.health.v1.Health/",
    "/grpc.reflection.v1.ServerReflection/",
    "/grpc.reflection.v1alpha.ServerReflection/",
)


def _bearer_token(metadata) -> str | None:
    """The token from an `authorization: Bearer <token>` header, or None."""
    for key, value in metadata or ():
        if key == "authorization":
            scheme, _, token = value.partition(" ")
            if scheme.lower() == "bearer" and token:
                return token
    return None


class AuthInterceptor(grpc.aio.ServerInterceptor):
    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = tokens  # {token_hash: user_id}, loaded at startup

    async def intercept_service(self, continuation, handler_call_details):
        handler = await continuation(handler_call_details)
        if handler is None or handler_call_details.method.startswith(PUBLIC_PREFIXES):
            return handler  # unknown method (gRPC answers UNIMPLEMENTED) or a public one

        token = _bearer_token(handler_call_details.invocation_metadata)
        user_id = find_user(self._tokens, token) if token else None

        if user_id is None:
            # Same kind of handler as the real one, so unary and stream calls both get
            # a clean UNAUTHENTICATED instead of a protocol error.
            def reject(_inner):
                async def abort(_request, context):
                    await context.abort(grpc.StatusCode.UNAUTHENTICATED, "missing or unknown token")

                return abort

            return replace_behavior(handler, reject)

        def with_user(inner):
            async def run(request, context):
                current_user.set(user_id)
                return await inner(request, context)

            return run

        return replace_behavior(handler, with_user)
