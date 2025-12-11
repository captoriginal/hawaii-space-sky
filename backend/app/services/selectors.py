import asyncio
import logging
from typing import Tuple
from datetime import datetime

from ..cache import is_cache_fresh, load_cache, save_cache
from ..config import Settings, get_settings
from ..data import get_demo_maunakea_conditions, get_demo_space_weather_data, get_demo_sun_data
from ..models import MaunakeaConditions, MoonInfo, SolarImage, SpaceWeatherData, SunData
from .astronomy import compute_moon_info
from .fetchers import fetch_space_weather, fetch_xray_flux
from .images import fetch_latest_solar_image

logger = logging.getLogger(__name__)


async def select_sun(settings: Settings) -> Tuple[SunData, str, bool]:
    stale = False
    if settings.DATA_MODE != "demo" and settings.USE_REAL_SUN:
        try:
            sun = await fetch_xray_flux(settings)
            save_cache("sun", sun.model_dump(), getattr(sun, "updated_at", None))
            return sun, "real", stale
        except Exception as exc:
            logger.warning("Sun real fetch failed: %s", exc)
            if is_cache_fresh("sun", settings.STALE_SUN_SECONDS):
                cached = load_cache("sun")
                if cached:
                    payload, _, cached_at = cached
                    stale = False
                    return SunData(**payload), "cache", stale
    cached = load_cache("sun")
    if cached:
        payload, _, cached_at = cached
        stale = True
        return SunData(**payload), "cache", stale
    return get_demo_sun_data(), "demo", stale


async def select_space_weather(settings: Settings) -> Tuple[SpaceWeatherData, str, bool]:
    stale = False
    if settings.DATA_MODE != "demo" and settings.USE_REAL_SPACE_WEATHER:
        try:
            space = await fetch_space_weather(settings)
            save_cache("space_weather", space.model_dump(), getattr(space, "updated_at", None))
            return space, "real", stale
        except Exception as exc:
            logger.warning("Space weather real fetch failed: %s", exc)
            if is_cache_fresh("space_weather", settings.STALE_SPACE_SECONDS):
                cached = load_cache("space_weather")
                if cached:
                    payload, _, _ = cached
                    return SpaceWeatherData(**payload), "cache", stale
    cached = load_cache("space_weather")
    if cached:
        payload, _, _ = cached
        stale = True
        return SpaceWeatherData(**payload), "cache", stale
    return get_demo_space_weather_data(), "demo", stale


async def select_solar_image(settings: Settings) -> Tuple[SolarImage | None, str, bool]:
    stale = False
    if settings.DATA_MODE != "demo" and settings.USE_REAL_SOLAR_IMAGES:
        try:
            img = await fetch_latest_solar_image(settings)
            if img:
                save_cache("solar_image", img.model_dump(), getattr(img, "captured_at", None))
                return img, "real", stale
        except Exception as exc:
            logger.warning("Solar image fetch failed: %s", exc)
            if is_cache_fresh("solar_image", settings.STALE_IMAGE_SECONDS):
                cached = load_cache("solar_image")
                if cached:
                    payload, _, _ = cached
                    return SolarImage(**payload), "cache", stale
    cached = load_cache("solar_image")
    if cached:
        payload, _, _ = cached
        stale = True
        return SolarImage(**payload), "cache", stale
    # demo placeholder fallback
    return SolarImage(
        url="/static/solar/placeholder.svg",
        source_name="Placeholder",
        wavelength=None,
        captured_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    ), "demo", stale


async def select_moon(settings: Settings) -> Tuple[MoonInfo | None, str, bool]:
    stale = False
    if settings.DATA_MODE != "demo" and settings.USE_REAL_MOON:
        try:
            moon = compute_moon_info(settings)
            save_cache("moon", moon.model_dump(), getattr(moon, "rise_time", None))
            return moon, "real", stale
        except Exception as exc:
            logger.warning("Moon info failed: %s", exc)
            if is_cache_fresh("moon", settings.STALE_MOON_SECONDS):
                cached = load_cache("moon")
                if cached:
                    payload, _, _ = cached
                    return MoonInfo(**payload), "cache", stale
    cached = load_cache("moon")
    if cached:
        payload, _, _ = cached
        stale = True
        return MoonInfo(**payload), "cache", stale
    # Demo moon info fallback
    demo = MoonInfo(
        illumination_fraction=0.18,
        rise_time=None,
        set_time=None,
        above_horizon_intervals=[],
        altitudes=[],
    )
    return demo, "demo", stale


async def select_maunakea(settings: Settings) -> Tuple[MaunakeaConditions, str, bool]:
    stale = False
    # Always rebuild if real MK is enabled to respect current configured URL
    if settings.DATA_MODE != "demo" and settings.USE_REAL_MAUNAKEA:
        mk = get_demo_maunakea_conditions()
        save_cache("maunakea", mk.model_dump(), getattr(mk, "updated_at", None))
        return mk, "real", stale

    cached = load_cache("maunakea")
    if cached and is_cache_fresh("maunakea", settings.STALE_MAUNAKEA_SECONDS):
        payload, _, _ = cached
        return MaunakeaConditions(**payload), "cache", stale
    mk = get_demo_maunakea_conditions()
    save_cache("maunakea", mk.model_dump(), getattr(mk, "updated_at", None))
    return mk, "demo", stale
