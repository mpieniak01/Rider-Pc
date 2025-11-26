# Rider-PC Configuration

Central hub for Rider-PC Client configuration documentation.

## Overview

Rider-PC requires configuration in several areas, depending on the features used and deployment environment. This document serves as a guide to all configuration aspects.

## Basic Configuration

### Environment Variables

Basic configuration variables are in the `.env` file:

```bash
# Rider-PI connection
RIDER_PI_HOST=192.168.1.100
RIDER_PI_PORT=8080

# ZMQ configuration
ZMQ_PUB_PORT=5555
ZMQ_SUB_PORT=5556

# Local server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Cache
CACHE_DB_PATH=data/cache.db
CACHE_TTL_SECONDS=30

# Logging
LOG_LEVEL=INFO
```

### Run Modes

- **Docker Mode**: Recommended for production - see [QUICKSTART.md](QUICKSTART.md#option-1-docker-recommended)
- **Local Mode**: For development - see [QUICKSTART.md](QUICKSTART.md#option-2-local-development)

## Configuration Guides

### 1. AI Models

**Document**: [AI_MODEL_CONFIGURATION.md](AI_MODEL_CONFIGURATION.md)

Configuration of three AI provider domains:
- **Voice Provider**: Whisper (ASR) + Piper (TTS)
- **Vision Provider**: YOLOv8 for object detection
- **Text Provider**: Ollama (LLM) for text generation

Includes:
- Model installation (automatic vs. manual)
- Model variant selection (tiny/base/small/medium/large)
- Mock mode configuration for testing
- Performance and memory optimization

### 2. Network Security

**Document**: [SECURITY_CONFIGURATION.md](SECURITY_CONFIGURATION.md)

Secure communication channels between Rider-PI and PC:
- **Development Mode**: Unencrypted connection for local network
- **WireGuard VPN**: Recommended for production - modern, lightweight protocol
- **Mutual TLS (mTLS)**: For environments requiring mutual authentication

Includes:
- WireGuard installation and configuration
- mTLS certificate generation
- Firewall configuration
- Automatic startup and monitoring

### 3. Task Queue

**Document**: [TASK_QUEUE_CONFIGURATION.md](TASK_QUEUE_CONFIGURATION.md)

Task queue broker configuration for asynchronous processing:
- **Redis**: Recommended for development - simple, fast
- **RabbitMQ**: Recommended for production - advanced features

Includes:
- Redis/RabbitMQ installation and configuration
- Priority queues (1-10)
- Persistence and reliability
- Performance optimization
- Backup and recovery

Priority mapping:
- Priority 1-2: Critical (obstacle avoidance)
- Priority 3-4: High (control)
- Priority 5-6: Normal (ASR/TTS)
- Priority 7-8: Low (text generation)
- Priority 9-10: Background (logging)

### 4. Monitoring

**Document**: [MONITORING_CONFIGURATION.md](MONITORING_CONFIGURATION.md)

Comprehensive monitoring with Prometheus and Grafana:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Node Exporter**: System metrics
- **Alertmanager**: Alert management

Includes:
- Monitoring stack installation
- Alert rules configuration
- Key metrics to monitor
- Ready-made Grafana dashboards
- Troubleshooting

Key alerts:
- High task queue length
- Circuit breaker open
- Low processing rate
- High memory usage
- High task failure rate

## Configuration Files

### Directory Structure

```
config/
├── providers.toml          # AI provider configuration (voice, vision, text)
├── .env                    # Environment variables
└── grafana-dashboard.json  # Grafana dashboard

.env.example               # Example configuration
```

### providers.toml File

Centralized configuration of all AI providers:

```toml
[voice]
asr_model = "base"
tts_model = "en_US-lessac-medium"
sample_rate = 16000
use_mock = false

[vision]
detection_model = "yolov8n"
confidence_threshold = 0.5
max_detections = 10
use_mock = false

[text]
model = "llama3.2:1b"
max_tokens = 512
temperature = 0.7
ollama_host = "http://localhost:11434"
use_mock = false
enable_cache = true
```

## Configuration Scenarios

### Development (Local environment)

```bash
# Minimal setup for development
ENABLE_PROVIDERS=false       # Use mock mode
SECURE_MODE=false            # No encryption on local network
ENABLE_TASK_QUEUE=false      # Synchronous processing
ENABLE_TELEMETRY=false       # Disable telemetry
LOG_LEVEL=DEBUG              # Detailed logs
```

### Production (Docker Compose)

```bash
# Full functionality
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=true
ENABLE_VISION_OFFLOAD=true
ENABLE_VOICE_OFFLOAD=true
ENABLE_TEXT_OFFLOAD=true
SECURE_MODE=true             # WireGuard VPN
LOG_LEVEL=INFO
```

### Testing (CI/CD)

```bash
# Minimal dependencies
ENABLE_PROVIDERS=true
use_mock=true                # In providers.toml
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=false
LOG_LEVEL=WARNING
```

## Ports and Services

| Service | Port | Type | Description |
|---------|------|------|-------------|
| **Rider-PC UI** | 8000 | Local | FastAPI Web UI |
| **Rider-Pi API** | 8080 | Remote | Robot REST API |
| **ZMQ PUB** | 5555 | Remote | Event publication from Pi |
| **ZMQ SUB** | 5556 | Remote | Response subscription |
| **ZMQ Telemetry** | 5557 | Local | Result publication from PC |
| **Redis** | 6379 | Local | Task queue broker |
| **Prometheus** | 9090 | Local | Metrics |
| **Grafana** | 3000 | Local | Dashboards |
| **Ollama** | 11434 | Local | LLM API |

## Troubleshooting

### Connection Issues

1. Check environment variables (`RIDER_PI_HOST`, `RIDER_PI_PORT`)
2. Verify network availability: `ping $RIDER_PI_HOST`
3. Test REST API: `curl http://$RIDER_PI_HOST:8080/healthz`
4. Check ZMQ ports: `ss -tulnp | grep 5555`
5. View logs: `LOG_LEVEL=DEBUG python -m pc_client.main`

### Provider Issues

1. Check if models are installed
2. Verify configuration in `config/providers.toml`
3. Test in mock mode: `use_mock = true`
4. Check provider logs: `grep "\[provider\]" logs/panel-*.log`
5. Monitor metrics: `curl http://localhost:8000/metrics | grep provider`

### Queue Issues

1. Check if Redis is running: `redis-cli ping`
2. Monitor queue length: `redis-cli LLEN task_queue:priority:5`
3. View tasks in queue: `redis-cli KEYS "task_queue:*"`
4. Check workers: `grep "\[worker\]" logs/panel-*.log`

## Further Information

- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Offload Integration**: [PC_OFFLOAD_INTEGRATION.md](PC_OFFLOAD_INTEGRATION.md)
- **Service Management**: [SERVICE_AND_RESOURCE_MANAGEMENT.md](SERVICE_AND_RESOURCE_MANAGEMENT.md)

## Local System Service Management

### Overview

Rider-PC can manage local systemd services on Linux systems. This enables the dashboard to start, stop, and restart system services like `rider-task-queue.service` or `rider-voice.service`.

### Configuration

To enable real systemd service management, set the following environment variables:

```bash
# Comma-separated list of systemd units to monitor and control
MONITORED_SERVICES=rider-pc.service,rider-voice.service,rider-task-queue.service

# Whether to use sudo for systemctl commands (default: true)
# Set to false if Rider-PC runs as root
SYSTEMD_USE_SUDO=true
```

### Sudoers Configuration

Since systemd operations require elevated privileges, you need to configure passwordless sudo access for the user running Rider-PC. This allows the application to execute `systemctl` commands without prompting for a password.

1. Create a sudoers file for Rider-PC:

```bash
sudo visudo -f /etc/sudoers.d/rider-pc
```

2. Add the following rules (replace `rider` with the username running Rider-PC):

> **Note**: These rules use `/usr/bin/systemctl`. On your system, verify the systemctl location with `which systemctl` and adjust the paths accordingly.

```sudoers
# Allow rider user to manage specific services without password
Cmnd_Alias RIDER_SERVICES = \
    /usr/bin/systemctl start rider-pc.service, \
    /usr/bin/systemctl stop rider-pc.service, \
    /usr/bin/systemctl restart rider-pc.service, \
    /usr/bin/systemctl enable rider-pc.service, \
    /usr/bin/systemctl disable rider-pc.service, \
    /usr/bin/systemctl start rider-voice.service, \
    /usr/bin/systemctl stop rider-voice.service, \
    /usr/bin/systemctl restart rider-voice.service, \
    /usr/bin/systemctl enable rider-voice.service, \
    /usr/bin/systemctl disable rider-voice.service, \
    /usr/bin/systemctl start rider-task-queue.service, \
    /usr/bin/systemctl stop rider-task-queue.service, \
    /usr/bin/systemctl restart rider-task-queue.service, \
    /usr/bin/systemctl enable rider-task-queue.service, \
    /usr/bin/systemctl disable rider-task-queue.service

rider ALL=(root) NOPASSWD: RIDER_SERVICES
```

3. Set correct permissions:

```bash
sudo chmod 440 /etc/sudoers.d/rider-pc
```

### Platform Behavior

| Platform | Behavior |
|----------|----------|
| **Linux + systemd** | Real service control via `systemctl` |
| **Linux without systemd** | Falls back to mock/simulated mode |
| **Windows** | Mock/simulated mode only |
| **macOS** | Mock/simulated mode only |
| **Docker** | Depends on container setup; typically mock mode |

In mock/simulated mode, the dashboard shows default services with simulated states. Service control actions update the state in memory without affecting the actual system.

### Security Considerations

- Only grant sudoers access for specific services you want to control
- Never use wildcards in sudoers rules for systemctl
- Regularly audit which services are controllable
- Consider running Rider-PC in a dedicated user account

## Documentation Status

- ✅ AI Model Configuration
- ✅ Network Security Configuration
- ✅ Task Queue Configuration
- ✅ Monitoring Configuration
- ✅ Configuration Hub (this document)
- ✅ Local System Service Management

**Last update**: 2025-11-26
