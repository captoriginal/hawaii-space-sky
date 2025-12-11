from typing import List

from .models import Alert, DashboardStatus


def get_current_alerts(status: DashboardStatus) -> List[Alert]:
    alerts: List[Alert] = []
    space = status.space_weather
    observing = status.observing_index
    sun = status.sun

    # Solar flare alert (M-class or higher)
    try:
        if sun.current_class.upper().startswith(("M", "X")):
            alerts.append(
                Alert(
                    id="solar_flare",
                    severity="warning",
                    title="Elevated solar flares",
                    description=f"Latest X-ray classification {sun.current_class}.",
                )
            )
    except Exception:
        pass

    if space.kp >= 5:
        severity = "warning" if space.kp < 7 else "alert"
        alerts.append(
            Alert(
                id="kp_high",
                severity=severity,
                title="Geomagnetic storm",
                description=f"Kp at {space.kp} indicates disturbed geomagnetic conditions.",
            )
        )

    if space.bz_series:
        recent_bz = [p.value_nT for p in space.bz_series[-3:]]
        if all(val <= -10 for val in recent_bz):
            alerts.append(
                Alert(
                    id="bz_southward",
                    severity="warning",
                    title="Strong southward Bz",
                    description="Bz sustained below -10 nT; enhanced geomagnetic coupling possible.",
                )
            )

    if observing.score >= 8:
        alerts.append(
            Alert(
                id="observing_excellent",
                severity="info",
                title="Excellent observing",
                description=f"Observing index at {observing.score}/10 ({observing.rating}).",
            )
        )

    return alerts
