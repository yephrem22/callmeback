"""Placeholder MCP service from spec 002 (cloud-infra); spec 008 replaces this file.

Keeps the edge contract honest before the real FastMCP server exists (PLAN.md §5, §16.5):
- refuses to start when MCP_TOKEN is shorter than 32 characters;
- 403 when the Host header is not in MCP_ALLOWED_HOSTS;
- 401 on /mcp* without `Authorization: Bearer <MCP_TOKEN>`;
- 200 {"placeholder": true} with the right token; 404 elsewhere.
Raw ASGI so the image needs nothing beyond uvicorn.
"""
from __future__ import annotations

import json
import logging
import os
import sys

log = logging.getLogger("mcp")
MIN_TOKEN_LEN = 32


def _settings() -> tuple[str, set[str], int]:
    token = os.environ.get("MCP_TOKEN", "")
    hosts = {h.strip().lower() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()}
    port = int(os.environ.get("MCP_PORT", "8001"))
    return token, hosts, port


async def _send(send, status: int, body: dict, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    raw = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]
                + (headers or [])})
    await send({"type": "http.response.body", "body": raw})


async def app(scope, receive, send) -> None:
    if scope["type"] != "http":
        return
    token, hosts, _ = _settings()
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    host = headers.get("host", "").split(":")[0].lower()
    path = scope.get("path", "")
    if hosts and host not in hosts:
        log.warning(json.dumps({"event": "mcp_host_rejected", "host": host}))
        await _send(send, 403, {"error": "host not allowed"})
        return
    if not path.startswith("/mcp"):
        await _send(send, 404, {"error": "not found"})
        return
    auth = headers.get("authorization", "")
    if auth != f"Bearer {token}":
        await _send(send, 401, {"error": "unauthorized"}, [(b"www-authenticate", b"Bearer")])
        return
    await _send(send, 200, {"placeholder": True, "note": "spec 008 replaces this service"})


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    token, hosts, port = _settings()
    if len(token) < MIN_TOKEN_LEN:
        print(f"MCP_TOKEN must be {MIN_TOKEN_LEN}+ characters; refusing to start (PLAN.md §16.5)", file=sys.stderr)
        return 1
    import uvicorn
    log.info(json.dumps({"event": "mcp_placeholder_start", "port": port, "allowed_hosts": sorted(hosts)}))
    uvicorn.run("mcp_server.server:app", host="0.0.0.0", port=port, workers=1, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
