import logging
import asyncio
import time
from typing import Optional
from datetime import datetime

import httpx

from ..config import Settings
from ..data import get_demo_space_weather_data, get_demo_sun_data
from ..models import SpaceWeatherData, SunData, XrayFluxPoint, BzPoint, SpeedPoint

logger = logging.getLogger(__name__)


def _flux_to_class(value: float) -> str:
    # GOES classification: A:1e-8, B:1e-7, C:1e-6, M:1e-5, X:1e-4
    thresholds = [1e-8, 1e-7, 1e-6, 1e-5, 1e-4]
    labels = ["A", "B", "C", "M", "X"]
    for i in range(len(thresholds) - 1, -1, -1):
        if value >= thresholds[i]:
            exponent = value / thresholds[i]
            return f"{labels[i]}{exponent:.1f}"
    return "A0.0"


def _flux_to_activity(value: float) -> str:
    if value >= 1e-5:
        return "stormy"
    if value >= 1e-6:
        return "active"
    return "quiet"


async def _get_with_retry(client: httpx.AsyncClient, url: str, settings: Settings):
    retries = settings.HTTP_MAX_RETRIES
    backoff = settings.RETRY_BACKOFF_SECONDS
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            if attempt >= retries:
                raise
            logger.warning("Fetch failed (%s), retrying %s/%s", exc, attempt + 1, retries)
            await asyncio.sleep(backoff * (attempt + 1))


async def fetch_xray_flux(settings: Settings) -> SunData:
    """
    Fetch GOES X-ray flux. Falls back to demo on error.
    """
    if settings.DATA_MODE == "demo" or not settings.USE_REAL_SUN:
        return get_demo_sun_data()

    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        try:
            resp = await _get_with_retry(client, settings.XRAY_FLUX_URL, settings)
            payload = resp.json()
        except Exception as exc:
            logger.warning("xray fetch failed (%s); falling back to demo", exc)
            return get_demo_sun_data()

    # payload is list of dicts with time_tag, flux, energy
    short_points = []
    long_points = []
    for item in payload[-40:]:
        try:
            ts = item.get("time_tag")
            flux = float(item.get("flux"))
            energy = item.get("energy")
            point = XrayFluxPoint(timestamp=ts, value_wm2=flux)
            if energy == "0.1-0.8":
                short_points.append(point)
            elif energy == "0.05-0.4":
                long_points.append(point)
        except Exception:
            continue

    short_points = short_points[-12:] if short_points else []
    long_points = long_points[-12:] if long_points else []

    latest_flux = short_points[-1].value_wm2 if short_points else 0.0
    current_class = _flux_to_class(latest_flux)
    activity_level = _flux_to_activity(latest_flux)
    updated_at = short_points[-1].timestamp if short_points else datetime.utcnow().isoformat() + "Z"

    return SunData(
        xray_flux_short=short_points or get_demo_sun_data().xray_flux_short,
        xray_flux_long=long_points or get_demo_sun_data().xray_flux_long,
        current_class=current_class,
        activity_level=activity_level,
        updated_at=updated_at,
        images=[],
    )


async def fetch_space_weather(settings: Settings) -> SpaceWeatherData:
    """
    Fetch solar wind/IMF and Kp. Falls back to demo on error.
    """
    if settings.DATA_MODE == "demo" or not settings.USE_REAL_SPACE_WEATHER:
        return get_demo_space_weather_data()

    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        try:
            plasma_resp = await _get_with_retry(client, settings.SOLAR_WIND_URL, settings)
            plasma = plasma_resp.json()
            mag_resp = await _get_with_retry(client, settings.IMF_URL, settings)
            mag = mag_resp.json()
            kp_resp = await _get_with_retry(client, settings.KP_URL, settings)
            kp_payload = kp_resp.json()
        except Exception as exc:
            logger.warning("space weather fetch failed (%s); falling back to demo", exc)
            return get_demo_space_weather_data()

    def parse_table(tbl, value_index, ts_index=0, limit=24):
        if not isinstance(tbl, list) or len(tbl) <= 1:
            return []
        data = []
        for row in tbl[1:][-limit:]:
            try:
                ts = row[ts_index]
                val = float(row[value_index])
                data.append((ts, val))
            except Exception:
                continue
        return data

    speed_data = parse_table(plasma, value_index=7, limit=24)  # speed_km_s
    bz_data = parse_table(mag, value_index=5, limit=24)  # bz_gsm

    bz_series = [BzPoint(timestamp=ts, value_nT=val) for ts, val in bz_data]
    speed_series = [SpeedPoint(timestamp=ts, value_km_s=val) for ts, val in speed_data]

    kp_val = None
    # planetary K index feed returns list with header row; last row has kp at index 1
    if isinstance(kp_payload, list) and len(kp_payload) > 1:
        try:
            kp_val = float(kp_payload[-1][1])
        except Exception:
            kp_val = None
    if kp_val is None:
        kp_val = 2.0

    updated_at = bz_series[-1].timestamp if bz_series else datetime.utcnow().isoformat() + "Z"

    return SpaceWeatherData(
        bz_series=bz_series or get_demo_space_weather_data().bz_series,
        speed_series=speed_series or get_demo_space_weather_data().speed_series,
        kp=kp_val,
        updated_at=updated_at,
    )


async def update_real_status(settings: Settings) -> tuple[SunData, SpaceWeatherData]:
    sun: Optional[SunData] = None
    space: Optional[SpaceWeatherData] = None
    results = await asyncio.gather(
        fetch_xray_flux(settings), fetch_space_weather(settings), return_exceptions=True
    )
    if isinstance(results[0], Exception):
        logger.warning("Sun fetch error: %s", results[0])
    else:
        sun = results[0]
    if isinstance(results[1], Exception):
        logger.warning("Space weather fetch error: %s", results[1])
    else:
        space = results[1]

    if sun is None:
        sun = get_demo_sun_data()
    if space is None:
        space = get_demo_space_weather_data()
    return sun, space
