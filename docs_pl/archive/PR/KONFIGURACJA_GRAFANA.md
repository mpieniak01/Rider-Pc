# Przewodnik Konfiguracji Grafana

## Przegląd

Szczegółowy przewodnik konfiguracji Grafana dla monitoringu systemu Rider-PC.

## Instalacja

### Ubuntu/Debian

```bash
# Dodaj klucz GPG
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Dodaj repozytorium
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"

# Zainstaluj
sudo apt-get update
sudo apt-get install grafana

# Uruchom
sudo systemctl daemon-reload
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
sudo systemctl status grafana-server
```

### Docker

```bash
docker run -d   --name=grafana   -p 3000:3000   -v grafana-storage:/var/lib/grafana   grafana/grafana-oss:latest
```

## Pierwsza Konfiguracja

### 1. Dostęp do UI

Otwórz http://localhost:3000

**Domyślne dane logowania:**
- Username: `admin`
- Password: `admin`

**Zmień hasło** przy pierwszym logowaniu!

### 2. Dodaj Źródło Danych Prometheus

1. Kliknij ⚙️ (Configuration) → Data Sources
2. Kliknij "Add data source"
3. Wybierz "Prometheus"
4. Konfiguruj:
   ```
   Name: Prometheus
   URL: http://localhost:9090
   Access: Server (default)
   ```
5. Kliknij "Save & Test"

## Import Dashboard Rider-PC

### Opcja 1: Import JSON

1. Kliknij + (Create) → Import
2. Upload `config/grafana-dashboard.json`
3. Wybierz Prometheus data source
4. Kliknij Import

### Opcja 2: Ręczne Tworzenie

#### Panel 1: Provider Task Rate

```json
{
  "title": "Provider Task Processing Rate",
  "type": "graph",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "rate(provider_tasks_processed_total{status="completed"}[5m])",
      "legendFormat": "{{provider}} - Completed",
      "refId": "A"
    },
    {
      "expr": "rate(provider_tasks_processed_total{status="failed"}[5m])",
      "legendFormat": "{{provider}} - Failed",
      "refId": "B"
    }
  ],
  "yaxes": [
    {
      "label": "Tasks/second",
      "format": "short"
    }
  ]
}
```

#### Panel 2: Task Queue Size

```json
{
  "title": "Task Queue Size by Priority",
  "type": "graph",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "task_queue_size",
      "legendFormat": "Priority {{priority}}",
      "refId": "A"
    }
  ],
  "yaxes": [
    {
      "label": "Queue Size",
      "format": "short"
    }
  ],
  "stack": true
}
```

#### Panel 3: Provider Duration (95th Percentile)

```json
{
  "title": "Provider Task Duration (p95)",
  "type": "graph",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "histogram_quantile(0.95, rate(provider_task_duration_seconds_bucket[5m]))",
      "legendFormat": "{{provider}} - p95",
      "refId": "A"
    }
  ],
  "yaxes": [
    {
      "label": "Duration (seconds)",
      "format": "s"
    }
  ]
}
```

#### Panel 4: Circuit Breaker State

```json
{
  "title": "Circuit Breaker State",
  "type": "stat",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "circuit_breaker_state",
      "legendFormat": "{{provider}}",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "mappings": [
        {
          "type": "value",
          "options": {
            "0": {
              "text": "CLOSED",
              "color": "green"
            },
            "1": {
              "text": "OPEN",
              "color": "red"
            }
          }
        }
      ]
    }
  }
}
```

#### Panel 5: Cache Performance

```json
{
  "title": "Cache Hit/Miss Rate",
  "type": "graph",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "rate(cache_hits_total[5m])",
      "legendFormat": "Hits",
      "refId": "A"
    },
    {
      "expr": "rate(cache_misses_total[5m])",
      "legendFormat": "Misses",
      "refId": "B"
    }
  ]
}
```

#### Panel 6: System Resources

```json
{
  "title": "Memory Usage",
  "type": "graph",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "process_resident_memory_bytes",
      "legendFormat": "RSS Memory",
      "refId": "A"
    }
  ],
  "yaxes": [
    {
      "label": "Bytes",
      "format": "bytes"
    }
  ]
}
```

## Konfiguracja Alertów

### 1. Utwórz Kanał Powiadomień

1. Alerting → Notification channels
2. Kliknij "New channel"
3. Wybierz typ (Email, Slack, Webhook, etc.)

**Email:**
```
Name: Admin Email
Type: Email
Addresses: admin@example.com
```

