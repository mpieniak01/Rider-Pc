# Rider-PI PC Client — Architecture Solution

## Related Project
https://github.com/mpieniak01/Rider-Pi 

## Architectural Concept

**Rider-PC is an autonomous Digital Twin system**, not a "UI replicator fetching interface from Rider-Pi".

### Key architectural features:
- **Independent web application**: Serves local static files (HTML/JS/CSS) from the `web/` directory
- **Data Synchronization (Data Sync)**: Fetches only state/data from Rider-Pi (REST + ZMQ), not interface code
- **Own technology stack**: Redis, Prometheus, Grafana, SQLite Cache, AI models
- **Bidirectional communication**: Not only displays data but processes AI tasks and sends back results
- **Processing Offload**: Vision (YOLOv8), Voice (Whisper/Piper), Text (Ollama) run locally on PC

Rider-PC **does not** fetch HTML/JS files from Rider-Pi at runtime. The UI was copied once during development phase, and updates require repository changes.

## 1. System Layer (Windows 11 + WSL2 Debian)
- Windows runs WSL2 virtual machine with Debian distribution, where the Python 3.9 client code is maintained.
- WSL network enables direct IP communication (LAN/VPN) between Rider-PI and PC.
- PC computational resources (CPU/GPU) are available to WSL; enable GPU support if needed (`wsl --install --webgpu`).

## 2. Application Layer in WSL (Python 3.9)
### 2.1 Rider-PI API Adapter
- Module consuming REST (`/healthz`, `/api/control`, `/api/chat/*`) and ZMQ streams (ports 5555/5556).
- Ensures contract compatibility with Rider-PI services and maps bus topics to local events.

### 2.2 Local Web Client (Digital Twin)
- FastAPI server (`pc_client/api/server.py`) serving static files directly from local `web/` directory.
- UI is not fetched from Rider-Pi in real-time — code replication was a one-time operation during development phase.
- Operating mechanism is Data Sync: PC has a local CacheManager (SQLite), which is fed with data from Rider-Pi via REST API and ZMQ streams, and UI queries the local PC API.
- Data comes from local Cache buffer; UI is exposed on PC local network on port 8000.

### 2.3 Data Buffer/Cache
- Lightweight database (Redis/SQLite) storing current screen states, snapshots (`data/`, `snapshots/`) and raw data streams.
- Enables fast UI reconstruction and packet buffering for AI providers.

### 2.4 PROVIDER Layer (Voice/Text/Vision) - AI Offload
Rider-PC is an **autonomous AI processing system**, not just a data display. PC processes tasks offloaded from Rider-Pi using its own computational resources:

- **Vision Provider** (`pc_client/providers/vision_provider.py`):
  - Processes images from `vision.frame.offload` events received via ZMQ
  - Implementation: YOLOv8 for object detection, with mock mode support
  - Results published back to Rider-Pi via ZMQ as `vision.obstacle.enhanced`
  - Configuration: `ENABLE_VISION_OFFLOAD=true`, YOLOv8n model or mock
  
- **Voice Provider** (`pc_client/providers/voice_provider.py`):
  - Offload ASR (Automatic Speech Recognition) and TTS (Text-to-Speech)
  - Implementation: Whisper (ASR) + Piper (TTS), with mock support
  - Receives: `voice.asr.request` (audio chunk) and `voice.tts.request` (text)
  - Publishes: `voice.asr.result` (transcription) and `voice.tts.chunk` (audio)
  - Configuration: `ENABLE_VOICE_OFFLOAD=true`, Whisper base + Piper models
  
- **Text Provider** (`pc_client/providers/text_provider.py`):
  - Local NLU/NLG models (Ollama, Transformers) or proxy to cloud APIs
  - REST endpoint `/providers/text/generate` for chat queries
  - Used by Rider-Pi when AI Mode is enabled
  - Configuration: `ENABLE_TEXT_OFFLOAD=true`, Ollama model or mock

**Offload architecture:** Rider-PC is not a passive "mirror" - it actively processes data and returns enriched results. Bidirectional communication via ZMQ (`telemetry.zmq_publisher.py`) allows the robot to immediately use the results.

### 2.5 Task Queue
- Broker (RabbitMQ/Redis) and Celery/Arq layer for asynchronous task offloading.
- Provides buffering and load balancing between providers.

## 3. Communication and Integration Layer

### 3.0 Port and Service Map
The system uses the following ports and endpoints:

| Service | Port | Type | Description |
|---------|------|------|-------------|
| **Rider-PC UI** | 8000 | Local | FastAPI entry point for operator (Web UI) |
| **Rider-Pi API** | 8080 | Remote | Robot REST API (query target) |
| **ZMQ PUB** | 5555 | Remote | Event publication from Rider-Pi (vision.*, motion.*) |
| **ZMQ SUB** | 5556 | Remote | Response subscription (optional) |
| **ZMQ Telemetry** | 5557 | Local | Offload results publication from PC to Pi |
| **Redis** | 6379 | Local | Task queue and cache broker |
| **Prometheus** | 9090 | Local | Monitoring metrics collection |
| **Grafana** | 3000 | Local | Metrics visualization and dashboards |

**Note:** Local ports (8000, 6379, 9090, 3000, 5557) operate on PC network. Remote ports (8080, 5555, 5556) point to Rider-Pi (configured via `RIDER_PI_HOST`).

