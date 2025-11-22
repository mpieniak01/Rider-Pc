# Task Queue Configuration Guide

## Przegląd

Przewodnik konfiguracji brokera kolejki zadań (Redis or RabbitMQ) for systemu Rider-PC Client.

## Wybór Brokera

### Redis (Recommended for Rozwoju)
- **Zalety**: Prosty, szybki, lekki
- **Wady**: Mniej funkcji niż RabbitMQ
- **Najlepsze for**: Development, małe wdrożenia

### RabbitMQ (Recommended for Produkcji)
- **Zalety**: Zaawansowane funkcje, niezawodny
- **Wady**: Bardziej złożony setup
- **Najlepsze for**: Produkcja, duża skala

## Opcja 1: Redis Setup

### Instalacja

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install redis-server
```

#### macOS
```bash
brew install redis
```

### Konfiguracja

Edytuj `/etc/redis/redis.conf`:

```conf
# Bind do localhost (bezpieczne)
bind 127.0.0.1

# Port (domyślnie 6379)
port 6379

# Włącz persystencję AOF
appendonly yes
appendfilename "appendonly.aof"

# Autosave
save 900 1
save 300 10
save 60 10000

# Max pamięć
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Uruchom Redis

```bash
# Start
sudo systemctl start redis-server

# Enable autostart
sudo systemctl enable redis-server

# Check status
sudo systemctl status redis-server

# Test połączenie
redis-cli ping
# Oczekiwana odpowiedź: PONG
```

### Konfiguracja Klienta PC

Zaktualizuj `.env`:

```bash
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Pozostaw puste if brak hasła
```

### Monitoring Redis

```bash
# Monitor komend w czasie rzeczywistym
redis-cli monitor

# Check statystyki
redis-cli info stats

# Check rozmiar kolejki
redis-cli LLEN task_queue:priority:5

# Check wszystkie klucze
redis-cli KEYS "task_queue:*"
```

## Opcja 2: RabbitMQ Setup

### Instalacja

#### Ubuntu/Debian
```bash
# Dodaj klucz Rabbit MQ APT
curl -fsSL https://github.com/rabbitmq/signing-keys/releases/download/2.0/rabbitmq-release-signing-key.asc | sudo apt-key add -

# Dodaj repozytorium
sudo apt install apt-transport-https
sudo tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
deb https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/deb/ubuntu focal main
EOF

# Zainstaluj
sudo apt update
sudo apt install rabbitmq-server
```

### Konfiguracja

Utwórz `/etc/rabbitmq/rabbitmq.conf`:

```conf
# Listener
listeners.tcp.default = 5672

# Management UI
management.listener.port = 15672

# Virtual host
default_vhost = /

# Użytkownik i hasło
default_user = admin
default_pass = secure_password
```

### Uruchom RabbitMQ

```bash
# Start
sudo systemctl start rabbitmq-server

# Enable autostart
sudo systemctl enable rabbitmq-server

# Włącz management plugin
sudo rabbitmq-plugins enable rabbitmq_management

# Check status
sudo rabbitmqctl status

# Lista vhosts
sudo rabbitmqctl list_vhosts

# Lista users
sudo rabbitmqctl list_users
```

### Utwórz Użytkownika i VHost

```bash
# Utwórz vhost
sudo rabbitmqctl add_vhost rider_pc

# Utwórz użytkownika
sudo rabbitmqctl add_user rider_user secure_password

# Set uprawnienia
sudo rabbitmqctl set_permissions -p rider_pc rider_user ".*" ".*" ".*"

# Set tagi użytkownika
sudo rabbitmqctl set_user_tags rider_user administrator
```

### Konfiguracja Klienta PC

Zaktualizuj `.env`:

```bash
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=rabbitmq
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_VHOST=rider_pc
RABBITMQ_USER=rider_user
RABBITMQ_PASSWORD=secure_password
```

### Monitoring RabbitMQ

```bash
# Management UI
# Otwórz http://localhost:15672
# Login: admin / secure_password

# CLI monitoring
sudo rabbitmqctl list_queues
sudo rabbitmqctl list_exchanges
sudo rabbitmqctl list_bindings

# Status kolejki
sudo rabbitmqctl list_queues name messages consumers
```

## Konfiguracja Kolejki Priorityowej

### Redis Implementation

Priority queues są implementowane jako osobne listy:

