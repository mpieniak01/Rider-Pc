# AI Provider Layer Implementation Guide

## Overview

This guide explains how to use and extend the AI Provider Layer for offloading computational tasks from Rider-PI to PC.

## Architecture

```
Rider-PI Device                    PC Client (WSL)
┌──────────────┐                  ┌──────────────────────┐
│ Voice App    │─────REST/ZMQ────→│  Task Queue          │
│ Vision App   │                  │  (Priority-based)    │
│ Navigator    │                  └──────────┬───────────┘
└──────────────┘                             │
                                             ↓
                                  ┌──────────────────────┐
                                  │  Task Queue Worker   │
                                  └──────────┬───────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     ↓                       ↓                       ↓
              ┌─────────────┐         ┌──────────────┐       ┌─────────────┐
              │Voice Provider│        │Vision Provider│       │Text Provider│
              │ (ASR/TTS)    │        │(Detection)    │       │(LLM/NLU)    │
              └──────┬───────┘        └──────┬────────┘       └──────┬──────┘
                     │                       │                       │
                     └───────────────────────┴───────────────────────┘
                                             │
                                    Results via ZMQ
                                             │
                                             ↓
                                      Rider-PI Device
```

## Quick Start

### 1. Enable Providers

Update your `.env` file:

```bash
# Enable AI providers
ENABLE_PROVIDERS=true

# Optional: Specify models (default: mock)
VOICE_MODEL=whisper-base
VISION_MODEL=yolov8n
TEXT_MODEL=llama-2-7b

# Enable task queue
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
TASK_QUEUE_HOST=localhost
TASK_QUEUE_PORT=6379
```

### 2. Setup Task Queue Broker

Choose between Redis (development) or RabbitMQ (production).

#### Redis Setup
```bash
# Install Redis
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server

# Test connection
redis-cli ping
# Should return: PONG
```

See [TASK_QUEUE_SETUP.md](TASK_QUEUE_SETUP.md) for detailed instructions.

### 3. Run with Providers

```bash
# Start PC client with providers enabled
python -m pc_client.main
```

## Task Envelope Format

All tasks use a unified JSON envelope format:

```python
from pc_client.providers.base import TaskEnvelope, TaskType

task = TaskEnvelope(
    task_id="unique-task-id",
    task_type=TaskType.VOICE_ASR,
    payload={
        "audio_data": "base64_encoded_audio",
        "format": "wav",
        "sample_rate": 16000
    },
    meta={
        "source": "rider-pi",
        "timestamp": 1234567890.0
    },
    priority=5  # 1 (highest) to 10 (lowest)
)
```

## Task Types

### Voice Tasks

**ASR (Speech-to-Text)**
```python
TaskType.VOICE_ASR
payload = {
    "audio_data": "base64_audio",
    "format": "wav|raw",
    "sample_rate": 16000
}
```

**TTS (Text-to-Speech)**
```python
TaskType.VOICE_TTS
payload = {
    "text": "Hello world",
    "voice": "default",
    "speed": 1.0
}
```

### Vision Tasks

**Object Detection**
```python
TaskType.VISION_DETECTION
payload = {
    "image_data": "base64_image",
    "format": "jpeg|png",
    "width": 640,
    "height": 480
}
```

**Frame Processing (for obstacle avoidance)**
```python
TaskType.VISION_FRAME
payload = {
    "frame_data": "base64_frame",
    "frame_id": 123,
    "timestamp": 1234567890.0
}
```

### Text Tasks

**Text Generation (LLM)**
```python
TaskType.TEXT_GENERATE
payload = {
    "prompt": "What is the weather?",
    "max_tokens": 512,
    "temperature": 0.7,
    "system_prompt": "You are a helpful assistant"
}
```

**Natural Language Understanding**
```python
TaskType.TEXT_NLU
payload = {
    "text": "Go to the kitchen",
    "tasks": ["intent", "entities", "sentiment"]
}
```

## Priority Levels

Tasks are processed based on priority (1 = highest, 10 = lowest):

