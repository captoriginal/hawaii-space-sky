import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageEnhance

from ..config import Settings
from ..models import SolarImage

logger = logging.getLogger(__name__)

STATIC_SOLAR_DIR = Path(__file__).resolve().parent.parent / "static" / "solar"
STATIC_SOLAR_DIR.mkdir(parents=True, exist_ok=True)


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
    url = settings.SOLAR_IMAGE_URL
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
