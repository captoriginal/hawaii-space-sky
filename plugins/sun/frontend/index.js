import { makeImageFullscreenable } from '/fullscreen.js';

const DEFAULT_CONFIG = {
  carouselBaseUrl: "https://services.swpc.noaa.gov/images/animations/suvi/primary/",
  carouselImages: [
    { id: "aia-094", path: "094/latest.png", label: "AIA 094" },
    { id: "aia-0131", path: "131/latest.png", label: "AIA 0131" },
    { id: "aia-0171", path: "171/latest.png", label: "AIA 0171" },
    { id: "aia-0195", path: "195/latest.png", label: "AIA 0195" },
    { id: "aia-0284", path: "284/latest.png", label: "AIA 0284" },
    { id: "aia-0304", path: "304/latest.png", label: "AIA 0304" }
  ],
  statusTtlMs: 60_000,
  statusRefreshMs: 90_000,
  carouselIntervalMs: 15_000,
  imageRefreshMs: 60_000
};

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
    this.imageLoadedOnce = false;
    this.config = { ...DEFAULT_CONFIG };
  }

  async init({ container, config }) {
    this.container = container;
    this.config = {
      carouselBaseUrl: config?.carousel_base_url
        || config?.solar_image_url
        || DEFAULT_CONFIG.carouselBaseUrl,
      carouselImages: Array.isArray(config?.carousel_images) && config.carousel_images.length
        ? config.carousel_images
        : DEFAULT_CONFIG.carouselImages,
      statusTtlMs: config?.status_ttl_ms ?? DEFAULT_CONFIG.statusTtlMs,
      statusRefreshMs: config?.status_refresh_ms ?? DEFAULT_CONFIG.statusRefreshMs,
      carouselIntervalMs: config?.carousel_interval_ms ?? DEFAULT_CONFIG.carouselIntervalMs,
      imageRefreshMs: config?.image_refresh_ms ?? DEFAULT_CONFIG.imageRefreshMs
    };
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
      unavailable: container.querySelector("[data-role='sun-unavailable']"),
    };
    this.showCurrentImage();
    this.autoplayTimer = setInterval(() => this.nextImage(), this.config.carouselIntervalMs);
    this.refreshTimer = setInterval(() => this.showCurrentImage(), this.config.imageRefreshMs);
  }

  start() {
    this.refreshStatus(true);
    this.statusTimer = setInterval(() => this.refreshStatus(false), this.config.statusRefreshMs);
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

  nextImage() {
    if (!Array.isArray(this.config.carouselImages) || !this.config.carouselImages.length) return;
    this.carouselIndex = (this.carouselIndex + 1) % this.config.carouselImages.length;
    this.showCurrentImage();
  }

  resolveImageUrl(item) {
    const cacheBust = `t=${Date.now()}`;
    if (item.url) {
      const joiner = item.url.includes("?") ? "&" : "?";
      return `${item.url}${joiner}${cacheBust}`;
    }
    if (!item.path) return null;
    if (!this.config.carouselBaseUrl) return null;
    const base = this.config.carouselBaseUrl.endsWith("/")
      ? this.config.carouselBaseUrl
      : `${this.config.carouselBaseUrl}/`;
    return `${base}${item.path}?${cacheBust}`;
  }

  showCurrentImage() {
    if (!this.dom.imageStack) return;
    const images = this.config.carouselImages;
    if (!images.length) {
      if (this.dom.placeholder) this.dom.placeholder.style.display = "grid";
      return;
    }
    const item = images[this.carouselIndex % images.length];
    const url = this.resolveImageUrl(item);
    if (!url) {
      if (this.dom.placeholder) this.dom.placeholder.style.display = "grid";
      return;
    }
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
      // Enable full-screen on click for the new image
      makeImageFullscreenable(nextImg);
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
      this.updateSource(status);
    } catch (err) {
      console.error("Sun plugin status error", err);
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

  showUnavailable() {
    if (this.dom.metrics) this.dom.metrics.style.display = "none";
    if (this.dom.unavailable) this.dom.unavailable.style.display = "block";
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
