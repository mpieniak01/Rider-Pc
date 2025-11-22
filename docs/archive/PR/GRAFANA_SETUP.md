# Grafana Setup Guide for Rider-PC

This guide walks you through the complete setup of Grafana for visualizing Rider-PC metrics, including Prometheus integration, dashboard configuration, and alerting setup.

## 📋 Prerequisites

- Ubuntu/Debian-based Linux system (WSL2 supported)
- Rider-PC client running with metrics enabled
- Prometheus installed and running (see below)
- Internet connection for downloading packages

## 🚀 Quick Start

### 1. Install Prometheus

First, install Prometheus to collect metrics from Rider-PC:

```bash
# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
tar xvfz prometheus-2.48.0.linux-amd64.tar.gz
sudo mv prometheus-2.48.0.linux-amd64 /opt/prometheus

# Copy configuration
sudo mkdir -p /etc/prometheus
sudo cp config/prometheus.yml /etc/prometheus/
sudo cp config/prometheus-alerts.yml /etc/prometheus/

# Create Prometheus user
sudo useradd -rs /bin/false prometheus

# Create data directory
sudo mkdir -p /var/lib/prometheus/data
sudo chown -R prometheus:prometheus /var/lib/prometheus
sudo chown -R prometheus:prometheus /etc/prometheus

# Create systemd service
sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
Documentation=https://prometheus.io/docs/introduction/overview/
After=network-online.target

[Service]
Type=simple
User=prometheus
ExecStart=/opt/prometheus/prometheus \\
  --config.file=/etc/prometheus/prometheus.yml \\
  --storage.tsdb.path=/var/lib/prometheus/data \\
  --web.console.templates=/opt/prometheus/consoles \\
  --web.console.libraries=/opt/prometheus/console_libraries
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start Prometheus
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus

# Check status
sudo systemctl status prometheus
```

Prometheus UI will be available at: **http://localhost:9090**

### 2. Install Node Exporter

Node Exporter provides system-level metrics (CPU, memory, disk, network):

```bash
# Download Node Exporter
cd /tmp
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar xvfz node_exporter-1.7.0.linux-amd64.tar.gz
sudo mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/

# Create node_exporter user
sudo useradd -rs /bin/false node_exporter

# Create systemd service
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
Documentation=https://prometheus.io/docs/guides/node-exporter/
After=network-online.target

[Service]
Type=simple
User=node_exporter
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start Node Exporter
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter

# Check status
sudo systemctl status node_exporter
```

Node Exporter metrics available at: **http://localhost:9100/metrics**

### 3. Install Grafana

Install Grafana for visualization:

```bash
# Add Grafana repository
sudo apt-get install -y software-properties-common apt-transport-https
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"

# Install Grafana
sudo apt-get update
sudo apt-get install -y grafana

# Start Grafana
sudo systemctl daemon-reload
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Check status
sudo systemctl status grafana-server
```

