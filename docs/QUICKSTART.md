# Rider-PC Quick Start

## Option 1: Docker (Recommended)

If no local `.env` exists, create it from the public template and set your
own addresses and provider options. Preserve any existing `.env`.
Review [configuration](CONFIGURATION.md) before starting the stack:

```bash
docker compose up -d
```

The stack can start models and supporting services. Review its configuration
and published ports before use. For an existing WSL environment use the local
command below, which avoids reinstalling dependencies through the stack launcher.

## Option 2: Local Development

```bash
.venv/bin/python --version
.venv/bin/python -m pip check
```

Keep the existing `.env`. Do not reinstall the full ML stack just to inspect the environment. Test scopes and commands are in the [development guide](development.md).

## Starting for validation

After reviewing configuration:

```bash
.venv/bin/python -m pc_client.main
```

This loads `.env` and configured providers. With `SERVER_PORT=8000`, open `http://localhost:8000/`. The direct command uses SERVER_PORT. `make start` uses PANEL_PORT when set, otherwise SERVER_PORT or 8000. It may install dependencies; review the launcher before use.

Once the robot is connected, verify its address, API port 8080 and `PC_PUBLIC_BASE_URL`, which must use the actual PC address/port reachable from Pi. Cached or mocked data do not establish device health.

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
| `PC_PUBLIC_BASE_URL` | _(unset)_ | URL Rider-Pi uses to reach this PC (`http://<pc_ip>:<panel_port>`) |
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
└── tests/                  # Tests
    ├── __init__.py
    ├── conftest.py         # auto-tagging of api/ui markers
    ├── e2e/                # Playwright UI/E2E tests
    └── ...                 # pc_client unit/integration tests
```

## Support

For issues or questions:
- Check the main [README.md](README.md)
- Review [ARCHITECTURE.md](ARCHITECTURE.md)
- See API specs in [api-specs/](api-specs/)