```python
# Priority 1 (najwyższy)
RPUSH task_queue:priority:1 task_json

# Priority 5 (normalny)
RPUSH task_queue:priority:5 task_json

# Priority 10 (najniższy)
RPUSH task_queue:priority:10 task_json
```

### RabbitMQ Implementation

Użyj priority queues:

```python
# Declare priority queue
channel.queue_declare(
    queue='task_queue',
    durable=True,
    arguments={'x-max-priority': 10}
)

# Publish z priorytetem
channel.basic_publish(
    exchange='',
    routing_key='task_queue',
    body=task_json,
    properties=pika.BasicProperties(
        delivery_mode=2,  # persistent
        priority=5  # 1-10
    )
)
```

## Mapowanie Priorityów

| Priority | Kategoria | Przykłady | Timeout |
|-----------|-----------|-----------|---------|
| 1-2 | Critical | Unikanie przeszkód | 50ms |
| 3-4 | High | Sterowanie | 200ms |
| 5-6 | Normal | ASR/TTS | 1s |
| 7-8 | Low | Generowanie tekstu | 5s |
| 9-10 | Background | Logowanie | 30s |

## Persystencja i Niezawodność

### Redis Persystencja

```bash
# AOF (Append Only File)
appendonly yes
appendfsync everysec

# RDB Snapshots
save 900 1
save 300 10
save 60 10000
```

### RabbitMQ Trwałość

```python
# Trwała kolejka
channel.queue_declare(queue='task_queue', durable=True)

# Trwałe wiadomości
channel.basic_publish(
    exchange='',
    routing_key='task_queue',
    body=message,
    properties=pika.BasicProperties(delivery_mode=2)  # persistent
)
```

## Performance Tuning

### Redis Optimization

```conf
# Zwiększ max połączeń
maxclients 10000

# Disable saves for wyższej wydajności (brak persystencji)
save ""

# Use pipeline for batch operations
tcp-keepalive 60
timeout 300
```

### RabbitMQ Optimization

```conf
# Zwiększ limity plików
vm_memory_high_watermark.relative = 0.6

# Channel max
channel_max = 2048

# Heartbeat
heartbeat = 60

# Prefetch count
basic.qos(prefetch_count=10)
```

## Backup i Recovery

### Redis Backup

```bash
# Manual snapshot
redis-cli BGSAVE

# Backup AOF file
cp /var/lib/redis/appendonly.aof /backup/

# Restore
sudo systemctl stop redis-server
cp /backup/appendonly.aof /var/lib/redis/
sudo systemctl start redis-server
```

### RabbitMQ Backup

```bash
# Export definitions
sudo rabbitmqctl export_definitions /backup/definitions.json

# Import definitions
sudo rabbitmqctl import_definitions /backup/definitions.json
```

## Rozwiązywanie Problemów

### Redis Issues

**Połączenie odmówione:**
```bash
# Check czy działa
sudo systemctl status redis-server

# Check port
sudo netstat -tlnp | grep 6379

# Test
redis-cli ping
```

**Pełna pamięć:**
```bash
# Check użycie pamięci
redis-cli INFO memory

# Wyczyść bazę danych (ostrożnie!)
redis-cli FLUSHDB

# Zwiększ maxmemory w konfiguracji
```

### RabbitMQ Issues

**Nie można połączyć:**
```bash
# Check czy działa
sudo systemctl status rabbitmq-server

# Check logi
sudo tail -f /var/log/rabbitmq/rabbit@hostname.log

# Check port
sudo netstat -tlnp | grep 5672
```

**Kolejka się zapchała:**
```bash
# Check długość kolejki
sudo rabbitmqctl list_queues

# Purge queue (ostrożnie!)
sudo rabbitmqctl purge_queue task_queue

# Zwiększ consumers
```

## Bezpieczeństwo

### Redis Security

```conf
# Wymagaj hasła
requirepass your_strong_password

# Bind tylko do localhost
bind 127.0.0.1

# Rename dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

### RabbitMQ Security

```bash
# Użyj silnych haseł
sudo rabbitmqctl change_password rider_user new_strong_password

# Włącz SSL
sudo rabbitmq-plugins enable rabbitmq_auth_mechanism_ssl

# Limit uprawnienia
sudo rabbitmqctl set_permissions -p rider_pc rider_user "^task_.*" "^task_.*" "^task_.*"
```

---

**Status**: Gotowe do Produkcji ✅  
**Recommended**: Redis for dev, RabbitMQ for prod  
**Data**: 2025-11-12
