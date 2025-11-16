# Quick Start Guide - Rider-PC Client

## Overview
The Rider-PC Client is now operational with the following components:
- ✅ REST API Adapter for consuming Rider-PI endpoints  
- ✅ ZMQ Subscriber for real-time data streams
- ✅ SQLite Cache for buffering data
- ✅ FastAPI Web Server replicating Rider-PI UI
- ✅ Comprehensive unit tests (25 tests passing)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Connection
Set environment variables to point to your Rider-PI device:

```bash
export RIDER_PI_HOST="192.168.1.100"  # Replace with your Rider-PI IP
export RIDER_PI_PORT="8080"
export ZMQ_PUB_PORT="5555"
```

### 3. Run the Server
```bash
./run.sh
```

Or with Python directly:
```bash
PYTHONPATH=. python -m pc_client.main
```

### 4. Access the UI
Open your browser to: `http://localhost:8000/`

## Architecture

```
┌─────────────────────────────────────────────┐
│           Rider-PI Device                    │
│  ┌────────────┐      ┌────────────┐        │
│  │ REST API   │      │ ZMQ PUB    │        │
│  │ :8080      │      │ :5555      │        │
│  └────────────┘      └────────────┘        │
└─────────────────────────────────────────────┘
         │                    │
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────────┐
│         PC Client (WSL/Linux)                │
│  ┌────────────────────────────────────┐     │
│  │  Adapter Layer                     │     │
│  │  • REST Client (httpx)             │     │
│  │  • ZMQ Subscriber (pyzmq)          │     │
│  └────────────────────────────────────┘     │
│                  │                           │
│                  ▼                           │
│  ┌────────────────────────────────────┐     │
│  │  Cache Layer (SQLite)              │     │
│  │  • Stores current states           │     │
│  │  • TTL-based expiration            │     │
│  └────────────────────────────────────┘     │
│                  │                           │
│                  ▼                           │
│  ┌────────────────────────────────────┐     │
│  │  Web Server (FastAPI)              │     │
│  │  • Serves static files             │     │
│  │  • Provides API endpoints          │     │
│  │  • Auto-refresh data every 2s      │     │
│  └────────────────────────────────────┘     │
│                  │                           │
└─────────────────────────────────────────────┘
                   │
                   ▼
          Browser (localhost:8000)

```

## Data Flow

1. **REST Sync (every 2s)**:
   - Background task fetches data from Rider-PI REST API
   - Data is cached in SQLite with 30s TTL
   - API endpoints serve cached data

2. **ZMQ Real-time**:
   - Subscriber connects to Rider-PI ZMQ publisher
   - Listens for topics: `vision.*`, `motion.*`, `robot.*`, `navigator.*`
   - Messages are automatically cached

3. **Web UI**:
   - Frontend polls API endpoints every 2s
   - Displays cached data from PC client
   - No direct connection to Rider-PI needed

## API Endpoints

All endpoints replicate Rider-PI REST API:

- `GET /` - Serves view.html dashboard
- `GET /healthz` - Health status
- `GET /state` - Current state
- `GET /sysinfo` - System information
- `GET /vision/snap-info` - Vision snapshot info
- `GET /vision/obstacle` - Obstacle detection data
- `GET /api/app-metrics` - Application metrics
- `GET /api/resource/camera` - Camera resource status
- `GET /api/bus/health` - Message bus health
- `GET /camera/placeholder` - Placeholder image

## Configuration Options

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RIDER_PI_HOST` | `localhost` | Rider-PI IP address |
| `RIDER_PI_PORT` | `8080` | REST API port |
| `ZMQ_PUB_PORT` | `5555` | ZMQ publisher port |
| `ZMQ_SUB_PORT` | `5556` | ZMQ subscriber port |
| `SERVER_HOST` | `0.0.0.0` | PC client server host |
| `SERVER_PORT` | `8000` | PC client server port |
| `CACHE_DB_PATH` | `data/cache.db` | SQLite database path |
| `CACHE_TTL_SECONDS` | `30` | Cache TTL in seconds |
| `LOG_LEVEL` | `INFO` | Logging level |

## Testing

Run unit tests:
```bash
pytest pc_client/tests/ -v
```

Test coverage:
- ✅ Cache operations (set, get, expire, cleanup)
- ✅ REST adapter (all endpoints)
- ✅ ZMQ subscriber (topic matching, handlers)

## Troubleshooting

### Connection Errors
If you see "All connection attempts failed" errors:
1. Verify Rider-PI is running and accessible
2. Check firewall rules on both PC and Rider-PI
3. Test connectivity: `ping <RIDER_PI_HOST>`
4. Test REST API: `curl http://<RIDER_PI_HOST>:8080/healthz`

### ZMQ Connection Issues
If ZMQ subscriber doesn't receive messages:
1. Verify ZMQ ports are open: 5555, 5556
2. Check Rider-PI ZMQ broker is running
3. Ensure topics are being published on Rider-PI

### UI Not Loading
If view.html doesn't render:
1. Check that `web/` directory exists
2. Verify static files are served at `/web/`
3. Check browser console for errors

## Next Steps

Future enhancements planned:
- [ ] Voice Provider (ASR/TTS offload to PC)
- [ ] Vision Provider (image processing on PC GPU)
- [ ] Text Provider (NLU/NLG with local models)
- [ ] Task Queue (RabbitMQ/Redis + Celery)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Docker containerization
- [ ] Secure VPN tunnel (WireGuard)

## Files Structure

```
pc_client/
├── __init__.py              # Package initialization
├── main.py                  # Application entry point
├── adapters/               # Data adapters
│   ├── __init__.py
│   ├── rest_adapter.py     # REST API client
│   └── zmq_subscriber.py   # ZMQ subscriber
├── api/                    # FastAPI server
│   ├── __init__.py
│   └── server.py           # Server implementation
├── cache/                  # Cache layer
│   ├── __init__.py
│   └── cache_manager.py    # SQLite cache
├── config/                 # Configuration
│   ├── __init__.py
│   └── settings.py         # Settings management
└── tests/                  # Unit tests
    ├── __init__.py
    ├── test_cache.py
    ├── test_rest_adapter.py
    └── test_zmq_subscriber.py
```

## Support

For issues or questions:
- Check the main [README.md](README.md)
- Review [ARCHITECTURE.md](ARCHITECTURE.md)
- See API specs in [api-specs/](api-specs/)
