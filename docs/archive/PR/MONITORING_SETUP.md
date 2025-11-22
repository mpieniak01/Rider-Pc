# Monitoring and Telemetry Setup Guide

## Overview

This document describes the monitoring, logging, and telemetry setup for the Rider-PC client and AI providers.

## Logging Standards

### Log Prefixes

All logs must use standardized prefixes for easy filtering:

- `[api]` - FastAPI server logs
- `[bridge]` - ZMQ bridge and adapters
- `[vision]` - Vision provider logs
- `[voice]` - Voice provider logs
- `[provider]` - Generic provider logs (text, etc.)

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for non-critical issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

### Log Format

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
```

Example logs:
```
2025-11-12 12:00:00 [INFO] [api] Server started on 0.0.0.0:8000
2025-11-12 12:00:01 [INFO] [bridge] ZMQ subscriber connected to tcp://10.0.0.1:5555
2025-11-12 12:00:02 [INFO] [vision] Vision models loaded (mock implementation)
2025-11-12 12:00:03 [INFO] [voice] Processing ASR task task-123
2025-11-12 12:00:04 [INFO] [provider] Text models loaded
```

### Log Rotation

Configure log rotation with `logrotate`:

Create `/etc/logrotate.d/rider-pc`:
```
/var/log/rider-pc/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 rider-pc rider-pc
    sharedscripts
    postrotate
        systemctl reload rider-pc || true
    endscript
}
```

## Prometheus Metrics

### Node Exporter Setup

Install Prometheus Node Exporter for system metrics:

```bash
# Download Node Exporter
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

# Create user
sudo useradd -rs /bin/false node_exporter

# Start service
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
```

Node Exporter metrics available at: `http://localhost:9100/metrics`

### FastAPI Metrics

Add Prometheus metrics to FastAPI:

```bash
pip install prometheus-fastapi-instrumentator
```

Update `pc_client/api/server.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator

def create_app(settings: Settings, cache: CacheManager) -> FastAPI:
    app = FastAPI(...)
    
    # Add Prometheus instrumentation
    Instrumentator().instrument(app).expose(app)
    
    return app
```

Metrics available at: `http://localhost:8000/metrics`

### Custom Provider Metrics

Add custom metrics for providers:

```python
from prometheus_client import Counter, Histogram, Gauge

# Task metrics
tasks_processed = Counter(
    'provider_tasks_processed_total',
    'Total tasks processed',
    ['provider', 'task_type', 'status']
)

task_duration = Histogram(
    'provider_task_duration_seconds',
    'Task processing duration',
    ['provider', 'task_type']
)

queue_size = Gauge(
    'task_queue_size',
    'Current task queue size',
    ['queue_name']
)

# Usage in provider
tasks_processed.labels(
    provider='VoiceProvider',
    task_type='voice.asr',
    status='completed'
).inc()

task_duration.labels(
    provider='VoiceProvider',
    task_type='voice.asr'
).observe(processing_time_ms / 1000.0)
```

## Prometheus Configuration

### Install Prometheus

```bash
# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xvfz prometheus-2.48.0.linux-amd64.tar.gz
sudo mv prometheus-2.48.0.linux-amd64 /opt/prometheus

# Create config
sudo mkdir -p /etc/prometheus
sudo tee /etc/prometheus/prometheus.yml > /dev/null <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Node Exporter
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
  
  # FastAPI
  - job_name: 'rider_pc_api'
    static_configs:
      - targets: ['localhost:8000']
  
  # Redis (if using redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
  
  # RabbitMQ
  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['localhost:15692']
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

# Start service
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
```

Prometheus UI available at: `http://localhost:9090`

## Grafana Dashboards

### Install Grafana

```bash
# Add Grafana repository
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Install Grafana
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

Grafana UI available at: `http://localhost:3000` (default: admin/admin)

### Configure Data Source

1. Login to Grafana
2. Go to Configuration > Data Sources
3. Add Prometheus data source:
   - URL: `http://localhost:9090`
   - Access: Server (default)
   - Click "Save & Test"

### Import Dashboards

#### System Dashboard (Node Exporter)

1. Go to Dashboards > Import
2. Enter dashboard ID: `1860` (Node Exporter Full)
3. Select Prometheus data source
4. Click Import

#### Custom Rider-PC Dashboard

Create a custom dashboard with panels:

**Panel 1: Task Queue Size**
```promql
task_queue_size
```

**Panel 2: Tasks Processed (Rate)**
```promql
rate(provider_tasks_processed_total[5m])
```

**Panel 3: Task Duration (p95)**
```promql
histogram_quantile(0.95, rate(provider_task_duration_seconds_bucket[5m]))
```

**Panel 4: Provider Status**
```promql
provider_tasks_processed_total{status="completed"}
provider_tasks_processed_total{status="failed"}
```

**Panel 5: CPU Usage**
```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

**Panel 6: Memory Usage**
```promql
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes
```

**Panel 7: Request Latency (API)**
```promql
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

