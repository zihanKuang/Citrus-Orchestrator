"""Streamable HTTP transport for the MCP server (Starlette + uvicorn)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable

from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Route

from .auth import is_authorized

logger = logging.getLogger(__name__)


def _expected_token() -> str:
    return os.getenv("MCP_AUTH_TOKEN", "")


async def health(_: Any) -> Any:
    from starlette.responses import PlainTextResponse

    return PlainTextResponse("ok")


class BearerAuthASGI:
    """Reject requests without a valid Bearer token before hitting MCP."""

    def __init__(self, app: Any, expected_token_getter: Callable[[], str]):
        self.app = app
        self.expected_token_getter = expected_token_getter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth_header = None
        for k, v in scope.get("headers", []):
            if k == b"authorization":
                auth_header = v.decode("latin-1")
                break

        if not is_authorized(auth_header, self.expected_token_getter()):
            body = b'{"error":"unauthorized"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


def build_starlette_app(mcp_server: Any) -> Any:
    """Expose /health (public) and /mcp (auth required)."""
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=True,
        stateless=True,
    )
    mcp_asgi = StreamableHTTPASGIApp(session_manager)
    protected = BearerAuthASGI(mcp_asgi, _expected_token)

    @asynccontextmanager
    async def lifespan(_app):
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/mcp", protected),
        ],
        lifespan=lifespan,
    )


async def run_streamable_http(
    mcp_server: Any,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    import uvicorn

    app = build_starlette_app(mcp_server)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
