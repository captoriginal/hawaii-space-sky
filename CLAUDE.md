# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hawai'i Space & Sky Dashboard - A full-stack web application providing near-real-time solar, geomagnetic, Maunakea weather, and observing conditions through a plugin-based architecture.

- **Backend**: FastAPI (Python 3.11+) with SQLite persistence and background refresh tasks
- **Frontend**: Vanilla HTML/CSS/ES modules (no frameworks) with dynamic plugin loading
- **Architecture**: Plugin-based system where each panel is an independent module with optional backend/frontend components

## Development Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run backend server
./start_backend.sh
# OR
uvicorn backend.app.main:app --reload --port 8000

# Access dashboard
open http://127.0.0.1:8000/

# Run tests
./run_tests.sh                  # All tests with coverage
./run_tests.sh --unit          # Unit tests only
./run_tests.sh --integration   # Integration tests only
pytest tests/unit/test_cache.py -v  # Single test file

# Code quality
black backend/ tests/           # Format (100 char line length)
ruff check backend/ tests/      # Lint
mypy backend/                   # Type check
```

## Plugin System Architecture

### Plugin Structure

Plugins are modular packages in `plugins/<name>/` with optional backend and frontend components:

```
plugins/
├── sun/
│   ├── backend/__init__.py      # Optional: defines register(app) for API routes
│   ├── frontend/index.js        # Required: exports default factory function
│   └── config.json              # Plugin configuration
├── earth/
│   ├── backend/__init__.py      # Provides /api/earth/loop endpoint
│   ├── frontend/index.js        # GOES-18 image carousel UI
│   └── config.json
└── maunakea/
    ├── frontend/index.js        # Conditions display + sky camera
    └── config.json
```

### Backend Plugin Contract

**File**: `plugins/<name>/backend/__init__.py`

```python
def register(app: FastAPI, helpers=None) -> None:
    """
    Called during app startup by backend/app/plugins/loader.py

    Register custom API routes, background tasks, or middleware.
    """
    router = APIRouter(prefix="/api/<plugin>", tags=["<plugin>"])

    @router.get("/endpoint")
    async def handler():
        return {"data": "..."}

    app.include_router(router)
```

Plugin backends are loaded automatically from `panels.json` mapping.

### Frontend Plugin Contract

**File**: `plugins/<name>/frontend/index.js`

```javascript
export default function createPlugin(host) {
  return {
    // Required: Initialize plugin with DOM container
    async init({ container, slotId, host, config }) {
      container.innerHTML = template;
      // Setup event listeners, DOM references
    },

    // Optional: Begin active operations (polling, updates)
    start() {
      this.timer = setInterval(() => this.poll(), 60000);
    },

    // Optional: Pause operations
    stop() {
      if (this.timer) clearInterval(this.timer);
    },

    // Optional: Final cleanup
    destroy() {
      // Remove listeners, abort requests
    }
  };
}
```

**Host Object** provides:
- `apiBase()`: Returns API base URL
- `fetchJson(path, options?)`: Fetch wrapper with base URL
- `getConfig()`: Returns plugin's config.json

### Plugin Loading Flow

1. **Frontend** (`app.js:initApp()`):
   - Fetches `/api/panels` → gets panel-to-plugin mapping from `panels.json`
   - For each slot: dynamically imports `/plugins/<name>/frontend/index.js`
   - Calls factory function with host object
   - Invokes `init()` with container DOM node, then `start()`

2. **Backend** (`main.py` startup):
   - `load_plugins(app)` reads `panels.json`
   - For each plugin: tries `import_module(f"plugins.{name}.backend")`
   - Calls `register(app)` if it exists
   - Plugin routes are now available (e.g., `/api/earth/loop`)

## Backend Architecture

### Core Data Flow

```
External APIs → Fetchers → Selectors → Status Builder → API Response
                    ↓           ↓
                 Cache DB   History DB
