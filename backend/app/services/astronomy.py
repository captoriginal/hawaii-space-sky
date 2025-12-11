from datetime import datetime, timedelta, timezone
from typing import List, Optional

from skyfield import api
from skyfield import almanac
import numpy as np

from ..config import Settings
from ..models import MoonInfo


def load_timescale():
    return api.load.timescale()


def compute_moon_info(settings: Settings, start: Optional[datetime] = None) -> MoonInfo:
    ts = load_timescale()
    eph = api.load("de421.bsp")
    if start is None:
        start = datetime.utcnow().replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=24)

    try:
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
    except Exception:
        # Fallback minimal Moon info to avoid breaking the status endpoint
        return MoonInfo(
            illumination_fraction=0.0,
            rise_time=None,
            set_time=None,
            above_horizon_intervals=[],
            altitudes=[],
        )
