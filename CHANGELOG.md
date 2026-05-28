# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.2.0] - 2026-05-28

### Added
- 16 tests covering `list_notes` (all filter combinations), `get_note_metadata` (found/not-found/no-tags), and `count_by` (valid/invalid field, with pre-filters). Tests use a real temp SQLite database for isolation.
- `pyproject.toml` with version field.

### Changed
- `DB_PATH` is now configurable via the `MEMORY_METADATA_DB` environment variable (default unchanged: `~/.claude/memory/.metadata.db`). Enables test isolation without monkeypatching.
- fastmcp pin updated to `>=3.2.4,<4`.

### Fixed
- `get_note_metadata` now returns `{"ok": False, "error": "not found"}` instead of `null` when the requested path is not in the index — consistent with the error-dict pattern used by other tools.
