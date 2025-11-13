# AI Model Setup Guide for Rider-PC

This guide covers how to set up and use the AI models integrated in Phase 4.

## Overview

Rider-PC supports three AI provider domains:
1. **Voice**: ASR (Speech-to-Text) and TTS (Text-to-Speech)
2. **Vision**: Object Detection and Frame Processing
3. **Text**: LLM Text Generation and NLU

All providers support **automatic fallback to mock mode** if models are unavailable.

---

## Quick Start (Mock Mode)

For development and testing without downloading models:

```bash
# No setup required! Providers automatically use mock mode
python -m pc_client.main
```

---

## Voice Provider Setup

### ASR (Automatic Speech Recognition) - Whisper

**Option 1: Automatic (Recommended)**
```bash
# Models download automatically on first use
# No manual setup required
```

**Option 2: Pre-download**
```python
import whisper
whisper.load_model("base")  # Downloads ~140MB
```

**Available Models**:
- `tiny`: 39M params, ~75MB - Fastest, lower accuracy
- `base`: 74M params, ~140MB - **Recommended** balance
- `small`: 244M params, ~460MB - Better accuracy
- `medium`: 769M params, ~1.5GB - High accuracy
- `large`: 1550M params, ~2.9GB - Best accuracy

### TTS (Text-to-Speech) - Piper

**Installation**:
```bash
# Ubuntu/Debian
sudo apt install piper-tts

# Or download binary from: https://github.com/rhasspy/piper
```

**Available Voices**: See [Piper Voices](https://rhasspy.github.io/piper-samples/)

---

## Vision Provider Setup

### Object Detection - YOLOv8

**Option 1: Automatic (Recommended)**
```bash
# Models download automatically on first use
# No manual setup required
```

**Option 2: Pre-download**
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # Downloads ~6MB
```

**Available Models**:
- `yolov8n`: 3.2M params, ~6MB - **Recommended** fastest
- `yolov8s`: 11.2M params, ~22MB - Small, balanced
- `yolov8m`: 25.9M params, ~50MB - Medium accuracy
- `yolov8l`: 43.7M params, ~84MB - Large, high accuracy
- `yolov8x`: 68.2M params, ~131MB - Extra large, best accuracy

---

## Text Provider Setup

### LLM - Ollama

**Installation**:

1. **Install Ollama**:
   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Or download from: https://ollama.com/download
   ```

2. **Pull a model**:
   ```bash
   # Lightweight model (Recommended for PC)
   ollama pull llama3.2:1b  # ~1.3GB
   
   # Or other models:
   ollama pull llama3.2:3b  # ~3.4GB
   ollama pull phi3:mini    # ~2.3GB
   ollama pull mistral:7b   # ~4.1GB
   ```

3. **Start Ollama server**:
   ```bash
   ollama serve
   # Server runs on http://localhost:11434
   ```

4. **Verify**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

**Available Models**:
- `llama3.2:1b`: 1B params - **Recommended** fastest
- `llama3.2:3b`: 3B params - Better quality
- `phi3:mini`: 3.8B params - Microsoft, good reasoning
- `mistral:7b`: 7B params - High quality
- `llama3.1:8b`: 8B params - Very high quality

See all models: https://ollama.com/library

---

## Configuration

### Voice Provider (`config/voice_provider.toml`)
```toml
[voice]
asr_model = "base"              # Whisper model
tts_model = "en_US-lessac-medium"  # Piper voice
sample_rate = 16000
use_mock = false                # Set true to force mock mode
```

### Vision Provider (`config/vision_provider.toml`)
```toml
[vision]
detection_model = "yolov8n"     # YOLO model
confidence_threshold = 0.5      # Detection confidence
max_detections = 10
use_mock = false                # Set true to force mock mode
```

### Text Provider (`config/text_provider.toml`)
```toml
[text]
model = "llama3.2:1b"           # Ollama model
max_tokens = 512
temperature = 0.7
ollama_host = "http://localhost:11434"
use_mock = false                # Set true to force mock mode
enable_cache = true
```

---

## Docker Setup

### Using Pre-downloaded Models

Edit `Dockerfile` to uncomment model download:
```dockerfile
# Download AI models (uncomment for faster startup)
RUN python -c "import whisper; whisper.load_model('base')"
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Using Ollama in Docker

Add to `docker-compose.yml`:
```yaml
environment:
  - OLLAMA_HOST=http://host.docker.internal:11434
```

Or run Ollama in Docker:
```yaml
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama-data:/root/.ollama
```

---

## Testing

### Test Voice Provider
```python
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = VoiceProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.VOICE_ASR,
    payload={"audio_data": "base64_audio_here"}
)

result = await provider.process_task(task)
print(result.result["text"])
```

### Test Vision Provider
```python
from pc_client.providers import VisionProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = VisionProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.VISION_DETECTION,
    payload={"image_data": "base64_image_here"}
)

result = await provider.process_task(task)
print(result.result["detections"])
```

### Test Text Provider
```python
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = TextProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.TEXT_GENERATE,
    payload={"prompt": "Explain robot navigation"}
)

result = await provider.process_task(task)
print(result.result["text"])
```

---

## Performance Tips

### CPU Optimization
- Use lightweight models (`yolov8n`, `whisper base`, `llama3.2:1b`)
- Reduce concurrent tasks in config
- Enable caching for repeated queries

### Memory Management
- Monitor model memory usage: `nvidia-smi` (GPU) or `htop` (CPU)
- Adjust `max_concurrent_tasks` based on available RAM
- Use smaller models if memory limited

### Storage
- Models cache in:
  - Whisper: `~/.cache/whisper/`
  - YOLO: `~/.cache/ultralytics/`
  - Ollama: `~/.ollama/models/`
- Clear cache if disk space limited

---

## Troubleshooting

### Whisper fails to load
```bash
# Reinstall with specific version
pip install --upgrade openai-whisper

# Or use mock mode
use_mock = true
```

### YOLO download fails
```bash
# Manual download
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Check internet connection
# Check disk space
```

### Ollama connection error
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check model is pulled
ollama list
```

### Out of memory
- Use smaller models
- Reduce `max_concurrent_tasks`
- Enable swap (WSL: increase `.wslconfig` memory)
- Use mock mode for testing

---

## Model Storage Locations

- **Whisper**: `~/.cache/whisper/`
- **YOLOv8**: `~/.cache/ultralytics/`
- **Ollama**: `~/.ollama/models/`
- **Piper**: System-dependent, check `/usr/share/piper/`

Total storage for recommended models: ~2-3GB

---

## Next Steps

1. Choose your deployment mode (mock or real models)
2. Install required dependencies
3. Update configuration files
4. Test providers individually
5. Deploy with Docker Compose

See [IMPLEMENTATION_COMPLETE_PHASE4.md](PR/IMPLEMENTATION_COMPLETE_PHASE4.md) for full deployment guide.
