"""DNS-rebinding protection: the HTTP app refuses a non-loopback Host or any Origin.

These drive the real Starlette app FastMCP builds, with the middleware main() hands to
mcp.run, so a guard that is defined but never wired in fails here. The request is MCP
`initialize`, which reads nothing from the index. The control test builds the same app
without the middleware and shows the foreign Host is then served, so the refusal cases
cannot pass vacuously.
"""

import asyncio

import pytest
from starlette.testclient import TestClient

from memory_metadata_mcp import server

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}


def _post(middleware, **headers):
    app = server.mcp.http_app(path="/mcp", middleware=middleware)
    with TestClient(app) as c:
        return c.post("/mcp", json=INIT, headers={**HEADERS, **headers})


@pytest.fixture(autouse=True)
def _no_extra_hosts(monkeypatch):
    monkeypatch.delenv("MEMORY_METADATA_ALLOWED_HOSTS", raising=False)


@pytest.mark.parametrize("host", ["localhost:8490", "127.0.0.1:8490", "[::1]:8490", "127.0.0.1:1"])
def test_loopback_host_is_served(host):
    assert _post(server._http_middleware(), host=host).status_code == 200


@pytest.mark.parametrize(
    "host",
    ["evil.example", "evil.example:8490", "192.0.2.10:8490", "localhost.evil.example:8490"],
)
def test_foreign_host_is_refused(host):
    assert _post(server._http_middleware(), host=host).status_code == 421


def test_control_without_the_guard_a_foreign_host_is_served():
    assert _post([], host="evil.example:8490").status_code == 200


@pytest.mark.parametrize("origin", ["http://evil.example", "http://127.0.0.1:8490", "null"])
def test_any_origin_is_refused(origin):
    r = _post(server._http_middleware(), host="127.0.0.1:8490", origin=origin)
    assert r.status_code == 403


def test_bound_loopback_address_is_served():
    r = _post(server._http_middleware(bind_host="127.0.0.2"), host="127.0.0.2:8490")
    assert r.status_code == 200


def test_exact_extra_host_is_served(monkeypatch):
    monkeypatch.setenv("MEMORY_METADATA_ALLOWED_HOSTS", "mm.internal:8490")
    assert _post(server._http_middleware(), host="mm.internal:8490").status_code == 200
    assert _post(server._http_middleware(), host="mm.internal:9999").status_code == 421


def test_wildcard_extra_host_refuses_to_start(monkeypatch):
    monkeypatch.setattr(server.mcp, "run", lambda **kw: pytest.fail("must not start"))
    monkeypatch.setenv("MEMORY_METADATA_HOST", "127.0.0.1")
    monkeypatch.setenv("MEMORY_METADATA_ALLOWED_HOSTS", "*.internal:8490")
    with pytest.raises(SystemExit, match="refusing to start"):
        server.main()


def test_main_hands_the_guard_to_mcp_run(monkeypatch):
    seen = {}
    monkeypatch.setattr(server.mcp, "run", lambda **kw: seen.update(kw))
    monkeypatch.setenv("MEMORY_METADATA_HOST", "127.0.0.1")
    monkeypatch.delenv("MEMORY_METADATA_ALLOW_NON_LOOPBACK", raising=False)
    server.main()
    [mw] = seen["middleware"]
    assert mw.cls is server.HostOriginGuard


def test_websocket_with_a_foreign_host_is_closed_unserved():
    reached = []

    async def app(scope, receive, send):
        reached.append(scope["type"])

    guard = server.HostOriginGuard(app, server._transport_security_settings(env={}))
    sent = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "websocket",
        "path": "/mcp",
        "headers": [(b"host", b"evil.example")],
        "query_string": b"",
    }
    asyncio.run(guard(scope, receive, send))
    assert sent == [{"type": "websocket.close", "code": 1008}]
    assert reached == []


def test_lifespan_scope_passes_through():
    reached = []

    async def app(scope, receive, send):
        reached.append(scope["type"])

    guard = server.HostOriginGuard(app, server._transport_security_settings(env={}))
    asyncio.run(guard({"type": "lifespan"}, None, None))
    assert reached == ["lifespan"]
