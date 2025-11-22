# Rider-PC Client — Architektura Rozwiązania

## Projekt powiązany
https://github.com/mpieniak01/Rider-Pi 

## Koncepcja Architektoniczna

**Rider-PC to autonomiczny system typu Digital Twin**, a nie "replikator UI pobierający interfejs z Rider-Pi".

### Kluczowe cechy architektury:
- **Niezależna aplikacja webowa**: Serwuje lokalne pliki statyczne (HTML/JS/CSS) z katalogu `web/`
- **Synchronizacja danych (Data Sync)**: Pobiera tylko stan/dane z Rider-Pi (REST + ZMQ), nie kod interfejsu
- **Własny stos technologiczny**: Redis, Prometheus, Grafana, SQLite Cache, modele AI
- **Dwukierunkowa komunikacja**: Nie tylko wyświetla dane, ale przetwarza zadania AI i odsyła wyniki
- **Offload przetwarzania**: Vision (YOLOv8), Voice (Whisper/Piper), Text (Ollama) działają lokalnie na PC

Rider-PC **nie** pobiera plików HTML/JS z Rider-Pi w runtime. UI był skopiowany jednorazowo w fazie rozwoju, a aktualizacje wymagają zmiany repozytorium.

## Integracja z Rider-Pi

System Rider-PC współpracuje z robotem Rider-Pi w modelu **Provider Architecture**:

### Dynamiczny Wybór Źródła Usług AI
- Rider-Pi może dynamicznie przełączać źródło usług AI: **lokalne modele** na Pi vs. **providery PC**
- Operator kontroluje kanały obsługi głosu, tekstu i obrazu w locie przez panel **Provider Control**
- Zachowana kompatybilność wsteczna - negocjacja wersji kontraktów

### Provider Control API
Rider-Pi udostępnia endpointy zarządzania providerami:
- `GET /api/providers/state` — lista domen (voice, text, vision) z aktywnym źródłem i stanem zdrowia
- `PATCH /api/providers/{domain}` — przełączanie między trybem `local` i `pc`
- `GET /api/providers/health` — raport łączności i latencji

### Circuit Breaker i Fallback
- Mechanizm circuit breaker automatycznie przełącza na tryb `local` po serii błędów
- Watchdog monitoruje RTT z PC - przekroczenie progu wyzwala alarm i fallback
- Heartbeat co ~5s weryfikuje dostępność PC (endpoint `/api/providers/pc-heartbeat`)

Szczegóły protokołu komunikacji i kontraktów ZMQ: [INTEGRACJA_OFFLOAD_PC.md](INTEGRACJA_OFFLOAD_PC.md)

## 1. Warstwa systemowa (Windows 11 + WSL2 Debian)
- Windows uruchamia maszynę WSL2 z dystrybucją Debian, w której utrzymywany jest kod kliencki w Pythonie 3.9.
- Sieć WSL umożliwia bezpośrednią komunikację IP (LAN/VPN) pomiędzy Rider-PI a PC.
- Zasoby obliczeniowe PC (CPU/GPU) są udostępniane do WSL; w razie potrzeby włącz obsługę GPU (`wsl --install --webgpu`).

## 2. Warstwa aplikacji w WSL (Python 3.9)
### 2.1 Adapter API Rider-PI
- Moduł konsumujący REST (`/healthz`, `/api/control`, `/api/chat/*`) oraz strumienie ZMQ (porty 5555/5556).
- Zapewnia zgodność kontraktową z usługami Rider-PI oraz mapuje tematy busa na lokalne zdarzenia.

### 2.2 Lokalny Klient Web (Digital Twin)
- Serwer FastAPI (`pc_client/api/server.py`) serwujący pliki statyczne bezpośrednio z lokalnego katalogu `web/`.
- UI nie jest pobierany z Rider-Pi w czasie rzeczywistym — replikacja kodu była jednorazowa podczas fazy rozwoju.
- Mechanizm działania to Data Sync: PC posiada lokalny CacheManager (SQLite), który jest zasilany danymi z Rider-Pi poprzez REST API i strumienie ZMQ, a UI odpytuje lokalne API PC.
- Dane pochodzą z lokalnego bufora Cache; UI wystawiany jest w sieci lokalnej PC na porcie 8000.

### 2.3 Bufor/Cache danych
- Lekka baza (Redis/SQLite) przechowująca bieżące stany ekranów, zrzuty (`data/`, `snapshots/`) i surowe strumienie danych.
- Umożliwia szybkie odtworzenie UI oraz buforowanie pakietów dla providerów AI.

### 2.4 Warstwa PROVIDER (Voice/Text/Vision) - AI Offload
Rider-PC to **autonomiczny system przetwarzania AI**, nie tylko wyświetlacz danych. PC przetwarza zadania offloadowane z Rider-Pi wykorzystując własne zasoby obliczeniowe:

