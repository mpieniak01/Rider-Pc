# Complete Integration Guide: AI Providers, Task Queue, and Telemetry

This guide provides step-by-step instructions for setting up the complete AI provider infrastructure with task queue and telemetry.

## Prerequisites

- Python 3.9+
- WSL2 (Windows) or Linux environment
- Network access to Rider-PI device
- At least 4GB available RAM
- 10GB available disk space

## Step 1: Install Dependencies

```bash
cd Rider-Pc
pip install -r requirements.txt
```

This installs:
- FastAPI and Uvicorn (web server)
- Redis client (task queue)
- PyZMQ (messaging)
- Prometheus client (metrics)
- Testing tools (pytest)

## Step 2: Setup Redis Task Queue

Redis serves as the persistent task queue broker.

### Install Redis

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install redis-server

# Verify installation
redis-server --version
```

### Configure Redis

Edit `/etc/redis/redis.conf`:

```ini
# Bind to localhost and VPN (if using)
bind 127.0.0.1 10.0.0.2

# Enable persistence
save 900 1
save 300 10
save 60 10000

# Set memory limit
maxmemory 256mb
maxmemory-policy allkeys-lru

# Enable AOF for durability
appendonly yes
```

### Start Redis

```bash
# Start service
sudo systemctl start redis-server

# Enable on boot
sudo systemctl enable redis-server

# Verify it's running
redis-cli ping
# Should return: PONG
```

## Step 3: Configure Environment

Create `.env` file from example:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Rider-PI Connection (use VPN address if configured)
RIDER_PI_HOST=10.0.0.1
RIDER_PI_PORT=8080

# ZMQ Ports
ZMQ_PUB_PORT=5555
ZMQ_SUB_PORT=5556

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Cache
CACHE_DB_PATH=data/cache.db
CACHE_TTL_SECONDS=30

# Logging
LOG_LEVEL=INFO

# Enable AI Providers
ENABLE_PROVIDERS=true
VOICE_MODEL=mock
VISION_MODEL=mock
TEXT_MODEL=mock

# Enable Task Queue
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
TASK_QUEUE_HOST=localhost
TASK_QUEUE_PORT=6379
TASK_QUEUE_PASSWORD=
TASK_QUEUE_MAX_SIZE=100

# Enable Telemetry
ENABLE_TELEMETRY=true
TELEMETRY_ZMQ_HOST=0.0.0.0
TELEMETRY_ZMQ_PORT=5557
```

## Step 4: Network Security (Optional but Recommended)

For production deployments, secure the connection between PC and Rider-PI.

### Option A: WireGuard VPN

See [NETWORK_SECURITY_SETUP.md](NETWORK_SECURITY_SETUP.md) for complete WireGuard setup.

Quick setup:

```bash
# Install WireGuard
sudo apt install wireguard

# Generate keys
wg genkey | tee privatekey | wg pubkey > publickey

# Configure /etc/wireguard/wg0.conf
# Start VPN
sudo wg-quick up wg0
```

Update `.env`:
```bash
RIDER_PI_HOST=10.0.0.1  # VPN address
```

### Option B: mTLS

For environments where VPN is not feasible, use mutual TLS authentication.

See [NETWORK_SECURITY_SETUP.md](NETWORK_SECURITY_SETUP.md) for certificate generation and setup.

## Step 5: Setup Monitoring (Optional but Recommended)

### Install Prometheus

```bash
# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xvfz prometheus-2.48.0.linux-amd64.tar.gz
sudo mv prometheus-2.48.0.linux-amd64 /opt/prometheus

# Create configuration
sudo mkdir -p /etc/prometheus
sudo tee /etc/prometheus/prometheus.yml > /dev/null <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'rider_pc'
    static_configs:
      - targets: ['localhost:8000']
EOF

# Create systemd service
sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/opt/prometheus/prometheus --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/var/lib/prometheus/data
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create user and directories
sudo useradd -rs /bin/false prometheus
sudo mkdir -p /var/lib/prometheus/data
sudo chown -R prometheus:prometheus /var/lib/prometheus

# Start Prometheus
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
```

Access Prometheus at: `http://localhost:9090`

### Install Node Exporter (System Metrics)

```bash
cd /tmp
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar xvfz node_exporter-1.7.0.linux-amd64.tar.gz
sudo mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/

# Create systemd service
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
User=node_exporter
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

sudo useradd -rs /bin/false node_exporter
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
```

## Step 6: Run the PC Client

Start the PC client:

```bash
python -m pc_client.main
```

You should see output like:

```
2025-11-12 13:28:36 [INFO] Rider-PC Client Starting
2025-11-12 13:28:36 [INFO] Rider-PI Host: 10.0.0.1:8080
2025-11-12 13:28:36 [INFO] Server: 0.0.0.0:8000
2025-11-12 13:28:36 [INFO] Cache manager initialized
2025-11-12 13:28:36 [INFO] FastAPI application created
2025-11-12 13:28:36 [INFO] Starting server on 0.0.0.0:8000
```

