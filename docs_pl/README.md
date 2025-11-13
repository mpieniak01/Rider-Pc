# Rider-PC Client

Infrastruktura klienta PC dla robota Rider-PI, zapewniająca:
- Adapter REST API do konsumowania punktów końcowych Rider-PI
- Subskrybent ZMQ dla strumieni danych w czasie rzeczywistym
- Lokalny cache SQLite do buforowania danych
- Serwer web FastAPI replikujący interfejs użytkownika Rider-PI
- **Warstwa Providerów AI** z prawdziwymi modelami ML (Głos, Wizja, Tekst)
- **Wdrożenie gotowe do produkcji** z Docker i CI/CD

## 🎉 Faza 4 Zakończona: Prawdziwe Modele AI i Wdrożenie Produkcyjne

Ten projekt teraz zawiera:
- ✅ **Prawdziwe Modele AI**: Whisper ASR, Piper TTS, YOLOv8 Vision, Ollama LLM
- ✅ **Wdrożenie Docker**: Kompletny stos z Redis, Prometheus, Grafana
- ✅ **Pipeline CI/CD**: Automatyczne testowanie, skanowanie bezpieczeństwa, budowy Docker
- ✅ **Sondy Zdrowia**: Punkty końcowe gotowości i żywotności zgodne z Kubernetes
- ✅ **Automatyczny Fallback**: Tryb mock gdy modele niedostępne

Zobacz [WDROZENIE_ZAKONCZONE_FAZA4.md](PR/WDROZENIE_ZAKONCZONE_FAZA4.md) dla szczegółów.

## Szybki Start

### Opcja 1: Docker (Zalecane)
```bash
# Utwórz plik .env
echo "RIDER_PI_HOST=192.168.1.100" > .env

# Uruchom pełny stos
docker-compose up -d

# Dostęp do usług
# Interfejs Rider-PC: http://localhost:8000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

### Opcja 2: Lokalne Środowisko Deweloperskie
```bash
# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom w trybie mock (nie wymaga modeli AI)
python -m pc_client.main
```

Zobacz [KONFIGURACJA_MODELI_AI.md](KONFIGURACJA_MODELI_AI.md) dla przewodnika konfiguracji modeli AI.

## Architektura

Klient PC składa się z trzech głównych warstw:

1. **Warstwa Adaptera** - Konsumuje dane z Rider-PI przez REST API i strumienie ZMQ
2. **Warstwa Cache** - Przechowuje bieżące stany w SQLite dla szybkiego dostępu
3. **Warstwa Serwera Web** - Serwer FastAPI służący pliki statyczne i udostępniający punkty końcowe API odczytujące z cache

## Wymagania Wstępne

- Python 3.9 lub wyższy
- WSL2 z Debian (dla użytkowników Windows)
- Dostęp sieciowy do urządzenia Rider-PI

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone https://github.com/mpieniak01/Rider-Pc.git
cd Rider-Pc
```

2. Utwórz środowisko wirtualne:
```bash
python3.9 -m venv venv
source venv/bin/activate  # Na Windows: venv\Scripts\activate
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

## Konfiguracja

Skonfiguruj klienta PC używając zmiennych środowiskowych:

```bash
# Połączenie z Rider-PI
export RIDER_PI_HOST="192.168.1.100"  # Adres IP Twojego Rider-PI
export RIDER_PI_PORT="8080"           # Port REST API

# Konfiguracja ZMQ
export ZMQ_PUB_PORT="5555"            # Port ZMQ PUB
export ZMQ_SUB_PORT="5556"            # Port ZMQ SUB

# Serwer lokalny
export SERVER_HOST="0.0.0.0"          # Host serwera
export SERVER_PORT="8000"             # Port serwera

# Cache
export CACHE_DB_PATH="data/cache.db"  # Ścieżka bazy danych SQLite
export CACHE_TTL_SECONDS="30"         # TTL cache w sekundach

# Logowanie
export LOG_LEVEL="INFO"               # Poziom logowania (DEBUG, INFO, WARNING, ERROR)
```

## Uruchamianie

Uruchom serwer klienta PC:

```bash
python -m pc_client.main
```

Lub jeśli zainstalowany jako pakiet:

```bash
python pc_client/main.py
```

Serwer uruchomi się domyślnie na `http://localhost:8000`.

Dostęp do interfejsu użytkownika pod adresem: `http://localhost:8000/`

## Punkty Końcowe API

Klient PC replikuje następujące punkty końcowe Rider-PI:

