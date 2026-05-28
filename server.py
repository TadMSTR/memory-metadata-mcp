#!/usr/bin/env python3
"""
memory-metadata-mcp — read-only MCP server exposing SQLite metadata index
for ~/.claude/memory/ notes.

Provides list_notes, get_note_metadata, and count_by tools.
All SQL queries use parameterized statements; no f-string injection.

Runs on 127.0.0.1:8490 via streamable-http transport.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

DB_PATH = Path(os.environ.get("MEMORY_METADATA_DB", str(Path.home() / ".claude/memory/.metadata.db")))

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
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
        expires_before: ISO date string — only notes expiring on or before this date (excludes 'never')
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
        conditions.append(
            "EXISTS (SELECT 1 FROM note_tags t WHERE t.path = n.path AND t.tag = ?)"
        )
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
        raise ValueError(
            f"field must be one of {sorted(ALLOWED_COUNT_FIELDS)}, got {field!r}"
        )

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


if __name__ == "__main__":
    host = os.environ.get("MEMORY_METADATA_HOST", "127.0.0.1")
    port = int(os.environ.get("MEMORY_METADATA_PORT", "8490"))
    mcp.run(transport="streamable-http", host=host, port=port)
