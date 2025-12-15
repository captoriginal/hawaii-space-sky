import pytest
from pydantic import ValidationError

from backend.app.models import (
    Alert,
    BzPoint,
    DashboardStatus,
    HistoryObservingPoint,
    HistoryResponse,
    HistorySpaceWeatherPoint,
    HistorySunPoint,
    MaunakeaConditions,
    MoonInfo,
    ObservingIndex,
    SolarImage,
    SpaceWeatherData,
    SpeedPoint,
    SunData,
    XrayFluxPoint,
)


class TestXrayFluxPoint:
    """Test XrayFluxPoint model."""

    def test_valid_xray_flux_point(self):
        """Test creating valid XrayFluxPoint."""
        point = XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.5e-6)
        assert point.timestamp == "2025-01-01T12:00:00Z"
        assert point.value_wm2 == 1.5e-6

    def test_xray_flux_point_serialization(self):
        """Test JSON serialization."""
        point = XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.5e-6)
        data = point.model_dump()
        assert data["timestamp"] == "2025-01-01T12:00:00Z"
        assert data["value_wm2"] == 1.5e-6

    def test_xray_flux_point_missing_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            XrayFluxPoint(timestamp="2025-01-01T12:00:00Z")

        with pytest.raises(ValidationError):
            XrayFluxPoint(value_wm2=1.5e-6)


class TestSunData:
    """Test SunData model."""

    def test_valid_sun_data(self):
        """Test creating valid SunData."""
        sun = SunData(
            xray_flux_short=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.5e-6)],
            xray_flux_long=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.4e-6)],
            current_class="C1.5",
            activity_level="active",
            updated_at="2025-01-01T12:00:00Z",
        )
        assert sun.current_class == "C1.5"
        assert sun.activity_level == "active"
        assert len(sun.xray_flux_short) == 1
        assert len(sun.images) == 0  # Default empty list

    def test_sun_data_with_images(self):
        """Test SunData with solar images."""
        sun = SunData(
            xray_flux_short=[],
            xray_flux_long=[],
            current_class="B1.0",
            activity_level="quiet",
            updated_at="2025-01-01T12:00:00Z",
            images=[
                SolarImage(
                    url="https://example.com/sun.jpg",
                    source_name="SDO",
                    wavelength="193",
                    captured_at="2025-01-01T12:00:00Z",
                )
            ],
        )
        assert len(sun.images) == 1
        assert sun.images[0].wavelength == "193"

    def test_sun_data_empty_series(self):
        """Test SunData with empty flux series."""
        sun = SunData(
            xray_flux_short=[],
            xray_flux_long=[],
            current_class="A0.0",
            activity_level="quiet",
            updated_at="2025-01-01T12:00:00Z",
        )
        assert len(sun.xray_flux_short) == 0
        assert len(sun.xray_flux_long) == 0


class TestSpaceWeatherData:
    """Test SpaceWeatherData model."""

    def test_valid_space_weather(self):
        """Test creating valid SpaceWeatherData."""
        space = SpaceWeatherData(
            bz_series=[BzPoint(timestamp="2025-01-01T12:00:00Z", value_nT=-5.2)],
            speed_series=[SpeedPoint(timestamp="2025-01-01T12:00:00Z", value_km_s=420.5)],
            kp=3.5,
            updated_at="2025-01-01T12:00:00Z",
        )
        assert space.kp == 3.5
        assert len(space.bz_series) == 1
        assert len(space.speed_series) == 1

    def test_space_weather_optional_kp(self):
        """Test that Kp can be None."""
        space = SpaceWeatherData(
            bz_series=[],
            speed_series=[],
            kp=None,
            updated_at="2025-01-01T12:00:00Z",
        )
        assert space.kp is None

    def test_space_weather_negative_values(self):
        """Test handling of negative Bz values."""
        space = SpaceWeatherData(
            bz_series=[BzPoint(timestamp="2025-01-01T12:00:00Z", value_nT=-999.9)],
            speed_series=[SpeedPoint(timestamp="2025-01-01T12:00:00Z", value_km_s=400.0)],
            kp=0.0,
            updated_at="2025-01-01T12:00:00Z",
        )
        assert space.bz_series[0].value_nT == -999.9


