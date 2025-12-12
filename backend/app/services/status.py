import logging
from datetime import datetime
from urllib.parse import urljoin

from ..alerts import get_current_alerts
from ..config import Settings, get_settings
from ..data import compute_observing_index
from ..models import DashboardStatus, SolarImage, SunData
from ..plugins import load_plugin_config
from ..services.selectors import (
    select_maunakea,
    select_moon,
    select_solar_image,
    select_space_weather,
    select_sun,
)
from ..storage import record_history

logger = logging.getLogger(__name__)

SUN_CONFIG = load_plugin_config("sun")
DEFAULT_CAROUSEL_IMAGES = [
    {"label": "AIA 0193", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg"},
    {"label": "AIA 0171", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0171.jpg"},
    {"label": "AIA 0304", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0304.jpg"},
    {"label": "AIA 0211", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0211.jpg"},
    {"label": "AIA 0131", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0131.jpg"},
    {"label": "AIA 0335", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0335.jpg"},
    {"label": "AIA 0094", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0094.jpg"}
]


def _resolve_catalog_url(entry: dict, base_url: str | None) -> str | None:
    """
    Build an absolute image URL from a catalog entry that may contain either a direct URL or
    a relative path meant to be joined with the configured solar image base URL.
    """
    if not entry:
        return None
    url = entry.get("url")
    if url:
        return url
    path = entry.get("path")
    if not path or not base_url:
        return None
    base = base_url if base_url.endswith("/") else base_url + "/"
    return urljoin(base, path)


def _augment_sun_images(sun: SunData | None, primary: SolarImage | None, settings: Settings) -> None:
    if not sun:
        return
    existing_urls = {img.url for img in sun.images}
    if primary and primary.url not in existing_urls:
        sun.images.append(primary)
        existing_urls.add(primary.url)
    base_url = (
        SUN_CONFIG.get("carousel_base_url")
        or SUN_CONFIG.get("solar_image_url")
        or settings.SOLAR_IMAGE_URL
    )
    carousel = SUN_CONFIG.get("carousel_images", DEFAULT_CAROUSEL_IMAGES)
    if not isinstance(carousel, list):
        carousel = DEFAULT_CAROUSEL_IMAGES
    for entry in carousel:
        url = _resolve_catalog_url(entry, base_url)
        label = entry.get("label", "Solar")
        if not url:
            continue
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
    _augment_sun_images(sun, solar_image, settings)

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
