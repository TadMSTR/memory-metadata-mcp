# Architecture

`memory-metadata-mcp` is a small, read-only FastMCP server that exposes structured
metadata queries over a SQLite index of Claude Code memory notes.

## Components

```
src/memory_metadata_mcp/
  __init__.py        # package version
  server.py          # FastMCP app, tools, logging, main() entry point
```

- **Transport:** streamable-HTTP, bound to `127.0.0.1:8490` (loopback only).
- **Framework:** FastMCP (`fastmcp>=3.2.4,<4`).
- **Logging:** `structlog`, JSON output, level from `LOG_LEVEL`.

## Data source

The server opens a read-only connection to the SQLite index at
`~/.claude/memory/.metadata.db` (override with `MEMORY_METADATA_DB`). The index is
populated and incrementally updated out-of-band by the memory pipeline — this server
never writes to it.

Schema (relevant columns):

- `notes(path, filename, tier, category, source, created, expires, archived_at,
  owner_agent, body_size, file_sha, last_indexed_at)`
- `note_tags(path, tag)`

## Tools

| Tool | Reads | Notes |
|------|-------|-------|
| `list_notes` | `notes` (+ `note_tags` for tag filter) | Filter by category/tier/tag/date/owner; `limit` clamped to 1–500 |
| `get_note_metadata` | `notes` + `note_tags` | Full row for one path, plus its tags |
| `count_by` | `notes` | Aggregate count grouped by an allowlisted field |

## Security model

- **Read-only** — no write, delete, or schema-modification tools.
- **Loopback-only** — binds to `127.0.0.1`; no Docker-network or external exposure.
- **Parameterized SQL** — all values use `?` placeholders.
- **`count_by` allowlist** — the `field` argument (the only interpolated identifier)
  is validated against `ALLOWED_COUNT_FIELDS` before it reaches the `GROUP BY`.

## Deployment

Runs as a PM2 process from `ecosystem.config.js` using the console entry point
`memory-metadata-mcp` (`memory_metadata_mcp.server:main`) out of the
`/opt/venvs/memory-metadata-mcp` virtualenv.
