import logging
from datetime import datetime

from ..alerts import get_current_alerts
from ..config import Settings, get_settings
from ..data import compute_observing_index
from ..models import DashboardStatus
from ..services.selectors import (
    select_maunakea,
    select_moon,
    select_solar_image,
    select_space_weather,
    select_sun,
)
from ..storage import record_history

logger = logging.getLogger(__name__)


async def build_status_payload(settings: Settings | None = None) -> DashboardStatus:
    if settings is None:
        settings = get_settings()

    sun, sun_origin, sun_stale = await select_sun(settings)
    space, space_origin, space_stale = await select_space_weather(settings)
    mk, mk_origin, mk_stale = await select_maunakea(settings)
    moon, moon_origin, moon_stale = await select_moon(settings)
    solar_image, solar_origin, solar_stale = await select_solar_image(settings)
    if sun and solar_image:
        sun.images = [solar_image]

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
