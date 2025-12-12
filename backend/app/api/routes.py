from fastapi import APIRouter, Query, HTTPException

from fastapi import APIRouter, Query

from ..cache import clear_cache
from ..models import DashboardStatus, HistoryResponse
from ..services.status import build_status_payload
from ..storage import fetch_history
from ..plugins import load_plugin_config

router = APIRouter(prefix="/api")


@router.get("/status", response_model=DashboardStatus)
async def get_status():
    return await build_status_payload()


@router.get("/history", response_model=HistoryResponse)
def get_history(hours: int = Query(24, ge=1, le=168)):
    """
    Return recent history points for sun, space weather, and observing index.
    """
    return fetch_history(hours)


@router.post("/cache/clear")
def clear_cache_endpoint():
    clear_cache()
    return {"status": "ok"}


@router.get("/plugins/{plugin_name}/config")
def get_plugin_config(plugin_name: str):
    config = load_plugin_config(plugin_name)
    if not config:
        raise HTTPException(status_code=404, detail="Plugin config not found")
    return config
