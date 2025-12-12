from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
from pathlib import Path

from .api.routes import router
from .config import get_settings
from .plugins import PANELS_CONFIG, get_panel_config, load_plugins
from .services.status import build_status_payload

logger = logging.getLogger(__name__)

app = FastAPI()
load_plugins(app)

# Allow all origins in dev so file:// or other local setups can hit it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],  # explicitly include file:// (null) origin
    allow_credentials=False,
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


@app.get("/api/panels")
def read_panel_config():
    return get_panel_config()


app.include_router(router)

# Serve the frontend bundle directly from FastAPI to avoid file:// origins
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
