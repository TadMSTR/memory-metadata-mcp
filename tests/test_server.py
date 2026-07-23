"""Tests for memory-metadata-mcp using a real temp SQLite database."""

import sqlite3
from pathlib import Path

import pytest


def _make_db(path: Path) -> None:
    """Create a minimal notes+note_tags schema with sample rows."""
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            filename TEXT,
            tier TEXT,
            category TEXT,
            source TEXT,
            created TEXT,
            expires TEXT,
            archived_at TEXT,
            owner_agent TEXT,
            body_size INTEGER,
            file_sha TEXT,
            last_indexed_at TEXT
        );
        CREATE TABLE note_tags (
            path TEXT,
            tag TEXT,
            PRIMARY KEY (path, tag)
        );
    """)
    con.executemany(
        "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                "/mem/shared/2026-01-01-a.md",
                "2026-01-01-a.md",
                "working",
                "decision-record",
                "dev",
                "2026-01-01",
                "never",
                None,
                "dev",
                512,
                "abc",
                "2026-01-01T00:00:00Z",
            ),
            (
                "/mem/shared/2026-02-01-b.md",
                "2026-02-01-b.md",
                "working",
                "transient-finding",
                "research",
                "2026-02-01",
                "2026-05-01",
                None,
                "research",
                256,
                "def",
                "2026-02-01T00:00:00Z",
            ),
            (
                "/mem/agents/dev/2026-03-01-c.md",
                "2026-03-01-c.md",
                "session",
                "session-summary",
                "dev",
                "2026-03-01",
                "2026-04-01",
                None,
                "dev",
                128,
                "ghi",
                "2026-03-01T00:00:00Z",
            ),
        ],
    )
    con.executemany(
        "INSERT INTO note_tags VALUES (?,?)",
        [
            ("/mem/shared/2026-01-01-a.md", "architecture"),
            ("/mem/shared/2026-01-01-a.md", "auth"),
            ("/mem/shared/2026-02-01-b.md", "debugging"),
        ],
    )
    con.commit()
    con.close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    _make_db(db)
    # Patch the module-level DB_PATH after import
    from memory_metadata_mcp import server as mm

    monkeypatch.setattr(mm, "DB_PATH", db)
    return db


# ── list_notes ────────────────────────────────────────────────────────────────


def test_list_notes_all(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes()
    assert len(results) == 3


def test_list_notes_filter_category(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(category="decision-record")
    assert len(results) == 1
    assert results[0]["category"] == "decision-record"


def test_list_notes_filter_tier(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(tier="working")
    assert len(results) == 2
    for r in results:
        assert r["tier"] == "working"


def test_list_notes_filter_tag(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(tag="architecture")
    assert len(results) == 1
    assert "2026-01-01-a.md" in results[0]["filename"]


def test_list_notes_filter_owner_agent(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(owner_agent="dev")
    assert len(results) == 2


def test_list_notes_filter_created_after(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(created_after="2026-02-01")
    assert len(results) == 2


def test_list_notes_filter_expires_before(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(expires_before="2026-04-02")
    # Only the session-summary note expires before 2026-04-02
    assert len(results) == 1
    assert results[0]["category"] == "session-summary"


def test_list_notes_limit(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(limit=2)
    assert len(results) == 2


def test_list_notes_limit_clamped(db_path):
    from memory_metadata_mcp import server as mm

    results = mm.list_notes(limit=0)
    # min(max(1, 0), 500) = 1
    assert len(results) == 1


# ── get_note_metadata ─────────────────────────────────────────────────────────


def test_get_note_metadata_found(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.get_note_metadata("/mem/shared/2026-01-01-a.md")
    assert result["path"] == "/mem/shared/2026-01-01-a.md"
    assert result["category"] == "decision-record"
    assert "architecture" in result["tags"]
    assert "auth" in result["tags"]


def test_get_note_metadata_not_found_returns_error_dict(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.get_note_metadata("/does/not/exist.md")
    assert result == {"ok": False, "error": "not found"}


def test_get_note_metadata_no_tags(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.get_note_metadata("/mem/agents/dev/2026-03-01-c.md")
    assert result["tags"] == []


# ── count_by ──────────────────────────────────────────────────────────────────


def test_count_by_category(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.count_by(field="category")
    assert result["decision-record"] == 1
    assert result["transient-finding"] == 1
    assert result["session-summary"] == 1


def test_count_by_tier(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.count_by(field="tier")
    assert result["working"] == 2
    assert result["session"] == 1


def test_count_by_tier_with_category_filter(db_path):
    from memory_metadata_mcp import server as mm

    result = mm.count_by(field="tier", category="decision-record")
    assert result == {"working": 1}


def test_count_by_invalid_field_raises(db_path):
    from memory_metadata_mcp import server as mm

    with pytest.raises(ValueError, match="field must be one of"):
        mm.count_by(field="unknown")


# ── logging / entry point ─────────────────────────────────────────────────────


def test_configure_logging_runs():
    from memory_metadata_mcp import server as mm

    # Should configure structlog without raising.
    mm._configure_logging()
    mm.log.info("smoke")


def test_main_invokes_mcp_run(monkeypatch):
    from memory_metadata_mcp import server as mm

    called = {}

    def fake_run(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(mm.mcp, "run", fake_run)
    monkeypatch.setenv("MEMORY_METADATA_HOST", "127.0.0.1")
    monkeypatch.setenv("MEMORY_METADATA_PORT", "8490")
    mm.main()
    assert called["transport"] == "streamable-http"
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8490