**Slack:**
```
Name: Slack Alerts
Type: Slack
Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 2. Utwórz Reguły Alertów

#### Alert 1: High Queue Size

```json
{
  "name": "High Task Queue",
  "conditions": [
    {
      "evaluator": {
        "params": [1000],
        "type": "gt"
      },
      "query": {
        "params": ["A", "5m", "now"]
      },
      "reducer": {
        "type": "avg"
      },
      "type": "query"
    }
  ],
  "executionErrorState": "alerting",
  "for": "5m",
  "frequency": "1m",
  "message": "Task queue size exceeds 1000",
  "name": "High Task Queue",
  "noDataState": "no_data",
  "notifications": []
}
```

#### Alert 2: Circuit Breaker Open

```json
{
  "name": "Circuit Breaker Open",
  "conditions": [
    {
      "evaluator": {
        "params": [0.5],
        "type": "gt"
      },
      "query": {
        "params": ["A", "5m", "now"]
      },
      "reducer": {
        "type": "avg"
      },
      "type": "query"
    }
  ],
  "executionErrorState": "alerting",
  "for": "5m",
  "message": "Circuit breaker is open for {{provider}}",
  "notifications": []
}
```

## Konfiguracja Zaawansowana

### Zmienne Dashboard

Użyj zmiennych dla dynamicznych dashboardów:

```json
{
  "templating": {
    "list": [
      {
        "name": "provider",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(provider_tasks_processed_total, provider)",
        "multi": true,
        "includeAll": true
      },
      {
        "name": "priority",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(task_queue_size, priority)",
        "multi": true
      }
    ]
  }
}
```

Użyj w zapytaniach:
```promql
provider_tasks_processed_total{provider=~"$provider"}
task_queue_size{priority=~"$priority"}
```

### Annotations

Dodaj wydarzenia do wykresów:

```json
{
  "annotations": {
    "list": [
      {
        "datasource": "Prometheus",
        "enable": true,
        "expr": "ALERTS{alertname="HighTaskQueue"}",
        "name": "Alerts",
        "step": "60s",
        "tagKeys": "alertname",
        "titleFormat": "Alert: {{alertname}}",
        "textFormat": "{{alertstate}}"
      }
    ]
  }
}
```

## Wskazówki Wydajnościowe

### 1. Ogranicz zakres czasu

```promql
# Zamiast
rate(metric[1h])

# Użyj
rate(metric[5m])
```

### 2. Użyj zmiennych dla filtrowania

```promql
# Zamiast pobierania wszystkich
metric{provider=~".*"}

# Użyj zmiennej
metric{provider=~"$provider"}
```

### 3. Agreguj dane

```promql
# Dla wielu instancji
sum(rate(metric[5m])) by (provider)
```

## Eksport i Backup

### Eksport Dashboard

```bash
# Przez API
curl -H "Authorization: Bearer YOUR_API_KEY"   http://localhost:3000/api/dashboards/db/rider-pc   > backup-dashboard.json

# Przez UI
Dashboard Settings → JSON Model → Copy to clipboard
```

### Backup Grafana Data

```bash
# Backup SQLite database
sudo cp /var/lib/grafana/grafana.db /backup/

# Backup konfiguracji
sudo cp /etc/grafana/grafana.ini /backup/

# Backup dashboards
sudo cp -r /var/lib/grafana/dashboards /backup/
```

## Rozwiązywanie Problemów

### Dashboard nie pokazuje danych

```bash
# Sprawdź połączenie z Prometheus
curl http://localhost:9090/api/v1/query?query=up

# Sprawdź czy metryki są scrapowane
curl http://localhost:9090/api/v1/targets

# Testuj zapytanie
curl 'http://localhost:9090/api/v1/query?query=provider_tasks_processed_total'
```

### Alertu nie działają

```bash
# Sprawdź reguły alertów
curl http://localhost:9090/api/v1/rules

# Sprawdź historię alertów
curl http://localhost:9090/api/v1/alerts

# Sprawdź logi Grafana
sudo journalctl -u grafana-server -f
```

## Dodatkowe Zasoby

- Oficjalna Dokumentacja: https://grafana.com/docs/
- Dashboard Gallery: https://grafana.com/grafana/dashboards/
- Community Forum: https://community.grafana.com/

---

**Status**: Gotowe do Produkcji ✅  
**Panele**: 10+ gotowych paneli  
**Alerty**: 5+ reguł alertów  
**Data**: 2025-11-12
