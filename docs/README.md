# Rider-PC Client

> **Autonomous Digital Twin System** for the Rider-Pi robot with AI processing and task offloading

PC-side client infrastructure for the Rider-Pi robot, providing:
- 🔌 REST API Adapter and ZMQ Subscriber for real-time data synchronization
- 💾 Local SQLite cache for state buffering
- 🌐 FastAPI web server serving the user interface
- �� **AI Provider Layer** with real ML models (Voice, Vision, Text)
- 🚀 **Production-ready deployment** with Docker and CI/CD

## 🎯 Project Goal

Rider-PC is **not** just a simple data display for the robot. It's an autonomous AI processing system that:
- Accepts computational tasks offloaded from Rider-Pi (Vision, Voice, Text)
- Processes them locally using PC resources (CPU/GPU)
- Returns enriched results back to the robot in real-time
- Operates as a Digital Twin with its own interface and technology stack

## 📊 Current Status

### ✅ Phase 4 Complete - Real AI Models and Production Deployment

- ✅ **Real AI Models**: Whisper ASR, Piper TTS, YOLOv8 Vision, Ollama LLM
- ✅ **Docker Deployment**: Complete stack with Redis, Prometheus, Grafana
- ✅ **CI/CD Pipeline**: Automated testing, security scanning, Docker builds
- ✅ **Health Probes**: Kubernetes-ready liveness and readiness endpoints
- ✅ **Automatic Fallback**: Mock mode when models unavailable
- ✅ **Circuit Breaker**: Automatic switching on failures
- ✅ **Telemetry**: Real-time Prometheus metrics

See details in [archive/PR/IMPLEMENTATION_COMPLETE_PHASE4.md](archive/PR/IMPLEMENTATION_COMPLETE_PHASE4.md)

## 🚀 Quick Start

**Option 1: Docker (Recommended for production)**
```bash
echo "RIDER_PI_HOST=192.168.1.100" > .env
docker-compose up -d
# Interface: http://localhost:8000
```

**Option 2: Local environment (Development)**
```bash
pip install -r requirements.txt
python -m pc_client.main
```

Full instructions: [QUICKSTART.md](QUICKSTART.md)

## 📚 Documentation - Table of Contents

### Basics
- **[QUICKSTART.md](QUICKSTART.md)** - Installation and first run (Docker + Local)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System concepts, layers, data flows
- **[PC_OFFLOAD_INTEGRATION.md](PC_OFFLOAD_INTEGRATION.md)** - Technical details of Rider-Pi communication protocol

### Configuration
- **[CONFIGURATION.md](CONFIGURATION.md)** - 📋 **Configuration Hub** - central guide for all configuration aspects
  - [AI_MODEL_CONFIGURATION.md](AI_MODEL_CONFIGURATION.md) - Whisper, Piper, YOLOv8, Ollama
  - [SECURITY_CONFIGURATION.md](SECURITY_CONFIGURATION.md) - WireGuard VPN, mTLS
  - [TASK_QUEUE_CONFIGURATION.md](TASK_QUEUE_CONFIGURATION.md) - Redis, RabbitMQ
  - [MONITORING_CONFIGURATION.md](MONITORING_CONFIGURATION.md) - Prometheus, Grafana

### Management
- **[SERVICE_AND_RESOURCE_MANAGEMENT.md](SERVICE_AND_RESOURCE_MANAGEMENT.md)** - Operations, monitoring, troubleshooting

### API Specifications
- **[api-specs/](api-specs/)** - Detailed REST endpoint specifications
  - [api-specs/README.md](api-specs/README.md) - API overview
  - [api-specs/CONTROL.md](api-specs/CONTROL.md) - Control API
  - [api-specs/NAVIGATOR.md](api-specs/NAVIGATOR.md) - Navigator API

### Notes and Plans
- [REPLICATION_NOTES.md](REPLICATION_NOTES.md) - Technical notes on replication mechanisms
- [FUTURE_WORK.md](FUTURE_WORK.md) - Planned improvements and development

### Archive
- **[archive/PR/](archive/PR/)** - Historical deployment reports (Phases 1-4)
  - Deployment statuses for each phase
  - Provider implementation guides
  - Completed phase summaries

## 🏗️ Architecture (Summary)

```
┌─────────────────────────────────────────┐
│           Rider-Pi (Robot)              │
│  REST API (8080) + ZMQ PUB (5555/5556)  │
└─────────────────────────────────────────┘
         │ Data Sync           │ Offload Tasks
         ▼                     ▼
┌─────────────────────────────────────────┐
│         Rider-PC (PC Client)            │
│  ┌───────────────────────────────────┐  │
│  │  Adapter Layer                    │  │
│  │  • REST Client • ZMQ Subscriber   │  │
│  └───────────────────────────────────┘  │
│           │ Cache (SQLite)  │            │
│  ┌───────────────────────────────────┐  │
│  │  FastAPI Server + Web UI          │  │
│  │  http://localhost:8000            │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  AI Provider Layer                │  │
│  │  • Vision (YOLOv8)                │  │
│  │  • Voice (Whisper/Piper)          │  │
│  │  • Text (Ollama)                  │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Infrastructure                   │  │
│  │  • Redis • Prometheus • Grafana   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │ Results (ZMQ)
         ▼
┌─────────────────────────────────────────┐
│  Rider-Pi receives enriched data        │
│  (vision.obstacle.enhanced, etc.)       │
└─────────────────────────────────────────┘
```

Full description: [ARCHITECTURE.md](ARCHITECTURE.md)

## 🔑 Key Features

### AI Processing Offload
- **Vision**: YOLOv8 object detection, obstacle classification
- **Voice**: ASR (Whisper) and TTS (Piper) with low latency
- **Text**: Local LLM (Ollama) for NLU/NLG

### Data Synchronization
- REST loop every 2s fetches state from Rider-Pi
- Real-time events via ZMQ (vision.*, motion.*, robot.*)
- Local SQLite cache with TTL for fast access

### Reliability
- Circuit Breaker - automatic fallback on errors
- Mock Mode - testing without real models
- Heartbeat - PC availability monitoring
- Priority Queue - critical tasks first

### Monitoring
- Prometheus metrics (50+ metrics)
- Grafana dashboards
- Alerts for anomalies
- Structured logs

## 🛠️ Technologies

- **Backend**: Python 3.9+, FastAPI, SQLite
- **AI Models**: Whisper, Piper, YOLOv8, Ollama
- **Communication**: ZMQ (pub/sub), REST API
- **Queue**: Redis / RabbitMQ
- **Monitoring**: Prometheus, Grafana
- **Deployment**: Docker, Docker Compose
- **Testing**: pytest, Playwright

## 📋 Requirements

- Python 3.9+
- WSL2 with Debian (for Windows users)
- Network access to Rider-Pi
- Docker (optional, for full stack)
- 2-3GB space for AI models (optional)

## 🤝 Related Project

- **Rider-Pi**: https://github.com/mpieniak01/Rider-Pi

## 📝 License

This project is part of the Rider-Pi ecosystem.

---

**Last update**: 2025-11-22  
**Status**: ✅ Phase 4 - Production Ready
