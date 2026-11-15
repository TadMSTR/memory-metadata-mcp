# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.4.1] - 2026-11-15

### Security
- **The SQLite index is opened read-only** (vikunja#1274). The connection used to be
  read-write, so read-only was only a property of the tool set, and a missing database
  was created empty on the first call, which then failed with no `notes` table. It is
  now opened as `file:<path>?mode=ro` (the path percent-encoded, so a `?` in it cannot
  become a URI parameter): a write fails at the connection, and a missing database raises.
- **A non-loopback `MEMORY_METADATA_HOST` refuses to start** (vikunja#1274). The value
  went straight to `mcp.run`, and the server has no authentication. Loopback addresses and
  `localhost` are accepted; anything else needs `MEMORY_METADATA_ALLOW_NON_LOOPBACK=1`,
  which logs a warning.
- **Host/Origin check on the HTTP app** (DNS-rebinding protection). A loopback bind is not
  isolation from a browser page on the same host whose name rebinds to 127.0.0.1. A request
  whose `Host` is not a loopback name or the bound address (any port) now gets 421, and any
  request carrying an `Origin` gets 403, using the MCP SDK's own `TransportSecurityMiddleware`.
  The port part is a prefix match (`localhost:8490.evil.example` passes). No browser can send
  that Host, so DNS rebinding stays closed, but this is not access control against a
  non-browser client.
  `MEMORY_METADATA_ALLOWED_HOSTS` adds exact `host:port` values; an entry containing `*`
  refuses to start.
- Dependency floors for two advisories: `opentelemetry-api>=1.45.2` (CVE-2026-126360) and
  `dnspython>=2.9.2` (CVE-2026-128089). The lock moves dnspython 2.9.0 → 2.9.2 and
  opentelemetry-api 1.45.1 → 1.45.2.

### Changed
- `ecosystem.config.js` derives `cwd` and the log path instead of naming one host's paths.

## [0.4.0] - 2026-10-26

### Changed
- **Dependencies are locked.** `uv.lock` is committed and pins the full tested set; a
  deploy builds a fresh venv from it (`uv sync --frozen --no-editable`). CI installs from
  the lock as well, so a green run describes the set that ships.
- `requirements.txt` removed. It only repeated the `pyproject.toml` ranges, and nothing
  read it.

### Security
- Dependency floors: fastmcp 3.4.10, mcp 1.30, starlette 1.3.1, python-multipart 0.0.31,
  pyjwt 2.15.0, anyio 4.14.2, h11 0.16.0, opentelemetry-api 1.45.1. Floors cover every
  package a request reaches. Other runtime packages are held at fixed versions by
  `uv.lock`, and the `pyproject.toml` comment names them.
- The setuptools build backend is pinned (84.2.1), since `uv.lock` does not lock build
  dependencies.
- README "Installation": the deploy recipe checks that the checkout is the remote release
  tag, pins the interpreter, and reads the installed version back.
- CI audits the locked runtime and dev sets (`pip-audit --strict --locked`) in place of
  `pip-audit .` on the declared ranges. A `latest` job, gating and run weekly, tests the
  newest versions the ranges allow.
- `release.yml` uses the same `actions/checkout` pin as `ci.yml`.

## [0.3.0] - 2026-07-23

### Changed
- **Repo brought to the forge Python-MCP standard.** Migrated to a `src/memory_metadata_mcp/`
  layout with a console entry point (`memory-metadata-mcp` = `memory_metadata_mcp.server:main`).
  The PM2 launch changes to `-m memory_metadata_mcp.server` (see `ecosystem.config.js`);
  HTTP host/port (`127.0.0.1:8490`) are unchanged.
- Added `structlog` JSON logging (level via `LOG_LEVEL`).

### Added
- CI workflow (`.github/workflows/ci.yml`) — 3.11/3.12/3.13 matrix, SHA-pinned actions,
  `ruff check` + `ruff format --check` + `pytest --cov` (fail-under 80) + `pip-audit --strict`.
- `ruff` + coverage config in `pyproject.toml`; `.gitleaks.toml`; `CONTRIBUTING.md`;
  `ARCHITECTURE.md`; committed `ecosystem.config.js`.
- Tests for the `main()` entry point and logging config.

### Removed
- Unused `pyyaml` dependency (never imported by the server).

### Security
- Audit `memory-mcp-trio-repo-standard-2026-07` (2026-07-23): clean — no findings for this repo.

## [0.2.0] - 2026-05-28

### Added
- 16 tests covering `list_notes` (all filter combinations), `get_note_metadata` (found/not-found/no-tags), and `count_by` (valid/invalid field, with pre-filters). Tests use a real temp SQLite database for isolation.
- `pyproject.toml` with version field.

### Changed
- `DB_PATH` is now configurable via the `MEMORY_METADATA_DB` environment variable (default unchanged: `~/.claude/memory/.metadata.db`). Enables test isolation without monkeypatching.
- fastmcp pin updated to `>=3.2.4,<4`.

### Fixed
- `get_note_metadata` now returns `{"ok": False, "error": "not found"}` instead of `null` when the requested path is not in the index — consistent with the error-dict pattern used by other tools.
