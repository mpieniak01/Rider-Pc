# Monitoring Configuration Guide

## Overview

Comprehensive guide for configuring Prometheus and Grafana monitoring for the Rider-PC Client system.

## Components

1. **Prometheus** - Metrics collection and storage
2. **Grafana** - Visualization and dashboards
3. **Node Exporter** - System metrics
4. **Alertmanager** - Alert management

## Installation Prometheus

### Ubuntu/Debian

```bash
# Download latest version
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvf prometheus-2.45.0.linux-amd64.tar.gz
sudo mv prometheus-2.45.0.linux-amd64 /opt/prometheus

# Create user
sudo useradd --no-create-home --shell /bin/false prometheus

# Create directories
sudo mkdir /etc/prometheus /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus /var/lib/prometheus

# Copy files
sudo cp /opt/prometheus/prometheus /opt/prometheus/promtool /usr/local/bin/
sudo chown prometheus:prometheus /usr/local/bin/prometheus /usr/local/bin/promtool
```

### Configuration Prometheus

Utwórz `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - "alerts.yml"

scrape_configs:
  # Rider-PC Application
  - job_name: 'rider-pc'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s

  # Node Exporter (System Metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']

  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
```

### Alert Rules

Utwórz `/etc/prometheus/alerts.yml`:

```yaml
groups:
  - name: rider_pc_alerts
    rules:
      # High Queue Size
      - alert: HighTaskQueueSize
        expr: task_queue_size > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task queue length"
          description: "Queue has {{ $value }} tasks"

      # Circuit Breaker Open
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker open for {{ $labels.provider }}"
          description: "Provider {{ $labels.provider }} not working"

      # Low Processing Rate
      - alert: LowProcessingRate
        expr: rate(provider_tasks_processed_total[5m]) < 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low processing rate"
          description: "Processing < 10 tasks/s"

      # High Memory Usage
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes > 1073741824  # 1GB
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Process uses {{ $value | humanize }} memory"

      # Provider Task Failures
      - alert: HighTaskFailureRate
        expr: rate(provider_tasks_processed_total{status="failed"}[5m]) > 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Wysoki wskaźnik awarii tasks"
          description: "More than 1 failure/s for {{ $labels.provider }}"
```

### Systemd Service

Utwórz `/etc/systemd/system/prometheus.service`:

```ini
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus   --config.file=/etc/prometheus/prometheus.yml   --storage.tsdb.path=/var/lib/prometheus/   --web.console.templates=/opt/prometheus/consoles   --web.console.libraries=/opt/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```

Start:

```bash
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
sudo systemctl status prometheus
```

## Installation Node Exporter

```bash
# Download
cd /tmp
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar xvf node_exporter-1.6.0.linux-amd64.tar.gz
sudo mv node_exporter-1.6.0.linux-amd64/node_exporter /usr/local/bin/

# Utwórz usługę
sudo tee /etc/systemd/system/node_exporter.service <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

# Start
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
```

## Installation Grafana

### Ubuntu/Debian

```bash
# Add repository
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Install
sudo apt-get update
sudo apt-get install grafana

# Start
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Configuration Grafana

Edytuj `/etc/grafana/grafana.ini`:

```ini
[server]
http_port = 3000
domain = localhost

[security]
admin_user = admin
admin_password = secure_password

[auth.anonymous]
enabled = false

[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/rider-pc.json
```

Restart:

```bash
sudo systemctl restart grafana-server
```

## Configuration Źródła Danych

1. Otwórz http://localhost:3000
2. Login: admin / secure_password
3. Configuration → Data Sources → Add data source
4. Wybierz Prometheus
5. URL: http://localhost:9090
6. Save & Test

## Import Dashboard

Dashboard JSON dostępny w `config/grafana-dashboard.json`:

1. Dashboards → Import
2. Upload JSON file or paste JSON
3. Wybierz Prometheus data source
4. Import

## Key Metrics

### Provider Metrics

```promql
# Szybkość przetwarzania
rate(provider_tasks_processed_total[5m])

# Czas przetwarzania (percentyle)
histogram_quantile(0.95, provider_task_duration_seconds_bucket)

# Wskaźnik awarii
rate(provider_tasks_processed_total{status="failed"}[5m])
/ rate(provider_tasks_processed_total[5m])

# Stan circuit breakera
circuit_breaker_state
```

### Queue Metrics

```promql
# Rozmiar kolejki
task_queue_size

# Szybkość enqueue
rate(task_queue_enqueued_total[5m])

# Szybkość dequeue
rate(task_queue_dequeued_total[5m])

# Czas oczekiwania
task_queue_wait_seconds
```

### System Metrics

```promql
# Użycie CPU
rate(process_cpu_seconds_total[5m])

# Użycie memory
process_resident_memory_bytes

# Otwarte połączenia
process_open_fds

# Goroutines/Threads
process_num_threads
```

## Alerts

### Configuration Alertmanager

Install:

```bash
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xvf alertmanager-0.26.0.linux-amd64.tar.gz
sudo mv alertmanager-0.26.0.linux-amd64/alertmanager /usr/local/bin/
```

Configuration `/etc/alertmanager/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@example.com'
        from: 'alertmanager@example.com'
        smarthost: smtp.gmail.com:587
        auth_username: 'alertmanager@example.com'
        auth_password: 'app_password'
```

## Dashboards

### Panel Provider Performance

```json
{
  "title": "Provider Performance",
  "targets": [
    {
      "expr": "rate(provider_tasks_processed_total[5m])",
      "legendFormat": "{{provider}} - {{status}}"
    }
  ]
}
```

### Panel Queue Size

```json
{
  "title": "Task Queue Size",
  "targets": [
    {
      "expr": "task_queue_size",
      "legendFormat": "Priority {{priority}}"
    }
  ]
}
```

## Troubleshooting

### Prometheus nie zbiera metryk

```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Check czy endpoint działa
curl http://localhost:8000/metrics

# Check logi
sudo journalctl -u prometheus -f
```

### Grafana nie łączy się z Prometheus

```bash
# Test połączenia
curl http://localhost:9090/-/healthy

# Check configuration data source w Grafana UI
# Configuration → Data Sources → Prometheus → Test
```

---

**Status**: Gotowe do Produkcji ✅  
**Metryki**: 50+ metryk udostępnionych  
**Dashboards**: 1 gotowy dashboard  
**Data**: 2025-11-12
