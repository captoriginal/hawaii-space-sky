from fastapi import APIRouter, Query

from ..alerts import get_current_alerts
from ..data import build_demo_status
from ..models import DashboardStatus, HistoryResponse
from ..storage import fetch_history, record_history

router = APIRouter(prefix="/api")


@router.get("/status", response_model=DashboardStatus)
def get_status():
    status = build_demo_status()
    status.alerts = get_current_alerts(status)
    # Store the latest snapshot for history endpoints
    record_history(status)
    return status


@router.get("/history", response_model=HistoryResponse)
def get_history(hours: int = Query(24, ge=1, le=168)):
    """
    Return recent history points for sun, space weather, and observing index.
    """
    return fetch_history(hours)
