from datetime import datetime, timedelta
from random import uniform
from typing import List, Optional

from .models import (
    DashboardStatus,
    SpaceWeatherData,
    SunData,
    XrayFluxPoint,
    BzPoint,
    SpeedPoint,
    MaunakeaConditions,
    ObservingIndex,
)


def _iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat() + "Z"


def _build_xray_series(now: datetime) -> List[XrayFluxPoint]:
    # Create a small time series with gentle variation to feel realistic
    base_short = 7e-7
    base_long = 4e-6
    points: List[XrayFluxPoint] = []
    for i in range(6, -1, -1):
        ts = now - timedelta(minutes=i * 5)
        jitter = uniform(-1, 1) * 1e-7
        points.append(XrayFluxPoint(timestamp=_iso(ts), value_wm2=base_short + jitter))
    return points


def _build_long_series(now: datetime) -> List[XrayFluxPoint]:
    base_long = 4e-6
    points: List[XrayFluxPoint] = []
    for i in range(6, -1, -1):
        ts = now - timedelta(minutes=i * 5)
        jitter = uniform(-1, 1) * 2e-7
        points.append(XrayFluxPoint(timestamp=_iso(ts), value_wm2=base_long + jitter))
    return points


def get_demo_sun_data() -> SunData:
    now = datetime.utcnow()
    xray_short = _build_xray_series(now)
    xray_long = _build_long_series(now)
    current_class = "C2.3"
    activity_level = "active"
    return SunData(
        xray_flux_short=xray_short,
        xray_flux_long=xray_long,
        current_class=current_class,
        activity_level=activity_level,
        updated_at=_iso(now),
    )


def _build_bz_series(now: datetime) -> List[BzPoint]:
    points: List[BzPoint] = []
    for i in range(12, -1, -1):
        ts = now - timedelta(minutes=i * 5)
        jitter = uniform(-3.5, 2.5)
        points.append(BzPoint(timestamp=_iso(ts), value_nT=round(jitter, 2)))
    return points


def _build_speed_series(now: datetime) -> List[SpeedPoint]:
    points: List[SpeedPoint] = []
    base_speed = 520
    for i in range(12, -1, -1):
        ts = now - timedelta(minutes=i * 5)
        jitter = uniform(-35, 30)
        points.append(
            SpeedPoint(timestamp=_iso(ts), value_km_s=round(base_speed + jitter, 1))
        )
    return points


def get_demo_space_weather_data() -> SpaceWeatherData:
    now = datetime.utcnow()
    bz_series = _build_bz_series(now)
    speed_series = _build_speed_series(now)
    kp = 3.7
    return SpaceWeatherData(
        bz_series=bz_series,
        speed_series=speed_series,
        kp=kp,
        updated_at=_iso(now),
    )


def get_demo_maunakea_conditions() -> MaunakeaConditions:
    now = datetime.utcnow()
    return MaunakeaConditions(
        sky_image_url="https://dummyimage.com/640x360/112244/ffffff&text=Maunakea+Sky",
        cloud_fraction=round(max(0.0, min(1.0, uniform(0.05, 0.4))), 2),
        seeing_arcsec=round(uniform(0.6, 1.3), 2),
        transparency_mag=round(uniform(0.05, 0.25), 2),
        humidity=round(uniform(30, 60), 1),
        temperature_c=round(uniform(1, 4), 1),
        wind_speed_mps=round(uniform(3, 12), 1),
        updated_at=_iso(now),
    )


def compute_observing_index(
    maunakea: MaunakeaConditions, maybe_moon_info: Optional[dict] = None
) -> ObservingIndex:
    score = 10.0

    if maunakea.cloud_fraction is not None:
        score -= maunakea.cloud_fraction * 5  # up to -5 for full clouds
    if maunakea.transparency_mag is not None:
        score -= min(maunakea.transparency_mag * 10, 2.5)
    if maunakea.seeing_arcsec is not None and maunakea.seeing_arcsec > 1.5:
        score -= (maunakea.seeing_arcsec - 1.5) * 2

    score = max(0.0, min(10.0, round(score, 1)))

    if score <= 3:
        rating = "poor"
    elif score <= 6:
        rating = "fair"
    elif score <= 8:
        rating = "good"
    else:
        rating = "excellent"

    moon_summary = None
    best_window = None
    if maybe_moon_info:
        moon_summary = maybe_moon_info.get("moon_summary")
        best_window = maybe_moon_info.get("best_window")
    else:
        moon_summary = "Waxing crescent (18%), sets at 22:47 HST"
        best_window = "21:00–01:30 HST"

    notes = [
        f"Clouds: {int(maunakea.cloud_fraction * 100)}% cover"
        if maunakea.cloud_fraction is not None
        else "Cloud cover unavailable",
        f"Seeing ~ {maunakea.seeing_arcsec}\""
        if maunakea.seeing_arcsec is not None
        else "Seeing unavailable",
    ]

    return ObservingIndex(
        score=score,
        rating=rating,
        best_window=best_window,
        moon_summary=moon_summary,
        notes=notes,
    )


def build_demo_status() -> DashboardStatus:
    sun = get_demo_sun_data()
    space_weather = get_demo_space_weather_data()
    maunakea = get_demo_maunakea_conditions()
    observing_index = compute_observing_index(maunakea)
    timestamp = _iso(datetime.utcnow())
    return DashboardStatus(
        sun=sun,
        space_weather=space_weather,
        maunakea=maunakea,
        observing_index=observing_index,
        timestamp=timestamp,
    )
