import { makeImageFullscreenable } from '/fullscreen.js';

const DEFAULT_CONFIG = {
  refreshIntervalMs: 600_000,
  introStatus: "Playing last 50 frames once…",
  liveStatus: "Showing latest GeoColor frame (updates every 10 minutes).",
};

const template = `
  <h2><span class="tag space">EARTH</span> Earth – GOES-18 GeoColor</h2>
  <div class="source" title="GOES-18 GeoColor loop (50 frames).">
    Source: <span class="badge real">NOAA</span>
  </div>
  <div class="carousel">
    <img data-role="earth-image" class="earth-image" alt="Earth GeoColor" style="width:100%;height:100%;object-fit:contain;background:#0f1b35;" />
    <div data-role="placeholder" class="placeholder" style="display:none;">No Earth imagery available</div>
  </div>
  <div class="summary" data-role="status">Loading Earth loop…</div>
`;

export default function createPlugin(host) {
  return new EarthPanelPlugin(host);
}

class EarthPanelPlugin {
  constructor(host) {
    this.host = host;
    this.container = null;
    this.dom = {};
    this.earthFrames = [];
    this.earthIndex = 0;
    this.earthLoopPlayed = false;
    this.animTimer = null;
    this.refreshTimer = null;
    this.config = { ...DEFAULT_CONFIG };
  }

  async init({ container, config }) {
    this.container = container;
    this.config = {
      refreshIntervalMs: config?.refresh_interval_ms ?? DEFAULT_CONFIG.refreshIntervalMs,
      introStatus: config?.intro_status ?? DEFAULT_CONFIG.introStatus,
      liveStatus: config?.live_status ?? DEFAULT_CONFIG.liveStatus,
    };
    container.innerHTML = template;
    this.dom = {
      image: container.querySelector("[data-role='earth-image']"),
      placeholder: container.querySelector("[data-role='placeholder']"),
      status: container.querySelector("[data-role='status']"),
    };
    // Enable full-screen on click
    makeImageFullscreenable(this.dom.image);
  }

  start() {
    this.loadFrames();
    this.refreshTimer = setInterval(() => this.loadFrames(), this.config.refreshIntervalMs);
  }

  stop() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    if (this.animTimer) clearInterval(this.animTimer);
    this.refreshTimer = null;
    this.animTimer = null;
  }

  destroy() {
    this.stop();
    if (this.container) this.container.innerHTML = "";
    this.container = null;
  }

  async loadFrames() {
    try {
      const resp = await fetch(`${this.host.apiBase()}/api/earth/loop`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (Array.isArray(data) && data.length) {
        this.earthFrames = data;
        if (this.earthLoopPlayed) {
          this.earthIndex = this.earthFrames.length - 1;
          this.dom.status.textContent = this.config.liveStatus;
          this.updateFrame();
        } else {
          this.earthIndex = 0;
          this.dom.status.textContent = this.config.introStatus;
          this.updateFrame();
          this.startIntroLoop();
        }
      } else {
        this.dom.status.textContent = "No Earth imagery available.";
        this.showPlaceholder();
      }
    } catch (err) {
      console.error("Earth plugin error", err);
      if (this.earthFrames.length === 0) {
        this.dom.status.textContent = "Earth loop unavailable – using last known frame, if any.";
        this.showPlaceholder();
      }
    }
  }

  updateFrame() {
    if (!this.earthFrames.length || !this.dom.image) {
      this.showPlaceholder();
      return;
    }
    const frame = this.earthFrames[this.earthIndex % this.earthFrames.length];
    this.dom.placeholder.style.display = "none";
    this.dom.image.style.display = "block";
    this.dom.image.src = frame.url;
    this.dom.image.alt = `Earth GeoColor ${frame.timestamp}`;
  }

  showPlaceholder() {
    if (this.dom.image) this.dom.image.style.display = "none";
    if (this.dom.placeholder) this.dom.placeholder.style.display = "grid";
  }

  startIntroLoop() {
    if (this.animTimer) {
      clearInterval(this.animTimer);
      this.animTimer = null;
    }
    if (this.earthLoopPlayed || this.earthFrames.length <= 1) {
      this.earthLoopPlayed = true;
      this.dom.status.textContent = this.config.liveStatus;
      return;
    }
    let framesRemaining = this.earthFrames.length - 1;
    this.animTimer = setInterval(() => {
      this.earthIndex = (this.earthIndex + 1) % this.earthFrames.length;
      this.updateFrame();
      framesRemaining -= 1;
      if (framesRemaining <= 0) {
        clearInterval(this.animTimer);
        this.animTimer = null;
        this.earthLoopPlayed = true;
        this.earthIndex = this.earthFrames.length - 1;
        this.updateFrame();
        this.dom.status.textContent = this.config.liveStatus;
      }
    }, 500);
  }
}