- **Vision Provider** (`pc_client/providers/vision_provider.py`):
  - Przetwarzanie obrazów z eventów `vision.frame.offload` odbieranych przez ZMQ
  - Implementacja: YOLOv8 dla detekcji obiektów, z obsługą trybu mock
  - Wyniki publikowane z powrotem do Rider-Pi przez ZMQ jako `vision.obstacle.enhanced`
  - Konfiguracja: `ENABLE_VISION_OFFLOAD=true`, model YOLOv8n lub mock
  
- **Voice Provider** (`pc_client/providers/voice_provider.py`):
  - Offload ASR (Automatic Speech Recognition) i TTS (Text-to-Speech)
  - Implementacja: Whisper (ASR) + Piper (TTS), z obsługą mock
  - Odbiera: `voice.asr.request` (audio chunk) i `voice.tts.request` (tekst)
  - Publikuje: `voice.asr.result` (transkrypcja) i `voice.tts.chunk` (audio)
  - Konfiguracja: `ENABLE_VOICE_OFFLOAD=true`, modele Whisper base + Piper
  
- **Text Provider** (`pc_client/providers/text_provider.py`):
  - Lokalne modele NLU/NLG (Ollama, Transformers) lub proxy do API chmurowych
  - Endpoint REST `/providers/text/generate` dla zapytań czatu
  - Używany przez Rider-Pi gdy włączony AI Mode
  - Konfiguracja: `ENABLE_TEXT_OFFLOAD=true`, model Ollama lub mock

**Architektura offload:** Rider-PC nie jest pasywnym "lustrem" - aktywnie przetwarza dane i zwraca wzbogacone wyniki. Komunikacja dwukierunkowa przez ZMQ (`telemetry.zmq_publisher.py`) pozwala robotowi natychmiast korzystać z wyników.

### 2.5 Kolejka zadań
- Broker (RabbitMQ/Redis) i warstwa Celery/Arq do asynchronicznego offloadu zadań.
- Zapewnia buforowanie oraz równoważenie obciążenia pomiędzy providerami.

## 3. Warstwa komunikacji i integracji

### 3.0 Mapa Portów i Usług
System wykorzystuje następujące porty i punkty końcowe:

| Usługa | Port | Typ | Opis |
|--------|------|-----|------|
| **Rider-PC UI** | 8000 | Lokalny | Punkt wejścia FastAPI dla operatora (Web UI) |
| **Rider-Pi API** | 8080 | Zdalny | REST API robota (cel zapytań) |
| **ZMQ PUB** | 5555 | Zdalny | Publikacja zdarzeń z Rider-Pi (vision.*, motion.*) |
| **ZMQ SUB** | 5556 | Zdalny | Subskrypcja odpowiedzi (opcjonalnie) |
| **ZMQ Telemetria** | 5557 | Lokalny | Publikacja wyników offload z PC do Pi |
| **Redis** | 6379 | Lokalny | Broker kolejki zadań i cache |
| **Prometheus** | 9090 | Lokalny | Zbieranie metryk monitoringu |
| **Grafana** | 3000 | Lokalny | Wizualizacja metryk i dashboardy |

**Uwaga:** Porty lokalne (8000, 6379, 9090, 3000, 5557) działają w sieci PC. Porty zdalne (8080, 5555, 5556) wskazują na Rider-Pi (konfigurowane przez `RIDER_PI_HOST`).

### 3.1 Kanały przychodzące z Rider-PI
- REST (port 8080) tunelowany przez VPN/mTLS.
- Strumień ZMQ PUB/SUB (5555/5556) z tematami `vision.*`, `voice.*`, `motion.state`, `robot.pose`.
- Transfer plików (SFTP/rsync/HTTP static) z katalogów `data/`, `snapshots/`.

### 3.2 Kanały wychodzące do Rider-PI
- REST (`/api/control`, `/api/chat/*`) dla komend i odpowiedzi rozszerzonych usług AI.
- PUB ZMQ z tematami typu `vision.obstacle.enhanced`, `voice.tts.chunk`, `events.sentiment.offload`.
- Zwracanie plików wynikowych (audio, mapy) kanałem SFTP/HTTP PUT.

### 3.3 Mechanizm Synchronizacji Danych (Data Sync Loop)
System Rider-PC synchronizuje dane z Rider-Pi poprzez dwa główne mechanizmy:

#### 3.3.1 Pętla Synchronizacji Okresowej (sync_data_periodically)
Funkcja `sync_data_periodically` w `pc_client/api/lifecycle.py` wykonuje się co **2 sekundy** i pobiera następujące dane:
- `/healthz` - stan zdrowia systemu
- `/state` - bieżący stan robota (tracking, navigator, camera)
- `/sysinfo` - informacje systemowe
- `/api/vision/snap/info` - informacje o snapshotach wizji
- `/api/vision/obstacle` - dane detekcji przeszkód
- `/api/app-metrics` - metryki aplikacji
- `/api/resources/camera` - stan zasobu kamery
- `/api/bus/health` - zdrowie magistrali komunikacyjnej

Wszystkie pobrane dane są zapisywane w lokalnym **CacheManager (SQLite)** z TTL domyślnie ustawionym na 30 sekund.

