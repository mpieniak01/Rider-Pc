# Rider-PC Client

> **Autonomiczny system typu Digital Twin** dla robota Rider-Pi z przetwarzaniem AI i offloadem zadań

Infrastruktura klienta PC dla robota Rider-Pi, zapewniająca:
- 🔌 Adapter REST API i Subskrybent ZMQ dla synchronizacji danych w czasie rzeczywistym
- 💾 Lokalny cache SQLite do buforowania stanów
- 🌐 Serwer web FastAPI serwujący interfejs użytkownika
- 🤖 **Warstwa Providerów AI** z prawdziwymi modelami ML (Głos, Wizja, Tekst)
- 🚀 **Wdrożenie gotowe do produkcji** z Docker i CI/CD

## 🎯 Cel Projektu

Rider-PC to **nie** prosty wyświetlacz danych z robota. To autonomiczny system przetwarzania AI, który:
- Przyjmuje zadania obliczeniowe offloadowane z Rider-Pi (Vision, Voice, Text)
- Przetwarza je lokalnie wykorzystując zasoby PC (CPU/GPU)
- Zwraca wzbogacone wyniki z powrotem do robota w czasie rzeczywistym
- Działa jako Digital Twin z własnym interfejsem i stosem technologicznym

## 📊 Aktualny Status

### ✅ Faza 4 Zakończona - Prawdziwe Modele AI i Wdrożenie Produkcyjne

- ✅ **Prawdziwe Modele AI**: Whisper ASR, Piper TTS, YOLOv8 Vision, Ollama LLM
- ✅ **Wdrożenie Docker**: Kompletny stos z Redis, Prometheus, Grafana
- ✅ **Pipeline CI/CD**: Automatyczne testowanie, skanowanie bezpieczeństwa, budowy Docker
- ✅ **Sondy Zdrowia**: Punkty końcowe gotowości i żywotności zgodne z Kubernetes
- ✅ **Automatyczny Fallback**: Tryb mock gdy modele niedostępne
- ✅ **Circuit Breaker**: Automatyczne przełączanie przy awariach
- ✅ **Telemetria**: Metryki Prometheus w czasie rzeczywistym

Zobacz szczegóły w [archive/PR/WDROZENIE_ZAKONCZONE_FAZA4.md](archive/PR/WDROZENIE_ZAKONCZONE_FAZA4.md)

## 🚀 Szybki Start

**Opcja 1: Docker (Zalecane dla produkcji)**
```bash
echo "RIDER_PI_HOST=192.168.1.100" > .env
docker-compose up -d
# Interfejs: http://localhost:8000
```

**Opcja 2: Lokalne środowisko (Rozwój)**
```bash
pip install -r requirements.txt
python -m pc_client.main
```

Pełna instrukcja: [SZYBKI_START.md](SZYBKI_START.md)

## 📚 Dokumentacja - Spis Treści

### Podstawy
- **[SZYBKI_START.md](SZYBKI_START.md)** - Instalacja i pierwsze uruchomienie (Docker + Local)
- **[ARCHITEKTURA.md](ARCHITEKTURA.md)** - Koncepcja systemu, warstwy, przepływy danych
- **[INTEGRACJA_OFFLOAD_PC.md](INTEGRACJA_OFFLOAD_PC.md)** - Szczegóły techniczne protokołu komunikacji z Rider-Pi

### Konfiguracja
- **[KONFIGURACJA.md](KONFIGURACJA.md)** - 📋 **Hub konfiguracyjny** - centralny przewodnik po wszystkich aspektach konfiguracji
  - [KONFIGURACJA_MODELI_AI.md](KONFIGURACJA_MODELI_AI.md) - Whisper, Piper, YOLOv8, Ollama
  - [KONFIGURACJA_BEZPIECZENSTWA.md](KONFIGURACJA_BEZPIECZENSTWA.md) - WireGuard VPN, mTLS
  - [KONFIGURACJA_KOLEJKI_ZADAN.md](KONFIGURACJA_KOLEJKI_ZADAN.md) - Redis, RabbitMQ
  - [KONFIGURACJA_MONITORINGU.md](KONFIGURACJA_MONITORINGU.md) - Prometheus, Grafana

