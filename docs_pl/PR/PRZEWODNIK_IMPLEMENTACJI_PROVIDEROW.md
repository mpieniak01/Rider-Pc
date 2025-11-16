# Przewodnik Implementacji Warstwy Providerów AI

## Przegląd

Ten przewodnik wyjaśnia jak używać i rozszerzać Warstwę Providerów AI do offloadowania zadań obliczeniowych z Rider-PI do PC.

## Architektura

```
Urządzenie Rider-PI                PC Client (WSL)
┌──────────────┐                  ┌──────────────────────┐
│ Aplikacja    │─────REST/ZMQ────→│  Kolejka Zadań       │
│ Głosu/Wizji  │                  │  (Oparta na          │
│ Nawigator    │                  │   Priorytetach)      │
└──────────────┘                  └──────────┬───────────┘
                                             │
                                             ↓
                                  ┌──────────────────────┐
                                  │  Worker Kolejki      │
                                  └──────────┬───────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     ↓                       ↓                       ↓
              ┌─────────────┐         ┌──────────────┐       ┌─────────────┐
              │Provider Głosu│        │Provider Wizji│       │Provider     │
              │ (ASR/TTS)    │        │(Detekcja)    │       │Tekstu       │
              └──────┬───────┘        └──────┬────────┘       │(LLM/NLU)    │
                     │                       │                └──────┬──────┘
                     └───────────────────────┴───────────────────────┘
                                             │
                                    Wyniki przez ZMQ
                                             │
                                             ↓
                                      Urządzenie Rider-PI
```

## Szybki Start

### 1. Włącz Providerów

Zaktualizuj plik `.env`:

```bash
# Włącz providerów AI
ENABLE_PROVIDERS=true

# Opcjonalnie: Określ modele (domyślnie: mock)
VOICE_MODEL=whisper-base
VISION_MODEL=yolov8n
TEXT_MODEL=llama-2-7b

# Włącz kolejkę zadań
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
TASK_QUEUE_HOST=localhost
TASK_QUEUE_PORT=6379
```

### 2. Skonfiguruj Brokera Kolejki Zadań

Wybierz między Redis (development) lub RabbitMQ (production).

#### Konfiguracja Redis
```bash
# Zainstaluj Redis
sudo apt install redis-server

# Uruchom Redis
sudo systemctl start redis-server

# Testuj połączenie
redis-cli ping
# Powinno zwrócić: PONG
```

Zobacz `KONFIGURACJA_KOLEJKI_ZADAN.md` dla szczegółowych instrukcji.

### 3. Uruchom z Providerami

```bash
# Uruchom klienta PC z włączonymi providerami
python -m pc_client.main
```

## Format Envelope Zadania

Wszystkie zadania używają ujednoliconego formatu envelope JSON:

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
    priority=5  # 1 (najwyższy) do 10 (najniższy)
)
```

## Typy Zadań

### Zadania Głosowe

**ASR (Mowa-na-Tekst)**
```python
TaskType.VOICE_ASR
payload = {
    "audio_data": "base64_audio",
    "format": "wav|raw",
    "sample_rate": 16000
}
```

**TTS (Tekst-na-Mowę)**
```python
TaskType.VOICE_TTS
payload = {
    "text": "Hello world",
    "voice": "default",
    "speed": 1.0
}
```

### Zadania Wizji

**Wykrywanie Obiektów**
```python
TaskType.VISION_DETECTION
payload = {
    "image_data": "base64_image",
    "format": "jpeg|png",
    "width": 640,
    "height": 480
}
```

**Przetwarzanie Klatek (dla unikania przeszkód)**
```python
TaskType.VISION_FRAME
payload = {
    "frame_data": "base64_frame",
    "frame_id": 123,
    "timestamp": 1234567890.0
}
```

### Zadania Tekstowe

**Generowanie LLM**
```python
TaskType.TEXT_GENERATE
payload = {
    "prompt": "Explain robot navigation",
    "max_tokens": 512,
    "temperature": 0.7
}
```

**NLU (Rozumienie Języka Naturalnego)**
```python
TaskType.TEXT_NLU
payload = {
    "text": "Start exploring mode",
    "task": "intent|entity|sentiment"
}
```

## Poziomy Priorytetów

Zadania mogą być przypisane do priorytetów 1-10:

| Priorytet | Kategoria | Przykłady | Czas SLA |
|-----------|-----------|-----------|----------|
| 1-2 | Krytyczne | Unikanie przeszkód, zatrzymanie awaryjne | <50ms |
| 3-4 | Wysokie | Komendy sterowania, wykrywanie obiektów | <200ms |
| 5-6 | Normalne | ASR/TTS, nawigacja | <1s |
| 7-8 | Niskie | Generowanie tekstu, cache | <5s |
| 9-10 | Tło | Logowanie, statystyki | Best effort |

## Circuit Breaker

Provider automatycznie wraca do trybu lokalnego po 5 kolejnych awariach:

```python
# Circuit breaker konfiguracja
failure_threshold = 5  # Otworzy się po 5 awariach
success_threshold = 2  # Zamknie się po 2 sukcesach
timeout = 60  # Sekundy przed ponowną próbą
```

**Stany Circuit Breakera:**
- `CLOSED`: Normalna operacja
- `OPEN`: Fallback do trybu lokalnego
- `HALF_OPEN`: Testowanie po timeoucie

## Telemetria i Metryki

### Metryki Prometheus

Dostępne pod `/metrics`:

```python
# Metryki providerów
provider_tasks_processed_total{provider="VoiceProvider", status="completed"}
provider_task_duration_seconds{provider="VoiceProvider"}
provider_circuit_breaker_state{provider="VoiceProvider"}