```

**Key Services** (`backend/app/services/`):

- **status.py**: `build_status_payload()` - Main orchestrator that assembles complete `DashboardStatus`
- **selectors.py**: Data source strategy (real/demo/cached) - returns `(data, origin, is_stale)`
- **fetchers.py**: HTTP calls with retry logic, parses external API responses
- **astronomy.py**: Moon/sun calculations using Skyfield library
- **images.py**: Download and cache images locally
- **maunakea.py**: Derives seeing/transparency from weather data using empirical formulas
- **earth_loop.py**: Fetches GOES-18 GeoColor frames from NOAA CDN

### Data Derivation: Maunakea Conditions

Seeing and transparency are **not measured directly** but derived from NOAA weather grid data:

**Seeing** (arcseconds) in `services/maunakea.py:73-79`:
```python
seeing = 0.6 + (cloud_fraction * 0.8) + (wind_mps / 30)
# Clamped to 0.5-2.5 arcsec
# Better seeing = fewer clouds + less wind
```

**Transparency** (magnitude loss) in `services/maunakea.py:82-88`:
```python
transparency = 0.05 + (cloud_fraction * 0.5) + (humidity/100 * 0.2)
# Clamped to 0.05-0.5 mag
# Better transparency = fewer clouds + lower humidity
```

These are approximations based on meteorological conditions, not actual observatory telemetry.

### Caching Strategy

**Three-layer cache system**:

1. **In-memory Plugin Cache** (60s): Frontend plugins cache `/api/status` to reduce API calls
2. **Backend Cache DB** (`cache.db`): Stores parsed API responses, checked before external HTTP calls
3. **History DB** (`history.db`): Time-series storage for `/api/history` charting endpoint

**Fallback Strategy** (in selectors.py):
```
1. Try fetch from external API (if USE_REAL_* enabled)
2. On failure/staleness: check cache.db
3. If no cache: return demo data
Returns: (data, origin, is_stale) tuple
```

### Database Management

**SQLite databases** use:
- Context managers for safe connection handling
- WAL (Write-Ahead Logging) mode for concurrency
- Automatic table creation on first use

**Clear caches**:
```bash
curl -X POST http://localhost:8000/api/cache/clear
# Removes cache.db, history.db, and cached static images
```

## Frontend Architecture

### Main Controller

**File**: `frontend/app.js`

- **PanelManager class**: Manages plugin lifecycle
  - Fetches panel configuration from backend
  - Dynamically imports plugin ES modules
  - Calls init() → start() → stop() → destroy() lifecycle hooks
  - Handles plugin errors gracefully

- **Global polling**: Fetches `/api/status` every 90 seconds
- **Module imports**: Uses dynamic `import(url)` for plugin loading

### Important: Module Import Paths

When plugins import shared utilities, use **absolute paths** from root:

```javascript
// Correct - absolute path from root
import { makeImageFullscreenable } from '/fullscreen.js';

// Wrong - relative paths fail with module loading
import { makeImageFullscreenable } from '../../../frontend/fullscreen.js';
```

**Note**: Use `http://127.0.0.1:8000` consistently (not `localhost:8000`) to avoid cross-origin module issues.

### Plugin Example: Image Carousel

Plugins managing dynamic images (Sun, Earth) use this pattern:

1. Create new `<img>` element with `opacity: 0`
2. Set absolute positioning in image stack
3. On load: fade in new image, fade out old
4. After transition: remove old image from DOM
5. Call `makeImageFullscreenable(imgElement)` for each new image

See `plugins/sun/frontend/index.js:160-180` for reference implementation.

## Configuration System

**Four-level hierarchy**:

1. **Environment** (`.env` file):
   ```
   DATA_MODE=real
   USE_REAL_SUN=True
   USE_REAL_SPACE_WEATHER=True
   USE_REAL_MAUNAKEA=True
   ```

