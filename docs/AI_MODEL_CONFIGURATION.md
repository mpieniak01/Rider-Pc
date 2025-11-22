# AI Model Configuration Guide for Rider-PC

This guide describes how to configure and use AI models integrated in Phase 4.

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
# No configuration required! Providers automatically use mock mode
python -m pc_client.main
```

---

## Voice Provider Configuration

### ASR (Automatic Speech Recognition) - Whisper

**Option 1: Automatic (Recommended)**
```bash
# Models download automatically on first use
# No manual configuration required
```

**Option 2: Pre-download**
```python
import whisper
whisper.load_model("base")  # Downloads ~140MB
```

**Available Models**:
- `tiny`: 39M parameters, ~75MB - Fastest, lower accuracy
- `base`: 74M parameters, ~140MB - **Recommended** balance
- `small`: 244M parameters, ~460MB - Better accuracy
- `medium`: 769M parameters, ~1.5GB - High accuracy
- `large`: 1550M parameters, ~2.9GB - Best accuracy

### TTS (Text-to-Speech) - Piper

**Installation**:
```bash
# Ubuntu/Debian
sudo apt install piper-tts

# Or download binary from: https://github.com/rhasspy/piper
```

**Available Voices**: See [Piper Voices](https://rhasspy.github.io/piper-samples/)

---

## Vision Provider Configuration

### Object Detection - YOLOv8

**Option 1: Automatic (Recommended)**
```bash
# Models download automatically on first use
# No manual configuration required
```

**Option 2: Pre-download**
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # Downloads ~6MB
```

**Available Models**:
- `yolov8n`: 3.2M parameters, ~6MB - **Recommended** fastest
- `yolov8s`: 11.2M parameters, ~22MB - Small, balanced
- `yolov8m`: 25.9M parameters, ~50MB - Medium accuracy
- `yolov8l`: 43.7M parameters, ~84MB - Large, high accuracy
- `yolov8x`: 68.2M parameters, ~131MB - Extra large, best accuracy

---

## Text Provider Configuration

### LLM - Ollama

**Installation**:

1. **Install Ollama**:
   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Or download from: https://ollama.com/download
   ```

2. **Pull model**:
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
   # Server runs at http://localhost:11434
   ```

4. **Verify**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

**Available Models**:
- `llama3.2:1b`: 1B parameters - **Recommended** fastest
- `llama3.2:3b`: 3B parameters - Better quality
- `phi3:mini`: 3.8B parameters - Microsoft, good reasoning
- `mistral:7b`: 7B parameters - High quality
- `llama3.1:8b`: 8B parameters - Very high quality

See all models: https://ollama.com/library

---

## Configuration (`config/providers.toml`)

### Voice Provider (section `[voice]`)
```toml
[voice]
asr_model = "base"              # Whisper model
tts_model = "en_US-lessac-medium"  # Piper voice
sample_rate = 16000
use_mock = false                # Set true to force mock mode
```

### Vision Provider (section `[vision]`)
```toml
[vision]
detection_model = "yolov8n"     # YOLO model
confidence_threshold = 0.5      # Detection confidence
max_detections = 10
use_mock = false                # Set true to force mock mode
```

### Text Provider (section `[text]`)
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

## Docker Configuration

### Using Pre-downloaded Models

Edit `Dockerfile` to uncomment model downloads:
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
- Reduce concurrent tasks in configuration
- Enable caching for repeated queries

### Memory Management
- Monitor model memory usage: `nvidia-smi` (GPU) or `htop` (CPU)
- Adjust `max_concurrent_tasks` based on available RAM
- Use smaller models if memory limited

### Storage
- Models cached in:
  - Whisper: `~/.cache/whisper/`
  - YOLO: `~/.cache/ultralytics/`
  - Ollama: `~/.ollama/models/`
- Clear cache if disk space limited

---

## Troubleshooting

### Whisper won't load
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
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check if model is downloaded
ollama list
```

### Out of memory
- Use smaller models
- Reduce `max_concurrent_tasks`
- Enable swap (WSL: increase memory in `.wslconfig`)
- Use mock mode for testing

---

## Model Storage Locations

- **Whisper**: `~/.cache/whisper/`
- **YOLOv8**: `~/.cache/ultralytics/`
- **Ollama**: `~/.ollama/models/`
- **Piper**: System-dependent, check `/usr/share/piper/`

Total space for recommended models: ~2-3GB

---

## Next Steps

1. Choose deployment mode (mock or real models)
2. Install required dependencies
3. Update configuration files
4. Test providers individually
5. Deploy with Docker Compose

See [IMPLEMENTATION_COMPLETE_PHASE4.md](archive/PR/IMPLEMENTATION_COMPLETE_PHASE4.md) for full deployment guide.
