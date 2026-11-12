"""Helper shared by interceptors that wrap an RPC handler's function."""


def replace_behavior(handler, wrap):
    """Copy of `handler` whose function is `wrap(original_function)`.

    Handles the two kinds this service has: unary-unary (most RPCs) and
    stream-unary (StreamProgress). Anything else is returned unchanged.
    """
    if handler.unary_unary:
        return handler._replace(unary_unary=wrap(handler.unary_unary))
    if handler.stream_unary:
        return handler._replace(stream_unary=wrap(handler.stream_unary))
    return handler
