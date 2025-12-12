const state = {
  nerdMode: false,
  lastStatus: null,
};

class PanelManager {
  constructor(rootNode = document) {
    this.rootNode = rootNode;
    this.plugins = new Map();
    this.nerdMode = false;
  }

  async init() {
    if (!this.rootNode) return;
    const config = await this.fetchPanelConfig();
    const panels = config.panels || {};
    for (const [slotId, pluginName] of Object.entries(panels)) {
      await this.mountPlugin(slotId, pluginName);
    }
    this.setNerdMode(state.nerdMode);
  }

  async fetchPanelConfig() {
    const resp = await fetch(`${apiBase()}/api/panels`);
    if (!resp.ok) throw new Error(`Panel config HTTP ${resp.status}`);
    return resp.json();
  }

  getSlot(slotId) {
    if (this.rootNode && typeof this.rootNode.querySelector === "function") {
      const scoped = this.rootNode.querySelector(`[data-panel-slot="${slotId}"]`);
      if (scoped) return scoped;
    }
    return document.querySelector(`[data-panel-slot="${slotId}"]`);
  }

  async mountPlugin(slotId, pluginName) {
    const slot = this.getSlot(slotId);
    if (!slot) return;
    try {
      const module = await import(`./plugins/${pluginName}/index.js`);
      const factory = module.default;
      if (typeof factory !== "function") throw new Error("Plugin factory missing");
      const plugin = factory({
        apiBase,
        fetchJson: (path, options) => fetch(`${apiBase()}${path}`, options),
        getNerdMode: () => this.nerdMode,
      });
      await plugin.init({ container: slot, slotId, host: this });
      plugin.start?.();
      this.plugins.set(slotId, plugin);
    } catch (err) {
      console.error(`Failed to mount plugin ${pluginName} for ${slotId}`, err);
      slot.innerHTML =
        "<div class='summary'>Unable to load this panel plugin. Check console for details.</div>";
    }
  }

  setNerdMode(enabled) {
    this.nerdMode = enabled;
    for (const plugin of this.plugins.values()) {
      plugin.setNerdMode?.(enabled);
    }
  }
}

const panelManager = new PanelManager(document);

initApp();

async function initApp() {
  try {
    await panelManager.init();
  } catch (err) {
    console.error("Unable to load panel plugins", err);
  }
  loadStatus();
  setupNerdToggle();
  setInterval(loadStatus, 90_000);
}

function apiBase() {
  const isFile = window.location.protocol === "file:";
  return isFile ? "http://127.0.0.1:8000" : "";
}

async function loadStatus() {
  try {
    const resp = await fetch(`${apiBase()}/api/status`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderStatus(data);
  } catch (err) {
    console.error(err);
    document.getElementById("updated-at").textContent = "Updated —";
  }
}

function formatLatest(series, field) {
  if (!series || series.length === 0) return "—";
  return series[series.length - 1][field];
}

function formatValue(value, suffix = "", fallback = "—") {
  if (value === null || value === undefined) return fallback;
  return `${value}${suffix}`;
}

function renderStatus(status) {
  const sun = status.sun || null;
  const space = status.space_weather || null;
  const maunakea = status.maunakea || null;
  const observing = status.observing_index || null;
  state.lastStatus = status;
}

function setupNerdToggle() {
  const checkbox = document.getElementById("nerd-toggle");
  checkbox.addEventListener("change", () => {
    state.nerdMode = checkbox.checked;
    panelManager.setNerdMode(state.nerdMode);
  });
}