- **Priority 1-3 (Critical)**: Obstacle avoidance, emergency stops
- **Priority 4-6 (Normal)**: Voice commands, object detection
- **Priority 7-10 (Background)**: Text generation, logging

Example:
```python
# Critical obstacle avoidance task
task = TaskEnvelope(
    task_id="obstacle-123",
    task_type=TaskType.VISION_FRAME,
    payload=frame_data,
    priority=1  # Will be processed first
)
```

## Creating Custom Providers

### Step 1: Extend BaseProvider

```python
from pc_client.providers.base import (
    BaseProvider,
    TaskEnvelope,
    TaskResult,
    TaskType,
    TaskStatus
)

class CustomProvider(BaseProvider):
    def __init__(self, config=None):
        super().__init__("CustomProvider", config)
        # Your initialization here
    
    async def _initialize_impl(self):
        """Load models, setup connections, etc."""
        self.logger.info("[provider] Loading custom models...")
        # Load your models here
    
    async def _shutdown_impl(self):
        """Cleanup resources."""
        self.logger.info("[provider] Cleaning up custom resources...")
        # Cleanup here
    
    async def _process_task_impl(self, task: TaskEnvelope) -> TaskResult:
        """Process the task."""
        # Your processing logic here
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"output": "processed data"}
        )
    
    def get_supported_tasks(self):
        """Return list of supported task types."""
        return [TaskType.VOICE_ASR, TaskType.VOICE_TTS]
```

### Step 2: Register Provider

```python
# In your application startup
from pc_client.providers import CustomProvider
from pc_client.queue import TaskQueue
from pc_client.queue.task_queue import TaskQueueWorker

# Initialize
custom_provider = CustomProvider(config={...})
await custom_provider.initialize()

# Add to worker
providers = {
    "custom": custom_provider,
    # ... other providers
}

queue = TaskQueue(max_size=100)
worker = TaskQueueWorker(queue, providers)
await worker.start()
```

## Integration with Actual Models

### Voice Provider with Whisper

```python
from pc_client.providers.voice_provider import VoiceProvider
import whisper

class WhisperVoiceProvider(VoiceProvider):
    async def _initialize_impl(self):
        self.logger.info(f"[voice] Loading Whisper model: {self.asr_model}")
        self.asr = whisper.load_model(self.asr_model)
    
    async def _process_asr(self, task):
        import base64
        import numpy as np
        
        # Decode audio
        audio_bytes = base64.b64decode(task.payload["audio_data"])
        audio = np.frombuffer(audio_bytes, dtype=np.float32)
        
        # Transcribe
        result = self.asr.transcribe(audio)
        
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "text": result["text"],
                "confidence": 0.95,
                "language": result["language"]
            }
        )
```

### Vision Provider with YOLO

```python
from pc_client.providers.vision_provider import VisionProvider
from ultralytics import YOLO

class YOLOVisionProvider(VisionProvider):
    async def _initialize_impl(self):
        self.logger.info(f"[vision] Loading YOLO model: {self.detection_model}")
        self.detector = YOLO(self.detection_model)
    
    async def _process_detection(self, task):
        import base64
        import cv2
        import numpy as np
        
        # Decode image
        img_bytes = base64.b64decode(task.payload["image_data"])
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        # Detect objects
        results = self.detector(img)
        
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "class": r.names[int(box.cls)],
                    "confidence": float(box.conf),
                    "bbox": box.xyxy[0].tolist()
                })
        
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "detections": detections,
                "num_detections": len(detections)
            }
        )
```

### Text Provider with LLM

```python
from pc_client.providers.text_provider import TextProvider
from transformers import pipeline

class LLMTextProvider(TextProvider):
    async def _initialize_impl(self):
        self.logger.info(f"[provider] Loading LLM: {self.model}")
        self.llm = pipeline("text-generation", model=self.model)
    
    async def _process_generate(self, task):
        prompt = task.payload["prompt"]
        max_tokens = task.payload.get("max_tokens", self.max_tokens)
        
        # Generate
        result = self.llm(
            prompt,
            max_new_tokens=max_tokens,
            temperature=self.temperature
        )
        
        generated_text = result[0]["generated_text"]
        
        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "text": generated_text,
                "tokens_used": len(generated_text.split())
            }
        )
```