### Zarządzanie
- **[ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md](ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md)** - Operacje, monitoring, troubleshooting

### Specyfikacje API
- **[api-specs/](api-specs/)** - Szczegółowe specyfikacje endpointów REST
  - [api-specs/README.md](api-specs/README.md) - Przegląd API
  - [api-specs/STEROWANIE.md](api-specs/STEROWANIE.md) - API sterowania
  - [api-specs/NAWIGATOR.md](api-specs/NAWIGATOR.md) - API nawigatora

### Notatki i Plany
- [NOTATKI_REPLIKACJI.md](NOTATKI_REPLIKACJI.md) - Notatki techniczne o mechanizmach replikacji
- [PRACE_PRZYSZLE.md](PRACE_PRZYSZLE.md) - Planowane usprawnienia i rozwój

### Archiwum
- **[archive/PR/](archive/PR/)** - Historyczne raporty wdrożeń (Fazy 1-4)
  - Statusy wdrożeń poszczególnych faz
  - Przewodniki implementacji providerów
  - Podsumowania zakończonych faz

## 🏗️ Architektura (Skrót)

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
│  │  Warstwa Adaptera                 │  │
│  │  • REST Client • ZMQ Subscriber   │  │
│  └───────────────────────────────────┘  │
│           │ Cache (SQLite)  │            │
│  ┌───────────────────────────────────┐  │
│  │  Serwer FastAPI + Web UI          │  │
│  │  http://localhost:8000            │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Warstwa Providerów AI            │  │
│  │  • Vision (YOLOv8)                │  │
│  │  • Voice (Whisper/Piper)          │  │
│  │  • Text (Ollama)                  │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Infrastruktura                   │  │
│  │  • Redis • Prometheus • Grafana   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │ Wyniki (ZMQ)
         ▼
┌─────────────────────────────────────────┐
│  Rider-Pi otrzymuje wzbogacone dane     │
│  (vision.obstacle.enhanced, etc.)       │
└─────────────────────────────────────────┘
```

Pełny opis: [ARCHITEKTURA.md](ARCHITEKTURA.md)

## 🔑 Kluczowe Funkcje

### Offload Przetwarzania AI
- **Vision**: Detekcja obiektów YOLOv8, klasyfikacja przeszkód
- **Voice**: ASR (Whisper) i TTS (Piper) z niskią latencją
- **Text**: Lokalne LLM (Ollama) dla NLU/NLG

### Synchronizacja Danych
- Pętla REST co 2s pobiera stan z Rider-Pi
- Real-time eventy przez ZMQ (vision.*, motion.*, robot.*)
- Lokalny cache SQLite z TTL dla szybkiego dostępu

### Niezawodność
- Circuit Breaker - automatyczny fallback przy błędach
- Tryb Mock - testowanie bez prawdziwych modeli
- Heartbeat - monitoring dostępności PC
- Kolejka priorytetowa - krytyczne zadania first

### Monitoring
- Metryki Prometheus (50+ metryk)
- Dashboardy Grafana
- Alerty dla anomalii
- Logi strukturyzowane

## 🛠️ Technologie

- **Backend**: Python 3.9+, FastAPI, SQLite
- **AI Models**: Whisper, Piper, YOLOv8, Ollama
- **Komunikacja**: ZMQ (pub/sub), REST API
- **Kolejka**: Redis / RabbitMQ
- **Monitoring**: Prometheus, Grafana
- **Deployment**: Docker, Docker Compose
- **Testing**: pytest, Playwright

## 📋 Wymagania

- Python 3.9+
- WSL2 z Debian (dla użytkowników Windows)
- Dostęp sieciowy do Rider-Pi
- Docker (opcjonalnie, dla pełnego stosu)
- 2-3GB miejsca dla modeli AI (opcjonalnie)

## 🤝 Projekt Powiązany

- **Rider-Pi**: https://github.com/mpieniak01/Rider-Pi

## 📝 Licencja

Ten projekt jest częścią ekosystemu Rider-Pi.

---

**Ostatnia aktualizacja**: 2025-11-22  
**Status**: ✅ Faza 4 - Gotowe do Produkcji
