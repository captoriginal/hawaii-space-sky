const state = {
  nerdMode: false,
  historyHours: 6,
  lastStatus: null,
};

class PanelManager {
  constructor(rootEl) {
    this.rootEl = rootEl;
    this.plugins = new Map();
    this.nerdMode = false;
  }

  async init() {
    if (!this.rootEl) return;
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

  async mountPlugin(slotId, pluginName) {
    const slot = this.rootEl.querySelector(`[data-panel-slot="${slotId}"]`);
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

const panelManager = new PanelManager(document.getElementById("panel-grid"));

initApp();

async function initApp() {
  try {
    await panelManager.init();
  } catch (err) {
    console.error("Unable to load panel plugins", err);
  }
  loadStatus();
  loadHistory(state.historyHours);
  setupHistoryControls();
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
    document.getElementById("summary-text").textContent =
      "Unable to load status right now. Check that the FastAPI server is running.";
    document.getElementById("nowcast").textContent = "Now · status unavailable (API error)";
    document.getElementById("updated-at").textContent = "Updated —";
  }
}

async function loadHistory(hours) {
  try {
    const resp = await fetch(`${apiBase()}/api/history?hours=${hours}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderHistory(data);
  } catch (err) {
    console.error(err);
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

function renderNerdSections({ observing }) {
  const nerdDisplay = state.nerdMode ? "block" : "none";
  const obsNerd = document.getElementById("obs-nerd");
  if (obsNerd) obsNerd.style.display = nerdDisplay;

  if (observing) {
    const moon = observing.moon_info
      ? `Moon illum ${Math.round(observing.moon_info.illumination_fraction * 100)}%`
      : "Moon info unavailable";
    document.getElementById("obs-raw").textContent =
      `Score ${observing.score}/10 (${observing.rating}); ${moon}; notes: ${(observing.notes || []).join(", ")}`;
  } else {
    document.getElementById("obs-raw").textContent = "— (no data)";
  }
}

function renderStatus(status) {
  const sun = status.sun || null;
  const space = status.space_weather || null;
  const maunakea = status.maunakea || null;
  const observing = status.observing_index || null;
  state.lastStatus = status;
  const sources = status.data_sources || {};

  const obsMetrics = document.getElementById("obs-metrics");
  const obsUnavailable = document.getElementById("obs-unavailable");

  if (observing) {
    if (obsMetrics) obsMetrics.style.display = "";
    if (obsUnavailable) obsUnavailable.style.display = "none";
    document.getElementById("obs-score").textContent = observing.score;
    document.getElementById("obs-rating").textContent = observing.rating;
    document.getElementById("obs-window").textContent = observing.best_window || "—";
    document.getElementById("obs-moon").textContent = observing.moon_summary || "—";
    document.getElementById("obs-notes").innerHTML = `<ul class="notes">${(observing.notes || [])
      .map((n) => `<li>${n}</li>`)
      .join("")}</ul>`;
    const moonInfo = observing.moon_info || {};
    const illum = moonInfo.illumination_fraction != null ? `${Math.round(moonInfo.illumination_fraction * 100)}%` : "—";
    document.getElementById("obs-moon-illum").textContent = illum;
    const times = [];
    if (moonInfo.rise_time) times.push(`Rise ${moonInfo.rise_time}`);
    if (moonInfo.set_time) times.push(`Set ${moonInfo.set_time}`);
    document.getElementById("obs-moon-times").textContent = times.join(" · ") || "—";
  } else {
    if (obsMetrics) obsMetrics.style.display = "none";
    if (obsUnavailable) obsUnavailable.style.display = "";
    document.getElementById("obs-score").textContent = "—";
    document.getElementById("obs-rating").textContent = "—";
    document.getElementById("obs-window").textContent = "—";
    document.getElementById("obs-moon").textContent = "—";
    document.getElementById("obs-moon-illum").textContent = "—";
    document.getElementById("obs-moon-times").textContent = "—";
    document.getElementById("obs-notes").textContent = "Notes unavailable";
  }

  const summary = [
    sun ? `X-ray flux currently ${sun.current_class} (${sun.activity_level}).` : "Sun data unavailable.",
    space ? `Geomagnetic Kp is ${space.kp}.` : "Space weather unavailable.",
    space ? `Bz at ${formatLatest(space.bz_series, "value_nT")} nT; solar wind ${formatLatest(space.speed_series, "value_km_s")} km/s.` : "",
    maunakea
      ? `Maunakea clouds ~${maunakea.cloud_fraction != null ? Math.round(maunakea.cloud_fraction * 100) + "%" : "—"}, seeing ${formatValue(maunakea.seeing_arcsec, '"')}, transparency loss ${formatValue(maunakea.transparency_mag, " mag")}.`
      : "Maunakea data unavailable.",
    observing ? `Observing index: ${observing.score}/10 (${observing.rating}).` : "Observing index unavailable.",
  ].join(" ");
  document.getElementById("summary-text").textContent = summary;
  document.getElementById("status-line").textContent = `Updated ${status.timestamp}`;
  document.getElementById("updated-at").textContent = `Updated ${status.timestamp}`;
  document.getElementById("nowcast").textContent = buildNowcast(sun, space, observing);
  renderAlerts(status.alerts || []);
  renderNerdSections({ observing });

  const obsSource = document.getElementById("source-obs");
  if (obsSource) {
    const origin = sources.observing_index || "demo";
    obsSource.textContent = origin;
    obsSource.classList.remove("real", "cache", "demo");
    obsSource.classList.add(origin);
  }
}

function renderHistory(history) {
  renderLineChart("chart-xray", history.sun, "xray_flux_short", { color: "#f7a541", label: "X-ray short" });
  renderLineChart("chart-space", history.space_weather, "bz", { color: "#54b6f8", label: "Bz (nT)" }, [
    { key: "speed_km_s", color: "#6be0c2" },
  ]);
  renderLineChart("chart-observing", history.observing_index, "index_score", { color: "#6be0c2", label: "Observing index" });
}

function renderLineChart(svgId, points, key, primary, extraSeries = []) {
  const svg = document.getElementById(svgId);
  const width = svg.clientWidth || 300;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = "";
  if (!points || points.length === 0) {
    svg.innerHTML = `<text x="${width / 2}" y="${height / 2}" text-anchor="middle" fill="#9bb1d8">No data</text>`;
    return;
  }

  const series = [primary, ...extraSeries];
  const allValues = series.flatMap((seriesMeta, idx) =>
    points.map((p) => Number(p[idx === 0 ? key : seriesMeta.key])).filter((v) => !Number.isNaN(v))
  );
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  series.forEach((seriesMeta, idx) => {
    const valueKey = idx === 0 ? key : seriesMeta.key;
    const color = seriesMeta.color || primary.color;
    const coords = points.map((p, i) => {
      const v = Number(p[valueKey]);
      const x = (i / Math.max(points.length - 1, 1)) * (width - 20) + 10;
      const y = height - ((v - min) / range) * (height - 20) - 10;
      return `${x},${y}`;
    });
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("points", coords.join(" "));
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", color);
    poly.setAttribute("stroke-width", "2");
    poly.setAttribute("opacity", idx === 0 ? "1" : "0.7");
    svg.appendChild(poly);
  });
}

function buildNowcast(sun, space, observing) {
  const parts = [];
  if (sun) {
    const level = sun.activity_level;
    let phrasing = "solar activity";
    if (level === "quiet") phrasing += " quiet";
    else if (level === "active") phrasing += " active (C-class flares possible)";
    else if (level === "stormy") phrasing += " high (M/X-class flares)";
    else phrasing += ` ${level}`;
    parts.push(phrasing);
  }

  if (space && space.kp !== undefined && space.kp !== null) {
    let geo = "";
    if (space.kp <= 3) geo = "geomagnetic conditions quiet";
    else if (space.kp <= 5) geo = "geomagnetic unsettled / minor storm levels";
    else geo = "geomagnetic storm conditions";
    geo += ` (Kp ${space.kp})`;
    parts.push(geo);
  }

  if (observing) {
    parts.push(`Maunakea observing ${observing.rating} (Index ${observing.score}/10)`);
  }

  if (parts.length === 0) return "Now · status unavailable";
  return `Now · ${parts.join(". ")}.`;
}

function renderAlerts(alerts) {
  const area = document.getElementById("alerts-area");
  area.innerHTML = "";
  if (!alerts || alerts.length === 0) {
    const div = document.createElement("div");
    div.className = "alert-card alert-info";
    div.innerHTML = "<h3>No active alerts</h3><p>All systems nominal.</p>";
    area.appendChild(div);
    return;
  }
  alerts.forEach((alert) => {
    const card = document.createElement("div");
    card.className = `alert-card alert-${alert.severity || "info"}`;
    card.innerHTML = `<h3>${alert.title}</h3><p>${alert.description}</p>`;
    area.appendChild(card);
  });
}

function setupHistoryControls() {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.historyHours = Number(chip.dataset.hours);
      loadHistory(state.historyHours);
    });
  });
}

function setupNerdToggle() {
  const checkbox = document.getElementById("nerd-toggle");
  checkbox.addEventListener("change", () => {
    state.nerdMode = checkbox.checked;
    renderNerdSections({ observing: state.lastStatus?.observing_index || null });
    panelManager.setNerdMode(state.nerdMode);
  });
}
