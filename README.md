# Rider-PC Client

PC-side client infrastructure for the Rider-PI robot, providing:
- REST API adapter for consuming Rider-PI endpoints
- ZMQ subscriber for real-time data streams  
- Local SQLite cache for buffering data
- FastAPI web server replicating the Rider-PI UI
- **AI Provider Layer** with real ML models (Voice, Vision, Text)
- **Production-ready deployment** with Docker and CI/CD

## 🎉 Phase 4 Complete: Real AI Models & Production Deployment

This project now includes:
- ✅ **Real AI Models**: Whisper ASR, Piper TTS, YOLOv8 Vision, Ollama LLM
- ✅ **Docker Deployment**: Complete stack with Redis, Prometheus, Grafana
- ✅ **CI/CD Pipeline**: Automated testing, security scanning, Docker builds
- ✅ **Health Probes**: Kubernetes-ready liveness and readiness endpoints
- ✅ **Automatic Fallback**: Mock mode when models unavailable

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

### Development Workflow

- **Python**: develop with Python 3.11 (CI target) while keeping code compatible with Rider-PI’s Python 3.9.
- **Tooling**: install lightweight dev deps and hooks:
  ```bash
  pip install -r requirements-ci.txt
  pre-commit install
  ```
- **Checks**: use the Make targets to stay aligned with CI:
  - `make lint` → `ruff check .`
  - `make format` → `ruff format .`
  - `make test` → pytest suite with async/timeouts configured like GitHub Actions.
- **CI split**: każdy `push` na `main` przechodzi przez workflow *Quick Checks* (ruff + skrócone unit testy). Pełen pipeline (`unit-tests`, `e2e-tests`, `css-ui-audit`, Copilot setup) odpalany jest w pull requestach.
- **Copilot / agent flow**: uruchom `./config/agent/run_tests.sh`, aby odtworzyć środowisko wykorzystywane przez GitHub Copilot coding agent.
  - Skrypt instaluje zależności z `config/agent/constraints.txt` i odpala pytest.
  - Szczegółowa checklista PR-ów: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
- **Rider-PI Integration**:
  - UI (`web/control.html`) now mirrors Rider-Pi, including “AI Mode” and “Provider Control” cards.
  - Backend proxies `/api/system/ai-mode` and `/api/providers/*` to Rider-Pi via the `RestAdapter`, caching results for offline development.
  - To test locally with the real device, update `.env` (`RIDER_PI_HOST`, `RIDER_PI_PORT`) and run `make start`, then open `http://localhost:8000/web/control.html`.
  - Vision offload is now wired end-to-end: set `ENABLE_PROVIDERS=true`, `ENABLE_TASK_QUEUE=true`, `ENABLE_VISION_OFFLOAD=true`, and point `TELEMETRY_ZMQ_HOST` at Rider-Pi so the PC publishes `vision.obstacle.enhanced` after processing `vision.frame.offload`.
  - Voice offload mirrors the same flow: `ENABLE_VOICE_OFFLOAD=true` lets Rider-PC consume `voice.asr.request` / `voice.tts.request`, run Whisper/Piper (or mock), and publish `voice.asr.result` / `voice.tts.chunk` back to Rider-Pi for immediate playback.
  - Text/LLM integration exposes `/providers/text/generate` plus a capability handshake (`GET /providers/capabilities`) so Rider-PI knows which domains/versions Rider-PC supports before przełączeniem.

## Documentation

📚 **[Full Documentation](docs/README.md)** - Complete documentation and guides

### Quick Links

- **[Quick Start Guide](docs/QUICKSTART.md)** - Get started quickly
- **[AI Model Configuration](docs/AI_MODEL_CONFIGURATION.md)** - Setup real AI models
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture overview
- **[Configuration Hub](docs/CONFIGURATION.md)** - Central configuration guide
- **[API Documentation](docs/api-specs/README.md)** - REST API reference
- **[Replication Notes](docs/REPLICATION_NOTES.md)** - Notes for replicating the project

### Configuration Guides

- **[AI Model Configuration](docs/AI_MODEL_CONFIGURATION.md)** - Whisper, Piper, YOLOv8, Ollama setup
- **[Security Configuration](docs/SECURITY_CONFIGURATION.md)** - WireGuard VPN, mTLS setup
- **[Task Queue Configuration](docs/TASK_QUEUE_CONFIGURATION.md)** - Redis, RabbitMQ setup
- **[Monitoring Configuration](docs/MONITORING_CONFIGURATION.md)** - Prometheus, Grafana setup

### Operations

- **[PC Offload Integration](docs/PC_OFFLOAD_INTEGRATION.md)** - Enabling AI mode / provider parity between Rider-Pi and Rider-PC
- **[Service Management](docs/SERVICE_AND_RESOURCE_MANAGEMENT.md)** - Operations, monitoring, troubleshooting
- **[Future Work](docs/FUTURE_WORK.md)** - Planned improvements and development

## License

This project is part of the Rider-PI ecosystem.

## See Also

- [Rider-PI Repository](https://github.com/mpieniak01/Rider-Pi)
