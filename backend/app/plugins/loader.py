import json
import logging
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Set

from fastapi import FastAPI

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PANEL_CONFIG_PATH = REPO_ROOT / "panels.json"
PLUGINS_ROOT = REPO_ROOT / "plugins"


def _load_panel_config() -> Dict[str, Any]:
    if not PANEL_CONFIG_PATH.exists():
        logger.warning("Panel config %s not found; defaulting to empty mapping", PANEL_CONFIG_PATH)
        return {"panels": {}}
    with PANEL_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


PANELS_CONFIG: Dict[str, Any] = _load_panel_config()


def get_panel_config() -> Dict[str, Any]:
    """
    Return the current panel configuration. Re-read the JSON file so runtime
    tweaks (e.g., panel-now) show up without restarting the backend.
    """
    try:
        return _load_panel_config()
    except Exception:
        logger.exception("Failed to reload panel configuration; falling back to cached copy")
        return PANELS_CONFIG


def _unique_plugin_names(config: Dict[str, Any]) -> Set[str]:
    panels = config.get("panels", {})
    return {plugin_name for plugin_name in panels.values() if plugin_name}


def load_plugins(app: FastAPI) -> None:
    """
    Dynamically import backend packages for each configured plugin and let them
    register their routes or background tasks with the FastAPI app.
    """
    for plugin_name in sorted(_unique_plugin_names(PANELS_CONFIG)):
        if not (PLUGINS_ROOT / plugin_name).exists():
            logger.warning("Configured plugin %s not found in %s", plugin_name, PLUGINS_ROOT)
            continue

        module_name = f"plugins.{plugin_name}.backend"
        try:
            module = import_module(module_name)
        except ImportError as exc:
            logger.error("Unable to import plugin %s (%s)", plugin_name, exc)
            continue

        register = getattr(module, "register", None)
        if callable(register):
            register(app)
            logger.info("Registered plugin backend: %s", plugin_name)
        else:
            logger.info("Plugin %s does not expose backend hooks; skipping", plugin_name)
