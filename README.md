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

## Documentation

📚 **[Full Documentation](docs/README.md)** - Complete documentation and guides

### Quick Links

- **[Quick Start Guide](docs/QUICKSTART.md)** - Get started quickly
- **[AI Model Setup](docs/AI_MODEL_SETUP.md)** - Setup real AI models
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture overview
- **[API Documentation](api-specs/README.md)** - REST API reference
- **[Replication Notes](docs/REPLICATION_NOTES.md)** - Notes for replicating the project

### Implementation Guides

- **[Provider Implementation Guide](docs/PR/PROVIDER_IMPLEMENTATION_GUIDE.md)** - How to use and extend AI providers
- **[Task Queue Setup](docs/PR/TASK_QUEUE_SETUP.md)** - Redis/RabbitMQ configuration
- **[Monitoring Setup](docs/PR/MONITORING_SETUP.md)** - Prometheus/Grafana setup
- **[Network Security Setup](docs/PR/NETWORK_SECURITY_SETUP.md)** - VPN/mTLS configuration

## License

This project is part of the Rider-PI ecosystem.

## See Also

- [Rider-PI Repository](https://github.com/mpieniak01/Rider-Pi)
