"""
Plugin loader utilities for registering panel-specific backend features.
"""

from .loader import PANELS_CONFIG, load_plugins, get_panel_config
from .config import load_plugin_config

__all__ = ["PANELS_CONFIG", "load_plugins", "get_panel_config", "load_plugin_config"]
