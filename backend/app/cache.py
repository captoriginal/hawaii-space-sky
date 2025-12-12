import json
import logging
import sqlite3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import get_settings
from .storage import clear_history_db

logger = logging.getLogger(__name__)


def _get_conn() -> sqlite3.Connection:
    settings = get_settings()
    db_path = settings.CACHE_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            domain TEXT PRIMARY KEY,
            payload TEXT,
            source_timestamp TEXT,
            cached_at TEXT
        )
        """
    )
    conn.commit()


def save_cache(domain: str, data: Any, source_timestamp: Optional[str] = None) -> None:
    conn = _get_conn()
    payload = json.dumps(data)
    cached_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    conn.execute(
        "INSERT OR REPLACE INTO cache (domain, payload, source_timestamp, cached_at) VALUES (?, ?, ?, ?)",
        (domain, payload, source_timestamp, cached_at),
    )
    conn.commit()


def load_cache(domain: str) -> Optional[Tuple[Dict[str, Any], str, str]]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT payload, source_timestamp, cached_at FROM cache WHERE domain = ?", (domain,)
    ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["payload"])
    except Exception:
        return None
    return payload, row["source_timestamp"], row["cached_at"]


def is_cache_fresh(domain: str, max_age_seconds: int) -> bool:
    cached = load_cache(domain)
    if not cached:
        return False
    _, _, cached_at = cached
    try:
        ts = datetime.fromisoformat(cached_at.replace("Z", ""))
    except Exception:
        return False
    return datetime.utcnow() - ts < timedelta(seconds=max_age_seconds)


def clear_cache():
    """
    Clear application caches: drop cache db contents, remove history db, and delete
    downloaded static images so panels start fresh.
    """
    settings = get_settings()
    cache_path = settings.CACHE_DB_PATH
    # Remove cache database file entirely to ensure a clean slate
    try:
        conn = sqlite3.connect(cache_path)
        conn.close()
    except Exception:
        pass
    try:
        cache_path.unlink()
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Failed to remove cache DB %s: %s", cache_path, exc)

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
