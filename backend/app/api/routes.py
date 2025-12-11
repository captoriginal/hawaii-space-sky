from fastapi import APIRouter, Query

from ..models import DashboardStatus, HistoryResponse, EarthFrame
from ..services.status import build_status_payload
from ..services.earth_loop import get_earth_loop
from ..storage import fetch_history

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


@router.get("/earth/loop", response_model=list[EarthFrame])
async def earth_loop():
    return await get_earth_loop()
