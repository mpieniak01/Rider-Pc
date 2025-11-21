# Rider-PC Client

PC-side client infrastructure for the Rider-PI robot, providing:
- REST API adapter for consuming Rider-PI endpoints
- ZMQ subscriber for real-time data streams  
- Local SQLite cache for buffering data
- FastAPI web server replicating the Rider-PI UI
- **AI Provider Layer** with real ML models (Voice, Vision, Text)
- **Production-ready deployment** with Docker and CI/CD

## Quick Start
### Option 1: Docker (Recommended)
```bash
# Create .env file
echo "RIDER_PI_HOST=192.168.1.100" > .env

# Start the full stack
docker-compose up -d

# Access services
# Rider-PC UI: http://localhost:8000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```
### Option 2: Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no AI models required)
python -m pc_client.main
```

See [AI_MODEL_SETUP.md](AI_MODEL_SETUP.md) for AI model setup guide.

### Development Workflow

- **Python**: develop on Python 3.11 (CI target) while keeping code compatible with Rider-PI’s Python 3.9.
- **Tooling**: `pip install -r requirements-ci.txt` and `pre-commit install` to get `ruff` hooks.
- **Make targets**: `make lint`, `make format`, `make test` mirror GitHub Actions.
- **Rider-Pi integration**:
  - Control panel (`web/control.html`) mirrors Rider-Pi, including the *AI Mode* card and *Provider Control* toggles.
  - Backend proxy endpoints (`/api/system/ai-mode`, `/api/providers/*`) forward to Rider-Pi via the `RestAdapter` and cache responses for offline dev/tests.
  - To operate the real robot, point `.env` at Rider-Pi and run `make start`, then browse `http://localhost:8000/web/control.html`.
  - Vision offload is wired to Rider-Pi’s ZMQ broker. Enable it by setting `ENABLE_PROVIDERS=true`, `ENABLE_TASK_QUEUE=true`, `ENABLE_VISION_OFFLOAD=true`, and `TELEMETRY_ZMQ_HOST=<Rider-Pi IP>` so the PC consumes `vision.frame.offload` and publishes `vision.obstacle.enhanced`.
  - Voice offload works the same way: add `ENABLE_VOICE_OFFLOAD=true` to stream `voice.asr.request`/`voice.tts.request` into the PC queue and emit `voice.asr.result`/`voice.tts.chunk` back to Rider-Pi.
  - Text/LLM support is exposed via `/providers/text/generate` (handshake: `GET /providers/capabilities`), so Rider-Pi can negotiate before delegating chat/NLU workloads. Use `ENABLE_TEXT_OFFLOAD=true` once gotowy.

## Architecture

The PC client consists of three main layers:

1. **Adapter Layer** - Consumes data from Rider-PI via REST API and ZMQ streams
2. **Cache Layer** - Stores current states in SQLite for quick access
3. **Web Server Layer** - FastAPI server that serves static files and provides API endpoints reading from cache

## Prerequisites

- Python 3.9 or higher
- WSL2 with Debian (for Windows users)
- Network access to Rider-PI device

## Installation

1. Clone the repository:
```bash
git clone https://github.com/mpieniak01/Rider-Pc.git
cd Rider-Pc
```

2. Create a virtual environment:
```bash
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Configure the PC client using environment variables:

```bash
# Rider-PI connection
export RIDER_PI_HOST="192.168.1.100"  # IP address of your Rider-PI
export RIDER_PI_PORT="8080"           # REST API port

# ZMQ configuration
export ZMQ_PUB_PORT="5555"            # ZMQ PUB port
export ZMQ_SUB_PORT="5556"            # ZMQ SUB port

# Local server
export SERVER_HOST="0.0.0.0"          # Server host
export SERVER_PORT="8000"             # Server port

# Cache
export CACHE_DB_PATH="data/cache.db"  # SQLite database path
export CACHE_TTL_SECONDS="30"         # Cache TTL in seconds

# Logging
export LOG_LEVEL="INFO"               # Log level (DEBUG, INFO, WARNING, ERROR)

# Providers / Vision offload
export ENABLE_PROVIDERS="true"
export ENABLE_TASK_QUEUE="true"
export ENABLE_VISION_OFFLOAD="true"
export ENABLE_VOICE_OFFLOAD="true"
export ENABLE_TEXT_OFFLOAD="true"
export TELEMETRY_ZMQ_HOST="$RIDER_PI_HOST"  # Publishes vision.obstacle.enhanced back to Rider-Pi
```

See [PC_OFFLOAD_INTEGRATION.md](PC_OFFLOAD_INTEGRATION.md) for the full workflow and troubleshooting tips.

## Running

Start the PC client server:

```bash
python -m pc_client.main
```

Or if installed as a package:

```bash
python pc_client/main.py
```

The server will start on `http://localhost:8000` by default.

Access the UI at: `http://localhost:8000/`

### Local Stack (no Docker)

If Docker/WSL2 is unavailable you can launch every service directly from the repository using the helper scripts:

```bash
# One-time setup (Ubuntu)
sudo apt install redis-server prometheus grafana

cd ~/Rider-Pc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust Rider-PI host if needed

# Start all services (Redis + Prometheus + Grafana + FastAPI)
scripts/start_local_stack.sh

# View logs under logs/, PIDs under .pids/

# When finished
scripts/stop_local_stack.sh
```

The helper scripts read the `PANEL_PORT` environment variable (default: `8080`) to decide where to expose the FastAPI panel. Example: `PANEL_PORT=8000 scripts/start_local_stack.sh`. Each run stores Python logs in `logs/panel-<port>.log`, so you can tail them without noisy console output.

For convenience you can also run:

```bash
make start   # start all services
make stop    # stop all services
make reload  # stop + start
```

The script takes care of creating/updating the virtualenv, setting environment variables from `.env`, and launching background processes. Logs are stored in `logs/` so you can inspect them for troubleshooting.

## API Endpoints

The PC client replicates the following Rider-PI endpoints:

- `GET /healthz` - Health check
- `GET /state` - Current state
- `GET /sysinfo` - System information
- `GET /vision/snap-info` - Vision snapshot info
- `GET /vision/obstacle` - Obstacle detection data
- `GET /api/app-metrics` - Application metrics
- `GET /api/resource/camera` - Camera resource status
- `GET /api/bus/health` - Message bus health

All endpoints return JSON data cached from the Rider-PI device.

## ZMQ Topics

The ZMQ subscriber listens to the following topic patterns:

- `vision.*` - Vision system events
- `motion.*` - Motion system events
- `robot.*` - Robot state events
- `navigator.*` - Navigator events

Messages are automatically cached and available through the REST API.

## Development

### Running Tests

Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-timeout
# UI/E2E need Playwright chromium if not already installed:
# python -m playwright install chromium --with-deps
```

Run all tests (unit + UI/E2E):
```bash
pytest -v
```

Split by markers (auto-added in tests/conftest.py):
```bash
# Unit/API only
pytest -m api
# UI/E2E only
pytest -m ui
```

Run specific test:
```bash
pytest pc_client/tests/test_cache.py -v
```

### Project Structure

```
pc_client/
├── __init__.py
├── main.py              # Application entry point
├── adapters/            # REST and ZMQ adapters
│   ├── rest_adapter.py
│   └── zmq_subscriber.py
├── api/                 # FastAPI server
│   └── server.py
├── cache/              # SQLite cache manager
│   └── cache_manager.py
├── config/             # Configuration
│   └── settings.py
└── tests/              # Unit tests
    ├── test_cache.py
    ├── test_rest_adapter.py
    └── test_zmq_subscriber.py
```

## Troubleshooting

### Connection Issues

If you cannot connect to Rider-PI:
1. Verify the Rider-PI IP address with `ping <RIDER_PI_HOST>`
2. Check that ports 8080, 5555, 5556 are accessible
3. Ensure firewall rules allow connections
4. Check the logs with `LOG_LEVEL=DEBUG`

### Cache Issues

If data is not updating:
1. Check that the cache database is writable
2. Verify cache TTL settings
3. Review logs for adapter errors

### UI Not Loading

If the web interface doesn't load:
1. Verify that the `web/` directory exists
2. Check that `view.html` is present
3. Ensure static files are being served at `/web/`

## AI Provider Layer - Phase 4 ✅

The PC client includes a production-ready AI provider layer for offloading computational tasks from Rider-PI:

### Real AI Models (with automatic mock fallback)

> **Note:** wcześniejsze pliki `config/vision_provider.toml`, `voice_provider.toml`, `text_provider.toml` zostały skonsolidowane w `config/providers.toml`, zachowując te same sekcje (`[vision]`, `[voice]`, `[text]`).

- **Voice Provider**:
  - **ASR**: OpenAI Whisper (base model, ~140MB)
  - **TTS**: Piper TTS (en_US-lessac-medium)
  - Konfiguracja sekcji `[voice]` w `config/providers.toml`
  
- **Vision Provider**:
  - **Detection**: YOLOv8 nano (~6MB)
  - Real-time object detection with bounding boxes
  - Obstacle classification for navigation
  - Konfiguracja sekcji `[vision]` w `config/providers.toml`
  
- **Text Provider**:
  - **LLM**: Ollama (llama3.2:1b, ~1.3GB)
  - Local inference, no cloud dependencies
  - Response caching
  - Konfiguracja sekcji `[text]` w `config/providers.toml`

### Infrastructure Features

- **Task Queue**: Priority-based asynchronous processing (Redis)
- **Circuit Breaker**: Automatic fallback on failures
- **Telemetry**: Real-time Prometheus metrics
- **Health Probes**: `/health/live` and `/health/ready` endpoints
- **Docker Deployment**: Complete stack with monitoring

### Quick Start with Real AI Models

**Option 1: Docker (All-in-one)**
```bash
docker-compose up -d
# Models download automatically on first use
```

**Option 2: Local Setup**

1. **Enable providers** in `.env`:
```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=true
```

2. **Setup dependencies**:
```bash
# Redis (task queue)
sudo apt install redis-server
sudo systemctl start redis-server

# Ollama (optional, for Text Provider)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:1b
```

3. **Run application**:
```bash
python -m pc_client.main
# Voice and Vision models download automatically
```

**Option 3: Mock Mode (No Models)**
```bash
# Set use_mock=true in config files or:
python -m pc_client.main
# Providers automatically fall back to mock if models unavailable
```

See [AI_MODEL_SETUP.md](AI_MODEL_SETUP.md) for detailed setup instructions.

4. Access monitoring:
```bash
# View Prometheus metrics
curl http://localhost:8000/metrics

# View application health
curl http://localhost:8000/healthz
```

### Telemetry and Monitoring

The PC client includes comprehensive telemetry:

- **Prometheus Metrics**: Task processing metrics, queue size, circuit breaker state
- **ZMQ Telemetry Publisher**: Send results back to Rider-PI via ZMQ
- **Logging**: Unified log prefixes ([voice], [vision], [provider], [bridge])
- **Metrics Endpoint**: `/metrics` for Prometheus scraping

Key metrics exposed:
- `provider_tasks_processed_total` - Total tasks processed by provider
- `provider_task_duration_seconds` - Task processing duration histogram  
- `task_queue_size` - Current task queue size
- `circuit_breaker_state` - Circuit breaker state per provider
- `cache_hits_total` / `cache_misses_total` - Cache performance

### Documentation

- [Provider Implementation Guide](PR/PROVIDER_IMPLEMENTATION_GUIDE.md) - How to use and extend providers
- [Network Security Setup](PR/NETWORK_SECURITY_SETUP.md) - VPN/mTLS configuration
- [Task Queue Setup](PR/TASK_QUEUE_SETUP.md) - Redis/RabbitMQ configuration
- [Monitoring Setup](PR/MONITORING_SETUP.md) - Prometheus/Grafana setup

### Task Types

- `voice.asr` - Speech-to-text (priority: 5)
- `voice.tts` - Text-to-speech (priority: 5)
- `vision.detection` - Object detection (priority: 8)
- `vision.frame` - Frame processing for obstacle avoidance (priority: 1, critical)
- `text.generate` - LLM text generation (priority: 3)
- `text.nlu` - Natural language understanding (priority: 5)

### Testing

All provider functionality includes comprehensive tests:
```bash
# Run all tests (87 tests total)
pytest pc_client/tests/ -v

# Run only provider tests
pytest pc_client/tests/test_providers.py -v

# Run telemetry tests
pytest pc_client/tests/test_telemetry.py -v

# Run integration tests
pytest pc_client/tests/test_integration.py -v
```
## License

This project is part of the Rider-PI ecosystem.
## See Also

- [Rider-PI Repository](https://github.com/mpieniak01/Rider-Pi)
- [API Documentation](api-specs/README.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Provider Implementation Guide](PR/PROVIDER_IMPLEMENTATION_GUIDE.md)
