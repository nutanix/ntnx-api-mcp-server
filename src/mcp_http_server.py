"""MCP streamable HTTP runtime server entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator

import uvicorn
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Message, Receive, Scope, Send

from src.config import Settings
from src.mcp_stdio_server import build_mcp_server

DEFAULT_MCP_PROTOCOL_VERSION = "2025-06-18"


async def _health(_request) -> JSONResponse:
    return JSONResponse({"ok": True})


def _normalize_initialize_payload(payload: object) -> bool:
    """Accept NAI's initialize probe when it omits protocolVersion."""
    if not isinstance(payload, dict):
        return False
    if payload.get("method") != "initialize":
        return False
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}
        payload["params"] = params
    if params.get("protocolVersion"):
        return False
    params["protocolVersion"] = DEFAULT_MCP_PROTOCOL_VERSION
    return True


class InitializeProtocolVersionCompatApp:
    """ASGI wrapper that normalizes a known NAI initialize probe shape."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        next_body = body
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None

        if _normalize_initialize_payload(payload):
            next_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers = [
                (name, value)
                for name, value in scope.get("headers", [])
                if name.lower() != b"content-length"
            ]
            headers.append((b"content-length", str(len(next_body)).encode("ascii")))
            scope = {**scope, "headers": headers}

        sent = False

        async def replay_receive() -> Message:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": next_body, "more_body": False}

        await self.app(scope, replay_receive, send)


def _build_app(settings: Settings) -> Starlette:
    mcp_server = build_mcp_server(settings)
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        stateless=True,
    )
    mcp_app = InitializeProtocolVersionCompatApp(StreamableHTTPASGIApp(session_manager))

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", endpoint=_health, methods=["GET"]),
            Route("/mcp", endpoint=mcp_app),
            Route("/", endpoint=mcp_app),
        ],
        lifespan=lifespan,
    )


def serve_http(settings: Settings) -> None:
    """Run the MCP streamable HTTP server."""
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("MCP_HTTP_PORT", "8080")))
    app = _build_app(settings)
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
