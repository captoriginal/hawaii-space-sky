import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app
from backend.app.models import (
    DashboardStatus,
    ObservingIndex,
    SpaceWeatherData,
    SunData,
    XrayFluxPoint,
)
from backend.app.storage import record_history


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        yield db_path


@pytest.fixture
def mock_build_status():
    """Mock build_status_payload to return test data."""
    test_status = DashboardStatus(
        sun=SunData(
            xray_flux_short=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.5e-6)],
            xray_flux_long=[XrayFluxPoint(timestamp="2025-01-01T12:00:00Z", value_wm2=1.4e-6)],
            current_class="C1.5",
            activity_level="active",
            updated_at="2025-01-01T12:00:00Z",
        ),
        timestamp="2025-01-01T12:00:00Z",
    )
    return test_status


class TestStatusEndpoint:
    """Test /api/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, client, mock_build_status):
        """Test successful status retrieval."""
        with patch(
            "backend.app.api.routes.build_status_payload", return_value=mock_build_status
        ):
            response = client.get("/api/status")
            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "sun" in data
            assert data["sun"]["current_class"] == "C1.5"

    @pytest.mark.asyncio
    async def test_get_status_returns_dashboard_status_model(self, client, mock_build_status):
        """Test that response matches DashboardStatus model."""
        with patch(
            "backend.app.api.routes.build_status_payload", return_value=mock_build_status
        ):
            response = client.get("/api/status")
            data = response.json()

            # Verify structure matches DashboardStatus
            assert "timestamp" in data
            assert "sun" in data
            assert "space_weather" in data or data.get("space_weather") is None
            assert "maunakea" in data or data.get("maunakea") is None
            assert "observing_index" in data or data.get("observing_index") is None
            assert "alerts" in data
            assert "data_sources" in data

    @pytest.mark.asyncio
    async def test_get_status_handles_service_error(self, client):
        """Test handling when status service raises error."""
        with patch(
            "backend.app.api.routes.build_status_payload",
            side_effect=Exception("Service error"),
        ):
            response = client.get("/api/status")
            assert response.status_code == 500


class TestHistoryEndpoint:
    """Test /api/history endpoint."""

    def test_get_history_default_params(self, client, temp_db):
        """Test history retrieval with default parameters."""
        with patch("backend.app.api.routes.fetch_history") as mock_fetch:
            mock_fetch.return_value = {"sun": [], "space_weather": [], "observing_index": []}
            response = client.get("/api/history")
            assert response.status_code == 200
            # Should call with default 24 hours
            mock_fetch.assert_called_once_with(24)

    def test_get_history_custom_hours(self, client):
        """Test history retrieval with custom hours parameter."""
        with patch("backend.app.api.routes.fetch_history") as mock_fetch:
            mock_fetch.return_value = {"sun": [], "space_weather": [], "observing_index": []}
            response = client.get("/api/history?hours=48")
            assert response.status_code == 200
            mock_fetch.assert_called_once_with(48)

    def test_get_history_validates_min_hours(self, client):
        """Test that hours parameter is validated (minimum)."""
        response = client.get("/api/history?hours=0")
        assert response.status_code == 422  # Validation error

    def test_get_history_validates_max_hours(self, client):
        """Test that hours parameter is validated (maximum)."""
        response = client.get("/api/history?hours=200")
        assert response.status_code == 422  # Validation error

    def test_get_history_returns_history_response_model(self, client):
        """Test that response matches HistoryResponse model."""
        with patch("backend.app.api.routes.fetch_history") as mock_fetch:
            mock_fetch.return_value = {"sun": [], "space_weather": [], "observing_index": []}
            response = client.get("/api/history")
            data = response.json()

            assert "sun" in data
            assert "space_weather" in data
            assert "observing_index" in data
            assert isinstance(data["sun"], list)
            assert isinstance(data["space_weather"], list)
            assert isinstance(data["observing_index"], list)


class TestCacheClearEndpoint:
    """Test /api/cache/clear endpoint."""

    def test_clear_cache_success(self, client):
        """Test successful cache clearing."""
        with patch("backend.app.api.routes.clear_cache") as mock_clear:
            response = client.post("/api/cache/clear")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            mock_clear.assert_called_once()

    def test_clear_cache_handles_error(self, client):
        """Test handling when cache clear raises error."""
        with patch("backend.app.api.routes.clear_cache", side_effect=Exception("Clear error")):
            response = client.post("/api/cache/clear")
            assert response.status_code == 500


class TestPluginConfigEndpoint:
    """Test /api/plugins/{plugin_name}/config endpoint."""

    def test_get_plugin_config_success(self, client):
        """Test successful plugin config retrieval."""
        mock_config = {"setting1": "value1", "setting2": 42}

        with patch("backend.app.api.routes.load_plugin_config", return_value=mock_config):
            response = client.get("/api/plugins/sun/config")
            assert response.status_code == 200
            data = response.json()
            assert data == mock_config

    def test_get_plugin_config_not_found(self, client):
        """Test handling when plugin config is not found."""
        with patch("backend.app.api.routes.load_plugin_config", return_value=None):
            response = client.get("/api/plugins/nonexistent/config")
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    def test_get_plugin_config_various_plugins(self, client):
        """Test retrieving config for different plugins."""
        configs = {
            "sun": {"carousel_interval": 15000},
            "earth": {"refresh_interval": 60000},
            "maunakea": {"image_url": "https://example.com"},
        }

        for plugin_name, config_data in configs.items():
            with patch("backend.app.api.routes.load_plugin_config", return_value=config_data):
                response = client.get(f"/api/plugins/{plugin_name}/config")
                assert response.status_code == 200
                assert response.json() == config_data


class TestPanelsEndpoint:
    """Test /api/panels endpoint."""

    def test_get_panels_config(self, client):
        """Test retrieving panels configuration."""
        mock_config = {
            "panels": {
                "panel-1": "sun",
                "panel-2": "earth",
                "panel-3": "maunakea",
            }
        }

        with patch("backend.app.main.get_panel_config", return_value=mock_config):
            response = client.get("/api/panels")
            assert response.status_code == 200
            data = response.json()
            assert data == mock_config

    def test_get_panels_empty_config(self, client):
        """Test retrieving empty panels configuration."""
        mock_config = {"panels": {}}

        with patch("backend.app.main.get_panel_config", return_value=mock_config):
            response = client.get("/api/panels")
            assert response.status_code == 200
            data = response.json()
            assert data["panels"] == {}


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        with patch("backend.app.api.routes.build_status_payload") as mock_build:
            mock_build.return_value = DashboardStatus(timestamp="2025-01-01T12:00:00Z")
            response = client.get("/api/status")

            # CORS headers should be present
            assert "access-control-allow-origin" in response.headers


class TestEndToEndFlow:
    """Test end-to-end API flows."""

    def test_record_and_fetch_history(self, client, temp_db):
        """Test recording status and fetching history."""
        # Create test status
        status = DashboardStatus(
            observing_index=ObservingIndex(
                score=7.5,
                rating="good",
                best_window="10pm - 2am",
                moon_summary="New moon",
                notes=["Clear skies"],
            ),
            timestamp="2025-01-01T12:00:00Z",
        )

        # Record to database
        with patch("backend.app.storage.get_db_path", return_value=temp_db):
            record_history(status, db_path=temp_db)

            # Fetch history
            with patch("backend.app.api.routes.fetch_history") as mock_fetch:
                from backend.app.storage import fetch_history as real_fetch

                mock_fetch.side_effect = lambda hours: real_fetch(hours, db_path=temp_db)

                response = client.get("/api/history?hours=24")
                assert response.status_code == 200
                data = response.json()
                assert len(data["observing_index"]) == 1
                assert data["observing_index"][0]["index_score"] == 7.5


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_invalid_http_methods(self, client):
        """Test that invalid HTTP methods return appropriate errors."""
        # POST to GET-only endpoint
        response = client.post("/api/status")
        assert response.status_code == 405  # Method Not Allowed

        # GET to POST-only endpoint
        response = client.get("/api/cache/clear")
        assert response.status_code == 405

    def test_invalid_query_parameters(self, client):
        """Test handling of invalid query parameters."""
        # Non-numeric hours parameter
        response = client.get("/api/history?hours=invalid")
        assert response.status_code == 422

        # Negative hours
        response = client.get("/api/history?hours=-5")
        assert response.status_code == 422

    def test_malformed_plugin_names(self, client):
        """Test handling of malformed plugin names."""
        with patch("backend.app.api.routes.load_plugin_config", return_value=None):
            # Special characters in plugin name
            response = client.get("/api/plugins/../../../etc/config")
            # FastAPI should handle path traversal
            assert response.status_code in [404, 422]