# Metryki kolejki
task_queue_size{priority="1"}
task_queue_size{priority="5"}

# Metryki cache
cache_hits_total
cache_misses_total
```

### Publisher Telemetrii ZMQ

Wyniki są automatycznie publikowane z powrotem do Rider-PI:

```python
# Tematy ZMQ
telemetry.voice  # Wyniki zadań głosowych
telemetry.vision  # Wyniki zadań wizji
telemetry.text  # Wyniki zadań tekstowych
```

## Rozszerzanie Providerów

### Tworzenie Własnego Providera

```python
from pc_client.providers.base import BaseProvider, TaskEnvelope

class MyCustomProvider(BaseProvider):
    def __init__(self, config=None):
        super().__init__(
            name="CustomProvider",
            config=config or {}
        )
    
    async def initialize(self):
        # Inicjalizuj Twoje modele lub zasoby
        self.model = await load_my_model()
    
    async def process_task(self, task: TaskEnvelope) -> TaskEnvelope:
        # Przetw órz zadanie
        result = await self.model.process(task.payload)
        
        # Zwróć wynik
        task.result = {"output": result}
        task.status = "completed"
        return task
    
    async def cleanup(self):
        # Wyczyść zasoby
        await self.model.close()
```

### Rejestracja Własnego Providera

```python
# W pc_client/providers/__init__.py
from .custom_provider import MyCustomProvider

PROVIDERS = {
    "voice": VoiceProvider,
    "vision": VisionProvider,
    "text": TextProvider,
    "custom": MyCustomProvider,  # Dodaj Twój provider
}
```

## Konfiguracja

### Plik Konfiguracyjny

Wszystkie providery korzystają z jednego pliku `config/providers.toml`. Każda domena ma własną sekcję:

- `[voice]` – ustawienia głosu (ASR/TTS)
- `[vision]` – ustawienia wizji (YOLO, frame offload)
- `[text]` – ustawienia LLM/NLU

**Przykład konfiguracji sekcji `[voice]`:**
```toml
[voice]
asr_model = "whisper-base"
tts_model = "piper-medium"
sample_rate = 16000
use_mock = false
max_concurrent_tasks = 4

[circuit_breaker]
failure_threshold = 5
success_threshold = 2
timeout = 60
```

## Najlepsze Praktyki

### 1. Priorytetyzacja Zadań
- Używaj priorytetów 1-2 dla zadań krytycznych bezpieczeństwa
- Zadania ASR/TTS mogą używać priorytetów 5-6
- Generowanie tekstu powinno używać priorytetów 7-8

### 2. Obsługa Błędów
- Zawsze implementuj fallback dla zadań krytycznych
- Loguj wszystkie awarie dla debugowania
- Monitor circuit breakera dla problemów sieciowych

### 3. Wydajność
- Używaj batch processing gdy możliwe
- Cache częstych wyników
- Monitor wykorzystania zasobów

### 4. Testowanie
- Testuj z trybem mock przed użyciem prawdziwych modeli
- Symuluj awarie sieci
- Przetestuj scenariusze wysokiego obciążenia

## Rozwiązywanie Problemów

### Provider Nie Inicjalizuje Się

```bash
# Sprawdź logi
tail -f logs/rider-pc.log | grep "\[provider\]"

# Sprawdź konfigurację
cat config/providers.toml

# Testuj ręcznie
python -c "from pc_client.providers import VoiceProvider; ..."
```

### Zadania Stuck w Kolejce

```bash
# Sprawdź rozmiar kolejki
redis-cli LLEN task_queue:priority:5

# Sprawdź czy worker działa
ps aux | grep task_queue

# Ręcznie opróżnij kolejkę
redis-cli FLUSHDB
```

### Circuit Breaker Ciągle Otwiera Się

```bash
# Sprawdź połączenie sieciowe
ping <RIDER_PI_HOST>

# Sprawdź logi błędów
grep "Circuit breaker opened" logs/rider-pc.log

# Zwiększ timeout
# W .env: CIRCUIT_BREAKER_TIMEOUT=120
```

## Monitoring

### Dashboardy Grafana

Importuj wstępnie skonfigurowany dashboard:

```bash
# Importuj dashboard
grafana-cli dashboards import config/grafana-dashboard.json
```

### Reguły Alertów

Konfiguruj alerty dla:
- Wysoki rozmiar kolejki (>1000 zadań)
- Circuit breaker otwarty (>5 minut)
- Niska szybkość przetwarzania (<10 zadań/s)
- Wysokie użycie pamięci (>80%)

## Dodatkowe Zasoby

- [KONFIGURACJA_KOLEJKI_ZADAN.md](KONFIGURACJA_KOLEJKI_ZADAN.md) - Konfiguracja Redis/RabbitMQ
- [KONFIGURACJA_MONITORINGU.md](KONFIGURACJA_MONITORINGU.md) - Konfiguracja Prometheus/Grafana
- [KONFIGURACJA_BEZPIECZENSTWA_SIECI.md](KONFIGURACJA_BEZPIECZENSTWA_SIECI.md) - VPN/mTLS setup
- [PRZEWODNIK_INTEGRACJI.md](PRZEWODNIK_INTEGRACJI.md) - Przewodnik integracji end-to-end

---

**Status**: Gotowe do Produkcji ✅  
**Wersja**: 1.0.0  
**Data Ostatniej Aktualizacji**: 2025-11-12