### Export Dashboard

Save dashboard JSON to `config/grafana-dashboard.json` for version control.

## Alerting

### Prometheus Alerting Rules

Create `/etc/prometheus/alerts.yml`:
```yaml
groups:
  - name: rider_pc_alerts
    interval: 30s
    rules:
      # Queue is full
      - alert: TaskQueueFull
        expr: task_queue_size >= 95
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Task queue is nearly full"
          description: "Queue size: {{ $value }}"
      
      # High failure rate
      - alert: HighTaskFailureRate
        expr: rate(provider_tasks_processed_total{status="failed"}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High task failure rate detected"
          description: "Failure rate: {{ $value }}/s"
      
      # Provider down
      - alert: ProviderDown
        expr: up{job="rider_pc_api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Rider-PC API is down"
          description: "API has been down for 1 minute"
      
      # High latency
      - alert: HighTaskLatency
        expr: histogram_quantile(0.95, rate(provider_task_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task processing latency"
          description: "P95 latency: {{ $value }}s"
      
      # Disk space low
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space"
          description: "Only {{ $value | humanizePercentage }} free"
```

Update Prometheus config to include alerts:
```yaml
# /etc/prometheus/prometheus.yml
rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

### Alertmanager Setup

```bash
# Download Alertmanager
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xvfz alertmanager-0.26.0.linux-amd64.tar.gz
sudo mv alertmanager-0.26.0.linux-amd64 /opt/alertmanager

# Create config
sudo mkdir -p /etc/alertmanager
sudo tee /etc/alertmanager/alertmanager.yml > /dev/null <<EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'email'

receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alertmanager@example.com'
        auth_password: 'password'
EOF

# Create systemd service
sudo tee /etc/systemd/system/alertmanager.service > /dev/null <<EOF
[Unit]
Description=Alertmanager
After=network.target

[Service]
Type=simple
User=alertmanager
ExecStart=/opt/alertmanager/alertmanager --config.file=/etc/alertmanager/alertmanager.yml --storage.path=/var/lib/alertmanager/data
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create user and directories
sudo useradd -rs /bin/false alertmanager
sudo mkdir -p /var/lib/alertmanager/data
sudo chown -R alertmanager:alertmanager /var/lib/alertmanager

# Start service
sudo systemctl daemon-reload
sudo systemctl start alertmanager
sudo systemctl enable alertmanager
```

## ZMQ Telemetry Publishing

Providers publish telemetry to ZMQ bus:

```python
import zmq
import json

class TelemetryPublisher:
    def __init__(self, endpoint: str):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(endpoint)
    
    def publish(self, topic: str, data: dict):
        message = [
            topic.encode('utf-8'),
            json.dumps(data).encode('utf-8')
        ]
        self.socket.send_multipart(message)
    
    def publish_task_result(self, result: TaskResult):
        self.publish(
            'telemetry.task.completed',
            {
                'task_id': result.task_id,
                'status': result.status.value,
                'processing_time_ms': result.processing_time_ms,
                'timestamp': time.time()
            }
        )
```

## Log Analysis

### Structured Logging

Use structured logging for easier parsing:

```python
import logging
import json

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, **kwargs):
        log_data = {'message': message, **kwargs}
        self.logger.info(json.dumps(log_data))
```

Example:
```python
logger = StructuredLogger('[provider] VoiceProvider')
logger.info('Task completed', task_id='task-123', duration_ms=150)
```

Output:
```json
{"message": "Task completed", "task_id": "task-123", "duration_ms": 150}
```

### Log Aggregation with Loki

For centralized logging:

```bash
# Install Loki
wget https://github.com/grafana/loki/releases/download/v2.9.3/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
sudo mv loki-linux-amd64 /usr/local/bin/loki

# Install Promtail (log shipper)
wget https://github.com/grafana/loki/releases/download/v2.9.3/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip
sudo mv promtail-linux-amd64 /usr/local/bin/promtail
```

Configure in Grafana:
1. Add Loki data source
2. Create log queries: `{job="rider-pc"} |= "[vision]"`

## Health Checks

Add health check endpoints:

```python
@app.get("/health/live")
async def liveness():
    """Liveness probe."""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """Readiness probe."""
    checks = {
        "cache": cache.is_healthy(),
        "providers": all_providers_initialized(),
        "queue": task_queue.is_healthy()
    }
    
    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks}
        )
```

## Performance Monitoring

### Key Metrics to Monitor

1. **Task Queue**
   - Queue size
   - Task throughput (tasks/sec)
   - Task latency (p50, p95, p99)
   - Queue full events

2. **Providers**
   - Task success rate
   - Processing time
   - Model load time
   - Error rate

3. **System Resources**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O

4. **API**
   - Request rate
   - Response time
   - Error rate (4xx, 5xx)

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Node Exporter](https://github.com/prometheus/node_exporter)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
