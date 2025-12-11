from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Location defaults for Maunakea, Hawai‘i
    LOCATION_LAT: float = 19.8207
    LOCATION_LON: float = -155.4681
    LOCATION_ELEV: float = 4205.0

    # Modes
    DATA_MODE: str = "demo"  # demo | hybrid | real
    USE_REAL_SUN: bool = False
    USE_REAL_SPACE_WEATHER: bool = False
    USE_REAL_SOLAR_IMAGES: bool = False
    USE_REAL_MOON: bool = False
    USE_REAL_MAUNAKEA: bool = False

    # External data endpoints
    XRAY_FLUX_URL: str = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
    SOLAR_WIND_URL: str = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    IMF_URL: str = "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json"
    KP_URL: str = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    SOLAR_IMAGE_URL: str = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg"
    # CFHT Nana'ao visible sky camera; source info: https://www.cfht.hawaii.edu/en/gallery/nanaao_data-access.php
    MAUNAKEA_SKYCAM_URL: str = "https://www.cfht.hawaii.edu/~nanaao/last_vis.png"

    # Timing / refresh (seconds)
    DATA_REFRESH_SECONDS: int = 300
    IMAGE_REFRESH_SECONDS: int = 900
    HTTP_TIMEOUT_SECONDS: float = 8.0
    HTTP_MAX_RETRIES: int = 2
    RETRY_BACKOFF_SECONDS: float = 0.8

    # Freshness thresholds (seconds)
    STALE_SUN_SECONDS: int = 1200
    STALE_SPACE_SECONDS: int = 1200
    STALE_IMAGE_SECONDS: int = 1800
    STALE_MOON_SECONDS: int = 86400
    STALE_MAUNAKEA_SECONDS: int = 1800

    # Paths
    CACHE_DB_PATH: Path = Path(__file__).resolve().parent / "cache.db"
    STATIC_DIR: Path = Path(__file__).resolve().parent / "static"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
