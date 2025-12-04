# Przewodnik Konfiguracji Monitoringu

## Przegląd

Kompleksowy przewodnik konfiguracji monitoringu Prometheus i Grafana dla systemu Rider-PC Client.

## Komponenty

1. **Prometheus** - Zbieranie i przechowywanie metryk
2. **Grafana** - Wizualizacja i dashboardy
3. **Node Exporter** - Metryki systemowe
4. **Alertmanager** - Zarządzanie alertami

## Instalacja Prometheus

### Ubuntu/Debian

```bash
# Pobierz najnowszą wersję
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvf prometheus-2.45.0.linux-amd64.tar.gz
sudo mv prometheus-2.45.0.linux-amd64 /opt/prometheus

# Utwórz użytkownika
sudo useradd --no-create-home --shell /bin/false prometheus

# Utwórz katalogi
sudo mkdir /etc/prometheus /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus /var/lib/prometheus

# Kopiuj pliki
sudo cp /opt/prometheus/prometheus /opt/prometheus/promtool /usr/local/bin/
sudo chown prometheus:prometheus /usr/local/bin/prometheus /usr/local/bin/promtool
```

### Konfiguracja Prometheus

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

### Reguły Alertów

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
          summary: "Wysoka długość kolejki zadań"
          description: "Kolejka ma {{ $value }} zadań"

      # Circuit Breaker Open
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker otwarty dla {{ $labels.provider }}"
          description: "Provider {{ $labels.provider }} nie działa"

      # Low Processing Rate
      - alert: LowProcessingRate
        expr: rate(provider_tasks_processed_total[5m]) < 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Niska szybkość przetwarzania"
          description: "Przetwarzanie < 10 zadań/s"

      # High Memory Usage
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes > 1073741824  # 1GB
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Wysokie użycie pamięci"
          description: "Proces używa {{ $value | humanize }} pamięci"

      # Provider Task Failures
      - alert: HighTaskFailureRate
        expr: rate(provider_tasks_processed_total{status="failed"}[5m]) > 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Wysoki wskaźnik awarii zadań"
          description: "Więcej niż 1 awaria/s dla {{ $labels.provider }}"
```

### Usługa Systemd

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

Uruchom:

```bash
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
sudo systemctl status prometheus
```

## Instalacja Node Exporter

```bash
# Pobierz
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

# Uruchom
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
```

## Instalacja Grafana

### Ubuntu/Debian

```bash
# Dodaj repozytorium
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Zainstaluj
sudo apt-get update
sudo apt-get install grafana

# Uruchom
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Konfiguracja Grafana

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

## Konfiguracja Źródła Danych

1. Otwórz http://localhost:3000
2. Login: admin / secure_password
3. Configuration → Data Sources → Add data source
4. Wybierz Prometheus
5. URL: http://localhost:9090
6. Save & Test

## Import Dashboard

Dashboard JSON dostępny w `config/grafana-dashboard.json`:

1. Dashboards → Import
2. Upload JSON file lub paste JSON
3. Wybierz Prometheus data source
4. Import

## Kluczowe Metryki

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

# Użycie pamięci
process_resident_memory_bytes

# Otwarte połączenia
process_open_fds

# Goroutines/Threads
process_num_threads
```

## Alerty

### Konfiguracja Alertmanager

Zainstaluj:

```bash
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xvf alertmanager-0.26.0.linux-amd64.tar.gz
sudo mv alertmanager-0.26.0.linux-amd64/alertmanager /usr/local/bin/
```

Konfiguracja `/etc/alertmanager/alertmanager.yml`:

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

## Dashboardy

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

## Rozwiązywanie Problemów

### Prometheus nie zbiera metryk

```bash
# Sprawdź targets
curl http://localhost:9090/api/v1/targets

# Sprawdź czy endpoint działa
curl http://localhost:8000/metrics

# Sprawdź logi
sudo journalctl -u prometheus -f
```

### Grafana nie łączy się z Prometheus

```bash
# Test połączenia
curl http://localhost:9090/-/healthy

# Sprawdź konfigurację data source w Grafana UI
# Configuration → Data Sources → Prometheus → Test
```

---

**Status**: Gotowe do Produkcji ✅  
**Metryki**: 50+ metryk udostępnionych  
**Dashboardy**: 1 gotowy dashboard  
**Data**: 2025-11-12