### 3.1 Incoming Channels from Rider-PI
- REST (port 8080) tunneled via VPN/mTLS.
- ZMQ PUB/SUB stream (5555/5556) with topics `vision.*`, `voice.*`, `motion.state`, `robot.pose`.
- File transfer (SFTP/rsync/HTTP static) from `data/`, `snapshots/` directories.

### 3.2 Outgoing Channels to Rider-PI
- REST (`/api/control`, `/api/chat/*`) for commands and enhanced AI service responses.
- ZMQ PUB with topics like `vision.obstacle.enhanced`, `voice.tts.chunk`, `events.sentiment.offload`.
- Returning result files (audio, maps) via SFTP/HTTP PUT channel.

### 3.3 Data Synchronization Mechanism (Data Sync Loop)
Rider-PC system synchronizes data with Rider-Pi through two main mechanisms:

#### 3.3.1 Periodic Synchronization Loop (sync_data_periodically)
The `sync_data_periodically` function in `pc_client/api/lifecycle.py` executes every **2 seconds** and fetches the following data:
- `/healthz` - system health status
- `/state` - current robot state (tracking, navigator, camera)
- `/sysinfo` - system information
- `/api/vision/snap/info` - vision snapshot information
- `/api/vision/obstacle` - obstacle detection data
- `/api/app-metrics` - application metrics
- `/api/resources/camera` - camera resource status
- `/api/bus/health` - communication bus health

All fetched data is stored in local **CacheManager (SQLite)** with TTL defaulting to 30 seconds.

#### 3.3.2 ZMQ Subscriber (Real-Time Events)
The `ZmqSubscriber` class in `pc_client/adapters/zmq_subscriber.py` listens for real-time events:
- Subscribes to topics: `vision.*`, `voice.*`, `motion.*`, `robot.*`, `navigator.*`
- Received events are immediately saved to Cache under key `zmq:{topic}`
- For offload tasks (e.g., `vision.frame.offload`, `voice.asr.request`) data is routed to the task queue

#### 3.3.3 API Endpoint Division
- **Read endpoints (GET)**: Serve data directly from local Cache (e.g., `/api/state`, `/api/sysinfo`)
- **Control endpoints (POST)**: Act as **Proxy** - forward commands to Rider-Pi and return response (e.g., `/api/control`, `/api/chat/*`)
- **Provider endpoints**: Process data locally and publish results via ZMQ Telemetry

## 4. Data Flows

### 4.1 Dashboard Synchronization (Data Sync)
1. **Rider-Pi** publishes state via REST API (`/state`, `/healthz`, `/sysinfo`) and ZMQ events (`vision.*`, `motion.*`)
2. **PC Cache** (SQLite) updated every 2s by `sync_data_periodically` + real-time by `ZmqSubscriber`
3. **Web UI** (local HTML/JS files in `web/`) queries local PC API (port 8000)
4. User's **Browser** renders data from local PC Cache

**Key:** UI does not fetch HTML/JS from Rider-Pi in real-time. Only **state data** is synchronized, not interface code.

### 4.2 Voice Offload (Voice Pipeline)
1. Rider-Pi publishes ZMQ event: `voice.asr.request` (audio chunk) or `voice.tts.request` (text)
2. PC `ZmqSubscriber` receives and enqueues to `TaskQueue` (Redis)
3. `VoiceProvider` processes via Whisper (ASR) or Piper (TTS)
4. Result published by `ZMQTelemetryPublisher` as `voice.asr.result` / `voice.tts.chunk`
5. Rider-Pi receives result and uses in voice application

### 4.3 Vision Offload (Vision Pipeline)
1. Rider-Pi publishes `vision.frame.offload` with image + tracking metadata
2. PC enqueues task with priority (default 1)
3. `VisionProvider` performs detection (YOLOv8) considering tracking state
4. Enriched data (`vision.obstacle.enhanced`) published back to Pi
5. Rider-Pi uses results in navigator/mapper

### 4.4 Text Offload (Text/LLM Pipeline)
1. Rider-Pi sends REST POST query to `/providers/text/generate`
2. PC `TextProvider` processes via Ollama/Transformers locally
3. Response returned synchronously via REST
4. Rider-Pi displays response in interface (web/face)

## 5. Extensibility and Management
- Implement providers as plugins (`providers/`), registered during startup.
- Version contracts (JSON schemas) and negotiate capabilities with Rider-PI.
- Ensure telemetry and logging consistent with prefixes `[api]`, `[bridge]`, `[vision]`, `[voice]`, `[provider]`.

## 6. Environment Installation (summary)
- WSL Debian installation: `wsl --install -d Debian`, then `wsl --update`.
- In WSL execute: `sudo apt update && sudo apt upgrade -y`.
- Install base and ML packages: `sudo apt install -y build-essential python3.9 python3.9-venv python3.9-dev git curl wget unzip pkg-config cmake ninja-build libzmq3-dev libssl-dev libffi-dev libjpeg-dev zlib1g-dev libgl1 libglib2.0-0 libopenblas-dev libsndfile1 ffmpeg alsa-utils portaudio19-dev`.
- (Optional) GPU: `sudo apt install -y nvidia-cuda-toolkit nvidia-cudnn`.
- Create Python environment: `python3.9 -m venv ~/venvs/rider-pi-pc && source ~/venvs/rider-pi-pc/bin/activate && pip install --upgrade pip`.

## 7. Configuration and Further Work
- Configure secure network channels, REST/ZMQ adapters, task queue, and monitoring (Prometheus/Grafana).
- Prepare CI/CD pipeline for builds and tests, and operational runbooks.