class TestMaunakeaConditions:
    """Test MaunakeaConditions model."""

    def test_valid_maunakea_conditions(self):
        """Test creating valid MaunakeaConditions."""
        conditions = MaunakeaConditions(
            sky_image_url="https://example.com/sky.jpg",
            cloud_fraction=0.25,
            seeing_arcsec=0.8,
            transparency_mag=0.15,
            humidity=35.0,
            temperature_c=5.0,
            wind_speed_mps=8.5,
            updated_at="2025-01-01T12:00:00Z",
        )
        assert conditions.cloud_fraction == 0.25
        assert conditions.seeing_arcsec == 0.8

    def test_maunakea_all_optional_fields(self):
        """Test that most fields are optional."""
        conditions = MaunakeaConditions(
            sky_image_url=None,
            cloud_fraction=None,
            seeing_arcsec=None,
            transparency_mag=None,
            humidity=None,
            temperature_c=None,
            wind_speed_mps=None,
            updated_at="2025-01-01T12:00:00Z",
        )
        assert conditions.sky_image_url is None
        assert conditions.cloud_fraction is None
        assert conditions.humidity is None


class TestObservingIndex:
    """Test ObservingIndex model."""

    def test_valid_observing_index(self):
        """Test creating valid ObservingIndex."""
        obs = ObservingIndex(
            score=7.5,
            rating="good",
            best_window="10pm - 2am",
            moon_summary="New moon",
            notes=["Clear skies", "Low humidity"],
        )
        assert obs.score == 7.5
        assert obs.rating == "good"
        assert len(obs.notes) == 2

    def test_observing_index_with_moon_info(self):
        """Test ObservingIndex with MoonInfo."""
        moon = MoonInfo(
            illumination_fraction=0.25,
            rise_time="20:00",
            set_time="06:00",
        )
        obs = ObservingIndex(
            score=8.0,
            rating="excellent",
            best_window=None,
            moon_summary=None,
            notes=[],
            moon_info=moon,
        )
        assert obs.moon_info.illumination_fraction == 0.25

    def test_observing_index_optional_fields(self):
        """Test that optional fields can be None."""
        obs = ObservingIndex(
            score=5.0,
            rating="fair",
            best_window=None,
            moon_summary=None,
            notes=[],
        )
        assert obs.best_window is None
        assert obs.moon_summary is None
        assert obs.moon_info is None


class TestAlert:
    """Test Alert model."""

    def test_valid_alert(self):
        """Test creating valid Alert."""
        alert = Alert(
            id="stale_sun_data",
            severity="warning",
            title="Stale Data",
            description="Sun data is outdated",
        )
        assert alert.severity == "warning"
        assert alert.title == "Stale Data"

    def test_alert_serialization(self):
        """Test alert JSON serialization."""
        alert = Alert(
            id="test_alert",
            severity="info",
            title="Test",
            description="Test description",
        )
        data = alert.model_dump()
        assert data["id"] == "test_alert"
        assert data["severity"] == "info"


class TestHistoryModels:
    """Test history-related models."""

    def test_history_sun_point(self):
        """Test HistorySunPoint with optional fields."""
        point = HistorySunPoint(
            timestamp="2025-01-01T12:00:00Z",
            xray_flux_short=1.5e-6,
            xray_flux_long=1.4e-6,
        )
        assert point.xray_flux_short == 1.5e-6

    def test_history_sun_point_null_values(self):
        """Test HistorySunPoint with None values."""
        point = HistorySunPoint(
            timestamp="2025-01-01T12:00:00Z",
            xray_flux_short=None,
            xray_flux_long=None,
        )
        assert point.xray_flux_short is None

    def test_history_space_weather_point(self):
        """Test HistorySpaceWeatherPoint."""
        point = HistorySpaceWeatherPoint(
            timestamp="2025-01-01T12:00:00Z",
            bz=-5.2,
            speed_km_s=420.5,
            kp=3.5,
        )
        assert point.bz == -5.2
        assert point.kp == 3.5

    def test_history_observing_point(self):
        """Test HistoryObservingPoint."""
        point = HistoryObservingPoint(
            timestamp="2025-01-01T12:00:00Z",
            index_score=7.5,
        )
        assert point.index_score == 7.5

    def test_history_response(self):
        """Test HistoryResponse aggregation."""
        response = HistoryResponse(
            sun=[
                HistorySunPoint(
                    timestamp="2025-01-01T12:00:00Z",
                    xray_flux_short=1.5e-6,
                    xray_flux_long=1.4e-6,
                )
            ],
            space_weather=[
                HistorySpaceWeatherPoint(
                    timestamp="2025-01-01T12:00:00Z",
                    bz=-5.2,
                    speed_km_s=420.5,
                    kp=3.5,
                )
            ],
            observing_index=[
                HistoryObservingPoint(timestamp="2025-01-01T12:00:00Z", index_score=7.5)
            ],
        )
        assert len(response.sun) == 1
        assert len(response.space_weather) == 1
        assert len(response.observing_index) == 1


