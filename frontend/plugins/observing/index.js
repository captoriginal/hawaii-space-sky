const STATUS_TTL = 60_000;

const formatValue = (value, suffix = "", fallback = "—") => {
  if (value === null || value === undefined) return fallback;
  return `${value}${suffix}`;
};

const latestValue = (series, field) => {
  if (!Array.isArray(series) || series.length === 0) return null;
  const point = series[series.length - 1];
  return point ? point[field] ?? null : null;
};

const formatNumber = (value, digits = 2) => {
  if (value === null || value === undefined) return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return Number(num.toFixed(digits));
};

const template = `
  <h2><span class="tag ground">OBS</span> Tonight’s Observing Index</h2>
  <div class="source" title="Derived from Maunakea conditions, moonlight, and other factors.">
    Source: <span class="badge" data-role="source">—</span>
  </div>
  <div class="observing-layout">
    <div class="metrics" data-role="metrics">
      <div class="metric">
        <span class="label" title="Overall observing quality combining atmosphere and moonlight.">Score (0–10)</span>
        <span class="value" data-role="score">—</span>
      </div>
      <div class="metric">
        <span class="label" title="Human readable interpretation of the score.">Rating</span>
        <span class="value" data-role="rating">—</span>
      </div>
      <div class="metric">
        <span class="label" title="Time window with the best observing conditions.">Best window</span>
        <span class="value" data-role="window">—</span>
      </div>
      <div class="metric">
        <span class="label" title="Current moon phase / summary.">Moon</span>
        <span class="value" data-role="moon">—</span>
      </div>
      <div class="metric">
        <span class="label" title="Moon illumination percentage.">Moon illum.</span>
        <span class="value" data-role="illum">—</span>
      </div>
      <div class="metric">
        <span class="label" title="Moonrise and moonset times.">Moonrise/set</span>
        <span class="value" data-role="moon-times">—</span>
      </div>
    </div>
    <div class="info-block">
      <div class="summary" data-role="summary-text" title="Space & sky summary.">Building summary…</div>
      <div class="summary" data-role="notes" title="Components influencing the observing index.">Notes loading…</div>
    </div>
  </div>
  <div class="nerd-section" data-role="nerd">
    <div data-role="raw"></div>
  </div>
  <div class="unavailable" data-role="unavailable" style="display:none;">Observing index unavailable</div>
`;

export default function createPlugin(host) {
  return new ObservingPanelPlugin(host);
}

class ObservingPanelPlugin {
  constructor(host) {
    this.host = host;
    this.container = null;
    this.dom = {};
    this.statusCache = null;
    this.statusCacheTs = 0;
    this.statusTimer = null;
    this.nerdMode = host?.getNerdMode?.() ?? false;
  }

  async init({ container }) {
    this.container = container;
    container.innerHTML = template;
    this.dom = {
      source: container.querySelector("[data-role='source']"),
      metrics: container.querySelector("[data-role='metrics']"),
      score: container.querySelector("[data-role='score']"),
      rating: container.querySelector("[data-role='rating']"),
      window: container.querySelector("[data-role='window']"),
      moon: container.querySelector("[data-role='moon']"),
      illum: container.querySelector("[data-role='illum']"),
      moonTimes: container.querySelector("[data-role='moon-times']"),
      notes: container.querySelector("[data-role='notes']"),
      nerd: container.querySelector("[data-role='nerd']"),
      raw: container.querySelector("[data-role='raw']"),
      unavailable: container.querySelector("[data-role='unavailable']"),
      summary: container.querySelector("[data-role='summary-text']"),
    };
    this.dom.nerd.style.display = this.nerdMode ? "block" : "none";
  }

