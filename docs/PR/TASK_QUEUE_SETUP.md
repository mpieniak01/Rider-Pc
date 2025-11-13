# Task Queue and Broker Setup Guide

## Overview

This document describes the setup and configuration of the task queue broker for asynchronous task offloading from Rider-PI to PC.

## Architecture

```
Rider-PI → REST/ZMQ → Task Queue → Workers → Providers (Voice/Vision/Text)
                ↓                      ↓
              Broker              Results → ZMQ → Rider-PI
```

## Option 1: Redis (Recommended for Development)

Redis is lightweight, easy to setup, and provides good performance for most use cases.

### Installation

#### On PC (WSL Debian)
```bash
sudo apt update
sudo apt install redis-server
```

### Configuration

Edit `/etc/redis/redis.conf`:

```ini
# Bind to VPN network
bind 10.0.0.2 127.0.0.1

# Enable persistence
save 900 1
save 300 10
save 60 10000

# Set max memory
maxmemory 256mb
maxmemory-policy allkeys-lru

# Enable AOF for durability
appendonly yes
appendfsync everysec
```

### Start Redis

```bash
# Start Redis
sudo systemctl start redis-server

# Enable on boot
sudo systemctl enable redis-server

# Check status
sudo systemctl status redis-server

# Test connection
redis-cli ping
```

### Python Client

Add to `requirements.txt`:
```
redis==5.0.1
```

Example usage:
```python
import redis

# Connect to Redis
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)

# Queue task
task_json = json.dumps(task.to_dict())
redis_client.lpush('task_queue', task_json)

# Dequeue task
task_json = redis_client.brpop('task_queue', timeout=1)
```

## Option 2: RabbitMQ (Recommended for Production)

RabbitMQ provides advanced features like routing, exchanges, and dead letter queues.

### Installation

#### On PC (WSL Debian)
```bash
sudo apt update
sudo apt install rabbitmq-server
```

### Configuration

```bash
# Enable management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Create user for PC client
sudo rabbitmqctl add_user rider_pc secure_password
sudo rabbitmqctl set_user_tags rider_pc administrator
sudo rabbitmqctl set_permissions -p / rider_pc ".*" ".*" ".*"

# Configure networking
sudo vim /etc/rabbitmq/rabbitmq.conf
```

Add to `/etc/rabbitmq/rabbitmq.conf`:
```ini
listeners.tcp.default = 5672
management.listener.port = 15672
management.listener.ssl = false
```

### Start RabbitMQ

```bash
# Start RabbitMQ
sudo systemctl start rabbitmq-server

# Enable on boot
sudo systemctl enable rabbitmq-server

# Check status
sudo systemctl status rabbitmq-server

# Access management UI
# http://localhost:15672 (default: guest/guest)
```

### Python Client (Celery)

Add to `requirements.txt`:
```
celery==5.3.4
kombu==5.3.4
```

Example configuration:
```python
from celery import Celery

app = Celery(
    'rider_pc_tasks',
    broker='pyamqp://rider_pc:secure_password@localhost:5672//',
    backend='rpc://'
)

# Task priorities
app.conf.task_default_priority = 5
app.conf.task_queue_max_priority = 10

# Configure queues
app.conf.task_routes = {
    'tasks.voice.*': {'queue': 'voice', 'priority': 5},
    'tasks.vision.*': {'queue': 'vision', 'priority': 8},  # Higher priority
    'tasks.text.*': {'queue': 'text', 'priority': 3}
}
```

## Option 3: ARQ (Alternative to Celery)

ARQ is a lightweight async task queue built on Redis.

### Installation

Add to `requirements.txt`:
```
arq==0.25.0
```

### Configuration

Create `pc_client/queue/arq_config.py`:
```python
from arq import create_pool
from arq.connections import RedisSettings

async def startup(ctx):
    ctx['providers'] = await initialize_providers()

async def shutdown(ctx):
    await cleanup_providers(ctx['providers'])

class WorkerSettings:
    functions = [process_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host='localhost', port=6379)
    max_jobs = 10
    job_timeout = 300  # 5 minutes
```

## Queue Configuration

### Priority Levels

Tasks are prioritized based on criticality:

- **Priority 1-3** (Highest): Critical tasks
  - Obstacle avoidance
  - Emergency stops
  - Real-time navigation
  
- **Priority 4-6** (Medium): Normal tasks
  - General voice commands
  - Object detection
  - Navigation planning
  
- **Priority 7-10** (Lowest): Background tasks
  - Text generation
  - Non-critical analysis
  - Logging and telemetry

### Queue Sizes

- **Vision Queue**: 50 tasks (high throughput)
- **Voice Queue**: 30 tasks (medium throughput)
- **Text Queue**: 20 tasks (lower throughput)

### Timeouts

- **Vision tasks**: 2 seconds
- **Voice tasks**: 5 seconds
- **Text tasks**: 30 seconds

## Circuit Breaker Configuration

The circuit breaker protects against provider failures:

```python
from pc_client.queue.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    success_threshold=2,      # Close after 2 successes
    timeout_seconds=60        # Try again after 60s
)
```

### Critical Task Handling

For critical tasks (e.g., obstacle avoidance):

1. Task submitted to queue with priority 1
2. If circuit breaker is OPEN → Immediate fallback to local processing
3. Result returned to Rider-PI with `fallback_required: true`
4. Rider-PI processes task locally

## Monitoring

### Redis Monitoring

```bash
# Monitor commands
redis-cli monitor

# Get stats
redis-cli info stats

# Check queue length
redis-cli llen task_queue
```

### RabbitMQ Monitoring

```bash
# List queues
sudo rabbitmqctl list_queues

# Check queue details
sudo rabbitmqctl list_queues name messages_ready messages_unacknowledged

# Management UI
# http://localhost:15672
```

### Prometheus Metrics

Add exporters for monitoring:

```bash
# Redis exporter
docker run -d -p 9121:9121 oliver006/redis_exporter

# RabbitMQ exporter (built-in)
sudo rabbitmq-plugins enable rabbitmq_prometheus
# Metrics at http://localhost:15692/metrics
```

## Security

### Redis Security

```bash
# Set password
redis-cli CONFIG SET requirepass "your_strong_password"

# Update redis.conf
requirepass your_strong_password

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
```

### RabbitMQ Security

```bash
# Use strong passwords
sudo rabbitmqctl change_password rider_pc new_strong_password

# Enable SSL/TLS
sudo rabbitmq-plugins enable rabbitmq_auth_mechanism_ssl

# Configure SSL
listeners.ssl.default = 5671
ssl_options.cacertfile = /path/to/ca_certificate.pem
ssl_options.certfile = /path/to/server_certificate.pem
ssl_options.keyfile = /path/to/server_key.pem
```

## Backup and Recovery

### Redis Backup

```bash
# Manual backup
redis-cli BGSAVE

# Backup file location
/var/lib/redis/dump.rdb

# Restore
cp backup/dump.rdb /var/lib/redis/
sudo systemctl restart redis-server
```

### RabbitMQ Backup

```bash
# Export definitions
sudo rabbitmqctl export_definitions /backup/rabbit_definitions.json

# Import definitions
sudo rabbitmqctl import_definitions /backup/rabbit_definitions.json
```

## Performance Tuning

### Redis Performance

```ini
# Increase max clients
maxclients 10000

# Disable slow operations
slowlog-log-slower-than 10000

# Use pipelining
tcp-keepalive 300
```

### RabbitMQ Performance

```ini
# Increase message prefetch
channel_max = 2047
frame_max = 131072

# Tune memory
vm_memory_high_watermark.relative = 0.6

# Enable lazy queues for large queues
queue_master_locator = min-masters
```

## Troubleshooting

### Redis Issues

```bash
# Check logs
sudo tail -f /var/log/redis/redis-server.log

# Test connection
redis-cli -h 10.0.0.2 ping

# Clear queue if stuck
redis-cli DEL task_queue
```

### RabbitMQ Issues

```bash
# Check logs
sudo tail -f /var/log/rabbitmq/rabbit@hostname.log

# Restart stuck queues
sudo rabbitmqctl stop_app
sudo rabbitmqctl start_app

# Purge queue
sudo rabbitmqctl purge_queue queue_name
```

## Integration with PC Client

Update `pc_client/config/settings.py`:

```python
# Task queue configuration
task_queue_backend: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_BACKEND", "redis"))
task_queue_host: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_HOST", "localhost"))
task_queue_port: int = field(default_factory=lambda: int(os.getenv("TASK_QUEUE_PORT", "6379")))
task_queue_password: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_PASSWORD", ""))
```

Example `.env`:
```bash
# Task Queue (Redis)
TASK_QUEUE_BACKEND=redis
TASK_QUEUE_HOST=localhost
TASK_QUEUE_PORT=6379
TASK_QUEUE_PASSWORD=your_password

# Or RabbitMQ
# TASK_QUEUE_BACKEND=rabbitmq
# TASK_QUEUE_HOST=localhost
# TASK_QUEUE_PORT=5672
# TASK_QUEUE_USER=rider_pc
# TASK_QUEUE_PASSWORD=secure_password
```

## Testing

### Test Redis Queue

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Enqueue test task
task = {"task_id": "test-1", "task_type": "voice.asr", "payload": {}}
r.lpush('task_queue', json.dumps(task))

# Dequeue test task
result = r.brpop('task_queue', timeout=5)
print(f"Dequeued: {result}")
```

### Test RabbitMQ Queue

```python
from celery import Celery

app = Celery('test', broker='pyamqp://guest@localhost//')

@app.task
def test_task(data):
    return f"Processed: {data}"

# Send task
result = test_task.delay({"test": "data"})
print(f"Task ID: {result.id}")
```

## References

- [Redis Documentation](https://redis.io/documentation)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Celery Documentation](https://docs.celeryproject.org/)
- [ARQ Documentation](https://arq-docs.helpmanual.io/)
