# Rider-PC Offload Integration Guide

This document explains how the Rider-PC stack mirrors Rider-Pi’s AI mode and provider controls, and how to validate end-to-end offload flows.

## Overview

Rider-Pi exposes a provider registry (`/api/system/ai-mode`, `/api/providers/*`) and a deterministic ZMQ contract (see `Rider-Pi/docs/OFFLOAD_PROVIDER_PROTOCOL.md`). Rider-PC implements the PC-side responsibilities:

- Serves an identical control panel (`web/control.html`) with **Tryb AI** and **Provider Control** cards.
- Proxies REST calls to Rider-Pi via `pc_client.adapters.rest_adapter.RestAdapter`.
- Runs AI workloads (voice, vision, text) and publishes enhanced data back to Rider-Pi via ZMQ (`vision.obstacle.enhanced`, `voice.asr.result`, etc.).

## Configuration

1. **Point to Rider-Pi**
   ```bash
   export RIDER_PI_HOST="192.168.1.100"
   export RIDER_PI_PORT="8080"
   ```
   (or edit `.env`)

2. **Start local stack**
   ```bash
   make start
   # UI: http://localhost:8000/web/control.html
   ```

3. **Optional**: enable real providers (`ENABLE_PROVIDERS=true`, Redis, etc.) as documented in `docs/AI_MODEL_SETUP.md`.

## Vision Offload Runtime (Rider-PC)

Set these flags in `.env` to ingest `vision.frame.offload` and publish `vision.obstacle.enhanced`:

```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
ENABLE_VISION_OFFLOAD=true
ENABLE_TELEMETRY=true             # or rely on auto-enable via ENABLE_VISION_OFFLOAD
TELEMETRY_ZMQ_HOST=$RIDER_PI_HOST # bus XSUB endpoint exposed by Rider-Pi
```

On startup Rider-PC creates:

1. `TaskQueue` (`pc_client.queue.task_queue.TaskQueue`) sized by `TASK_QUEUE_MAX_SIZE`.
2. `VisionProvider` configured from `[vision]` section in `config/providers.toml` (mock mode when `VISION_MODEL=mock`).
3. `TaskQueueWorker` + `ZMQTelemetryPublisher` which links task results to the Rider-Pi broker.
4. A ZMQ handler for `vision.frame.offload` that wraps frames into `TaskEnvelope` instances and enqueues them with `frame_priority`.

Results flow back via `ZMQTelemetryPublisher.publish_vision_obstacle_enhanced`, so navigator consumes the enhanced topic immediately after each frame is processed.

## Voice Offload Runtime (ASR/TTS)

To stream audio to Rider-PC and replay the synthesized response:

```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
ENABLE_VOICE_OFFLOAD=true
ENABLE_TELEMETRY=true
TELEMETRY_ZMQ_HOST=$RIDER_PI_HOST
```

The startup sequence wires:

1. Shared `TaskQueue`/`TaskQueueWorker` (created once per process).
2. `VoiceProvider` configured from `[voice]` section in `config/providers.toml` (mock mode if `VOICE_MODEL=mock`).
3. ZMQ handlers for `voice.asr.request` and `voice.tts.request` that create `TaskEnvelope` entries with priorities declared in the TOML (defaults: ASR=5, TTS=6).
4. Worker telemetry fan-out:
   - `publish_voice_asr_result` → `voice.asr.result` with transcript/metadata.
   - `publish_voice_tts_chunk` → `voice.tts.chunk` with Base64 PCM that Rider-Pi replays directly.

The provider keeps emitting results even for empty audio chunks, so Rider-Pi receives the required “heartbeat” responses that prevent automatic fallback.

## Text / LLM Offload Runtime

Rider-PC udostępnia REST `POST /providers/text/generate` (alias `/api/providers/text/generate`) odpowiadający na payload:

```json
{
  "prompt": "co robi navigator?",
  "mode": "chat",
  "context": {"locale": "pl-PL"},
  "system_prompt": "You are Rider assistant",
  "max_tokens": 200,
  "temperature": 0.7
}
```

Odpowiedź:

