import { makeImageFullscreenable } from '/fullscreen.js';

const template = `
  <h2><span class="tag ground">MK</span> Maunakea Conditions</h2>
  <div class="source" title="Where this Maunakea data came from.">
    Source: <span class="badge" data-role="source">—</span>
    <span data-role="stale" class="stale-dot" style="display:none;" title="Data may be stale — verify timestamps."></span>
  </div>
  <img data-role="sky-image" class="sky-image" alt="Maunakea sky" title="Latest available Maunakea sky image." />
  <div data-role="image-placeholder" class="placeholder-box" style="display:none;" title="Image unavailable.">Sky image unavailable</div>
  <div class="metrics" data-role="mk-metrics">
    <div class="metric"><span class="label">Cloud fraction</span><span class="value" data-role="cloud-fraction">—</span></div>
    <div class="metric"><span class="label">Seeing</span><span class="value" data-role="seeing">—</span></div>
    <div class="metric"><span class="label">Transparency loss</span><span class="value" data-role="transparency">—</span></div>
    <div class="metric"><span class="label">Humidity</span><span class="value" data-role="humidity">—</span></div>
    <div class="metric"><span class="label">Temperature</span><span class="value" data-role="temperature">—</span></div>
    <div class="metric"><span class="label">Wind speed</span><span class="value" data-role="wind">—</span></div>
  </div>
  <div class="status-line" data-role="updated" title="Timestamp of latest measurements."></div>
  <div class="unavailable" data-role="unavailable" style="display:none;">Maunakea data unavailable</div>
`;

const formatValue = (value, suffix = "", fallback = "—") => {
  if (value === null || value === undefined) return fallback;
  return `${value}${suffix}`;
};

const resolveUrl = (hostBase, path) => {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${hostBase}${path}`;
  return path;
};

export default function createPlugin(host) {
  return new MaunakeaPanelPlugin(host);
}

class MaunakeaPanelPlugin {
  constructor(host) {
    this.host = host;
    this.container = null;
    this.dom = {};
    this.statusCache = null;
    this.statusCacheTs = 0;
    this.statusTimer = null;
    this.config = {
      statusTtlMs: 60_000,
      refreshIntervalMs: 90_000,
    };
  }

  async init({ container, config }) {
    this.container = container;
    this.config = {
      statusTtlMs: config?.status_ttl_ms ?? 60_000,
      refreshIntervalMs: config?.refresh_interval_ms ?? 90_000,
    };
    container.innerHTML = template;
    this.dom = {
      source: container.querySelector("[data-role='source']"),
      stale: container.querySelector("[data-role='stale']"),
      image: container.querySelector("[data-role='sky-image']"),
      placeholder: container.querySelector("[data-role='image-placeholder']"),
      metrics: container.querySelector("[data-role='mk-metrics']"),
      cloud: container.querySelector("[data-role='cloud-fraction']"),
      seeing: container.querySelector("[data-role='seeing']"),
      transparency: container.querySelector("[data-role='transparency']"),
      humidity: container.querySelector("[data-role='humidity']"),
      temperature: container.querySelector("[data-role='temperature']"),
      wind: container.querySelector("[data-role='wind']"),
      updated: container.querySelector("[data-role='updated']"),
      unavailable: container.querySelector("[data-role='unavailable']"),
    };
    // Enable full-screen on click
    makeImageFullscreenable(this.dom.image);
  }

  start() {
    this.refreshStatus(true);
    this.statusTimer = setInterval(
      () => this.refreshStatus(false),
      this.config.refreshIntervalMs
    );
  }

  stop() {
    if (this.statusTimer) clearInterval(this.statusTimer);
    this.statusTimer = null;
  }

  destroy() {
    this.stop();
    if (this.container) this.container.innerHTML = "";
    this.container = null;
  }

  async refreshStatus(force = false) {
    try {
      const status = await this.fetchStatus(force);
      const mk = status?.maunakea;
      if (!mk) {
        this.showUnavailable();
        return;
      }
      this.dom.unavailable.style.display = "none";
      this.dom.metrics.style.display = "";
      this.updateImage(mk);
      this.dom.cloud.textContent =
        mk.cloud_fraction != null ? `${Math.round(mk.cloud_fraction * 100)}%` : "—";
      this.dom.seeing.textContent = formatValue(mk.seeing_arcsec, '"');
      this.dom.transparency.textContent = formatValue(mk.transparency_mag, " mag");
      this.dom.humidity.textContent = formatValue(mk.humidity, "%");
      this.dom.temperature.textContent = formatValue(mk.temperature_c, " °C");
      this.dom.wind.textContent = formatValue(mk.wind_speed_mps, " m/s");
      this.dom.updated.textContent = mk.updated_at ? `Updated ${mk.updated_at}` : "";
      this.updateSource(status);
    } catch (err) {
      console.error("Maunakea plugin error", err);
      this.showUnavailable();
    }
  }

  async fetchStatus(force = false) {
    const now = Date.now();
    if (!force && this.statusCache && now - this.statusCacheTs < this.config.statusTtlMs) {
      return this.statusCache;
    }
    const resp = await fetch(`${this.host.apiBase()}/api/status`);
    if (!resp.ok) throw new Error(`Status HTTP ${resp.status}`);
    const data = await resp.json();
    this.statusCache = data;
    this.statusCacheTs = now;
    return data;
  }

  updateImage(mk) {
    if (!this.dom.image) return;
    if (mk.sky_image_url) {
      const url = resolveUrl(this.host.apiBase(), mk.sky_image_url);
      this.dom.image.src = url;
      this.dom.image.style.display = "block";
      this.dom.placeholder.style.display = "none";
    } else {
      this.dom.image.removeAttribute("src");
      this.dom.image.style.display = "none";
      this.dom.placeholder.style.display = "grid";
    }
  }

  showUnavailable() {
    if (this.dom.metrics) this.dom.metrics.style.display = "none";
    if (this.dom.unavailable) this.dom.unavailable.style.display = "block";
    if (this.dom.placeholder) this.dom.placeholder.style.display = "grid";
  }

  updateSource(status) {
    const origin = status?.data_sources?.maunakea || "demo";
    if (this.dom.source) {
      this.dom.source.textContent = origin;
      this.dom.source.classList.remove("real", "cache", "demo", "unavailable");
      this.dom.source.classList.add(origin);
    }
    const stale = (status?.alerts || []).some((a) => a.id === "stale_maunakea");
    if (this.dom.stale) this.dom.stale.style.display = stale ? "inline-block" : "none";
  }
}