## Step 7: Verify Setup

### Check Health

```bash
curl http://localhost:8000/healthz
```

### Check Metrics

```bash
curl http://localhost:8000/metrics
```

Should show Prometheus metrics including:
- `provider_tasks_processed_total`
- `provider_task_duration_seconds`
- `task_queue_size`
- `circuit_breaker_state`

### Check Redis Queue

```bash
redis-cli info stats
redis-cli llen task_queue:priority_medium
```

### Test Provider

Create a test task:

```python
import asyncio
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskEnvelope, TaskType

async def test():
    provider = VoiceProvider()
    await provider.initialize()
    
    task = TaskEnvelope(
        task_id="test-1",
        task_type=TaskType.VOICE_ASR,
        payload={
            "audio_data": "base64_audio",
            "format": "wav",
            "sample_rate": 16000
        }
    )
    
    result = await provider.process_task(task)
    print(f"Result: {result.to_dict()}")
    
    await provider.shutdown()

asyncio.run(test())
```

## Step 8: Integrate with Rider-PI

On Rider-PI, configure offload endpoints:

```python
# In Rider-PI apps/voice or apps/vision
import requests

def offload_task_to_pc(task_data):
    """Send task to PC for processing."""
    response = requests.post(
        "http://10.0.0.2:8000/api/task/offload",
        json=task_data,
        timeout=5
    )
    return response.json()
```

Subscribe to telemetry results:

```python
import zmq

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://10.0.0.2:5557")
socket.setsockopt_string(zmq.SUBSCRIBE, "telemetry.task.completed")

while True:
    topic, data = socket.recv_multipart()
    print(f"Received: {topic} - {data}")
```

## Testing

Run comprehensive tests:

```bash
# All tests
pytest pc_client/tests/ -v

# Provider tests only
pytest pc_client/tests/test_providers.py -v

# Telemetry tests
pytest pc_client/tests/test_telemetry.py -v

# Integration tests (requires Redis running)
pytest pc_client/tests/test_integration.py -v
```

## Troubleshooting

### Redis Connection Issues

```bash
# Check if Redis is running
sudo systemctl status redis-server

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Test connection
redis-cli ping
```

### ZMQ Issues

```bash
# Check if ports are in use
netstat -tulpn | grep 5557

# Test ZMQ binding
python -c "import zmq; ctx = zmq.Context(); s = ctx.socket(zmq.PUB); s.bind('tcp://0.0.0.0:5557'); print('OK')"
```

### Provider Initialization Errors

Check logs for detailed error messages:

```bash
# Run with DEBUG logging
LOG_LEVEL=DEBUG python -m pc_client.main
```

### Memory Issues

If running out of memory:

1. Reduce task queue size in `.env`:
   ```bash
   TASK_QUEUE_MAX_SIZE=50
   ```

2. Configure Redis memory limit:
   ```ini
   # /etc/redis/redis.conf
   maxmemory 128mb
   ```

## Performance Tuning

### Redis

```ini
# /etc/redis/redis.conf

# Disable slow operations
slowlog-log-slower-than 10000

# Use pipelining
tcp-keepalive 300

# Tune for low latency
hz 100
```

### Task Queue

Adjust queue priorities in `.env` based on your workload:

```bash
# For vision-heavy workloads
TASK_QUEUE_MAX_SIZE=200

# For low-latency requirements
TASK_QUEUE_BACKEND=redis  # Lower latency than RabbitMQ
```

### System Resources

Monitor with:

```bash
# System resources
htop

# Redis metrics
redis-cli --stat

# Prometheus metrics
curl http://localhost:8000/metrics | grep provider_task_duration
```

## Next Steps

1. **Setup Grafana**: Visualize metrics with dashboards (see [MONITORING_SETUP.md](MONITORING_SETUP.md))

2. **Configure Alerting**: Setup Prometheus Alertmanager for notifications

3. **Scale Workers**: Run multiple worker processes for higher throughput

4. **Deploy AI Models**: Replace mock implementations with real models:
   - Whisper for ASR
   - Coqui TTS for speech synthesis
   - YOLOv8 for object detection
   - Local LLM for text generation

5. **Production Hardening**:
   - Enable authentication
   - Setup SSL/TLS
   - Configure firewall rules
   - Enable log rotation
   - Setup backup procedures

## References

- [Provider Implementation Guide](PROVIDER_IMPLEMENTATION_GUIDE.md)
- [Network Security Setup](NETWORK_SECURITY_SETUP.md)
- [Task Queue Setup](TASK_QUEUE_SETUP.md)
- [Monitoring Setup](MONITORING_SETUP.md)
- [Redis Documentation](https://redis.io/documentation)
- [Prometheus Documentation](https://prometheus.io/docs/)
