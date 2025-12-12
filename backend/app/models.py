from pydantic import BaseModel, Field
from typing import List, Optional


class SolarImage(BaseModel):
    url: str
    source_name: str
    wavelength: Optional[str] = None
    captured_at: Optional[str] = None


class XrayFluxPoint(BaseModel):
    timestamp: str
    value_wm2: float


class SunData(BaseModel):
    xray_flux_short: List[XrayFluxPoint]
    xray_flux_long: List[XrayFluxPoint]
    current_class: str
    activity_level: str
    updated_at: str
    images: List[SolarImage] = Field(default_factory=list)


class BzPoint(BaseModel):
    timestamp: str
    value_nT: float


class SpeedPoint(BaseModel):
    timestamp: str
    value_km_s: float


class SpaceWeatherData(BaseModel):
    bz_series: List[BzPoint]
    speed_series: List[SpeedPoint]
    kp: Optional[float]
    updated_at: str


class MaunakeaConditions(BaseModel):
    sky_image_url: Optional[str]
    cloud_fraction: Optional[float]  # 0-1
    seeing_arcsec: Optional[float]
    transparency_mag: Optional[float]
    humidity: Optional[float]
    temperature_c: Optional[float]
    wind_speed_mps: Optional[float]
    updated_at: str


class MoonInfo(BaseModel):
    illumination_fraction: float
    rise_time: Optional[str] = None
    set_time: Optional[str] = None
    above_horizon_intervals: List[dict] = Field(default_factory=list)
    altitudes: List[List] = Field(default_factory=list)


class ObservingIndex(BaseModel):
    score: float  # 0-10
    rating: str  # "poor", "fair", "good", "excellent"
    best_window: Optional[str]
    moon_summary: Optional[str]
    notes: List[str]
    moon_info: Optional[MoonInfo] = None


class Alert(BaseModel):
    id: str
    severity: str  # info, warning, alert
    title: str
    description: str


class HistorySunPoint(BaseModel):
    timestamp: str
    xray_flux_short: Optional[float]
    xray_flux_long: Optional[float]


class HistorySpaceWeatherPoint(BaseModel):
    timestamp: str
    bz: Optional[float]
    speed_km_s: Optional[float]
    kp: Optional[float]


class HistoryObservingPoint(BaseModel):
    timestamp: str
    index_score: Optional[float]


class HistoryResponse(BaseModel):
    sun: List[HistorySunPoint]
    space_weather: List[HistorySpaceWeatherPoint]
    observing_index: List[HistoryObservingPoint]

class EarthFrame(BaseModel):
    url: str
    timestamp: str


class DashboardStatus(BaseModel):
    sun: Optional[SunData] = None
    space_weather: Optional[SpaceWeatherData] = None
    maunakea: Optional[MaunakeaConditions] = None
    observing_index: Optional[ObservingIndex] = None
    alerts: List[Alert] = Field(default_factory=list)
    data_sources: dict = Field(default_factory=dict)
    timestamp: str
