import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.app.models import (
    BzPoint,
    DashboardStatus,
    ObservingIndex,
    SpaceWeatherData,
    SpeedPoint,
    SunData,
    XrayFluxPoint,
)
from backend.app.storage import (
    clear_history_db,
    fetch_history,
    get_connection,
    record_history,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + "-wal").unlink(missing_ok=True)
            Path(str(db_path) + "-shm").unlink(missing_ok=True)


@pytest.fixture
def sample_dashboard_status():
    """Create a sample DashboardStatus for testing."""
    return DashboardStatus(
        sun=SunData(
            xray_flux_short=[
                XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.5e-6),
                XrayFluxPoint(timestamp="2025-01-01T12:05:00Z", value_wm2=1.6e-6),
            ],
            xray_flux_long=[
                XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.4e-6),
                XrayFluxPoint(timestamp="2025-01-01T12:05:00Z", value_wm2=1.5e-6),
            ],
            current_class="C1.5",
            activity_level="active",
            updated_at="2025-01-01T12:05:00Z",
        ),
        space_weather=SpaceWeatherData(
            bz_series=[
                BzPoint(timestamp="2025-01-01T12:00:00Z", value_nT=-5.2),
                BzPoint(timestamp="2025-01-01T12:05:00Z", value_nT=-3.8),
            ],
            speed_series=[
                SpeedPoint(timestamp="2025-01-01T12:00:00Z", value_km_s=420.5),
                SpeedPoint(timestamp="2025-01-01T12:05:00Z", value_km_s=425.3),
            ],
            kp=3.5,
            updated_at="2025-01-01T12:05:00Z",
        ),
        observing_index=ObservingIndex(
            score=7.5,
            rating="good",
            best_window="10pm - 2am",
            moon_summary="New moon",
            notes=["Clear skies", "Low humidity"],
        ),
        timestamp="2025-01-01T12:05:00Z",
    )


