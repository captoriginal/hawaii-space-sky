import json
import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

from .config import get_settings
from .storage import clear_history_db

logger = logging.getLogger(__name__)


def get_cache_db_path() -> Path:
    """Get the cache database path from settings."""
    settings = get_settings()
    return settings.CACHE_DB_PATH


@contextmanager
def get_cache_connection(
    db_path: Optional[Path] = None,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that provides a cache database connection.
    This ensures proper connection lifecycle management and thread safety.

    Args:
        db_path: Optional path to database file. If None, uses default from settings.

    Yields:
        sqlite3.Connection: Database connection with row factory set
    """
    if db_path is None:
        db_path = get_cache_db_path()

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
        logger.error("Cache database connection error: %s", exc)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create cache table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            domain TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            source_timestamp TEXT,
            cached_at TEXT NOT NULL
        )
        """
    )
    # Add index on cached_at for efficient cleanup queries
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cache_cached_at
        ON cache(cached_at)
        """
    )
    conn.commit()


def save_cache(
    domain: str,
    data: Any,
    source_timestamp: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """
    Save data to cache.

    Args:
        domain: Cache key/domain identifier
        data: Data to cache (will be JSON serialized)
        source_timestamp: Optional timestamp from the data source
        db_path: Optional database path for testing
    """
    with get_cache_connection(db_path) as conn:
        payload = json.dumps(data)
        cached_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        conn.execute(
            "INSERT OR REPLACE INTO cache (domain, payload, source_timestamp, cached_at) VALUES (?, ?, ?, ?)",
            (domain, payload, source_timestamp, cached_at),
        )
        conn.commit()


def load_cache(
    domain: str, db_path: Optional[Path] = None
) -> Optional[Tuple[Dict[str, Any], Optional[str], str]]:
    """
    Load data from cache.

    Args:
        domain: Cache key/domain identifier
        db_path: Optional database path for testing

    Returns:
        Tuple of (data, source_timestamp, cached_at) or None if not found
    """
    with get_cache_connection(db_path) as conn:
        row = conn.execute(
            "SELECT payload, source_timestamp, cached_at FROM cache WHERE domain = ?", (domain,)
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode cached JSON for domain %s: %s", domain, exc)
            return None
        return payload, row["source_timestamp"], row["cached_at"]


def is_cache_fresh(
    domain: str, max_age_seconds: int, db_path: Optional[Path] = None
) -> bool:
    """
    Check if cached data is fresh (within max_age).

    Args:
        domain: Cache key/domain identifier
        max_age_seconds: Maximum age in seconds
        db_path: Optional database path for testing

    Returns:
        True if cache exists and is fresh, False otherwise
    """
    cached = load_cache(domain, db_path)
    if not cached:
        return False
    _, _, cached_at = cached
    try:
        ts = datetime.fromisoformat(cached_at.replace("Z", ""))
    except ValueError as exc:
        logger.warning("Invalid timestamp in cache for domain %s: %s", domain, exc)
        return False
    return datetime.utcnow() - ts < timedelta(seconds=max_age_seconds)


def clear_cache(db_path: Optional[Path] = None) -> None:
    """
    Clear application caches: remove cache db, history db, and downloaded static images.

    Args:
        db_path: Optional database path for testing
    """
    if db_path is None:
        db_path = get_cache_db_path()

    # Remove cache database file entirely to ensure a clean slate
    try:
        db_path.unlink()
        # Also remove WAL and SHM files if they exist
        wal_path = db_path.with_suffix(".db-wal")
        shm_path = db_path.with_suffix(".db-shm")
        wal_path.unlink(missing_ok=True)
        shm_path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Failed to remove cache DB %s: %s", db_path, exc)

    # Remove history database
    clear_history_db()

    # Remove downloaded static images (keep placeholders)
    static_root = Path(__file__).resolve().parent / "static"
    for subdir in ["solar", "maunakea"]:
        dir_path = static_root / subdir
        if not dir_path.exists():
            continue
        for item in dir_path.iterdir():
            if item.is_file() and item.stem.startswith("placeholder"):
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.warning("Failed to remove cached asset %s: %s", item, exc)
