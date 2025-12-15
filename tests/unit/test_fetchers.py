import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from backend.app.config import Settings
from backend.app.services.fetchers import (
    _flux_to_activity,
    _flux_to_class,
    _get_with_retry,
    fetch_space_weather,
    fetch_xray_flux,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        HTTP_TIMEOUT_SECONDS=5.0,
        HTTP_MAX_RETRIES=2,
        RETRY_BACKOFF_SECONDS=0.1,  # Short backoff for testing
        XRAY_FLUX_URL="https://test.example.com/xray",
        SOLAR_WIND_URL="https://test.example.com/solar-wind",
        IMF_URL="https://test.example.com/imf",
        KP_URL="https://test.example.com/kp",
    )


class TestFluxClassification:
    """Test X-ray flux classification functions."""

    def test_flux_to_class_a_range(self):
        """Test classification in A-class range."""
        assert _flux_to_class(1e-8) == "A1.0"
        assert _flux_to_class(5e-8) == "A5.0"
        assert _flux_to_class(9.9e-8) == "A9.9"

    def test_flux_to_class_b_range(self):
        """Test classification in B-class range."""
        assert _flux_to_class(1e-7) == "B1.0"
        assert _flux_to_class(5e-7) == "B5.0"

    def test_flux_to_class_c_range(self):
        """Test classification in C-class range."""
        assert _flux_to_class(1e-6) == "C1.0"
        assert _flux_to_class(5.5e-6) == "C5.5"

    def test_flux_to_class_m_range(self):
        """Test classification in M-class range."""
        assert _flux_to_class(1e-5) == "M1.0"
        assert _flux_to_class(5e-5) == "M5.0"

    def test_flux_to_class_x_range(self):
        """Test classification in X-class range."""
        assert _flux_to_class(1e-4) == "X1.0"
        assert _flux_to_class(1e-3) == "X10.0"

    def test_flux_to_class_below_threshold(self):
        """Test classification below A-class threshold."""
        assert _flux_to_class(1e-9) == "A0.0"
        assert _flux_to_class(0) == "A0.0"

    def test_flux_to_activity_quiet(self):
        """Test activity level classification for quiet conditions."""
        assert _flux_to_activity(1e-9) == "quiet"
        assert _flux_to_activity(1e-7) == "quiet"
        assert _flux_to_activity(9.9e-7) == "quiet"

    def test_flux_to_activity_active(self):
        """Test activity level classification for active conditions."""
        assert _flux_to_activity(1e-6) == "active"
        assert _flux_to_activity(5e-6) == "active"
        assert _flux_to_activity(9.9e-6) == "active"

    def test_flux_to_activity_stormy(self):
        """Test activity level classification for stormy conditions."""
        assert _flux_to_activity(1e-5) == "stormy"
        assert _flux_to_activity(1e-4) == "stormy"