class TestDashboardStatus:
    """Test DashboardStatus model."""

    def test_minimal_dashboard_status(self):
        """Test creating minimal DashboardStatus."""
        status = DashboardStatus(timestamp="2025-01-01T12:00:00Z")
        assert status.sun is None
        assert status.space_weather is None
        assert status.maunakea is None
        assert status.observing_index is None
        assert len(status.alerts) == 0
        assert len(status.data_sources) == 0

    def test_complete_dashboard_status(self):
        """Test creating complete DashboardStatus."""
        status = DashboardStatus(
            sun=SunData(
                xray_flux_short=[],
                xray_flux_long=[],
                current_class="C1.5",
                activity_level="active",
                updated_at="2025-01-01T12:00:00Z",
            ),
            space_weather=SpaceWeatherData(
                bz_series=[],
                speed_series=[],
                kp=3.5,
                updated_at="2025-01-01T12:00:00Z",
            ),
            maunakea=MaunakeaConditions(
                sky_image_url=None,
                cloud_fraction=None,
                seeing_arcsec=None,
                transparency_mag=None,
                humidity=None,
                temperature_c=None,
                wind_speed_mps=None,
                updated_at="2025-01-01T12:00:00Z",
            ),
            observing_index=ObservingIndex(
                score=7.5,
                rating="good",
                best_window=None,
                moon_summary=None,
                notes=[],
            ),
            alerts=[
                Alert(
                    id="test_alert",
                    severity="info",
                    title="Test",
                    description="Test alert",
                )
            ],
            data_sources={"sun": "real", "space_weather": "cache"},
            timestamp="2025-01-01T12:00:00Z",
        )
        assert status.sun is not None
        assert status.space_weather is not None
        assert len(status.alerts) == 1
        assert status.data_sources["sun"] == "real"

    def test_dashboard_status_serialization(self):
        """Test full serialization of DashboardStatus."""
        status = DashboardStatus(
            sun=SunData(
                xray_flux_short=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1e-6)],
                xray_flux_long=[],
                current_class="C1.0",
                activity_level="active",
                updated_at="2025-01-01T12:00:00Z",
            ),
            timestamp="2025-01-01T12:00:00Z",
        )
        data = status.model_dump()
        assert data["timestamp"] == "2025-01-01T12:00:00Z"
        assert data["sun"]["current_class"] == "C1.0"
        assert len(data["sun"]["xray_flux_short"]) == 1


class TestModelValidation:
    """Test model validation edge cases."""

    def test_invalid_timestamp_format_accepted(self):
        """Test that Pydantic accepts various timestamp formats as strings."""
        # Pydantic doesn't validate timestamp format by default
        point = XrayFluxPoint(timestamp="invalid-timestamp", value_wm2=1.0)
        assert point.timestamp == "invalid-timestamp"

    def test_negative_score_accepted(self):
        """Test that negative scores are accepted (no validation constraint)."""
        obs = ObservingIndex(
            score=-1.0,  # No constraint prevents this
            rating="poor",
            best_window=None,
            moon_summary=None,
            notes=[],
        )
        assert obs.score == -1.0

    def test_large_numeric_values(self):
        """Test handling of very large numeric values."""
        point = XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1e100)
        assert point.value_wm2 == 1e100

    def test_empty_string_values(self):
        """Test empty string values."""
        alert = Alert(
            id="",
            severity="",
            title="",
            description="",
        )
        assert alert.id == ""
        assert alert.severity == ""
