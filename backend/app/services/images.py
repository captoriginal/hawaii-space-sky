import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageEnhance

from ..config import Settings
from ..plugins import load_plugin_config
from ..models import SolarImage

logger = logging.getLogger(__name__)

STATIC_SOLAR_DIR = Path(__file__).resolve().parent.parent / "static" / "solar"
STATIC_SOLAR_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CAROUSEL_IMAGES = [
    {"label": "AIA 0193", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg"},
    {"label": "AIA 0171", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0171.jpg"},
    {"label": "AIA 0304", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0304.jpg"},
    {"label": "AIA 0211", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0211.jpg"},
    {"label": "AIA 0131", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0131.jpg"},
    {"label": "AIA 0335", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0335.jpg"},
    {"label": "AIA 0094", "url": "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0094.jpg"},
]


def _enhance_image(path: Path) -> None:
    try:
        img = Image.open(path)
        max_dim = 900
        img.thumbnail((max_dim, max_dim))
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)
        img.save(path)
    except Exception as exc:
        logger.warning("image enhancement failed: %s", exc)


async def fetch_latest_solar_image(settings: Settings) -> Optional[SolarImage]:
    """
    Download the latest solar image to static storage and return metadata.
    """
    sun_config = load_plugin_config("sun")
    base_url = (
        sun_config.get("carousel_base_url")
        or sun_config.get("solar_image_url")
        or settings.SOLAR_IMAGE_URL
    )
    carousel = sun_config.get("carousel_images") or DEFAULT_CAROUSEL_IMAGES
    if not isinstance(carousel, list):
        carousel = DEFAULT_CAROUSEL_IMAGES

    # Prefer a fully qualified URL; if the configured value looks like a base path, fall back to
    # the first carousel entry that can be resolved.
    url = base_url if base_url and Path(base_url).suffix else None
    if url is None:
        for entry in carousel:
            candidate = entry.get("url")
            if not candidate:
                path = entry.get("path")
                if path and base_url:
                    base = base_url if base_url.endswith("/") else base_url + "/"
                    candidate = urljoin(base, path)
            if candidate:
                url = candidate
                break

    if not url:
        return None

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = Path(url).suffix or ".jpg"
    local_name = f"solar_{ts}{suffix}"
    local_path = STATIC_SOLAR_DIR / local_name

    async with httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            _enhance_image(local_path)
        except Exception as exc:
            logger.warning("solar image fetch failed (%s)", exc)
            return None

    return SolarImage(
        url=f"/static/solar/{local_name}",
        source_name="Configured solar source",
        wavelength=None,
        captured_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    )