2. **Settings Class** (`backend/app/config.py`):
   - Pydantic BaseSettings with defaults
   - `get_settings()` returns singleton
   - Controls data sources, URLs, timeouts, stale thresholds

3. **Plugin Configs** (`plugins/<name>/config.json`):
   - Plugin-specific settings (URLs, refresh intervals)
   - Loaded via `load_plugin_config(name)` (LRU-cached)
   - Accessible at `/api/plugins/<name>/config`

4. **Panel Mapping** (`panels.json`):
   - Maps slot IDs to plugin names
   - Example: `{"panels": {"panel-1": "sun", "panel-2": "earth"}}`

## API Endpoints

```
GET  /api/status                        # Current dashboard status (DashboardStatus model)
GET  /api/history?hours=<1-168>        # Time-series history (HistoryResponse model)
GET  /api/panels                        # Panel configuration (panels.json)
GET  /api/plugins/<name>/config        # Plugin config (config.json)
POST /api/cache/clear                   # Admin: clear all caches
GET  /api/earth/loop                    # Earth plugin: GOES-18 frames
```

## Testing Infrastructure

**Structure**:
- `tests/unit/`: 121 tests for cache, storage, fetchers, models, plugin loader
- `tests/integration/`: 10 tests for API endpoints and flows
- Coverage: >90% overall, >85% for core modules

**Key Patterns**:
- Fixtures provide isolated temp databases
- Mock external HTTP calls with `@patch`
- Use `@pytest.mark.asyncio` for async tests
- TestClient for API integration tests

**Test Files**:
- `test_cache.py`: Cache database operations (25 tests)
- `test_storage.py`: History database operations (30 tests)
- `test_fetchers.py`: HTTP retry + data parsing (17 tests)
- `test_models.py`: Pydantic validation (28 tests)
- `test_plugin_loader.py`: Plugin loading system (21 tests)
- `test_api.py`: API endpoints + flows (10 tests)

## Common Tasks

### Adding a New Plugin

1. Create `plugins/my_plugin/frontend/index.js`:
   ```javascript
   export default function createPlugin(host) {
     return {
       async init({ container, config }) {
         container.innerHTML = "<div>My Plugin</div>";
       },
       start() { /* polling logic */ },
     };
   }
   ```

2. Optional: Create `plugins/my_plugin/backend/__init__.py`:
   ```python
   def register(app, helpers=None):
       router = APIRouter(prefix="/api/my_plugin")
       @router.get("/data")
       async def get_data():
           return {"data": "..."}
       app.include_router(router)
   ```

3. Create `plugins/my_plugin/config.json`:
   ```json
   {"refresh_ms": 60000}
   ```

4. Register in `panels.json`:
   ```json
   {"panels": {"panel-1": "my_plugin"}}
   ```

### Adding a New API Endpoint

1. Add route in `backend/app/api/routes.py`
2. Implement service logic in `backend/app/services/`
3. Add Pydantic model in `backend/app/models.py`
4. Write tests in `tests/integration/test_api.py`

### Debugging Plugin Issues

**Plugin not loading**:
- Check browser console for import errors
- Verify plugin listed in `panels.json`
- Check backend logs for `register()` errors
- Ensure paths use absolute imports (`/fullscreen.js` not `../../../`)

**Module import failures**:
- Use `http://127.0.0.1:8000` not `localhost:8000`
- Check Network tab for 404s on module URLs
- Verify `assetBase()` matches `apiBase()` in app.js

## Code Style

**Python**:
- Black formatting (100 char line length)
- Type hints mandatory (mypy strict mode)
- Async/await for I/O-bound operations
- Context managers for database connections

**JavaScript**:
- Vanilla ES modules (no bundler)
- Class-based plugins with lifecycle methods
- camelCase naming
- DOM references stored during init()

**SQL**:
- Context managers for all connections
- WAL mode for concurrency
- Indexes on time-based queries
