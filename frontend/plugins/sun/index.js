const SUN_IMAGES_BASE = "https://sdo.gsfc.nasa.gov/assets/img/latest/";
const SUN_IMAGE_LIST = [
  { id: "aia-0193", path: "latest_512_0193.jpg", label: "AIA 0193" },
  { id: "aia-0171", path: "latest_512_0171.jpg", label: "AIA 0171" },
  { id: "aia-0304", path: "latest_512_0304.jpg", label: "AIA 0304" },
  { id: "aia-0211", path: "latest_512_0211.jpg", label: "AIA 0211" },
  { id: "aia-0131", path: "latest_512_0131.jpg", label: "AIA 0131" },
  { id: "aia-0335", path: "latest_512_0335.jpg", label: "AIA 0335" },
  { id: "aia-094", path: "latest_512_0094.jpg", label: "AIA 094" },
  { id: "aia-1600", path: "latest_512_1600.jpg", label: "AIA 1600" },
  { id: "aia-1700", path: "latest_512_1700.jpg", label: "AIA 1700" },
  { id: "aia-211193171", path: "latest_1024_211193171.jpg", label: "AIA 211, 193, 171" },
  { id: "aia-304211171", path: "f_304_211_171_512.jpg", label: "AIA 304, 211, 171" },
  { id: "aia-094335193", path: "f_094_335_193_512.jpg", label: "AIA 094, 335, 193" },
  { id: "aia-171-hmib", path: "f_HMImag_171_512.jpg", label: "AIA 171 & HMIB" },
  { id: "hmi-mag", path: "latest_512_HMIB.jpg", label: "HMI Magnetogram" },
  { id: "hmi-intensity", path: "latest_512_HMII.jpg", label: "HMI Intensitygram" },
  { id: "hmi-doppler", path: "latest_512_HMID.jpg", label: "HMI Dopplergram" },
];

const STATUS_TTL = 60_000;

const template = `
  <h2><span class="tag sun">SUN</span> The Sun</h2>
  <div class="source" title="Where this solar data came from.">
    Source: <span data-role="source" class="badge">—</span>
    <span data-role="stale" class="stale-dot" style="display:none;" title="Data may be stale — review timestamps."></span>
  </div>
  <div class="carousel">
    <img data-role="sun-image" class="solar-image" alt="Solar view" title="Latest available solar image." />
    <div data-role="sun-placeholder" class="placeholder" style="display:none;">Solar image unavailable</div>
  </div>
  <div class="metrics" data-role="sun-metrics">
    <div class="metric">
      <span class="label" title="GOES soft X-ray flux classification.">Current X-ray class</span>
      <span class="value" data-role="xray-class">—</span>
    </div>
    <div class="metric">
      <span class="label" title="Qualitative solar activity level.">Activity level</span>
      <span class="value" data-role="activity-level">—</span>
    </div>
  </div>
  <div class="nerd-section" data-role="nerd">
    <table>
      <thead>
        <tr><th>Timestamp</th><th>Short</th><th>Long</th></tr>
      </thead>
      <tbody data-role="sun-table-body"></tbody>
    </table>
  </div>
  <div class="unavailable" data-role="sun-unavailable" style="display:none;">Sun data unavailable</div>
`;

export default function createPlugin(host) {
  return new SunPanelPlugin(host);
}

class SunPanelPlugin {
  constructor(host) {
    this.host = host;
    this.container = null;
    this.dom = {};
    this.carouselIndex = 0;
    this.autoplayTimer = null;
    this.refreshTimer = null;
    this.statusTimer = null;
    this.statusCache = null;
    this.statusCacheTs = 0;
    this.nerdMode = host?.getNerdMode?.() ?? false;
  }

