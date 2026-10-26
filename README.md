# memory-metadata-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Built with FastMCP](https://img.shields.io/badge/Built%20with-FastMCP-orange)](https://github.com/jlowin/fastmcp)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-enabled-blueviolet)](https://claude.ai/code)

Read-only MCP server exposing structured metadata queries over a SQLite index of Claude Code memory notes. Part of the [homelab-agent](https://github.com/TadMSTR/homelab-agent) memory lifecycle system.

## What It Does

Claude Code agents accumulate memory notes in `~/.claude/memory/`. This server makes that corpus queryable by metadata — filter by category, tier, tag, date range, or source agent without touching file contents.

Three tools:

| Tool | What It Does |
|------|-------------|
| `list_notes` | Filter notes by category, tier, tag, date range, or owner agent. Returns paths and metadata only — no body content. |
| `get_note_metadata` | Return full frontmatter metadata for a single note by absolute path, including its tag list. |
| `count_by` | Aggregate counts grouped by `category`, `tier`, `source`, or `owner_agent` — with optional pre-filters. |

## The Index

The server reads from a SQLite WAL-mode database at `~/.claude/memory/.metadata.db`. The index is populated by a companion indexer script and updated incrementally on each memory note write.

Each note record stores: `path`, `filename`, `tier`, `category`, `source`, `created`, `expires`, `owner_agent`, `body_size`, `file_sha`, `last_indexed_at`. Tags live in a separate `note_tags` table and are returned on `get_note_metadata` calls.

The six memory categories and their retention policies:

| Category | Expires |
|----------|---------|
| `transient-finding` | 90 days |
| `session-summary` | 30 days |
| `decision-record` | Never |
| `design-document` | Never |
| `research-finding-permanent` | Never |
| `competitive-snapshot` | Never |

## Transport

Streamable-HTTP on `127.0.0.1:8490` — host-local only, not exposed to Docker networks or external interfaces.

MCP endpoint: `http://127.0.0.1:8490/mcp`

## Setup

Dependencies are pinned in `uv.lock`. Install exactly that set with
[uv](https://docs.astral.sh/uv/):

```bash
uv sync --frozen --extra dev
source .venv/bin/activate
```

Run directly:

```bash
memory-metadata-mcp
# or, equivalently:
python -m memory_metadata_mcp.server
```

A committed `ecosystem.config.js` runs it under PM2 from the
`/opt/venvs/memory-metadata-mcp` virtualenv (`-m memory_metadata_mcp.server`,
host/port from the env block).

## Installation

memory-metadata-mcp is not published to PyPI. Install from a checkout of a release tag,
from the committed `uv.lock`, so the dependency set is the one CI tested and audited.

```bash
VERSION=0.4.0
VENV=/opt/venvs/memory-metadata-mcp

# 1. The checkout is clean and is exactly the release tag on the remote. A local tag
#    can be moved, and a dirty tree would be installed as it stands.
git fetch --tags origin
test -z "$(git status --porcelain)"
# The peeled line (^{}) is listed last for an annotated tag; a lightweight tag has one line.
test "$(git rev-parse HEAD)" = \
  "$(git ls-remote origin "refs/tags/v$VERSION" "refs/tags/v$VERSION^{}" | tail -n1 | cut -f1)"

# 2. Build a fresh venv at the path the service runs from. Pin the interpreter: uv
#    otherwise prefers a Python it manages itself, which `uv python` can later remove
#    or replace under a running service. --no-editable installs a copy of the package,
#    so the service does not follow later changes to the checkout.
UV_PROJECT_ENVIRONMENT=$VENV \
  uv sync --frozen --no-editable --python /usr/bin/python3.13

# 3. Confirm what was installed.
"$VENV/bin/python3" -c "import importlib.metadata as m, memory_metadata_mcp.server; print(m.version('memory-metadata-mcp'))"
```

Build a fresh venv rather than installing into an existing one. `pip install .` into an
existing venv keeps whatever older dependency versions it finds there, if they still
satisfy the declared ranges. Build at the final path rather than building elsewhere and
moving it: console-script shebangs embed the venv path. A uv-built venv has no `pip`.
Stop the service before replacing its venv, and restart it after step 3.

CI audits the locked set on every push and weekly, but nothing reads a scheduled run's
result unless you watch it. Audit the deployed venv where it runs as well (for example
`pip-audit --path <venv>/lib/python3.13/site-packages`).

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MEMORY_METADATA_HOST` | `127.0.0.1` | Bind address |
| `MEMORY_METADATA_PORT` | `8490` | Port |

The DB path is always `~/.claude/memory/.metadata.db` (resolved via `Path.home()`). If the database doesn't exist, the server starts but tool calls will fail until the indexer has run at least once.

## Security

- **Read-only** — no write, delete, or schema-modification tools
- **Loopback-only** — binds to `127.0.0.1` by default; no Docker network exposure
- **Parameterized SQL** — all queries use `?` placeholders; no f-string injection
- **`count_by` allowlist** — the `field` argument is validated against an explicit set before being interpolated into the GROUP BY clause

## Wiring to Claude Code

Add to your agent manifest or global MCP config:

```json
{
  "mcpServers": {
    "memory-metadata": {
      "type": "http",
      "url": "http://127.0.0.1:8490/mcp"
    }
  }
}
```

## Related

- [memory-search-mcp](https://github.com/TadMSTR/memory-search-mcp) — full-text body search over the same corpus via OpenSearch (personal-agent scoped)
- [homelab-agent](https://github.com/TadMSTR/homelab-agent) — full platform docs, including [memory-lifecycle](https://github.com/TadMSTR/homelab-agent/blob/main/docs/components/memory-lifecycle.md)

## License

MIT