  start() {
    this.refreshStatus(true);
    this.statusTimer = setInterval(() => this.refreshStatus(false), 90_000);
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

  setNerdMode(enabled) {
    this.nerdMode = enabled;
    if (this.dom.nerd) this.dom.nerd.style.display = enabled ? "block" : "none";
  }

  async refreshStatus(force = false) {
    try {
      const status = await this.fetchStatus(force);
      const observing = status?.observing_index;
      if (!observing) {
        this.showUnavailable();
        return;
      }
      this.renderObserving(observing);
      this.updateSource(status);
    } catch (err) {
      console.error("Observing plugin error", err);
      this.showUnavailable();
    }
  }

  async fetchStatus(force = false) {
    const now = Date.now();
    if (!force && this.statusCache && now - this.statusCacheTs < STATUS_TTL) {
      return this.statusCache;
    }
    const resp = await fetch(`${this.host.apiBase()}/api/status`);
    if (!resp.ok) throw new Error(`Status HTTP ${resp.status}`);
    const data = await resp.json();
    this.statusCache = data;
    this.statusCacheTs = now;
    return data;
  }

  renderObserving(observing) {
    this.dom.unavailable.style.display = "none";
    this.dom.metrics.style.display = "";
    this.dom.score.textContent = observing.score != null ? observing.score : "—";
    this.dom.rating.textContent = observing.rating || "—";
    this.dom.window.textContent = observing.best_window || "—";
    this.dom.moon.textContent = observing.moon_summary || "—";
    const moonInfo = observing.moon_info || {};
    this.dom.illum.textContent =
      moonInfo.illumination_fraction != null ? `${Math.round(moonInfo.illumination_fraction * 100)}%` : "—";
    const times = [];
    if (moonInfo.rise_time) times.push(`Rise ${moonInfo.rise_time}`);
    if (moonInfo.set_time) times.push(`Set ${moonInfo.set_time}`);
    this.dom.moonTimes.textContent = times.join(" · ") || "—";

    const notes = observing.notes || [];
    if (notes.length) {
      this.dom.notes.innerHTML = `<ul class="notes">${notes.map((n) => `<li>${n}</li>`).join("")}</ul>`;
    } else {
      this.dom.notes.textContent = "Notes unavailable";
    }

    const moon = observing.moon_info
      ? `Moon illum ${Math.round(observing.moon_info.illumination_fraction * 100)}%`
      : "Moon info unavailable";
    if (this.dom.raw) {
      this.dom.raw.textContent = `Score ${observing.score}/10 (${observing.rating}); ${moon}; notes: ${notes.join(", ")}`;
    }
    if (this.dom.summary) {
      const sun = this.statusCache?.sun;
      const space = this.statusCache?.space_weather;
      const maunakea = this.statusCache?.maunakea;
      const summaryParts = [
        sun ? `X-ray flux currently ${sun.current_class} (${sun.activity_level}).` : "Sun data unavailable.",
        space ? `Geomagnetic Kp is ${space.kp}.` : "Space weather unavailable.",
        space
          ? `Bz at ${formatNumber(latestValue(space.bz_series, "value_nT"))} nT; solar wind ${formatNumber(
              latestValue(space.speed_series, "value_km_s")
            )} km/s.`
          : "",
        maunakea
          ? `Maunakea clouds ~${maunakea.cloud_fraction != null ? Math.round(maunakea.cloud_fraction * 100) + "%" : "—"}, seeing ${formatValue(
              maunakea.seeing_arcsec,
              '"'
            )}, transparency loss ${formatValue(maunakea.transparency_mag, " mag")}.`
          : "Maunakea data unavailable.",
        `Observing index: ${observing.score}/10 (${observing.rating}).`,
      ]
        .filter(Boolean)
        .join(" ");
      this.dom.summary.textContent = summaryParts;
    }
  }

  showUnavailable() {
    if (this.dom.metrics) this.dom.metrics.style.display = "none";
    if (this.dom.unavailable) this.dom.unavailable.style.display = "block";
    if (this.dom.notes) this.dom.notes.textContent = "Observing index unavailable";
  }

  updateSource(status) {
    const origin = status?.data_sources?.observing_index || "demo";
    if (this.dom.source) {
      this.dom.source.textContent = origin;
      this.dom.source.classList.remove("real", "cache", "demo", "unavailable");
      this.dom.source.classList.add(origin);
    }
  }
}