Grafana UI available at: **http://localhost:3000**
- Default username: `admin`
- Default password: `admin` (you'll be prompted to change it)

## 🔧 Configure Grafana

### 1. Add Prometheus Data Source

1. Log in to Grafana at http://localhost:3000
2. Click **⚙️ Configuration** → **Data Sources**
3. Click **Add data source**
4. Select **Prometheus**
5. Configure:
   - **Name**: `Prometheus`
   - **URL**: `http://localhost:9090`
   - **Access**: `Server (default)`
6. Click **Save & Test**

You should see: ✅ "Data source is working"

### 2. Import Rider-PC Dashboard

#### Option A: Import from JSON file

1. Click **➕ Create** → **Import**
2. Click **Upload JSON file**
3. Select `config/grafana-dashboard.json` from the repository
4. Select **Prometheus** as the data source
5. Click **Import**

#### Option B: Manual Dashboard Creation

If you prefer to build the dashboard manually:

1. Click **➕ Create** → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** data source
4. Add the following panels:

**Panel 1: Task Queue Size**
- Query: `task_queue_size`
- Visualization: Time series
- Title: "Task Queue Size"

**Panel 2: Tasks Processed Rate**
- Query A: `rate(provider_tasks_processed_total{status="completed"}[5m])`
- Query B: `rate(provider_tasks_processed_total{status="failed"}[5m])`
- Visualization: Time series
- Title: "Tasks Processed (Rate)"

**Panel 3: Task Duration (p95)**
- Query: `histogram_quantile(0.95, rate(provider_task_duration_seconds_bucket[5m]))`
- Visualization: Time series
- Title: "Task Duration (p95)"

**Panel 4: CPU Usage**
- Query: `100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
- Visualization: Time series
- Title: "CPU Usage"

**Panel 5: Memory Usage**
- Query: `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100`
- Visualization: Time series
- Title: "Memory Usage"

**Panel 6: Provider Status**
- Query: `sum by (provider) (rate(provider_tasks_processed_total{status="completed"}[5m]))`
- Visualization: Stat
- Title: "Provider Status"

**Panel 7: Circuit Breaker State**
- Query: `circuit_breaker_state`
- Visualization: Stat
- Title: "Circuit Breaker State"

**Panel 8: Cache Performance**
- Query A: `rate(cache_hits_total[5m])`
- Query B: `rate(cache_misses_total[5m])`
- Visualization: Time series
- Title: "Cache Performance"

### 3. Import Node Exporter Dashboard

For comprehensive system metrics:

1. Click **➕ Create** → **Import**
2. Enter dashboard ID: **1860** (Node Exporter Full)
3. Click **Load**
4. Select **Prometheus** as the data source
5. Click **Import**

This provides detailed system metrics including:
- CPU, Memory, Disk, Network usage
- Process statistics
- File system details
- Network interface statistics

## 📊 Understanding the Dashboard

### Key Metrics Explained

#### Task Queue Metrics
- **task_queue_size**: Current number of tasks in queue (0-100)
- **Alert threshold**: ≥95 tasks triggers warning

#### Provider Performance
- **provider_tasks_processed_total**: Counter of completed/failed tasks
- **provider_task_duration_seconds**: Histogram of task processing times
- **p95 latency**: 95th percentile of task duration

#### System Metrics
- **CPU Usage**: Percentage of CPU time used (0-100%)
- **Memory Usage**: Percentage of RAM used (0-100%)
- **Disk Space**: Available disk space percentage
- **Network I/O**: Bytes sent/received per second

#### Circuit Breaker
- **State 0 (Closed)**: Normal operation ✅
- **State 1 (Open)**: Failures detected, using fallback ⚠️
- **State 2 (Half-Open)**: Testing recovery 🔄

### Dashboard Features

- **Auto-refresh**: Updates every 10 seconds
- **Time range**: Last 1 hour by default
- **Zoom**: Click and drag to zoom into time period
- **Legend**: Click series name to toggle visibility
- **Tooltips**: Hover over graphs for exact values

## 🚨 Configure Alerting

### 1. Install Alertmanager

```bash
# Download Alertmanager
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xvfz alertmanager-0.26.0.linux-amd64.tar.gz
sudo mv alertmanager-0.26.0.linux-amd64 /opt/alertmanager

# Create configuration directory
sudo mkdir -p /etc/alertmanager

# Create basic configuration
sudo tee /etc/alertmanager/alertmanager.yml > /dev/null <<EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    # Add your notification configuration here
    # Examples: email, slack, webhook, etc.

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
EOF

# Create alertmanager user
sudo useradd -rs /bin/false alertmanager

# Create data directory
sudo mkdir -p /var/lib/alertmanager/data
sudo chown -R alertmanager:alertmanager /var/lib/alertmanager
sudo chown -R alertmanager:alertmanager /etc/alertmanager

# Create systemd service
sudo tee /etc/systemd/system/alertmanager.service > /dev/null <<EOF
[Unit]
Description=Alertmanager
Documentation=https://prometheus.io/docs/alerting/alertmanager/
After=network-online.target

[Service]
Type=simple
User=alertmanager
ExecStart=/opt/alertmanager/alertmanager \\
  --config.file=/etc/alertmanager/alertmanager.yml \\
  --storage.path=/var/lib/alertmanager/data
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start Alertmanager
sudo systemctl daemon-reload
sudo systemctl start alertmanager
sudo systemctl enable alertmanager

# Check status
sudo systemctl status alertmanager
```

Alertmanager UI available at: **http://localhost:9093**

### 2. Configure Grafana Alerts

Grafana can also send alerts independently:

1. In Grafana, go to **Alerting** → **Contact points**
2. Click **New contact point**
3. Configure your notification channel (Email, Slack, etc.)
4. Test the contact point
5. Go to **Notification policies** to configure routing

## 🔍 Verifying the Setup

### Check All Services

```bash
# Check Prometheus
curl http://localhost:9090/-/healthy

# Check Node Exporter
curl http://localhost:9100/metrics | head

# Check Rider-PC metrics
curl http://localhost:8000/metrics | grep provider

# Check Grafana
curl http://localhost:3000/api/health

# Check Alertmanager
curl http://localhost:9093/-/healthy
```

### View Metrics in Prometheus

1. Open http://localhost:9090
2. Go to **Graph** tab
3. Try queries:
   - `task_queue_size`
   - `rate(provider_tasks_processed_total[5m])`
   - `node_cpu_seconds_total`

### Test Alerts

To test alerting:

1. Generate high queue load:
```bash
# This would need actual implementation
python -c "from pc_client import test_queue_load; test_queue_load()"
```

2. Check Prometheus alerts: http://localhost:9090/alerts
3. Check Alertmanager: http://localhost:9093

## 📱 Mobile Access

To access dashboards from mobile devices:

1. Configure Grafana to listen on all interfaces:
```bash
sudo nano /etc/grafana/grafana.ini
# Find [server] section and set:
# http_addr = 0.0.0.0
```

2. Restart Grafana:
```bash
sudo systemctl restart grafana-server
```

3. Access from mobile: `http://<PC_IP>:3000`

## 🔒 Security Considerations

### Enable Authentication

Grafana comes with authentication enabled by default. To configure:

1. Edit `/etc/grafana/grafana.ini`
2. Under `[auth]`, configure authentication method
3. Consider enabling HTTPS for production

### Firewall Rules

If using firewall, allow necessary ports:

```bash
sudo ufw allow 9090/tcp  # Prometheus
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9093/tcp  # Alertmanager
```

## 🐛 Troubleshooting

### Prometheus Not Scraping Targets

Check Prometheus targets: http://localhost:9090/targets

If targets are down:
1. Verify Rider-PC is running: `curl http://localhost:8000/healthz`
2. Verify Node Exporter: `curl http://localhost:9100/metrics`
3. Check Prometheus logs: `sudo journalctl -u prometheus -f`

### Grafana Dashboard Shows No Data

1. Verify data source connection in Grafana
2. Check Prometheus has data: http://localhost:9090/graph
3. Verify time range in dashboard
4. Check query syntax in panel

### High Resource Usage

If Prometheus uses too much memory:

1. Reduce retention period in `/etc/prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
storage:
  tsdb:
    retention.time: 15d  # Reduce from default 15d
```

2. Restart Prometheus: `sudo systemctl restart prometheus`

## 📚 Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Node Exporter Metrics](https://github.com/prometheus/node_exporter)
- [PromQL Queries](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)

## 🎯 Next Steps

After setup:

1. ✅ Verify all services are running
2. ✅ Import dashboards
3. ✅ Configure alerting
4. ✅ Set up notification channels
5. ✅ Create custom dashboards for your needs
6. ✅ Set up regular backups of Grafana dashboards

## 📊 Example Queries

Here are some useful Prometheus queries for Rider-PC:

```promql
# Average task processing time by provider
avg(rate(provider_task_duration_seconds_sum[5m])) by (provider)

# Task success rate
rate(provider_tasks_processed_total{status="completed"}[5m]) / 
rate(provider_tasks_processed_total[5m])

# Queue fullness percentage
(task_queue_size / 100) * 100

# Memory available in GB
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Disk usage percentage
100 - ((node_filesystem_avail_bytes{mountpoint="/"} / 
node_filesystem_size_bytes{mountpoint="/"}) * 100)
```

---

**Installation Complete!** 🎉

Your Grafana monitoring stack is now ready. Access the dashboard at http://localhost:3000 and start monitoring your Rider-PC infrastructure.
