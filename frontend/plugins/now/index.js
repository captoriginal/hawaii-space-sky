const STATUS_TTL = 60_000;

const template = `
  <div class="nowcast" data-role="nowcast">Now · loading status…</div>
  <div class="alerts" data-role="alerts"></div>
`;

export default function createPlugin(host) {
  return new NowPanelPlugin(host);
}

class NowPanelPlugin {
  constructor(host) {
    this.host = host;
    this.container = null;
    this.dom = {};
    this.statusCache = null;
    this.statusCacheTs = 0;
    this.statusTimer = null;
  }

  async init({ container }) {
    this.container = container;
    container.classList.add("now-alert-row");
    container.innerHTML = template;
    this.dom = {
      nowcast: container.querySelector("[data-role='nowcast']"),
      alerts: container.querySelector("[data-role='alerts']"),
    };
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

  async refreshStatus(force = false) {
    try {
      const status = await this.fetchStatus(force);
      this.renderNowcast(status);
      this.renderAlerts(status.alerts || []);
    } catch (err) {
      console.error("Now plugin error", err);
      if (this.dom.nowcast) {
        this.dom.nowcast.textContent = "Now · status unavailable (API error)";
      }
      this.renderAlerts([]);
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

  renderNowcast(status) {
    if (!this.dom.nowcast) return;
    const sun = status.sun;
    const space = status.space_weather;
    const observing = status.observing_index;
    const parts = [];
    const missing = [];
    if (sun) {
      const level = sun.activity_level;
      let phrasing = "solar activity";
      if (level === "quiet") phrasing += " quiet";
      else if (level === "active") phrasing += " active (C-class flares possible)";
      else if (level === "stormy") phrasing += " high (M/X-class flares)";
      else phrasing += ` ${level}`;
      parts.push(phrasing);
    } else {
      missing.push("Sun data unavailable");
    }
    if (space && space.kp != null) {
      let geo = "";
      if (space.kp <= 3) geo = "geomagnetic conditions quiet";
      else if (space.kp <= 5) geo = "geomagnetic unsettled / minor storm levels";
      else geo = "geomagnetic storm conditions";
      geo += ` (Kp ${space.kp})`;
      parts.push(geo);
    } else {
      missing.push("Space weather unavailable");
    }
    if (observing) {
      parts.push(`Maunakea observing ${observing.rating} (Index ${observing.score}/10)`);
    } else {
      missing.push("Observing index unavailable");
    }
    const sentences = [...parts];
    if (missing.length) sentences.push(missing.join(". "));
    this.dom.nowcast.textContent = sentences.length
      ? `Now · ${sentences.join(". ")}.`
      : "Now · status unavailable";
  }

  renderAlerts(alerts) {
    if (!this.dom.alerts) return;
    this.dom.alerts.innerHTML = "";
    if (!alerts.length) {
      const div = document.createElement("div");
      div.className = "alert-card alert-info";
      div.innerHTML = "<h3>No active alerts</h3><p>All systems nominal.</p>";
      this.dom.alerts.appendChild(div);
      return;
    }
    alerts.forEach((alert) => {
      const card = document.createElement("div");
      card.className = `alert-card alert-${alert.severity || "info"}`;
      card.innerHTML = `<h3>${alert.title}</h3><p>${alert.description}</p>`;
      this.dom.alerts.appendChild(card);
    });
  }
}
