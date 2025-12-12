import logging
from typing import Optional, Tuple
from datetime import datetime

from ..cache import is_cache_fresh, load_cache, save_cache
from ..config import Settings
from ..data import get_demo_maunakea_conditions, get_demo_space_weather_data, get_demo_sun_data
from ..models import MaunakeaConditions, MoonInfo, SolarImage, SpaceWeatherData, SunData
from .astronomy import compute_moon_info
from .fetchers import fetch_space_weather, fetch_xray_flux
from .maunakea import fetch_maunakea_conditions
from .images import fetch_latest_solar_image

logger = logging.getLogger(__name__)


async def select_sun(settings: Settings) -> Tuple[Optional[SunData], str, bool]:
    if settings.DATA_MODE == "demo":
        return get_demo_sun_data(), "demo", False
    if not settings.USE_REAL_SUN:
        return None, "unavailable", False
    try:
        sun = await fetch_xray_flux(settings)
        save_cache("sun", sun.model_dump(), getattr(sun, "updated_at", None))
        return sun, "real", False
    except Exception as exc:
        logger.warning("Sun real fetch failed: %s", exc)
    cached = load_cache("sun")
    if cached:
        payload, _, _ = cached
        stale = not is_cache_fresh("sun", settings.STALE_SUN_SECONDS)
        return SunData(**payload), "cache", stale
    return None, "unavailable", True


async def select_space_weather(settings: Settings) -> Tuple[Optional[SpaceWeatherData], str, bool]:
    if settings.DATA_MODE == "demo":
        return get_demo_space_weather_data(), "demo", False
    if not settings.USE_REAL_SPACE_WEATHER:
        return None, "unavailable", False
    try:
        space = await fetch_space_weather(settings)
        save_cache("space_weather", space.model_dump(), getattr(space, "updated_at", None))
        return space, "real", False
    except Exception as exc:
        logger.warning("Space weather real fetch failed: %s", exc)
    cached = load_cache("space_weather")
    if cached:
        payload, _, _ = cached
        stale = not is_cache_fresh("space_weather", settings.STALE_SPACE_SECONDS)
        return SpaceWeatherData(**payload), "cache", stale
    return None, "unavailable", True


async def select_solar_image(settings: Settings) -> Tuple[SolarImage | None, str, bool]:
    if settings.DATA_MODE == "demo":
        return (
            SolarImage(
                url="/static/solar/placeholder.svg",
                source_name="Placeholder",
                wavelength=None,
                captured_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            ),
            "demo",
            False,
        )
    if not settings.USE_REAL_SOLAR_IMAGES:
        return None, "unavailable", False
    try:
        img = await fetch_latest_solar_image(settings)
        if img:
            save_cache("solar_image", img.model_dump(), getattr(img, "captured_at", None))
            return img, "real", False
    except Exception as exc:
        logger.warning("Solar image fetch failed: %s", exc)
    cached = load_cache("solar_image")
    if cached:
        payload, _, _ = cached
        stale = not is_cache_fresh("solar_image", settings.STALE_IMAGE_SECONDS)
        return SolarImage(**payload), "cache", stale
    return None, "unavailable", True


async def select_moon(settings: Settings) -> Tuple[MoonInfo | None, str, bool]:
    if settings.DATA_MODE == "demo":
        demo = MoonInfo(
            illumination_fraction=0.18,
            rise_time=None,
            set_time=None,
            above_horizon_intervals=[],
            altitudes=[],
        )
        return demo, "demo", False
    if not settings.USE_REAL_MOON:
        return None, "unavailable", False
    try:
        moon = compute_moon_info(settings)
        save_cache("moon", moon.model_dump(), getattr(moon, "rise_time", None))
        return moon, "real", False
    except Exception as exc:
        logger.warning("Moon info failed: %s", exc)
    cached = load_cache("moon")
    if cached:
        payload, _, _ = cached
        stale = not is_cache_fresh("moon", settings.STALE_MOON_SECONDS)
        return MoonInfo(**payload), "cache", stale
    return None, "unavailable", True


async def select_maunakea(settings: Settings) -> Tuple[Optional[MaunakeaConditions], str, bool]:
    if settings.DATA_MODE == "demo":
        mk = get_demo_maunakea_conditions()
        save_cache("maunakea", mk.model_dump(), getattr(mk, "updated_at", None))
        return mk, "demo", False
    if not settings.USE_REAL_MAUNAKEA:
        return None, "unavailable", False
    try:
        mk = await fetch_maunakea_conditions(settings)
        save_cache("maunakea", mk.model_dump(), getattr(mk, "updated_at", None))
        return mk, "real", False
    except Exception as exc:
        logger.warning("Maunakea real fetch failed: %s", exc)
    cached = load_cache("maunakea")
    if cached:
        payload, _, _ = cached
        stale = not is_cache_fresh("maunakea", settings.STALE_MAUNAKEA_SECONDS)
        return MaunakeaConditions(**payload), "cache", stale
    return None, "unavailable", True