## Circuit Breaker and Fallback

The circuit breaker automatically detects provider failures and triggers fallback:

```python
from pc_client.queue.circuit_breaker import CircuitBreakerConfig

# Configure circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    success_threshold=2,      # Close after 2 successes
    timeout_seconds=60        # Try again after 60s
)

# Use with task queue
queue = TaskQueue(
    max_size=100,
    enable_circuit_breaker=True
)
```

When circuit is OPEN:
1. Task returns with `status=FAILED`
2. Error message: "Circuit breaker open, use local processing"
3. Meta includes: `fallback_required: true`
4. Rider-PI should process task locally

## Telemetry and Monitoring

### Provider Telemetry

```python
# Get provider telemetry
telemetry = provider.get_telemetry()
# Returns:
# {
#     "provider": "VoiceProvider",
#     "initialized": true,
#     "supported_tasks": ["voice.asr", "voice.tts"],
#     "asr_model": "whisper-base",
#     "tts_model": "tacotron2"
# }
```

### Queue Statistics

```python
# Get queue stats
stats = queue.get_stats()
# Returns:
# {
#     "total_queued": 1000,
#     "total_processed": 980,
#     "total_failed": 20,
#     "current_size": 5,
#     "queue_full_count": 0,
#     "circuit_breaker": {
#         "state": "closed",
#         "failure_count": 0
#     }
# }
```

### Task Results

Every task result includes:
```python
result = TaskResult(
    task_id="...",
    status=TaskStatus.COMPLETED,
    result={...},
    processing_time_ms=150.5,  # How long it took
    meta={
        "model": "whisper-base",
        "...": "..."
    }
)
```

## Performance Optimization

### 1. Batch Processing

Process multiple tasks together:
```python
async def process_batch(tasks):
    results = await asyncio.gather(*[
        provider.process_task(task)
        for task in tasks
    ])
    return results
```

### 2. Model Caching

Implement LRU cache for repeated requests:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_inference(input_hash):
    return model.predict(input_hash)
```

### 3. GPU Utilization

Use GPU when available:
```python
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)
```

## Security Considerations

1. **Validate Input**: Always validate task payloads
2. **Limit Size**: Set maximum payload sizes
3. **Rate Limiting**: Implement per-source rate limits
4. **Sanitize Output**: Clean sensitive data from results
5. **Secure Channel**: Use VPN/mTLS (see [NETWORK_SECURITY_SETUP.md](NETWORK_SECURITY_SETUP.md))

## Troubleshooting

### Provider Not Initializing

```bash
# Check logs
LOG_LEVEL=DEBUG python -m pc_client.main

# Look for [provider] initialization messages
```

### Tasks Not Processing

```bash
# Check queue stats
# In Python console:
>>> from pc_client.queue import TaskQueue
>>> queue.get_stats()
```

### High Latency

1. Check model size (use smaller models for faster inference)
2. Enable GPU acceleration
3. Adjust priority levels
4. Increase worker count

### Circuit Breaker Always Open

1. Check provider health: `provider.get_telemetry()`
2. Review error logs
3. Test provider independently
4. Adjust circuit breaker thresholds

## Examples

See complete examples in `pc_client/tests/test_integration.py`:
- End-to-end voice offload
- End-to-end vision offload
- End-to-end text offload
- Priority queue handling
- Circuit breaker fallback

## References

- [Provider Base Classes](pc_client/providers/base.py)
- [Task Queue Implementation](pc_client/queue/task_queue.py)
- [Circuit Breaker Pattern](pc_client/queue/circuit_breaker.py)
- [Network Security Setup](NETWORK_SECURITY_SETUP.md)
- [Task Queue Setup](TASK_QUEUE_SETUP.md)
- [Monitoring Setup](MONITORING_SETUP.md)