class TestStorageConnection:
    """Test storage database connection management."""

    def test_connection_creates_database(self, temp_db):
        """Test that connection creates database file."""
        assert not temp_db.exists()
        with get_connection(temp_db) as conn:
            assert conn is not None
        assert temp_db.exists()

    def test_connection_creates_all_tables(self, temp_db):
        """Test that all required tables are created."""
        with get_connection(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row["name"] for row in cursor.fetchall()]
            assert "sun_history" in tables
            assert "space_weather_history" in tables
            assert "observing_history" in tables

    def test_connection_creates_indexes(self, temp_db):
        """Test that indexes are created on ts_epoch columns."""
        with get_connection(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
            indexes = [row["name"] for row in cursor.fetchall()]
            assert "idx_sun_ts_epoch" in indexes
            assert "idx_space_ts_epoch" in indexes
            assert "idx_observing_ts_epoch" in indexes

    def test_connection_enables_wal_mode(self, temp_db):
        """Test that WAL mode is enabled."""
        with get_connection(temp_db) as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            result = cursor.fetchone()
            assert result[0].lower() == "wal"

    def test_connection_closes_properly(self, temp_db):
        """Test that connection closes after context manager."""
        conn_ref = None
        with get_connection(temp_db) as conn:
            conn_ref = conn

        with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
            conn_ref.execute("SELECT 1")


class TestRecordHistory:
    """Test record_history functionality."""

    def test_record_complete_status(self, temp_db, sample_dashboard_status):
        """Test recording a complete dashboard status."""
        record_history(sample_dashboard_status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            # Check sun history
            sun_row = conn.execute("SELECT * FROM sun_history").fetchone()
            assert sun_row is not None
            assert sun_row["timestamp"] == "2025-01-01T12:05:00Z"
            assert sun_row["xray_flux_short"] == 1.6e-6
            assert sun_row["xray_flux_long"] == 1.5e-6

            # Check space weather history
            space_row = conn.execute("SELECT * FROM space_weather_history").fetchone()
            assert space_row is not None
            assert space_row["bz"] == -3.8
            assert space_row["speed_km_s"] == 425.3
            assert space_row["kp"] == 3.5

            # Check observing history
            obs_row = conn.execute("SELECT * FROM observing_history").fetchone()
            assert obs_row is not None
            assert obs_row["index_score"] == 7.5

    def test_record_partial_status_sun_only(self, temp_db):
        """Test recording status with only sun data."""
        status = DashboardStatus(
            sun=SunData(
                xray_flux_short=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1e-6)],
                xray_flux_long=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1e-6)],
                current_class="B1.0",
                activity_level="quiet",
                updated_at="2025-01-01T12:00:00Z",
            ),
            timestamp="2025-01-01T12:00:00Z",
        )
        record_history(status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            sun_count = conn.execute("SELECT COUNT(*) FROM sun_history").fetchone()[0]
            space_count = conn.execute("SELECT COUNT(*) FROM space_weather_history").fetchone()[0]
            obs_count = conn.execute("SELECT COUNT(*) FROM observing_history").fetchone()[0]

            assert sun_count == 1
            assert space_count == 0
            assert obs_count == 0

    def test_record_replaces_duplicate_timestamp(self, temp_db, sample_dashboard_status):
        """Test that recording with same timestamp replaces existing data."""
        record_history(sample_dashboard_status, db_path=temp_db)

        # Modify and record again
        sample_dashboard_status.observing_index.score = 9.0
        record_history(sample_dashboard_status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            rows = conn.execute("SELECT * FROM observing_history").fetchall()
            assert len(rows) == 1
            assert rows[0]["index_score"] == 9.0

    def test_record_multiple_timestamps(self, temp_db):
        """Test recording multiple different timestamps."""
        for i in range(5):
            status = DashboardStatus(
                observing_index=ObservingIndex(
                    score=float(i),
                    rating="test",
                    best_window=None,
                    moon_summary=None,
                    notes=[],
                ),
                timestamp=f"2025-01-01T12:{i:02d}:00Z",
            )
            record_history(status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM observing_history").fetchone()[0]
            assert count == 5

    def test_record_handles_empty_series(self, temp_db):
        """Test recording sun data with empty flux series."""
        status = DashboardStatus(
            sun=SunData(
                xray_flux_short=[],
                xray_flux_long=[],
                current_class="A0.0",
                activity_level="quiet",
                updated_at="2025-01-01T12:00:00Z",
            ),
            timestamp="2025-01-01T12:00:00Z",
        )
        record_history(status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            row = conn.execute("SELECT * FROM sun_history").fetchone()
            assert row is not None
            assert row["xray_flux_short"] is None
            assert row["xray_flux_long"] is None

    def test_record_sets_ts_epoch(self, temp_db, sample_dashboard_status):
        """Test that ts_epoch is correctly calculated."""
        record_history(sample_dashboard_status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            row = conn.execute("SELECT ts_epoch FROM sun_history").fetchone()
            # Verify it's a reasonable epoch timestamp (year 2025)
            assert row["ts_epoch"] > 1735689600  # 2025-01-01 00:00:00 UTC
            assert row["ts_epoch"] < 1767225600  # 2026-01-01 00:00:00 UTC


class TestFetchHistory:
    """Test fetch_history functionality."""

    def test_fetch_empty_history(self, temp_db):
        """Test fetching from empty database."""
        result = fetch_history(hours=24, db_path=temp_db)
        assert result.sun == []
        assert result.space_weather == []
        assert result.observing_index == []

    def test_fetch_recent_data(self, temp_db):
        """Test fetching recent data within time window."""
        # Record some recent data
        for i in range(5):
            status = DashboardStatus(
                observing_index=ObservingIndex(
                    score=float(i), rating="test", best_window=None, moon_summary=None, notes=[]
                ),
                timestamp=(datetime.utcnow() - timedelta(hours=i)).isoformat() + "Z",
            )
            record_history(status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        assert len(result.observing_index) == 5

    def test_fetch_excludes_old_data(self, temp_db):
        """Test that old data outside time window is excluded."""
        # Record old data
        old_status = DashboardStatus(
            observing_index=ObservingIndex(
                score=1.0, rating="old", best_window=None, moon_summary=None, notes=[]
            ),
            timestamp=(datetime.utcnow() - timedelta(hours=48)).isoformat() + "Z",
        )
        record_history(old_status, db_path=temp_db)

        # Record recent data
        recent_status = DashboardStatus(
            observing_index=ObservingIndex(
                score=5.0, rating="recent", best_window=None, moon_summary=None, notes=[]
            ),
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        record_history(recent_status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        assert len(result.observing_index) == 1
        assert result.observing_index[0].index_score == 5.0

    def test_fetch_orders_by_time(self, temp_db):
        """Test that results are ordered chronologically."""
        timestamps = [
            (datetime.utcnow() - timedelta(hours=5)).isoformat() + "Z",
            (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z",
            (datetime.utcnow() - timedelta(hours=8)).isoformat() + "Z",
        ]

        for ts in timestamps:
            status = DashboardStatus(
                observing_index=ObservingIndex(
                    score=1.0, rating="test", best_window=None, moon_summary=None, notes=[]
                ),
                timestamp=ts,
            )
            record_history(status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        # Should be in ascending time order
        assert result.observing_index[0].timestamp == timestamps[2]
        assert result.observing_index[1].timestamp == timestamps[0]
        assert result.observing_index[2].timestamp == timestamps[1]

    def test_fetch_all_data_types(self, temp_db, sample_dashboard_status):
        """Test fetching returns all data types."""
        record_history(sample_dashboard_status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        assert len(result.sun) == 1
        assert len(result.space_weather) == 1
        assert len(result.observing_index) == 1

        # Verify data integrity
        assert result.sun[0].xray_flux_short == 1.6e-6
        assert result.space_weather[0].bz == -3.8
        assert result.observing_index[0].index_score == 7.5

    def test_fetch_handles_null_values(self, temp_db):
        """Test fetching handles NULL values in optional fields."""
        # Manually insert data with NULLs
        with get_connection(temp_db) as conn:
            ts = datetime.utcnow().isoformat() + "Z"
            ts_epoch = datetime.utcnow().timestamp()
            conn.execute(
                "INSERT INTO sun_history (timestamp, ts_epoch, xray_flux_short, xray_flux_long) VALUES (?, ?, NULL, NULL)",
                (ts, ts_epoch),
            )
            conn.commit()

        result = fetch_history(hours=24, db_path=temp_db)
        assert len(result.sun) == 1
        assert result.sun[0].xray_flux_short is None
        assert result.sun[0].xray_flux_long is None


class TestClearHistoryDb:
    """Test clear_history_db functionality."""

    def test_clear_removes_database(self, temp_db, sample_dashboard_status):
        """Test that clear removes the database file."""
        record_history(sample_dashboard_status, db_path=temp_db)
        assert temp_db.exists()

        clear_history_db(db_path=temp_db)
        assert not temp_db.exists()

    def test_clear_nonexistent_database(self, temp_db):
        """Test clearing nonexistent database doesn't raise error."""
        assert not temp_db.exists()
        # Should not raise
        clear_history_db(db_path=temp_db)

    def test_clear_removes_wal_files(self, temp_db, sample_dashboard_status):
        """Test that WAL files are also removed."""
        record_history(sample_dashboard_status, db_path=temp_db)

        wal_path = Path(str(temp_db) + "-wal")
        shm_path = Path(str(temp_db) + "-shm")

        clear_history_db(db_path=temp_db)

        assert not temp_db.exists()
        assert not wal_path.exists()
        assert not shm_path.exists()


class TestDataIntegrity:
    """Test data integrity and edge cases."""

    def test_concurrent_writes_different_timestamps(self, temp_db):
        """Test writing different timestamps concurrently."""
        for i in range(10):
            status = DashboardStatus(
                observing_index=ObservingIndex(
                    score=float(i), rating="test", best_window=None, moon_summary=None, notes=[]
                ),
                timestamp=f"2025-01-01T12:{i:02d}:00Z",
            )
            record_history(status, db_path=temp_db)

        with get_connection(temp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM observing_history").fetchone()[0]
            assert count == 10

    def test_large_values(self, temp_db):
        """Test handling of large numeric values."""
        status = DashboardStatus(
            space_weather=SpaceWeatherData(
                bz_series=[BzPoint(timestamp="2025-01-01T12:00:00Z", value_nT=999999.9)],
                speed_series=[
                    SpeedPoint(timestamp="2025-01-01T12:00:00Z", value_km_s=999999.9)
                ],
                kp=9.9,
                updated_at="2025-01-01T12:00:00Z",
            ),
            timestamp="2025-01-01T12:00:00Z",
        )
        record_history(status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        assert result.space_weather[0].bz == 999999.9
        assert result.space_weather[0].speed_km_s == 999999.9

    def test_negative_values(self, temp_db):
        """Test handling of negative values."""
        status = DashboardStatus(
            space_weather=SpaceWeatherData(
                bz_series=[BzPoint(timestamp="2025-01-01T12:00:00Z", value_nT=-999.9)],
                speed_series=[SpeedPoint(timestamp="2025-01-01T12:00:00Z", value_km_s=400.0)],
                kp=0.0,
                updated_at="2025-01-01T12:00:00Z",
            ),
            timestamp="2025-01-01T12:00:00Z",
        )
        record_history(status, db_path=temp_db)

        result = fetch_history(hours=24, db_path=temp_db)
        assert result.space_weather[0].bz == -999.9
