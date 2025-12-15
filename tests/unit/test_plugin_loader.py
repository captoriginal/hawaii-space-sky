import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI

from backend.app.plugins.loader import (
    _load_panel_config,
    _unique_plugin_names,
    get_panel_config,
    load_plugins,
)


@pytest.fixture
def temp_panels_config():
    """Create a temporary panels.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "panels.json"
        config_data = {
            "panels": {
                "panel-1": "sun",
                "panel-2": "earth",
                "panel-3": "maunakea",
            }
        }
        with config_path.open("w") as f:
            json.dump(config_data, f)
        yield config_path, config_data


class TestLoadPanelConfig:
    """Test _load_panel_config function."""

    def test_load_valid_config(self, temp_panels_config):
        """Test loading valid panel configuration."""
        config_path, expected_data = temp_panels_config

        with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", config_path):
            config = _load_panel_config()
            assert config == expected_data

    def test_load_missing_config(self):
        """Test loading when config file doesn't exist."""
        nonexistent_path = Path("/nonexistent/panels.json")

        with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", nonexistent_path):
            config = _load_panel_config()
            assert config == {"panels": {}}

    def test_load_malformed_config(self):
        """Test loading malformed JSON config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            config_path = Path(f.name)

        try:
            with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", config_path):
                with pytest.raises(json.JSONDecodeError):
                    _load_panel_config()
        finally:
            config_path.unlink()

    def test_load_empty_config(self):
        """Test loading empty config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            config_path = Path(f.name)

        try:
            with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", config_path):
                config = _load_panel_config()
                assert "panels" not in config or config["panels"] == {}
        finally:
            config_path.unlink()


class TestGetPanelConfig:
    """Test get_panel_config function."""

    def test_get_panel_config_success(self, temp_panels_config):
        """Test successful retrieval of panel config."""
        config_path, expected_data = temp_panels_config

        with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", config_path):
            config = get_panel_config()
            assert config == expected_data

    def test_get_panel_config_fallback_on_error(self, temp_panels_config):
        """Test fallback to cached config on reload error."""
        config_path, expected_data = temp_panels_config

        with patch("backend.app.plugins.loader.PANEL_CONFIG_PATH", config_path):
            # Load initial config
            with patch("backend.app.plugins.loader.PANELS_CONFIG", expected_data):
                # Simulate error on reload
                with patch(
                    "backend.app.plugins.loader._load_panel_config",
                    side_effect=Exception("Read error"),
                ):
                    config = get_panel_config()
                    # Should return cached config
                    assert config == expected_data


class TestUniquePluginNames:
    """Test _unique_plugin_names function."""

    def test_unique_names_from_config(self):
        """Test extracting unique plugin names."""
        config = {
            "panels": {
                "panel-1": "sun",
                "panel-2": "earth",
                "panel-3": "sun",  # Duplicate
                "panel-4": "maunakea",
            }
        }
        names = _unique_plugin_names(config)
        assert names == {"sun", "earth", "maunakea"}

    def test_unique_names_empty_config(self):
        """Test with empty config."""
        config = {"panels": {}}
        names = _unique_plugin_names(config)
        assert names == set()

    def test_unique_names_missing_panels_key(self):
        """Test with missing 'panels' key."""
        config = {}
        names = _unique_plugin_names(config)
        assert names == set()

    def test_unique_names_filters_empty_strings(self):
        """Test that empty strings are filtered out."""
        config = {
            "panels": {
                "panel-1": "sun",
                "panel-2": "",
                "panel-3": "earth",
            }
        }
        names = _unique_plugin_names(config)
        assert names == {"sun", "earth"}


class TestLoadPlugins:
    """Test load_plugins function."""

    def test_load_plugins_successful(self):
        """Test successful plugin loading."""
        app = FastAPI()
        config = {"panels": {"panel-1": "test_plugin"}}

        mock_module = Mock()
        mock_register = Mock()
        mock_module.register = mock_register

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=True):
                    with patch(
                        "backend.app.plugins.loader.import_module", return_value=mock_module
                    ):
                        load_plugins(app)
                        mock_register.assert_called_once_with(app)

    def test_load_plugins_no_register_function(self):
        """Test plugin without register function."""
        app = FastAPI()
        config = {"panels": {"panel-1": "test_plugin"}}

        mock_module = Mock(spec=[])  # No register attribute

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=True):
                    with patch(
                        "backend.app.plugins.loader.import_module", return_value=mock_module
                    ):
                        # Should not raise, just log
                        load_plugins(app)

    def test_load_plugins_import_error(self):
        """Test handling of import errors."""
        app = FastAPI()
        config = {"panels": {"panel-1": "broken_plugin"}}

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=True):
                    with patch(
                        "backend.app.plugins.loader.import_module",
                        side_effect=ImportError("Module not found"),
                    ):
                        # Should not raise, just log error
                        load_plugins(app)

    def test_load_plugins_missing_plugin_directory(self):
        """Test handling of missing plugin directory."""
        app = FastAPI()
        config = {"panels": {"panel-1": "missing_plugin"}}

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=False):
                    # Should not raise, just log warning
                    load_plugins(app)

    def test_load_plugins_multiple_plugins(self):
        """Test loading multiple plugins."""
        app = FastAPI()
        config = {
            "panels": {
                "panel-1": "plugin_a",
                "panel-2": "plugin_b",
                "panel-3": "plugin_a",  # Duplicate should only load once
            }
        }

        mock_module_a = Mock()
        mock_register_a = Mock()
        mock_module_a.register = mock_register_a

        mock_module_b = Mock()
        mock_register_b = Mock()
        mock_module_b.register = mock_register_b

        def import_side_effect(module_name):
            if "plugin_a" in module_name:
                return mock_module_a
            elif "plugin_b" in module_name:
                return mock_module_b
            raise ImportError()

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=True):
                    with patch(
                        "backend.app.plugins.loader.import_module", side_effect=import_side_effect
                    ):
                        load_plugins(app)
                        # Each plugin should be registered once despite duplicates
                        mock_register_a.assert_called_once_with(app)
                        mock_register_b.assert_called_once_with(app)

    def test_load_plugins_sorted_order(self):
        """Test that plugins are loaded in sorted order."""
        app = FastAPI()
        config = {
            "panels": {
                "panel-1": "zebra",
                "panel-2": "alpha",
                "panel-3": "beta",
            }
        }

        loaded_order = []

        def track_import(module_name):
            plugin_name = module_name.split(".")[1]
            loaded_order.append(plugin_name)
            mock = Mock()
            mock.register = Mock()
            return mock

        with patch("backend.app.plugins.loader.PANELS_CONFIG", config):
            with patch("backend.app.plugins.loader.PLUGINS_ROOT", Path("/fake/plugins")):
                with patch("backend.app.plugins.loader.Path.exists", return_value=True):
                    with patch(
                        "backend.app.plugins.loader.import_module", side_effect=track_import
                    ):
                        load_plugins(app)
                        # Should be loaded in alphabetical order
                        assert loaded_order == ["alpha", "beta", "zebra"]
