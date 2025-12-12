import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

import httpx

from ..config import Settings
from ..models import MaunakeaConditions
from .fetchers import _get_with_retry

logger = logging.getLogger(__name__)

POINTS_ENDPOINT = "https://api.weather.gov/points/{lat},{lon}"
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _parse_valid_window(valid_time: str) -> Tuple[datetime, datetime]:
    """
    valid_time strings look like: 2023-09-28T06:00:00+00:00/PT1H.
    Return (start, end) as UTC datetimes.
    """
    start_str, _, duration_str = valid_time.partition("/")
    start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    match = _DURATION_RE.match(duration_str or "")
    hours = int(match.group(1) or 0) if match else 0
    minutes = int(match.group(2) or 0) if match else 0
    duration = timedelta(hours=hours, minutes=minutes) or timedelta(hours=1)
    return start, start + duration


def _value_for_now(series: Dict[str, Any]) -> Tuple[float | None, datetime | None]:
    values = (series or {}).get("values") or []
    now = datetime.now(timezone.utc)
    for entry in values:
        valid = entry.get("validTime")
        if not valid:
            continue
        try:
            start, end = _parse_valid_window(valid)
        except Exception:
            continue
        if start <= now < end:
            return entry.get("value"), start
    if values:
        first = values[0]
        valid = first.get("validTime")
        start = None
        if valid:
            try:
                start, _ = _parse_valid_window(valid)
            except Exception:
                start = None
        return first.get("value"), start
    return None, None


def _convert_wind_to_mps(value: float | None, uom: str | None) -> float | None:
    if value is None:
        return None
    if not uom:
        return value
    if "m_s" in uom:
        return value
    if "km_h" in uom:
        return value * (1000 / 3600)
    if "knot" in uom or "kt" in uom:
        return value * 0.514444
    return value


def _derive_seeing(cloud_fraction: float | None, wind_mps: float | None) -> float | None:
    if cloud_fraction is None and wind_mps is None:
        return None
    cf = cloud_fraction or 0.0
    wind = wind_mps or 3.0
    seeing = 0.6 + cf * 0.8 + wind / 30
    return round(min(max(seeing, 0.5), 2.5), 2)


def _derive_transparency(cloud_fraction: float | None, humidity: float | None) -> float | None:
    if cloud_fraction is None and humidity is None:
        return None
    cf = cloud_fraction or 0.0
    hum = (humidity or 40) / 100
    transparency = 0.05 + cf * 0.5 + hum * 0.2
    return round(min(max(transparency, 0.05), 0.5), 2)


async def fetch_maunakea_conditions(settings: Settings) -> MaunakeaConditions:
    """
    Fetch Maunakea conditions using NOAA's weather.gov grid data near the summit.
    """
    point_url = POINTS_ENDPOINT.format(lat=settings.LOCATION_LAT, lon=settings.LOCATION_LON)
    headers = {"User-Agent": "hawaii-space-sky/0.1 (+https://github.com/)"}

    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, headers=headers, follow_redirects=True
    ) as client:
        point_resp = await _get_with_retry(client, point_url, settings)
        point_data = point_resp.json()
        grid_url = point_data["properties"]["forecastGridData"]
        grid_resp = await _get_with_retry(client, grid_url, settings)
        grid = grid_resp.json()

    props = grid.get("properties", {})

    sky_cover, sky_ts = _value_for_now(props.get("skyCover"))
    humidity, _ = _value_for_now(props.get("relativeHumidity"))
    temp_c, temp_ts = _value_for_now(props.get("temperature"))
    wind_speed_raw, _ = _value_for_now(props.get("windSpeed"))
    wind_uom = props.get("windSpeed", {}).get("uom")
    wind_speed_mps = (
        round(_convert_wind_to_mps(wind_speed_raw, wind_uom), 1)
        if wind_speed_raw is not None
        else None
    )

    cloud_fraction = None
    if sky_cover is not None:
        cloud_fraction = max(0.0, min(1.0, sky_cover / 100))

    seeing = _derive_seeing(cloud_fraction, wind_speed_mps)
    transparency = _derive_transparency(cloud_fraction, humidity)

    updated_ref = sky_ts or temp_ts or datetime.utcnow().replace(tzinfo=timezone.utc)
    updated_at = updated_ref.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return MaunakeaConditions(
        sky_image_url=settings.MAUNAKEA_SKYCAM_URL,
        cloud_fraction=cloud_fraction,
        seeing_arcsec=seeing,
        transparency_mag=transparency,
        humidity=round(humidity, 1) if humidity is not None else None,
        temperature_c=round(temp_c, 1) if temp_c is not None else None,
        wind_speed_mps=wind_speed_mps,
        updated_at=updated_at,
    )
