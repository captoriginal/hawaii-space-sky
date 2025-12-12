import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

PLUGINS_ROOT = Path(__file__).resolve().parents[3] / "plugins"


@lru_cache()
def load_plugin_config(plugin_name: str) -> Dict[str, Any]:
    config_path = PLUGINS_ROOT / plugin_name / "config.json"
    if not config_path.exists():
        logger.warning("Plugin %s config %s missing; using defaults", plugin_name, config_path)
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load config for plugin %s (%s)", plugin_name, exc)
        return {}
