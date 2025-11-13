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

See [IMPLEMENTATION_COMPLETE_PHASE4.md](PR/IMPLEMENTATION_COMPLETE_PHASE4.md) for details.

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
```

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
```

Run tests:
```bash
pytest pc_client/tests/ -v
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

- **Voice Provider**: 
  - **ASR**: OpenAI Whisper (base model, ~140MB)
  - **TTS**: Piper TTS (en_US-lessac-medium)
  - Config: `config/voice_provider.toml`
  
- **Vision Provider**: 
  - **Detection**: YOLOv8 nano (~6MB)
  - Real-time object detection with bounding boxes
  - Obstacle classification for navigation
  - Config: `config/vision_provider.toml`
  
- **Text Provider**: 
  - **LLM**: Ollama (llama3.2:1b, ~1.3GB)
  - Local inference, no cloud dependencies
  - Response caching
  - Config: `config/text_provider.toml`

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
- [API Documentation](../api-specs/README.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Provider Implementation Guide](PR/PROVIDER_IMPLEMENTATION_GUIDE.md)