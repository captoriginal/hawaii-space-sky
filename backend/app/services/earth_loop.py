import re
import time
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import HTTPException

from ..config import get_settings
from ..plugins import load_plugin_config
from ..models import EarthFrame

logger = logging.getLogger(__name__)

EARTH_CACHE: List[EarthFrame] = []
EARTH_CACHE_TS: float = 0.0
EARTH_CONFIG = load_plugin_config("earth")
EARTH_CACHE_TTL = EARTH_CONFIG.get("cache_ttl_seconds", 600)

LISTING_PATTERN = EARTH_CONFIG.get(
    "filename_regex", r"(\d{4})(\d{3})(\d{2})(\d{2})_GOES18-ABI-FD-GEOCOLOR-1808x1808\.jpg"
)
LISTING_RE = re.compile(LISTING_PATTERN)
BASE_URL = EARTH_CONFIG.get(
    "loop_base_url", "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/GEOCOLOR/"
)
TIMESTAMP_RE = re.compile(r"(\d{4})(\d{3})(\d{2})(\d{2})")


def _parse_timestamp_from_filename(name: str) -> Optional[str]:
    m = TIMESTAMP_RE.search(name)
    if not m:
        return None
    year, jjj, hh, mm = m.groups()
    try:
        dt = datetime.strptime(f"{year}{jjj}{hh}{mm}", "%Y%j%H%M")
        return dt.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return None


async def fetch_earth_frames() -> List[EarthFrame]:
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        try:
            resp = await client.get(BASE_URL)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Earth loop fetch failed: %s", exc)
            raise

    matches = [match.group(0) for match in LISTING_RE.finditer(resp.text)]
    unique = list(dict.fromkeys(matches))
    if not unique:
        raise HTTPException(status_code=503, detail="No earth frames found")
    unique_sorted = sorted(unique)
    last_50 = unique_sorted[-50:]
    frames: List[EarthFrame] = []
    for fname in last_50:
        ts = _parse_timestamp_from_filename(fname)
        if not ts:
            continue
        frames.append(EarthFrame(url=f"{BASE_URL}{fname}", timestamp=ts))
    if not frames:
        raise HTTPException(status_code=503, detail="No valid earth frames parsed")
    return frames


async def get_earth_loop() -> List[EarthFrame]:
    global EARTH_CACHE, EARTH_CACHE_TS
    now = time.time()
    if EARTH_CACHE and now - EARTH_CACHE_TS < EARTH_CACHE_TTL:
        return EARTH_CACHE
    try:
        frames = await fetch_earth_frames()
        EARTH_CACHE = frames
        EARTH_CACHE_TS = now
        return frames
    except Exception:
        if EARTH_CACHE:
            logger.warning("Using cached earth frames after fetch failure")
            return EARTH_CACHE
        raise HTTPException(status_code=503, detail="Earth loop unavailable")
