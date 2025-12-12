from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from skyfield import almanac, api
import numpy as np

from ..config import Settings
from ..models import MoonInfo

REPO_ROOT = Path(__file__).resolve().parents[3]
EPHEMERIS_PATH = REPO_ROOT / "de421.bsp"


def load_timescale():
    return api.load.timescale()


def _load_ephemeris():
    if EPHEMERIS_PATH.exists():
        return api.load_file(EPHEMERIS_PATH)
    return api.load("de421.bsp")


def compute_moon_info(settings: Settings, start: Optional[datetime] = None) -> MoonInfo:
    ts = load_timescale()
    eph = _load_ephemeris()
    if start is None:
        start = datetime.utcnow().replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=24)

    earth = eph["earth"]
    topo = api.Topos(
        latitude_degrees=settings.LOCATION_LAT,
        longitude_degrees=settings.LOCATION_LON,
        elevation_m=settings.LOCATION_ELEV,
    )
    observer = earth + topo

    times = ts.utc(start.year, start.month, start.day, start.hour, range(0, 25))
    moon_altitudes = []
    for t in times:
        astrometric = observer.at(t).observe(eph["moon"])
        alt, _, _ = astrometric.apparent().altaz()
        moon_altitudes.append((t.utc_datetime().isoformat(), alt.degrees))

    phase = almanac.moon_phase(eph, ts.from_datetime(start))
    illumination_fraction = (1 + np.cos(phase.radians)) / 2

    t0 = ts.from_datetime(start)
    t1 = ts.from_datetime(end)
    f = almanac.risings_and_settings(eph, eph["moon"], observer)
    times_rs, events = almanac.find_discrete(t0, t1, f)
    intervals: List[dict] = []
    for t, ev in zip(times_rs, events):
        label = "rise" if ev else "set"
        intervals.append({label: t.utc_datetime().isoformat()})

    rise_time = None
    set_time = None
    for entry in intervals:
        if "rise" in entry and rise_time is None:
            rise_time = entry["rise"]
        if "set" in entry and set_time is None:
            set_time = entry["set"]

    return MoonInfo(
        illumination_fraction=illumination_fraction,
        rise_time=rise_time,
        set_time=set_time,
        above_horizon_intervals=intervals,
        altitudes=moon_altitudes,
    )
