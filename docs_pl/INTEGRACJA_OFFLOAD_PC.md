# Przewodnik Integracji Offload Rider-PC

Ten dokument wyjaśnia, jak stos Rider-PC odzwierciedla tryb AI i kontrolę providerów Rider-Pi oraz jak zweryfikować przepływy offload end-to-end.

## Przegląd

Rider-Pi udostępnia rejestr providerów (`/api/system/ai-mode`, `/api/providers/*`) i deterministyczny kontrakt ZMQ (zobacz `Rider-Pi/docs/OFFLOAD_PROVIDER_PROTOCOL.md`). Rider-PC implementuje obowiązki po stronie PC:

- Serwuje identyczny panel kontrolny (`web/control.html`) z kartami **Tryb AI** i **Kontrola Providerów**.
- Przekazuje wywołania REST do Rider-Pi przez `pc_client.adapters.rest_adapter.RestAdapter`.
- Uruchamia obciążenia AI (głos, wizja, tekst) i publikuje ulepszone dane z powrotem do Rider-Pi przez ZMQ (`vision.obstacle.enhanced`, `voice.asr.result`, itp.).

## Konfiguracja

1. **Wskaż na Rider-Pi**
   ```bash
   export RIDER_PI_HOST="192.168.1.100"
   export RIDER_PI_PORT="8080"
   ```
   (lub edytuj `.env`)

2. **Ogłoś URL Rider-PC (wymagane dla Kontroli Providerów)**
   ```bash
   export PC_PUBLIC_BASE_URL="http://192.168.1.179:8080"   # IP/port osiągalny z Rider-Pi
   ```
   Pętla heartbeat jest pomijana gdy ta zmienna jest pusta, powodując że Rider-Pi oznacza PC jako `pc_unreachable`.

3. **Uruchom lokalny stos**
   ```bash
   make start
   # Interfejs: http://localhost:8000/web/control.html
   ```

4. **Opcjonalnie**: włącz prawdziwe providery (`ENABLE_PROVIDERS=true`, Redis, itp.) jak udokumentowano w `docs/AI_MODEL_SETUP.md`.

## Środowisko Wykonawcze Offload Wizji (Rider-PC)

Ustaw te flagi w `.env` aby pobierać `vision.frame.offload` i publikować `vision.obstacle.enhanced`:

```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
ENABLE_VISION_OFFLOAD=true
ENABLE_TELEMETRY=true             # lub polegaj na auto-włączeniu przez ENABLE_VISION_OFFLOAD
TELEMETRY_ZMQ_HOST=$RIDER_PI_HOST # punkt końcowy bus XSUB udostępniony przez Rider-Pi
```

Przy starcie Rider-PC tworzy:

1. `TaskQueue` (`pc_client.queue.task_queue.TaskQueue`) o rozmiarze `TASK_QUEUE_MAX_SIZE`.
2. `VisionProvider` skonfigurowany z sekcji `[vision]` w `config/providers.toml` (tryb mock gdy `VISION_MODEL=mock`).
3. `TaskQueueWorker` + `ZMQTelemetryPublisher` który łączy wyniki zadań z brokerem Rider-Pi.
4. Handler ZMQ dla `vision.frame.offload` który pakuje ramki w instancje `TaskEnvelope` i kolejkuje je z `frame_priority`.

Wyniki płyną z powrotem przez `ZMQTelemetryPublisher.publish_vision_obstacle_enhanced`, więc navigator konsumuje ulepszony temat natychmiast po przetworzeniu każdej ramki.

## Środowisko Wykonawcze Offload Głosu (ASR/TTS)

Aby przesyłać audio do Rider-PC i odtwarzać syntezowaną odpowiedź:

```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
ENABLE_VOICE_OFFLOAD=true
ENABLE_TELEMETRY=true
TELEMETRY_ZMQ_HOST=$RIDER_PI_HOST
```

Sekwencja uruchamiania podłącza:

1. Współdzielone `TaskQueue`/`TaskQueueWorker` (utworzone raz na proces).
2. `VoiceProvider` skonfigurowany z sekcji `[voice]` w `config/providers.toml` (tryb mock jeśli `VOICE_MODEL=mock`).
3. Handlery ZMQ dla `voice.asr.request` i `voice.tts.request` które tworzą wpisy `TaskEnvelope` z priorytetami zadeklarowanymi w TOML (domyślnie: ASR=5, TTS=6).
4. Rozproszenie telemetrii workera:
   - `publish_voice_asr_result` → `voice.asr.result` z transkrypcją/metadanymi.
   - `publish_voice_tts_chunk` → `voice.tts.chunk` z Base64 PCM które Rider-Pi odtwarza bezpośrednio.

Provider kontynuuje emitowanie wyników nawet dla pustych fragmentów audio, więc Rider-Pi otrzymuje wymagane odpowiedzi "heartbeat" które zapobiegają automatycznemu fallbackowi.

## Środowisko Wykonawcze Offload Tekstu / LLM

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

## Zachowanie Proxy REST