- `GET /healthz` - Sprawdzenie stanu zdrowia
- `GET /state` - Bieżący stan
- `GET /sysinfo` - Informacje systemowe
- `GET /vision/snap-info` - Informacje o zrzucie ekranu wizji
- `GET /vision/obstacle` - Dane wykrywania przeszkód
- `GET /api/app-metrics` - Metryki aplikacji
- `GET /api/resource/camera` - Status zasobu kamery
- `GET /api/bus/health` - Stan zdrowia magistrali komunikatów

Wszystkie punkty końcowe zwracają dane JSON z cache z urządzenia Rider-PI.

## Tematy ZMQ

Subskrybent ZMQ nasłuchuje następujących wzorców tematów:

- `vision.*` - Zdarzenia systemu wizji
- `motion.*` - Zdarzenia systemu ruchu
- `robot.*` - Zdarzenia stanu robota
- `navigator.*` - Zdarzenia nawigatora

Wiadomości są automatycznie cachowane i dostępne przez REST API.

## Rozwój

### Uruchamianie Testów

Zainstaluj zależności testowe:
```bash
pip install pytest pytest-asyncio pytest-timeout
```

Uruchom testy:
```bash
pytest pc_client/tests/ -v
```

Uruchom konkretny test:
```bash
pytest pc_client/tests/test_cache.py -v
```

### Struktura Projektu

```
pc_client/
├── __init__.py
├── main.py              # Punkt wejścia aplikacji
├── adapters/            # Adaptery REST i ZMQ
│   ├── rest_adapter.py
│   └── zmq_subscriber.py
├── api/                 # Serwer FastAPI
│   └── server.py
├── cache/              # Menedżer cache SQLite
│   └── cache_manager.py
├── config/             # Konfiguracja
│   └── settings.py
└── tests/              # Testy jednostkowe
    ├── test_cache.py
    ├── test_rest_adapter.py
    └── test_zmq_subscriber.py
```

## Rozwiązywanie Problemów

### Problemy z Połączeniem

Jeśli nie możesz połączyć się z Rider-PI:
1. Sprawdź adres IP Rider-PI za pomocą `ping <RIDER_PI_HOST>`
2. Sprawdź, czy porty 8080, 5555, 5556 są dostępne
3. Upewnij się, że reguły firewall zezwalają na połączenia
4. Sprawdź logi za pomocą `LOG_LEVEL=DEBUG`

### Problemy z Cache

Jeśli dane nie są aktualizowane:
1. Sprawdź, czy baza danych cache jest zapisywalna
2. Zweryfikuj ustawienia TTL cache
3. Przejrzyj logi pod kątem błędów adaptera

### Interfejs Użytkownika się Nie Ładuje

Jeśli interfejs web się nie ładuje:
1. Sprawdź, czy katalog `web/` istnieje
2. Sprawdź, czy `view.html` jest obecny
3. Upewnij się, że pliki statyczne są serwowane pod `/web/`

## Warstwa Providerów AI - Faza 4 ✅

Klient PC zawiera gotową do produkcji warstwę providerów AI do odciążenia zadań obliczeniowych z Rider-PI:

### Prawdziwe Modele AI (z automatycznym fallbackiem do mock)

- **Provider Głosu**: 
  - **ASR**: OpenAI Whisper (model base, ~140MB)
  - **TTS**: Piper TTS (en_US-lessac-medium)
  - Konfiguracja: `config/voice_provider.toml`
  
- **Provider Wizji**: 
  - **Detekcja**: YOLOv8 nano (~6MB)
  - Wykrywanie obiektów w czasie rzeczywistym z ramkami ograniczającymi
  - Klasyfikacja przeszkód dla nawigacji
  - Konfiguracja: `config/vision_provider.toml`
  
- **Provider Tekstu**: 
  - **LLM**: Ollama (llama3.2:1b, ~1.3GB)
  - Lokalne wnioskowanie, brak zależności chmurowych
  - Cachowanie odpowiedzi
  - Konfiguracja: `config/text_provider.toml`

### Funkcje Infrastruktury

- **Kolejka Zadań**: Przetwarzanie asynchroniczne oparte na priorytetach (Redis)
- **Circuit Breaker**: Automatyczny fallback przy awariach
- **Telemetria**: Metryki Prometheus w czasie rzeczywistym
- **Sondy Zdrowia**: Punkty końcowe `/health/live` i `/health/ready`
- **Wdrożenie Docker**: Kompletny stos z monitoringiem

