import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import get_settings


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
