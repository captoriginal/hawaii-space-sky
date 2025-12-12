import logging
from datetime import datetime

from ..alerts import get_current_alerts
from ..config import Settings, get_settings
from ..data import compute_observing_index
from ..models import DashboardStatus, SolarImage, SunData
from ..services.selectors import (
    select_maunakea,
    select_moon,
    select_solar_image,
    select_space_weather,
    select_sun,
)
from ..storage import record_history

logger = logging.getLogger(__name__)

SDO_IMAGE_CATALOG = [
    ("AIA 0193", "latest_512_0193.jpg"),
    ("AIA 0171", "latest_512_0171.jpg"),
    ("AIA 0304", "latest_512_0304.jpg"),
    ("AIA 0211", "latest_512_0211.jpg"),
    ("AIA 0131", "latest_512_0131.jpg"),
    ("AIA 0335", "latest_512_0335.jpg"),
    ("AIA 0094", "latest_512_0094.jpg"),
    ("AIA 1600", "latest_512_1600.jpg"),
    ("AIA 1700", "latest_512_1700.jpg"),
    ("AIA 211/193/171", "latest_1024_211193171.jpg"),
    ("AIA 304/211/171", "f_304_211_171_512.jpg"),
    ("AIA 094/335/193", "f_094_335_193_512.jpg"),
    ("AIA 171 & HMIB", "f_HMImag_171_512.jpg"),
    ("HMI Magnetogram", "latest_512_HMIB.jpg"),
    ("HMI Intensitygram", "latest_512_HMII.jpg"),
    ("HMI Dopplergram", "latest_512_HMID.jpg"),
]
SDO_IMAGE_BASE = "https://sdo.gsfc.nasa.gov/assets/img/latest/"


def _augment_sun_images(sun: SunData | None, primary: SolarImage | None) -> None:
    if not sun:
        return
    existing_urls = {img.url for img in sun.images}
    if primary and primary.url not in existing_urls:
        sun.images.append(primary)
        existing_urls.add(primary.url)
    for label, path in SDO_IMAGE_CATALOG:
        url = f"{SDO_IMAGE_BASE}{path}"
        if url in existing_urls:
            continue
        sun.images.append(
            SolarImage(
                url=url,
                source_name=label,
                captured_at=None,
            )
        )


async def build_status_payload(settings: Settings | None = None) -> DashboardStatus:
    if settings is None:
        settings = get_settings()

    sun, sun_origin, sun_stale = await select_sun(settings)
    space, space_origin, space_stale = await select_space_weather(settings)
    mk, mk_origin, mk_stale = await select_maunakea(settings)
    moon, moon_origin, moon_stale = await select_moon(settings)
    solar_image, solar_origin, solar_stale = await select_solar_image(settings)
    _augment_sun_images(sun, solar_image)

    observing_index = (
        compute_observing_index(maunakea=mk, moon_info=moon, space_weather=space)
        if mk
        else None
    )

    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    data_sources = {
        "sun": sun_origin,
        "space_weather": space_origin,
        "maunakea": mk_origin,
        "moon": moon_origin,
        "solar_image": solar_origin,
        "observing_index": "computed" if observing_index else "unavailable",
    }
    status = DashboardStatus(
        sun=sun,
        space_weather=space,
        maunakea=mk,
        observing_index=observing_index,
        alerts=[],
        data_sources=data_sources,
        timestamp=timestamp,
    )

    if sun and sun_stale:
        status.alerts.append(
            {
                "id": "stale_sun_data",
                "severity": "warning",
                "title": "Sun data outdated",
                "description": "Using cached Sun data older than freshness window.",
            }
        )
    if space and space_stale:
        status.alerts.append(
            {
                "id": "stale_space_data",
                "severity": "warning",
                "title": "Space weather data outdated",
                "description": "Using cached space weather data older than freshness window.",
            }
        )
    if solar_image and solar_stale:
        status.alerts.append(
            {
                "id": "stale_solar_image",
                "severity": "info",
                "title": "Solar image cached",
                "description": "Using cached solar image.",
            }
        )
    if mk and mk_stale:
        status.alerts.append(
            {
                "id": "stale_maunakea",
                "severity": "warning",
                "title": "Maunakea data cached",
                "description": "Using cached Maunakea conditions.",
            }
        )
    if moon and moon_stale:
        status.alerts.append(
            {
                "id": "stale_moon",
                "severity": "info",
                "title": "Moon data cached",
                "description": "Using cached Moon data.",
            }
        )

    status.alerts.extend(get_current_alerts(status))

    try:
        record_history(status)
    except Exception as exc:
        logger.warning("History record failed (%s)", exc)
    return status