### Szybki Start z Prawdziwymi Modelami AI

**Opcja 1: Docker (Wszystko w jednym)**
```bash
docker-compose up -d
# Modele pobierają się automatycznie przy pierwszym użyciu
```

**Opcja 2: Konfiguracja Lokalna**

1. **Włącz providerów** w `.env`:
```bash
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=true
```

2. **Konfiguruj zależności**:
```bash
# Redis (kolejka zadań)
sudo apt install redis-server
sudo systemctl start redis-server

# Ollama (opcjonalnie, dla Provider Tekstu)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:1b
```

3. **Uruchom aplikację**:
```bash
python -m pc_client.main
# Modele Głosu i Wizji pobierają się automatycznie
```

**Opcja 3: Tryb Mock (Bez Modeli)**
```bash
# Ustaw use_mock=true w plikach konfiguracyjnych lub:
python -m pc_client.main
# Providerzy automatycznie przechodzą do trybu mock jeśli modele niedostępne
```

Zobacz [KONFIGURACJA_MODELI_AI.md](KONFIGURACJA_MODELI_AI.md) dla szczegółowych instrukcji konfiguracji.

4. Dostęp do monitoringu:
```bash
# Zobacz metryki Prometheus
curl http://localhost:8000/metrics

# Zobacz stan zdrowia aplikacji
curl http://localhost:8000/healthz
```

### Telemetria i Monitoring

Klient PC zawiera kompleksową telemetrię:

- **Metryki Prometheus**: Metryki przetwarzania zadań, rozmiar kolejki, stan circuit breakera
- **Publisher Telemetrii ZMQ**: Wysyłanie wyników z powrotem do Rider-PI przez ZMQ
- **Logowanie**: Ujednolicone prefiksy logów ([voice], [vision], [provider], [bridge])
- **Punkt Końcowy Metryk**: `/metrics` dla scrapowania Prometheus

Kluczowe udostępnione metryki:
- `provider_tasks_processed_total` - Całkowita liczba zadań przetworzonych przez providera
- `provider_task_duration_seconds` - Histogram czasu przetwarzania zadania
- `task_queue_size` - Bieżący rozmiar kolejki zadań
- `circuit_breaker_state` - Stan circuit breakera na providera
- `cache_hits_total` / `cache_misses_total` - Wydajność cache

### Dokumentacja

- [Przewodnik Implementacji Providerów](PR/PRZEWODNIK_IMPLEMENTACJI_PROVIDEROW.md) - Jak używać i rozszerzać providerów
- [Konfiguracja Bezpieczeństwa Sieci](PR/KONFIGURACJA_BEZPIECZENSTWA_SIECI.md) - Konfiguracja VPN/mTLS
- [Konfiguracja Kolejki Zadań](PR/KONFIGURACJA_KOLEJKI_ZADAN.md) - Konfiguracja Redis/RabbitMQ
- [Konfiguracja Monitoringu](PR/KONFIGURACJA_MONITORINGU.md) - Konfiguracja Prometheus/Grafana

### Typy Zadań

- `voice.asr` - Mowa-na-tekst (priorytet: 5)
- `voice.tts` - Tekst-na-mowę (priorytet: 5)
- `vision.detection` - Wykrywanie obiektów (priorytet: 8)
- `vision.frame` - Przetwarzanie klatek dla unikania przeszkód (priorytet: 1, krytyczne)
- `text.generate` - Generowanie tekstu LLM (priorytet: 3)
- `text.nlu` - Rozumienie języka naturalnego (priorytet: 5)

### Testowanie

Wszystkie funkcje providerów zawierają kompleksowe testy:
```bash
# Uruchom wszystkie testy (87 testów w sumie)
pytest pc_client/tests/ -v

# Uruchom tylko testy providerów
pytest pc_client/tests/test_providers.py -v

# Uruchom testy telemetrii
pytest pc_client/tests/test_telemetry.py -v

# Uruchom testy integracyjne
pytest pc_client/tests/test_integration.py -v
```

## Licencja

Ten projekt jest częścią ekosystemu Rider-PI.

## Zobacz Również

- [Repozytorium Rider-PI](https://github.com/mpieniak01/Rider-Pi)
- [Dokumentacja API](../api-specs_pl/README.md)
- [Przegląd Architektury](ARCHITEKTURA.md)
- [Przewodnik Implementacji Providerów](PR/PRZEWODNIK_IMPLEMENTACJI_PROVIDEROW.md)