class TestGetWithRetry:
    """Test HTTP retry logic."""

    @pytest.mark.asyncio
    async def test_successful_request(self, mock_settings):
        """Test successful request on first attempt."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _get_with_retry(mock_client, "https://test.com", mock_settings)

        assert result == mock_response
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_settings):
        """Test retries on failed requests."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError("Server error", request=Mock(), response=Mock()),
                httpx.HTTPStatusError("Server error", request=Mock(), response=Mock()),
                Mock(),  # Success on third attempt
            ]
        )

        result = await _get_with_retry(mock_client, "https://test.com", mock_settings)

        assert result is not None
        # Should retry twice before succeeding (3 total attempts)
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self, mock_settings):
        """Test that exception is raised after max retries."""
        mock_client = AsyncMock()
        error = httpx.HTTPStatusError("Server error", request=Mock(), response=Mock())
        mock_client.get = AsyncMock(side_effect=error)

        with pytest.raises(httpx.HTTPStatusError):
            await _get_with_retry(mock_client, "https://test.com", mock_settings)

        # Should attempt: 1 initial + 2 retries = 3 total
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_backoff_timing(self, mock_settings):
        """Test that backoff delay increases with attempts."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[
                httpx.ConnectTimeout("Timeout", request=Mock()),
                httpx.ConnectTimeout("Timeout", request=Mock()),
                Mock(),  # Success on third
            ]
        )

        start_time = asyncio.get_event_loop().time()
        await _get_with_retry(mock_client, "https://test.com", mock_settings)
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should have delays: 0.1 (first retry) + 0.2 (second retry) = 0.3 minimum
        assert elapsed >= 0.3


class TestFetchXrayFlux:
    """Test X-ray flux fetching."""

    @pytest.mark.asyncio
    async def test_fetch_xray_flux_success(self, mock_settings):
        """Test successful X-ray flux fetch."""
        mock_response_data = [
            {
                "time_tag": "2025-01-01T12:00:00Z",
                "flux": 1.5e-6,
                "energy": "0.1-0.8",
            },
            {
                "time_tag": "2025-01-01T12:00:00Z",
                "flux": 1.4e-6,
                "energy": "0.05-0.4",
            },
            {
                "time_tag": "2025-01-01T12:05:00Z",
                "flux": 1.6e-6,
                "energy": "0.1-0.8",
            },
            {
                "time_tag": "2025-01-01T12:05:00Z",
                "flux": 1.5e-6,
                "energy": "0.05-0.4",
            },
        ]

        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_response_data)
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await fetch_xray_flux(mock_settings)

            assert result.xray_flux_short
            assert result.xray_flux_long
            assert len(result.xray_flux_short) >= 1
            assert len(result.xray_flux_long) >= 1
            assert result.current_class == "C1.6"
            assert result.activity_level == "active"

    @pytest.mark.asyncio
    async def test_fetch_xray_flux_empty_data(self, mock_settings):
        """Test handling of empty response data."""
        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json = Mock(return_value=[])
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="missing points"):
                await fetch_xray_flux(mock_settings)

    @pytest.mark.asyncio
    async def test_fetch_xray_flux_malformed_data(self, mock_settings):
        """Test handling of malformed response data."""
        mock_response_data = [
            {"time_tag": "2025-01-01T12:00:00Z", "flux": "invalid", "energy": "0.1-0.8"},
        ]

        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_response_data)
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="missing points"):
                await fetch_xray_flux(mock_settings)


class TestFetchSpaceWeather:
    """Test space weather data fetching."""

    @pytest.mark.asyncio
    async def test_fetch_space_weather_success(self, mock_settings):
        """Test successful space weather data fetch."""
        plasma_data = [
            ["time", "density", "speed", "temperature"],  # Header
            ["2025-01-01 12:00:00", 5.0, 420.5, 100000],
            ["2025-01-01 12:05:00", 5.2, 425.0, 100500],
        ]

        mag_data = [
            ["time", "bx", "by", "bz", "bt", "bz_gsm"],  # Header
            ["2025-01-01 12:00:00", 1.0, 2.0, 3.0, 4.0, -5.2],
            ["2025-01-01 12:05:00", 1.1, 2.1, 3.1, 4.1, -3.8],
        ]

        kp_data = [
            ["time_tag", "kp"],  # Header
            ["2025-01-01 12:00:00", 3.5],
        ]

        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            def get_side_effect(url):
                mock_response = Mock()
                if "plasma" in url or "solar-wind" in url:
                    mock_response.json = Mock(return_value=plasma_data)
                elif "mag" in url or "imf" in url:
                    mock_response.json = Mock(return_value=mag_data)
                elif "kp" in url:
                    mock_response.json = Mock(return_value=kp_data)
                mock_response.raise_for_status = Mock()
                return mock_response

            mock_client.get = AsyncMock(side_effect=get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await fetch_space_weather(mock_settings)

            assert result.bz_series
            assert result.speed_series
            assert len(result.bz_series) >= 1
            assert len(result.speed_series) >= 1
            assert result.kp == 3.5

    @pytest.mark.asyncio
    async def test_fetch_space_weather_missing_kp(self, mock_settings):
        """Test handling of missing Kp data."""
        plasma_data = [["time", "speed"], ["2025-01-01 12:00:00", 420.5]]
        mag_data = [["time", "bz_gsm"], ["2025-01-01 12:00:00", -5.2]]
        kp_data = []  # Empty Kp data

        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            def get_side_effect(url):
                mock_response = Mock()
                if "plasma" in url or "solar-wind" in url:
                    mock_response.json = Mock(return_value=plasma_data)
                elif "mag" in url or "imf" in url:
                    mock_response.json = Mock(return_value=mag_data)
                elif "kp" in url:
                    mock_response.json = Mock(return_value=kp_data)
                mock_response.raise_for_status = Mock()
                return mock_response

            mock_client.get = AsyncMock(side_effect=get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Kp payload missing"):
                await fetch_space_weather(mock_settings)


class TestDataParsing:
    """Test data parsing edge cases."""

    @pytest.mark.asyncio
    async def test_handles_partial_valid_data(self, mock_settings):
        """Test that partial valid data is used, invalid rows skipped."""
        mock_response_data = [
            {
                "time_tag": "2025-01-01T12:00:00Z",
                "flux": 1.5e-6,
                "energy": "0.1-0.8",
            },
            {
                "time_tag": "2025-01-01T12:05:00Z",
                "flux": "invalid",  # This should be skipped
                "energy": "0.1-0.8",
            },
            {
                "time_tag": "2025-01-01T12:10:00Z",
                "flux": 1.6e-6,
                "energy": "0.1-0.8",
            },
            {
                "time_tag": "2025-01-01T12:00:00Z",
                "flux": 1.4e-6,
                "energy": "0.05-0.4",
            },
        ]

        with patch("backend.app.services.fetchers.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_response_data)
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await fetch_xray_flux(mock_settings)

            # Should have parsed 2 short wavelength points (skipped the invalid one)
            assert len(result.xray_flux_short) == 2
            assert result.xray_flux_short[0].value_wm2 == 1.5e-6
            assert result.xray_flux_short[1].value_wm2 == 1.6e-6