  async init({ container }) {
    this.container = container;
    container.innerHTML = template;
    this.dom = {
      source: container.querySelector("[data-role='source']"),
      stale: container.querySelector("[data-role='stale']"),
      image: container.querySelector("[data-role='sun-image']"),
      placeholder: container.querySelector("[data-role='sun-placeholder']"),
      metrics: container.querySelector("[data-role='sun-metrics']"),
      xrayClass: container.querySelector("[data-role='xray-class']"),
      activity: container.querySelector("[data-role='activity-level']"),
      nerd: container.querySelector("[data-role='nerd']"),
      nerdBody: container.querySelector("[data-role='sun-table-body']"),
      unavailable: container.querySelector("[data-role='sun-unavailable']"),
    };
    this.dom.nerd.style.display = this.nerdMode ? "block" : "none";
    this.showCurrentImage();
    this.autoplayTimer = setInterval(() => this.nextImage(), 15_000);
    this.refreshTimer = setInterval(() => this.showCurrentImage(), 60_000);
  }

  start() {
    this.refreshStatus(true);
    this.statusTimer = setInterval(() => this.refreshStatus(false), 90_000);
  }

  stop() {
    if (this.autoplayTimer) clearInterval(this.autoplayTimer);
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    if (this.statusTimer) clearInterval(this.statusTimer);
    this.autoplayTimer = this.refreshTimer = this.statusTimer = null;
  }

  destroy() {
    this.stop();
    if (this.container) this.container.innerHTML = "";
    this.container = null;
  }

  setNerdMode(enabled) {
    this.nerdMode = enabled;
    if (this.dom.nerd) {
      this.dom.nerd.style.display = enabled ? "block" : "none";
    }
  }

  nextImage() {
    this.carouselIndex = (this.carouselIndex + 1) % SUN_IMAGE_LIST.length;
    this.showCurrentImage();
  }

  showCurrentImage() {
    if (!this.dom.image) return;
    const item = SUN_IMAGE_LIST[this.carouselIndex % SUN_IMAGE_LIST.length];
    const url = `${SUN_IMAGES_BASE}${item.path}?t=${Date.now()}`;
    let failed = false;
    this.dom.placeholder.style.display = "none";
    this.dom.image.style.display = "block";
    this.dom.image.src = url;
    this.dom.image.alt = item.label;
    this.dom.image.onerror = () => {
      failed = true;
      this.dom.image.style.display = "none";
      this.dom.placeholder.style.display = "grid";
    };
    this.dom.image.onload = () => {
      if (!failed) {
        this.dom.image.style.display = "block";
        this.dom.placeholder.style.display = "none";
      }
    };
  }

  async refreshStatus(force = false) {
    try {
      const status = await this.fetchStatus(force);
      const sun = status?.sun;
      if (!sun) {
        this.showUnavailable();
        return;
      }
      this.dom.unavailable.style.display = "none";
      this.dom.metrics.style.display = "";
      this.dom.xrayClass.textContent = sun.current_class;
      this.dom.activity.textContent = sun.activity_level;
      this.renderNerdTable(sun);
      this.updateSource(status);
    } catch (err) {
      console.error("Sun plugin status error", err);
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

  showUnavailable() {
    if (this.dom.metrics) this.dom.metrics.style.display = "none";
    if (this.dom.unavailable) this.dom.unavailable.style.display = "block";
  }

  renderNerdTable(sun) {
    if (!this.dom.nerdBody) return;
    this.dom.nerdBody.innerHTML = "";
    const shorts = (sun.xray_flux_short || []).slice(-5);
    const longs = (sun.xray_flux_long || []).slice(-5);
    shorts.forEach((point, idx) => {
      const longVal = longs[idx] || longs[longs.length - 1];
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${point.timestamp}</td><td>${point.value_wm2.toExponential(2)}</td><td>${longVal.value_wm2.toExponential(2)}</td>`;
      this.dom.nerdBody.appendChild(tr);
    });
  }

  updateSource(status) {
    const origin = status?.data_sources?.sun || "demo";
    if (this.dom.source) {
      this.dom.source.textContent = origin;
      this.dom.source.classList.remove("real", "cache", "demo");
      this.dom.source.classList.add(origin);
    }
    const alerts = status?.alerts || [];
    const stale = alerts.some((a) => a.id === "stale_sun_data");
    if (this.dom.stale) this.dom.stale.style.display = stale ? "inline-block" : "none";
  }
}
