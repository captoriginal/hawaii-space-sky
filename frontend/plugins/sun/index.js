const SUN_IMAGES_BASE = "https://services.swpc.noaa.gov/images/animations/suvi/primary/";
const SUN_IMAGE_LIST = [
  { id: "aia-094", path: "094/latest.png", label: "AIA 094" },
  { id: "aia-0131", path: "131/latest.png", label: "AIA 0131" },
  { id: "aia-0171", path: "171/latest.png", label: "AIA 0171" },   
  { id: "aia-0195", path: "195/latest.png", label: "AIA 0195" },
  { id: "aia-0284", path: "284/latest.png", label: "AIA 0284" },
  { id: "aia-0304", path: "304/latest.png", label: "AIA 0304" },
];

const STATUS_TTL = 60_000;

const template = `
  <h2><span class="tag sun">SUN</span> The Sun</h2>
  <div class="source" title="Where this solar data came from.">
    Source: <span data-role="source" class="badge">—</span>
    <span data-role="stale" class="stale-dot" style="display:none;" title="Data may be stale — review timestamps."></span>
  </div>
  <div class="carousel">
    <div class="sun-image-stack" data-role="sun-image-stack">
      <img data-role="sun-image" class="solar-image" alt="Solar view" title="Latest available solar image." />
    </div>
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
    this.imageLoadedOnce = false;
  }

  async init({ container }) {
    this.container = container;
    container.innerHTML = template;
    this.dom = {
      source: container.querySelector("[data-role='source']"),
      stale: container.querySelector("[data-role='stale']"),
      imageStack: container.querySelector("[data-role='sun-image-stack']"),
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
    if (!this.dom.imageStack) return;
    const item = SUN_IMAGE_LIST[this.carouselIndex % SUN_IMAGE_LIST.length];
    const url = `${SUN_IMAGES_BASE}${item.path}?t=${Date.now()}`;
    const wrapper = this.dom.imageStack;
    const current = this.dom.image;
    const nextImg = document.createElement("img");
    nextImg.className = current?.className || "solar-image";
    nextImg.alt = item.label;
    nextImg.style.opacity = this.imageLoadedOnce ? "0" : "1";
    nextImg.style.position = "absolute";
    nextImg.style.inset = "0";
    const cleanupFailure = () => {
      nextImg.remove();
      if (!wrapper.querySelector("img")) {
        this.dom.placeholder.style.display = "grid";
      }
    };
    nextImg.onerror = () => {
      cleanupFailure();
    };
    nextImg.onload = () => {
      this.imageLoadedOnce = true;
      this.dom.placeholder.style.display = "none";
      requestAnimationFrame(() => {
        nextImg.style.opacity = "1";
        if (current) {
          current.style.opacity = "0";
        }
      });
      setTimeout(() => {
        if (current && current !== nextImg) current.remove();
        this.dom.image = nextImg;
      }, 1500);
    };
    wrapper.appendChild(nextImg);
    nextImg.src = url;
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
      this.dom.source.classList.remove("real", "cache", "demo", "unavailable");
      this.dom.source.classList.add(origin);
    }
    const alerts = status?.alerts || [];
    const stale = alerts.some((a) => a.id === "stale_sun_data");
    if (this.dom.stale) this.dom.stale.style.display = stale ? "inline-block" : "none";
  }
}
