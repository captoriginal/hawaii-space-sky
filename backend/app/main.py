from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import asyncio
import logging

from .api.routes import router
from .config import get_settings
from .services.status import build_status_payload

logger = logging.getLogger(__name__)

app = FastAPI()

# Allow all origins in dev so file:// or other local setups can hit it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in dev, this is fine; we'll tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


async def background_refresh():
    settings = get_settings()
    if settings.DATA_MODE == "demo":
        return
    while True:
        try:
            await build_status_payload(settings)
        except Exception as exc:
            logger.warning("Background refresh failed: %s", exc)
        await asyncio.sleep(settings.DATA_REFRESH_SECONDS)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_refresh())


app.include_router(router)
