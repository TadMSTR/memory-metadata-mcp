# memory-metadata-mcp

Read-only FastMCP server that exposes the SQLite metadata index for
`~/.claude/memory/` notes.

## Tools

- `list_notes(category, tier, tag, created_after, expires_before, owner_agent, limit)` — query notes by filter
- `get_note_metadata(path)` — full metadata for one note (includes tags)
- `count_by(field, category, tier)` — aggregation counts; field must be one of: category, tier, source, owner_agent

## Running

PM2 service: `memory-metadata-mcp`
Endpoint: `http://127.0.0.1:8490/mcp`
Transport: streamable-http

## DB

Index at `~/.claude/memory/.metadata.db` (SQLite WAL mode), overridable with
`MEMORY_METADATA_DB`. Populated by a companion indexer script that is not part of this
repo, and updated incrementally on each memory note write.

## Security

- Read-only: no write tools
- Binds to 127.0.0.1 by default (`MEMORY_METADATA_HOST`); the bind is not validated in code
- All SQL queries use parameterized statements
- `count_by` field validated against explicit allowlist
