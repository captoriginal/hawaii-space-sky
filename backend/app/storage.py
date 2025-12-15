import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, List, Optional

from .config import get_settings
from .models import (
    DashboardStatus,
    HistoryObservingPoint,
    HistoryResponse,
    HistorySpaceWeatherPoint,
    HistorySunPoint,
)

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Get the database path from settings."""
    settings = get_settings()
    # Use a history-specific path alongside cache
    return settings.CACHE_DB_PATH.parent / "history.db"


@contextmanager
def get_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that provides a database connection.
    This ensures proper connection lifecycle management and thread safety.

    Args:
        db_path: Optional path to database file. If None, uses default from settings.

    Yields:
        sqlite3.Connection: Database connection with row factory set
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        # Use timeout to handle concurrent writes better
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        _ensure_tables(conn)
        yield conn
    except sqlite3.Error as exc:
        logger.error("Database connection error: %s", exc)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sun_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL NOT NULL,
            xray_flux_short REAL,
            xray_flux_long REAL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sun_ts_epoch
        ON sun_history(ts_epoch)
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS space_weather_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL NOT NULL,
            bz REAL,
            speed_km_s REAL,
            kp REAL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_space_ts_epoch
        ON space_weather_history(ts_epoch)
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observing_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL NOT NULL,
            index_score REAL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observing_ts_epoch
        ON observing_history(ts_epoch)
        """
    )
    conn.commit()


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp string, handling 'Z' suffix."""
    clean = ts_str.replace("Z", "")
    return datetime.fromisoformat(clean)


def record_history(status: DashboardStatus, db_path: Optional[Path] = None) -> None:
    """
    Record dashboard status to history database.

    Args:
        status: Dashboard status to record
        db_path: Optional database path for testing
    """
    with get_connection(db_path) as conn:
        try:
            ts = _parse_ts(status.timestamp)
        except Exception:
            ts = datetime.utcnow()
        ts_epoch = ts.timestamp()

        if status.sun:
            sun_short = (
                status.sun.xray_flux_short[-1].value_wm2
                if status.sun.xray_flux_short
                else None
            )
            sun_long = (
                status.sun.xray_flux_long[-1].value_wm2 if status.sun.xray_flux_long else None
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO sun_history (timestamp, ts_epoch, xray_flux_short, xray_flux_long)
                VALUES (?, ?, ?, ?)
                """,
                (status.timestamp, ts_epoch, sun_short, sun_long),
            )

        if status.space_weather:
            bz = (
                status.space_weather.bz_series[-1].value_nT
                if status.space_weather.bz_series
                else None
            )
            speed = (
                status.space_weather.speed_series[-1].value_km_s
                if status.space_weather.speed_series
                else None
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO space_weather_history (timestamp, ts_epoch, bz, speed_km_s, kp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (status.timestamp, ts_epoch, bz, speed, status.space_weather.kp),
            )

        if status.observing_index:
            conn.execute(
                """
                INSERT OR REPLACE INTO observing_history (timestamp, ts_epoch, index_score)
                VALUES (?, ?, ?)
                """,
                (status.timestamp, ts_epoch, status.observing_index.score),
            )
        conn.commit()


def fetch_history(hours: int, db_path: Optional[Path] = None) -> HistoryResponse:
    """
    Fetch historical data for the specified time window.

    Args:
        hours: Number of hours of history to fetch (1-168)
        db_path: Optional database path for testing

    Returns:
        HistoryResponse with sun, space weather, and observing data
    """
    with get_connection(db_path) as conn:
        cutoff_epoch = (datetime.utcnow() - timedelta(hours=hours)).timestamp()

        sun_rows = conn.execute(
            """
            SELECT timestamp, xray_flux_short, xray_flux_long
            FROM sun_history
            WHERE ts_epoch >= ?
            ORDER BY ts_epoch ASC
            """,
            (cutoff_epoch,),
        ).fetchall()

        space_rows = conn.execute(
            """
            SELECT timestamp, bz, speed_km_s, kp
            FROM space_weather_history
            WHERE ts_epoch >= ?
            ORDER BY ts_epoch ASC
            """,
            (cutoff_epoch,),
        ).fetchall()

        observing_rows = conn.execute(
            """
            SELECT timestamp, index_score
            FROM observing_history
            WHERE ts_epoch >= ?
            ORDER BY ts_epoch ASC
            """,
            (cutoff_epoch,),
        ).fetchall()

        sun_data: List[HistorySunPoint] = [
            HistorySunPoint(
                timestamp=row["timestamp"],
                xray_flux_short=row["xray_flux_short"],
                xray_flux_long=row["xray_flux_long"],
            )
            for row in sun_rows
        ]
        space_data: List[HistorySpaceWeatherPoint] = [
            HistorySpaceWeatherPoint(
                timestamp=row["timestamp"],
                bz=row["bz"],
                speed_km_s=row["speed_km_s"],
                kp=row["kp"],
            )
            for row in space_rows
        ]
        observing_data: List[HistoryObservingPoint] = [
            HistoryObservingPoint(timestamp=row["timestamp"], index_score=row["index_score"])
            for row in observing_rows
        ]
        return HistoryResponse(
            sun=sun_data, space_weather=space_data, observing_index=observing_data
        )


def clear_history_db(db_path: Optional[Path] = None) -> None:
    """
    Remove the history database file.

    Args:
        db_path: Optional database path for testing
    """
    if db_path is None:
        db_path = get_db_path()

    try:
        db_path.unlink()
        # Also remove WAL and SHM files if they exist
        wal_path = db_path.with_suffix(".db-wal")
        shm_path = db_path.with_suffix(".db-shm")
        wal_path.unlink(missing_ok=True)
        shm_path.unlink(missing_ok=True)
    except FileNotFoundError:
        return
    except Exception as exc:
        logger.warning("Failed to remove history DB %s: %s", db_path, exc)
