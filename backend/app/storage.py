import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from .models import (
    DashboardStatus,
    HistoryObservingPoint,
    HistoryResponse,
    HistorySpaceWeatherPoint,
    HistorySunPoint,
)

DB_PATH = Path(__file__).resolve().parent / "history.db"
_conn = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _ensure_tables(_conn)
    return _conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sun_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL,
            xray_flux_short REAL,
            xray_flux_long REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS space_weather_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL,
            bz REAL,
            speed_km_s REAL,
            kp REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observing_history (
            timestamp TEXT PRIMARY KEY,
            ts_epoch REAL,
            index_score REAL
        )
        """
    )
    conn.commit()


def _parse_ts(ts_str: str) -> datetime:
    clean = ts_str.replace("Z", "")
    return datetime.fromisoformat(clean)


def record_history(status: DashboardStatus) -> None:
    conn = get_conn()
    try:
        ts = _parse_ts(status.timestamp)
    except Exception:
        ts = datetime.utcnow()
    ts_epoch = ts.timestamp()

    sun_short = (
        status.sun.xray_flux_short[-1].value_wm2 if status.sun.xray_flux_short else None
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

    bz = status.space_weather.bz_series[-1].value_nT if status.space_weather.bz_series else None
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

    conn.execute(
        """
        INSERT OR REPLACE INTO observing_history (timestamp, ts_epoch, index_score)
        VALUES (?, ?, ?)
        """,
        (status.timestamp, ts_epoch, status.observing_index.score),
    )
    conn.commit()


def fetch_history(hours: int) -> HistoryResponse:
    conn = get_conn()
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
