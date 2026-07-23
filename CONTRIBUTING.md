# Contributing

## Development setup

```bash
git clone https://github.com/TadMSTR/memory-metadata-mcp.git
cd memory-metadata-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
# Full suite with coverage (must stay >= 80%)
pytest --cov=memory_metadata_mcp --cov-report=term-missing
```

## Linting

```bash
ruff check .
ruff format --check .
```

## Code style

- Python 3.11+, type annotations throughout
- `structlog` for logging — JSON output, never log note bodies or credentials
- All SQL uses `?` placeholders; the only interpolated identifier (`count_by` field)
  is validated against `ALLOWED_COUNT_FIELDS` first
- Read-only server: do not add write/delete/schema-modifying tools

## Releasing

1. Update `CHANGELOG.md` (move `[Unreleased]` to a versioned section).
2. Bump `version` in `pyproject.toml` and `__version__` in `src/memory_metadata_mcp/__init__.py`.
3. Tag `vX.Y.Z` after the PR merges.
