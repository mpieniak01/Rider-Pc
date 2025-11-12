# Rider-PC Client

PC-side client infrastructure for the Rider-PI robot, providing:
- REST API adapter for consuming Rider-PI endpoints
- ZMQ subscriber for real-time data streams  
- Local SQLite cache for buffering data
- FastAPI web server replicating the Rider-PI UI

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

## AI Provider Layer (NEW)

The PC client now includes an AI provider layer for offloading computational tasks from Rider-PI:

### Features

- **Voice Provider**: ASR (speech-to-text) and TTS (text-to-speech) offload
- **Vision Provider**: Object detection and frame processing for obstacle avoidance
- **Text Provider**: LLM text generation and NLU with caching
- **Task Queue**: Priority-based asynchronous task processing (Redis/RabbitMQ)
- **Circuit Breaker**: Automatic fallback to local processing on failures
- **Telemetry**: Real-time metrics and performance monitoring

### Quick Start with Providers

1. Enable providers in `.env`:
```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
```

2. Setup Redis (task queue broker):
```bash
sudo apt install redis-server
sudo systemctl start redis-server
```

3. Run with providers:
```bash
python -m pc_client.main
```

### Documentation

- [Provider Implementation Guide](PROVIDER_IMPLEMENTATION_GUIDE.md) - How to use and extend providers
- [Network Security Setup](NETWORK_SECURITY_SETUP.md) - VPN/mTLS configuration
- [Task Queue Setup](TASK_QUEUE_SETUP.md) - Redis/RabbitMQ configuration
- [Monitoring Setup](MONITORING_SETUP.md) - Prometheus/Grafana setup

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
# Run all tests (73 tests total)
pytest pc_client/tests/ -v

# Run only provider tests
pytest pc_client/tests/test_providers.py -v

# Run integration tests
pytest pc_client/tests/test_integration.py -v
```

## License

This project is part of the Rider-PI ecosystem.

## See Also

- [Rider-PI Repository](https://github.com/mpieniak01/Rider-Pi)
- [API Documentation](api-specs/README.md)
- [Architecture Overview](pc_client_architecture.md)
- [Provider Implementation Guide](PROVIDER_IMPLEMENTATION_GUIDE.md)