| Endpoint (PC)             | Cel na Rider-Pi              | Uwagi                                                                 |
|---------------------------|------------------------------|-----------------------------------------------------------------------|
| `GET /api/system/ai-mode` | `/api/system/ai-mode`        | Odpowiedź cachowana pod `ai_mode` dla offline fallback.              |
| `PUT /api/system/ai-mode` | `/api/system/ai-mode`        | Nieobsługiwane wartości → `400`, brak adaptera → `503`.              |
| `GET /api/providers/state`| `/api/providers/state`       | Przechowuje ostatnią odpowiedź w `providers_state`.                  |
| `PATCH /api/providers/{domain}` | `/api/providers/{domain}` | Domeny: `voice`, `text`, `vision`. Przekazuje `target`/`force`.     |
| `GET /api/providers/health`| `/api/providers/health`     | Cachowane jako `providers_health`.                                    |

Gdy Rider-Pi jest nieosiągalny, FastAPI wraca do cachowanych wartości domyślnych, więc interfejs pozostaje użyteczny w offline dev/test scenariuszach (zalogowane ostrzeżenia pokazują błędy proxy).

## Mapowanie Interfejsu

- Karta **Tryb AI** odpytuje `/api/system/ai-mode` co kilka sekund i aktualizuje badge (`Local` / `PC Offload`).
- Karta **Kontrola Providerów** odczytuje `domains` z `/api/providers/state` i renderuje pigułki per-domena + przyciski. Kliknięcie przycisku wysyła `PATCH /api/providers/{domain}` przez proxy.
- Badge zdrowia PC odzwierciedla `pc_health` z tego samego payloadu (opóźnienie, osiągalność).

## Heartbeat Providera & Osiągalność PC

- Rider-Pi udostępnia `POST /api/providers/pc-heartbeat` który zapisuje ostatnio osiągalny URL PC i opóźnienie.  
  Serwer FastAPI Rider-PC wywołuje ten endpoint co ~5 sekund przez `RestAdapter`.
- Pętla jest włączona tylko gdy `PC_PUBLIC_BASE_URL` jest ustawione (w `.env`). Ustaw to na URL który Rider-Pi może osiągnąć, np. `http://192.168.1.179:8080`.
- Payload heartbeat pakuje ogłoszony bazowy URL plus najnowszy snapshot możliwości, pozwalając Rider-Pi pokazywać dokładne badge `pc_health` w Kontroli Providerów.
- Jeśli watchdog na Rider-Pi nie otrzymuje heartbeatów przez `FAIL_THRESHOLD` interwałów, automatycznie wraca do trybu `local`, więc utrzymanie bazowego URL jako rutowalnego (VPN/NAT/forwarding) jest krytyczne.

## Testowanie & Diagnostyka

- Programatyczna kontrola poprawności dla ścieżki wizji:
  ```bash
  # Z Rider-Pi strumieniującym ramki
  curl http://localhost:8000/health/live                # FastAPI żywy
  curl http://localhost:8000/api/providers/state        # Parytet UI
  tail -f logs/panel-8080.log | grep vision.frame       # potwierdza przyjmowanie kolejki
  ```
- Pokrycie Pytest zawiera `test_worker_publishes_vision_results` zapewniające rozproszenie telemetrii:
  ```bash
  pytest pc_client/tests/test_queue.py::test_worker_publishes_vision_results -q
  ```
- Kontrole programatyczne:
  ```bash
  curl http://localhost:8000/api/system/ai-mode
  curl -X PUT http://localhost:8000/api/system/ai-mode -H 'Content-Type: application/json' -d '{"mode":"pc_offload"}'
  curl http://localhost:8000/api/providers/state
  curl -X PATCH http://localhost:8000/api/providers/voice -H 'Content-Type: application/json' -d '{"target":"pc"}'
  ```
- Automatyczne testy:
  ```bash
  make lint
  make test              # zawiera test_provider_control_api.py & test_rest_adapter.py
  ```
  Te zestawy pokrywają fallbacki cache, zachowanie proxy adaptera i oczekiwania kontraktu UI.

## Obsługa Błędów

- Brak REST adaptera (`app.state.rest_adapter is None`) → odpowiedzi `503` dla mutujących endpointów; endpointy GET zwracają cachowane wartości domyślne.
- 5xx z Rider-Pi → wynik proxy przekazany, ostrzeżenie zalogowane i istniejący cache zachowany.
- Provider PATCH z nieprawidłową domeną/celem → `400` z opisową wiadomością.

## Dokumenty Referencyjne

- Kontrakt Rider-Pi: `Rider-Pi/docs/OFFLOAD_PROVIDER_PROTOCOL.md`
- Specyfikacja web UI Rider-Pi: `Rider-Pi/docs/ui/control.md`
- Szczegóły Trybu AI: `Rider-Pi/docs/AI_MODE_SWITCHER.md`
- Architektura stosu providerów: `docs/RIDER_PI_ARCH.md`, `docs/ARCHITECTURE.md`
