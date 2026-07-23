# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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

## [0.2.0] - 2026-05-28

### Added
- 16 tests covering `list_notes` (all filter combinations), `get_note_metadata` (found/not-found/no-tags), and `count_by` (valid/invalid field, with pre-filters). Tests use a real temp SQLite database for isolation.
- `pyproject.toml` with version field.

### Changed
- `DB_PATH` is now configurable via the `MEMORY_METADATA_DB` environment variable (default unchanged: `~/.claude/memory/.metadata.db`). Enables test isolation without monkeypatching.
- fastmcp pin updated to `>=3.2.4,<4`.

### Fixed
- `get_note_metadata` now returns `{"ok": False, "error": "not found"}` instead of `null` when the requested path is not in the index — consistent with the error-dict pattern used by other tools.
