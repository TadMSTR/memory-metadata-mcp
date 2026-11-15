#!/usr/bin/env python3
"""
memory-metadata-mcp — read-only MCP server exposing SQLite metadata index
for ~/.claude/memory/ notes.

Provides list_notes, get_note_metadata, and count_by tools.
All SQL queries use parameterized statements; no f-string injection.

Runs on 127.0.0.1:8490 via streamable-http transport.
"""

import ipaddress
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP
from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings
from starlette.middleware import Middleware
from starlette.requests import HTTPConnection

DB_PATH = Path(
    os.environ.get("MEMORY_METADATA_DB", str(Path.home() / ".claude/memory/.metadata.db"))
)


def _configure_logging() -> None:
    """Configure structlog for JSON output at the level given by LOG_LEVEL."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger("memory-metadata-mcp")

mcp = FastMCP(
    "memory-metadata-mcp",
    instructions=(
        "Read-only metadata index for ~/.claude/memory/ notes. "
        "Query by category, tier, tag, date ranges, or agent. "
        "Returns file metadata only — no body content."
    ),
)

ALLOWED_COUNT_FIELDS = {"category", "tier", "source", "owner_agent"}


def _connect() -> sqlite3.Connection:
    """Open the index read-only (vikunja#1274).

    ``mode=ro`` makes a write fail at the connection rather than relying on the tool set
    having none, and a missing DB raises instead of being created empty. ``as_uri()``
    percent-encodes the path, so a ``?`` or ``#`` in it cannot become a URI parameter.
    """
    uri = DB_PATH.absolute().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@mcp.tool
def list_notes(
    category: str | None = None,
    tier: str | None = None,
    tag: str | None = None,
    created_after: str | None = None,
    expires_before: str | None = None,
    owner_agent: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    List memory notes matching the given filters.

    Args:
        category: Filter by category (e.g. 'design-document', 'transient-finding')
        tier: Filter by tier (e.g. 'working', 'durable', 'distilled')
        tag: Filter to notes that include this tag
        created_after: ISO date string — only notes created on or after this date
        expires_before: ISO date — only notes expiring on/before this date (excludes 'never')
        owner_agent: Filter by owner_agent field
        limit: Max rows to return (default 50, max 500)
    """
    limit = min(max(1, limit), 500)

    conditions: list[str] = []
    params: list[Any] = []

    if category is not None:
        conditions.append("n.category = ?")
        params.append(category)
    if tier is not None:
        conditions.append("n.tier = ?")
        params.append(tier)
    if tag is not None:
        conditions.append("EXISTS (SELECT 1 FROM note_tags t WHERE t.path = n.path AND t.tag = ?)")
        params.append(tag)
    if created_after is not None:
        conditions.append("n.created >= ?")
        params.append(created_after)
    if expires_before is not None:
        conditions.append("n.expires != 'never' AND n.expires <= ?")
        params.append(expires_before)
    if owner_agent is not None:
        conditions.append("n.owner_agent = ?")
        params.append(owner_agent)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT n.path, n.filename, n.tier, n.category, n.source,
               n.created, n.expires, n.owner_agent, n.body_size, n.last_indexed_at
        FROM notes n
        {where}
        ORDER BY n.created DESC
        LIMIT ?
    """
    params.append(limit)

    with _connect() as con:
        rows = con.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


@mcp.tool
def get_note_metadata(path: str) -> dict[str, Any]:
    """
    Return full metadata for a single note by its absolute path.

    Returns {"ok": False, "error": "not found"} if the note is not in the index.
    """
    sql = """
        SELECT n.path, n.filename, n.tier, n.category, n.source,
               n.created, n.expires, n.archived_at, n.owner_agent,
               n.body_size, n.file_sha, n.last_indexed_at
        FROM notes n
        WHERE n.path = ?
    """
    tag_sql = "SELECT tag FROM note_tags WHERE path = ? ORDER BY tag"

    with _connect() as con:
        row = con.execute(sql, (path,)).fetchone()
        if row is None:
            return {"ok": False, "error": "not found"}
        result = dict(row)
        tags = [r[0] for r in con.execute(tag_sql, (path,)).fetchall()]
        result["tags"] = tags

    return result


@mcp.tool
def count_by(
    field: str,
    category: str | None = None,
    tier: str | None = None,
) -> dict[str, int]:
    """
    Return a count breakdown grouped by the given field.

    Args:
        field: Field to group by — one of: category, tier, source, owner_agent
        category: Optional category filter applied before grouping
        tier: Optional tier filter applied before grouping
    """
    if field not in ALLOWED_COUNT_FIELDS:
        raise ValueError(f"field must be one of {sorted(ALLOWED_COUNT_FIELDS)}, got {field!r}")

    conditions: list[str] = []
    params: list[Any] = []

    if category is not None:
        conditions.append("category = ?")
        params.append(category)
    if tier is not None:
        conditions.append("tier = ?")
        params.append(tier)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    # field is validated against ALLOWED_COUNT_FIELDS allowlist above
    sql = f"SELECT {field}, COUNT(*) as cnt FROM notes {where} GROUP BY {field} ORDER BY cnt DESC"

    with _connect() as con:
        rows = con.execute(sql, params).fetchall()

    return {row[0] if row[0] is not None else "(null)": row[1] for row in rows}


_NON_LOOPBACK_OPT_IN = "MEMORY_METADATA_ALLOW_NON_LOOPBACK"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_bind_host(host: str) -> None:
    """Refuse a non-loopback bind unless the operator opted in (vikunja#1274).

    The server has no authentication, so a non-loopback bind serves the index to anyone
    who can reach the port. An opt-in exists for a deployment that puts its own access
    control in front.
    """
    if _is_loopback(host):
        return
    if os.environ.get(_NON_LOOPBACK_OPT_IN, "").strip().lower() in ("1", "true", "yes"):
        log.warning("non_loopback_bind", host=host, opt_in=_NON_LOOPBACK_OPT_IN)
        return
    raise SystemExit(
        f"memory-metadata-mcp: refusing to bind {host[:64]!r}: not a loopback address. "
        f"The server has no authentication. Set {_NON_LOOPBACK_OPT_IN}=1 to allow it."
    )


# DNS-rebinding protection (NE-22). A loopback bind is not isolation from a browser on the
# same host: a page whose name rebinds to 127.0.0.1 is same-origin with this server. So a
# request whose Host is not a loopback name (any port) or the bound address is refused
# (421), and so is any request carrying an Origin (403): no browser is a legitimate client.
# FastMCP builds its transport with mcp's own check switched off, so mcp's check is applied
# here as a Starlette middleware handed to mcp.run().
_LOOPBACK_NAMES = ("127.0.0.1", "localhost", "[::1]")
_ALLOWED_HOSTS_ENV_VAR = "MEMORY_METADATA_ALLOWED_HOSTS"


def _transport_security_settings(
    env: dict | None = None, bind_host: str | None = None
) -> TransportSecuritySettings:
    """Loopback names on any port, the bound host, and exact MEMORY_METADATA_ALLOWED_HOSTS.

    `name:*` is mcp's wildcard and a prefix match (`startswith(name + ":")`), so
    `localhost:8490.evil.example` passes too. No browser can send that (a URL port is
    digits), so it does not reopen DNS rebinding. Extra entries must be exact `host:port`:
    one containing `*` raises ValueError, and main() refuses to start.
    """
    env = os.environ if env is None else env
    names = list(_LOOPBACK_NAMES)
    if bind_host is not None:
        literal = f"[{bind_host.split('%')[0]}]" if ":" in bind_host else bind_host
        if literal not in names:
            names.append(literal)
    extras = [h.strip() for h in env.get(_ALLOWED_HOSTS_ENV_VAR, "").split(",") if h.strip()]
    if any("*" in h for h in extras):
        raise ValueError(
            f"{_ALLOWED_HOSTS_ENV_VAR} entries must be exact host:port values; "
            "an entry contains '*', which mcp would treat as a wildcard"
        )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"{name}:*" for name in names] + extras,
        allowed_origins=[],
    )


class HostOriginGuard:
    """ASGI middleware: refuse a request whose Host or Origin is not allowed.

    The refusal is mcp's own (421 for Host, 403 for Origin). The header values are never
    logged: they are caller-controlled and unbounded.
    """

    def __init__(self, app, settings: TransportSecuritySettings):
        self.app = app
        self.check = TransportSecurityMiddleware(settings)
        # mcp logs each refusal with the raw header value; this class logs it without.
        logging.getLogger("mcp.server.transport_security").setLevel(logging.ERROR)

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            refusal = await self.check.validate_request(HTTPConnection(scope), is_post=False)
            if refusal is not None:
                log.warning("http_request_refused", status=refusal.status_code, scope=scope["type"])
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await refusal(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _http_middleware(bind_host: str | None = None) -> list[Middleware]:
    return [Middleware(HostOriginGuard, settings=_transport_security_settings(bind_host=bind_host))]


def main() -> None:
    """Console entry point — start the streamable-http MCP server."""
    _configure_logging()
    host = os.environ.get("MEMORY_METADATA_HOST", "127.0.0.1")
    _check_bind_host(host)
    try:
        middleware = _http_middleware(bind_host=host)
    except ValueError as e:
        raise SystemExit(f"memory-metadata-mcp: refusing to start: {e}") from None
    port = int(os.environ.get("MEMORY_METADATA_PORT", "8490"))
    log.info("starting", host=host, port=port, db_path=str(DB_PATH))
    mcp.run(transport="streamable-http", host=host, port=port, middleware=middleware)


if __name__ == "__main__":
    main()