```json
{
  "task_id": "text-generate-...",
  "text": "Navigator aktualnie...",
  "tokens_used": 57,
  "from_cache": false,
  "meta": {"model": "llama3.2:1b", "engine": "ollama"}
}
```

Włączamy moduł flagą `ENABLE_TEXT_OFFLOAD=true`, a Capability handshake (`GET /providers/capabilities`) zwróci, czy Rider-PC obsługuje `chat`/`nlu`. Rider-Pi może więc:

1. Przed przełączeniem domeny sprawdzić `capabilities["text"]["mode"] == "pc"`.
2. W trybie `pc` przekierować `/apps/chat` do powyższego endpointu z time-outem (np. 2 s).
3. W przypadku błędu (HTTP 5xx) / braku odpowiedzi spaść do lokalnych presetów i oznaczyć domenę `text` w `provider_registry` jako `local`.

## REST Proxy Behaviour

| Endpoint (PC)             | Target on Rider-Pi           | Notes                                                                 |
|---------------------------|------------------------------|-----------------------------------------------------------------------|
| `GET /api/system/ai-mode` | `/api/system/ai-mode`        | Response cached under `ai_mode` for offline fallback.                 |
| `PUT /api/system/ai-mode` | `/api/system/ai-mode`        | Unsupported values → `400`, missing adapter → `503`.                  |
| `GET /api/providers/state`| `/api/providers/state`       | Stores latest response in `providers_state`.                          |
| `PATCH /api/providers/{domain}` | `/api/providers/{domain}` | Domains: `voice`, `text`, `vision`. Forwards `target`/`force`.        |
| `GET /api/providers/health`| `/api/providers/health`     | Cached as `providers_health`.                                         |

When Rider-Pi is unreachable, FastAPI falls back to cached defaults so the UI remains usable in offline dev/test scenarios (logged warnings show the proxy failures).

## UI Mapping

- **Tryb AI** card polls `/api/system/ai-mode` every few seconds and updates the badge (`Local` / `PC Offload`).
- **Provider Control** card reads `domains` from `/api/providers/state` and renders per-domain pills + buttons. Clicking a button issues `PATCH /api/providers/{domain}` via the proxy.
- A PC health badge reflects `pc_health` from the same payload (latency, reachability).

## Testing & Diagnostics

- Programmatic sanity check for the vision path:
  ```bash
  # With Rider-Pi streaming frames
  curl http://localhost:8000/health/live                # FastAPI alive
  curl http://localhost:8000/api/providers/state        # UI parity
  tail -f logs/panel-8080.log | grep vision.frame       # confirms queue ingestion
  ```
- Pytest coverage includes `test_worker_publishes_vision_results` ensuring telemetry fan-out:
  ```bash
  pytest pc_client/tests/test_queue.py::test_worker_publishes_vision_results -q
  ```
- Programmatic checks:
  ```bash
  curl http://localhost:8000/api/system/ai-mode
  curl -X PUT http://localhost:8000/api/system/ai-mode -H 'Content-Type: application/json' -d '{"mode":"pc_offload"}'
  curl http://localhost:8000/api/providers/state
  curl -X PATCH http://localhost:8000/api/providers/voice -H 'Content-Type: application/json' -d '{"target":"pc"}'
  ```
- Automated tests:
  ```bash
  make lint
  make test              # includes test_provider_control_api.py & test_rest_adapter.py
  ```
  These suites cover cache fallbacks, adapter proxy behaviour, and UI contract expectations.

## Failure Handling

- Missing REST adapter (`app.state.rest_adapter is None`) → `503` responses for mutating endpoints; GET endpoints return cached defaults.
- 5xx from Rider-Pi → proxied result propagated, warning logged, and existing cache retained.
- Provider PATCH with invalid domain/target → `400` with descriptive message.

## Reference Documents

- Rider-Pi contract: `Rider-Pi/docs/OFFLOAD_PROVIDER_PROTOCOL.md`
- Rider-Pi web UI spec: `Rider-Pi/docs/ui/control.md`
- AI Mode details: `Rider-Pi/docs/AI_MODE_SWITCHER.md`
- Provider stack architecture: `docs/RIDER_PI_ARCH.md`, `docs/ARCHITECTURE.md`
