import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.app.cache import (
    clear_cache,
    get_cache_connection,
    is_cache_fresh,
    load_cache,
    save_cache,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + "-wal").unlink(missing_ok=True)
            Path(str(db_path) + "-shm").unlink(missing_ok=True)


class TestCacheConnection:
    """Test cache database connection management."""

    def test_connection_creates_database(self, temp_db):
        """Test that connection creates database file."""
        assert not temp_db.exists()
        with get_cache_connection(temp_db) as conn:
            assert conn is not None
        assert temp_db.exists()

    def test_connection_creates_tables(self, temp_db):
        """Test that tables are created on connection."""
        with get_cache_connection(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cache'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["name"] == "cache"

    def test_connection_creates_index(self, temp_db):
        """Test that index is created on cached_at column."""
        with get_cache_connection(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cache_cached_at'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_connection_enables_wal_mode(self, temp_db):
        """Test that WAL mode is enabled for concurrent access."""
        with get_cache_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            assert result[0].lower() == "wal"

    def test_connection_closes_properly(self, temp_db):
        """Test that connection is closed after context manager exits."""
        conn_ref = None
        with get_cache_connection(temp_db) as conn:
            conn_ref = conn
            assert conn_ref is not None

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
            conn_ref.execute("SELECT 1")

    def test_connection_rollback_on_error(self, temp_db):
        """Test that connection rolls back on error."""
        with pytest.raises(sqlite3.OperationalError):
            with get_cache_connection(temp_db) as conn:
                # Try to insert invalid data
                conn.execute("INSERT INTO nonexistent_table VALUES (?)", ("data",))


class TestSaveCache:
    """Test save_cache functionality."""

    def test_save_simple_data(self, temp_db):
        """Test saving simple dictionary data."""
        data = {"key": "value", "number": 42}
        save_cache("test_domain", data, db_path=temp_db)

        # Verify data was saved
        with get_cache_connection(temp_db) as conn:
            row = conn.execute(
                "SELECT domain, payload FROM cache WHERE domain = ?", ("test_domain",)
            ).fetchone()
            assert row is not None
            assert row["domain"] == "test_domain"
            assert json.loads(row["payload"]) == data

    def test_save_with_source_timestamp(self, temp_db):
        """Test saving data with source timestamp."""
        data = {"value": 123}
        source_ts = "2025-01-01T12:00:00Z"
        save_cache("test_domain", data, source_timestamp=source_ts, db_path=temp_db)

        with get_cache_connection(temp_db) as conn:
            row = conn.execute(
                "SELECT source_timestamp FROM cache WHERE domain = ?", ("test_domain",)
            ).fetchone()
            assert row["source_timestamp"] == source_ts

    def test_save_replaces_existing(self, temp_db):
        """Test that saving to existing domain replaces data."""
        save_cache("test_domain", {"version": 1}, db_path=temp_db)
        save_cache("test_domain", {"version": 2}, db_path=temp_db)

        with get_cache_connection(temp_db) as conn:
            rows = conn.execute("SELECT * FROM cache WHERE domain = ?", ("test_domain",)).fetchall()
            assert len(rows) == 1
            assert json.loads(rows[0]["payload"]) == {"version": 2}

    def test_save_sets_cached_at(self, temp_db):
        """Test that cached_at timestamp is set."""
        before = datetime.utcnow()
        save_cache("test_domain", {"data": "test"}, db_path=temp_db)
        after = datetime.utcnow()

        with get_cache_connection(temp_db) as conn:
            row = conn.execute(
                "SELECT cached_at FROM cache WHERE domain = ?", ("test_domain",)
            ).fetchone()
            cached_at = datetime.fromisoformat(row["cached_at"].replace("Z", ""))
            assert before <= cached_at <= after

    def test_save_complex_data(self, temp_db):
        """Test saving complex nested data structures."""
        data = {
            "list": [1, 2, 3],
            "nested": {"a": {"b": {"c": "deep"}}},
            "mixed": [{"x": 1}, {"y": 2}],
        }
        save_cache("complex", data, db_path=temp_db)

        loaded = load_cache("complex", db_path=temp_db)
        assert loaded is not None
        assert loaded[0] == data


class TestLoadCache:
    """Test load_cache functionality."""

    def test_load_nonexistent(self, temp_db):
        """Test loading from nonexistent domain returns None."""
        result = load_cache("nonexistent", db_path=temp_db)
        assert result is None

    def test_load_existing_data(self, temp_db):
        """Test loading existing cached data."""
        data = {"key": "value"}
        save_cache("test_domain", data, db_path=temp_db)

        result = load_cache("test_domain", db_path=temp_db)
        assert result is not None
        payload, source_ts, cached_at = result
        assert payload == data
        assert isinstance(cached_at, str)

    def test_load_returns_all_fields(self, temp_db):
        """Test that load returns payload, source_timestamp, and cached_at."""
        data = {"value": 42}
        source_ts = "2025-01-01T00:00:00Z"
        save_cache("test_domain", data, source_timestamp=source_ts, db_path=temp_db)

        result = load_cache("test_domain", db_path=temp_db)
        assert result is not None
        payload, loaded_source_ts, cached_at = result
        assert payload == data
        assert loaded_source_ts == source_ts
        assert cached_at is not None

    def test_load_handles_corrupted_json(self, temp_db):
        """Test that load handles corrupted JSON gracefully."""
        # Manually insert corrupted JSON
        with get_cache_connection(temp_db) as conn:
            conn.execute(
                "INSERT INTO cache (domain, payload, cached_at) VALUES (?, ?, ?)",
                ("corrupted", "{invalid json", datetime.utcnow().isoformat() + "Z"),
            )
            conn.commit()

        result = load_cache("corrupted", db_path=temp_db)
        assert result is None


class TestIsCacheFresh:
    """Test is_cache_fresh functionality."""

    def test_fresh_cache(self, temp_db):
        """Test that recently cached data is fresh."""
        save_cache("test_domain", {"data": "test"}, db_path=temp_db)
        assert is_cache_fresh("test_domain", max_age_seconds=60, db_path=temp_db) is True

    def test_stale_cache(self, temp_db):
        """Test that old cached data is stale."""
        # Manually insert old data
        old_time = (datetime.utcnow() - timedelta(seconds=120)).isoformat() + "Z"
        with get_cache_connection(temp_db) as conn:
            conn.execute(
                "INSERT INTO cache (domain, payload, cached_at) VALUES (?, ?, ?)",
                ("old_domain", json.dumps({"data": "old"}), old_time),
            )
            conn.commit()

        assert is_cache_fresh("old_domain", max_age_seconds=60, db_path=temp_db) is False

    def test_nonexistent_cache(self, temp_db):
        """Test that nonexistent cache is not fresh."""
        assert is_cache_fresh("nonexistent", max_age_seconds=60, db_path=temp_db) is False

    def test_cache_freshness_boundary(self, temp_db):
        """Test cache freshness at the boundary."""
        # Cache data exactly at the max age
        boundary_time = (datetime.utcnow() - timedelta(seconds=60)).isoformat() + "Z"
        with get_cache_connection(temp_db) as conn:
            conn.execute(
                "INSERT INTO cache (domain, payload, cached_at) VALUES (?, ?, ?)",
                ("boundary", json.dumps({"data": "test"}), boundary_time),
            )
            conn.commit()

        # Should be stale (not fresh) because it's >= max_age
        assert is_cache_fresh("boundary", max_age_seconds=60, db_path=temp_db) is False

    def test_invalid_timestamp_format(self, temp_db):
        """Test handling of invalid timestamp format."""
        with get_cache_connection(temp_db) as conn:
            conn.execute(
                "INSERT INTO cache (domain, payload, cached_at) VALUES (?, ?, ?)",
                ("invalid_ts", json.dumps({"data": "test"}), "not-a-timestamp"),
            )
            conn.commit()

        assert is_cache_fresh("invalid_ts", max_age_seconds=60, db_path=temp_db) is False


class TestClearCache:
    """Test clear_cache functionality."""

    def test_clear_removes_database(self, temp_db):
        """Test that clear_cache removes the database file."""
        # Create and populate cache
        save_cache("test_domain", {"data": "test"}, db_path=temp_db)
        assert temp_db.exists()

        # Clear cache
        clear_cache(db_path=temp_db)

        # Database should be removed
        assert not temp_db.exists()

    def test_clear_nonexistent_database(self, temp_db):
        """Test that clearing nonexistent database doesn't raise error."""
        assert not temp_db.exists()
        # Should not raise
        clear_cache(db_path=temp_db)

    def test_clear_removes_wal_files(self, temp_db):
        """Test that WAL files are also removed."""
        # Create cache with WAL mode
        save_cache("test_domain", {"data": "test"}, db_path=temp_db)

        # WAL files might be created
        wal_path = Path(str(temp_db) + "-wal")
        shm_path = Path(str(temp_db) + "-shm")

        # Clear cache
        clear_cache(db_path=temp_db)

        # All files should be removed
        assert not temp_db.exists()
        assert not wal_path.exists()
        assert not shm_path.exists()


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    def test_multiple_reads(self, temp_db):
        """Test that multiple reads work correctly."""
        save_cache("test_domain", {"value": 42}, db_path=temp_db)

        # Multiple reads should all succeed
        for _ in range(10):
            result = load_cache("test_domain", db_path=temp_db)
            assert result is not None
            assert result[0] == {"value": 42}

    def test_sequential_writes(self, temp_db):
        """Test that sequential writes work correctly."""
        for i in range(10):
            save_cache(f"domain_{i}", {"value": i}, db_path=temp_db)

        # Verify all writes succeeded
        with get_cache_connection(temp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            assert count == 10
