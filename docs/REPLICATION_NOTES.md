# UI and API Contract Replication Notes

## Overview
This document describes the files replicated from [Rider-Pi](https://github.com/mpieniak01/Rider-Pi) to Rider-Pc repository to enable PC client development.

## Replicated Directories

### 1. `web/` - Frontend UI Components (14 files)
Purpose: Provides the web interface for 1:1 UI replication on the PC client.

**Structure:**
```
web/
├── assets/
│   ├── dashboard-common.css       # Common dashboard styles
│   ├── i18n.js                    # Internationalization support (PL/EN)
│   ├── menu.js                    # Dynamic menu loader
│   ├── icons/
│   │   ├── flag-en.svg            # English language flag
│   │   └── flag-pl.svg            # Polish language flag
│   └── riderai_logi.svg           # RiderAI logo
├── chat.html                      # Voice and text chat interface
├── control.html                   # Robot movement control panel
├── dashboard_menu_template.html   # Reusable menu template
├── google_home.html               # Google Home integration interface
├── home.html                      # Main landing page
├── navigation.html                # Autonomous navigation interface (Rekonesans)
├── system.html                    # System status and diagnostics
└── view.html                      # Mini dashboard with metrics and camera
```

**Key Features:**
- Responsive dashboard design with dark theme
- Multi-language support (Polish/English)
- Real-time data visualization
- Camera feed integration
- System metrics display
- API metrics tracking

**Integration Notes:**
- These files should be connected to a **local Buffer/Cache** (Redis/SQLite) rather than directly to Rider-PI backend
- The UI expects data from endpoints like `/healthz`, `/state`, `/sysinfo`, `/vision/snap-info`
- Static files are served from the `/web/` path
- Auto-refresh mechanisms (≈2s) for live data
- When `TEST_MODE=true`, `MockRestAdapter` now delivers full demo payloads (Google Home devices, Rider-Pi/PC/Ollama model lists, logic summary, etc.), so the UI renders every widget without HTML probes or manual tweaks.
- GitHub Actions contains a `css-ui-audit` job (see `.github/workflows/ci-cd.yml`) that runs `npm run lint:css`, `npm run css:size`, and `npm run css:audit` using Playwright Firefox and attaches `logs/css_audit_summary.json` plus `logs/css_audit/*.png` as artifacts. Local reproduction: `npm ci && python -m playwright install firefox --with-deps && npm run css:audit`.

### 2. `config/` - Provider Configuration Files (30 files)
Purpose: Defines provider configurations and parameters for contract negotiation between PC and Rider-PI.

**Structure:**
```
config/
├── agent/                         # Agent test configuration
│   ├── constraints.txt            # Python package constraints
│   ├── requirements-test.txt      # Test dependencies
│   └── run_tests.sh              # Test execution script
├── alsa/                          # Audio configuration
│   ├── aliases.toml              # ALSA device aliases
│   ├── asoundrc.wm8960           # WM8960 audio codec config
│   ├── mpg123.sh                 # MP3 player script
│   ├── preflight.sh              # Audio preflight checks
│   ├── wm8960-apply.sh           # Apply WM8960 settings
│   └── wm8960-mixer.sh           # WM8960 mixer controls
├── local/                         # Local configuration overrides
│   └── .gitignore                # Ignore local config files
├── camera.toml                    # Camera configuration
├── choreography.toml              # Event-to-action mappings
├── face.toml                      # Robot face animation config
├── google_bridge.toml             # Google Home bridge config
├── jupyter.toml                   # Jupyter notebook config
├── motion.toml                    # Motion control configuration
├── motion_actions.toml            # Predefined motion actions
├── providers.toml                 # Provider configuration
├── voice.toml                     # Active voice configuration
├── voice_gemini_example.toml      # Google Gemini voice example
├── voice_gemini_file.toml         # Gemini file-based config
├── voice_local_file.toml          # Local voice processing
├── voice_openai_file.toml         # OpenAI file-based config
├── voice_openai_streaming.toml    # OpenAI streaming config
└── voice_openai_streaming_fallback.toml  # OpenAI with fallback
```

**Key Configuration Categories:**

**Voice Providers:**
- Multiple provider options: OpenAI, Google Gemini, local processing
- Streaming and file-based modes
- Fallback mechanisms
- ASR (Automatic Speech Recognition) and TTS (Text-to-Speech) parameters
- VAD (Voice Activity Detection) configuration

**Vision Providers:**
- Edge detection configuration
- Obstacle detection parameters
- SSD (Single Shot Detection) model settings
- Camera frame processing
- Snapshot management

**Motion Configuration:**
- Balance control parameters
- Motion actions and choreography
- Event-driven motion responses

**Integration Notes:**
- Default configurations are provided in the `config/` directory
- To customize, copy any config file to `config/local/*.toml` and modify as needed
- Local configs are gitignored to prevent committing sensitive data
- Use these configs to define default provider choices for PC client
- Configure PC connector parameters for contract negotiation

### 3. `docs/api-specs/` - API Documentation (3 files)
Purpose: Serves as API contracts for REST client generation and contract testing.

**Structure:**
```
docs/api-specs/
├── README.md        # API overview and common patterns
├── control.md       # Robot movement and control API
└── navigator.md     # Autonomous navigation API
```

**API Categories:**

**Control API** (`/api/control`):
- Generic control commands (drive, stop, spin)
- Balance control (`/api/control/balance`)
- Height adjustment (`/api/control/height`)
- Command patterns with linear velocity (lx) and angular velocity (az)

**Navigator API** (`/api/navigator`):
- Start/stop autonomous navigation
- Configuration management
- Return home functionality
- Real-time status updates

**Common Patterns:**
- CORS support on all endpoints
- Standard JSON response format: `{"ok": true/false, "data": {...}}`
- Timestamp fields in Unix epoch format
- ZMQ bus integration for commands
- HTTP preflight (OPTIONS) support

**Integration Notes:**
- Use these specs to generate REST client with `httpx` (async)
- Implement contract tests to verify API compatibility
- Base URL: `http://robot-ip:8080`
- All endpoints support OPTIONS for CORS preflight

## File Statistics
- **Total files copied:** 47
- **web/:** 14 files (HTML, CSS, JavaScript, SVG)
- **config/:** 30 files (TOML, shell scripts)
- **docs/api-specs/:** 3 files (Markdown documentation)

## Source Information
- **Source Repository:** https://github.com/mpieniak01/Rider-Pi
- **Target Repository:** https://github.com/mpieniak01/Rider-Pc
- **Replication Date:** 2025-11-12
- **Purpose:** Enable PC client development with 1:1 UI replication and API integration

## Next Steps

### 1. API Adapter Implementation
- Generate REST client from API specs using `httpx`
- Implement ZMQ SUB socket for bus topics (`vision.*`, `voice.*`, `motion.state`, `robot.pose`)
- Create contract tests based on docs/api-specs documentation
- Handle REST endpoints: `/healthz`, `/api/control`, `/api/chat/*`, etc.
- Map ZMQ topics to local domain events

### 2. Buffer/Cache Implementation
- Set up Redis or SQLite for local data buffering
- Cache screen states and snapshots
- Buffer raw data streams for providers
- Implement quick UI restoration
- Handle data synchronization with Rider-PI

### 3. UI Integration
- Configure web server (FastAPI) to serve files from `web/`
- Connect UI to local Buffer/Cache instead of Rider-PI directly
- Implement data endpoints that UI expects
- Enable real-time updates via WebSocket or polling
- Test all dashboard pages for functionality

### 4. Provider Configuration
- Review and customize config files for PC environment
- Copy relevant config files from `config/` to `config/local/` and customize as needed
- Configure Voice Provider for ASR/TTS offload
- Configure Vision Provider for image processing
- Configure Text Provider for NLU/NLG tasks
- Set up provider discovery and negotiation

## Additional Resources
- [Rider-Pc Architecture](ARCHITECTURE.md)
- [Rider-Pc Next Steps](FUTURE_WORK.md)
- [Rider-Pi Device Architecture](RIDER_PI_ARCH.md)
- [Rider-Pi Project](https://github.com/mpieniak01/Rider-Pi)