#### 3.3.2 Subskrybent ZMQ (Real-Time Events)
Klasa `ZmqSubscriber` w `pc_client/adapters/zmq_subscriber.py` nasłuchuje zdarzeń w czasie rzeczywistym:
- Subskrybuje tematy: `vision.*`, `voice.*`, `motion.*`, `robot.*`, `navigator.*`
- Odbierane eventy są natychmiast zapisywane w Cache pod kluczem `zmq:{topic}`
- Dla zadań offload (np. `vision.frame.offload`, `voice.asr.request`) dane są kierowane do kolejki zadań

#### 3.3.3 Podział Endpointów API
- **Endpointy odczytu (GET)**: Serwują dane bezpośrednio z lokalnego Cache (np. `/api/state`, `/api/sysinfo`)
- **Endpointy kontroli (POST)**: Działają jako **Proxy** - przekazują komendy do Rider-Pi i zwracają odpowiedź (np. `/api/control`, `/api/chat/*`)
- **Endpointy providerów**: Przetwarzają dane lokalnie i publikują wyniki przez ZMQ Telemetry

## 4. Przepływy danych

### 4.1 Synchronizacja Dashboard (Data Sync)
1. **Rider-Pi** publikuje stan przez REST API (`/state`, `/healthz`, `/sysinfo`) i eventy ZMQ (`vision.*`, `motion.*`)
2. **PC Cache** (SQLite) aktualizowany co 2s przez `sync_data_periodically` + real-time przez `ZmqSubscriber`
3. **Web UI** (lokalne pliki HTML/JS w `web/`) odpytuje lokalne API PC (port 8000)
4. **Przeglądarka** użytkownika renderuje dane z lokalnego Cache PC

**Kluczowe:** UI nie pobiera HTML/JS z Rider-Pi w czasie rzeczywistym. Synchronizowane są tylko **dane stanu**, nie kod interfejsu.

### 4.2 Offload Głosu (Voice Pipeline)
1. Rider-Pi publikuje event ZMQ: `voice.asr.request` (audio chunk) lub `voice.tts.request` (tekst)
2. PC `ZmqSubscriber` odbiera i enqueue do `TaskQueue` (Redis)
3. `VoiceProvider` przetwarza przez Whisper (ASR) lub Piper (TTS)
4. Wynik publikowany przez `ZMQTelemetryPublisher` jako `voice.asr.result` / `voice.tts.chunk`
5. Rider-Pi odbiera wynik i używa w aplikacji voice

### 4.3 Offload Wizji (Vision Pipeline)
1. Rider-Pi publikuje `vision.frame.offload` z obrazem + metadanymi tracking
2. PC enqueue zadanie z priorytetem (domyślnie 1)
3. `VisionProvider` wykonuje detekcję (YOLOv8) z uwzględnieniem stanu tracking
4. Wzbogacone dane (`vision.obstacle.enhanced`) publikowane z powrotem do Pi
5. Rider-Pi używa wyników w navigator/mapper

### 4.4 Offload Tekstu (Text/LLM Pipeline)
1. Rider-Pi wysyła zapytanie REST POST do `/providers/text/generate`
2. PC `TextProvider` przetwarza przez Ollama/Transformers lokalnie
3. Odpowiedź zwracana synchronicznie przez REST
4. Rider-Pi wyświetla odpowiedź w interfejsie (web/face)

## 5. Rozszerzalność i zarządzanie
- Providerów implementuj jako pluginy (`providers/`), rejestrowane podczas startu.
- Wersjonuj kontrakty (schematy JSON) i negocjuj możliwości z Rider-PI.
- Zadbaj o telemetrię i logging spójny z prefiksami `[api]`, `[bridge]`, `[vision]`, `[voice]`, `[provider]`.

## 6. Instalacja środowiska (skrót)
- Instalacja WSL Debian: `wsl --install -d Debian`, następnie `wsl --update`.
- W WSL wykonaj: `sudo apt update && sudo apt upgrade -y`.
- Zainstaluj pakiety bazowe i ML: `sudo apt install -y build-essential python3.9 python3.9-venv python3.9-dev git curl wget unzip pkg-config cmake ninja-build libzmq3-dev libssl-dev libffi-dev libjpeg-dev zlib1g-dev libgl1 libglib2.0-0 libopenblas-dev libsndfile1 ffmpeg alsa-utils portaudio19-dev`.
- (Opcjonalnie) GPU: `sudo apt install -y nvidia-cuda-toolkit nvidia-cudnn`.
- Utwórz środowisko Python: `python3.9 -m venv ~/venvs/rider-pi-pc && source ~/venvs/rider-pi-pc/bin/activate && pip install --upgrade pip`.

## 7. Konfiguracja i dalsze prace
- Skonfiguruj bezpieczne kanały sieciowe, adaptery REST/ZMQ, kolejkę zadań oraz monitoring (Prometheus/Grafana).

- Przygotuj pipeline CI/CD dla budowy i testów oraz runbooki operacyjne.
