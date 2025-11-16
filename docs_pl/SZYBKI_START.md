# Przewodnik Szybkiego Startu - Rider-PC Client

## Przegląd
Rider-PC Client jest teraz operacyjny z następującymi komponentami:
- ✅ Adapter REST API do konsumowania punktów końcowych Rider-PI
- ✅ Subskrybent ZMQ dla strumieni danych w czasie rzeczywistym
- ✅ Cache SQLite do buforowania danych
- ✅ Serwer Web FastAPI replikujący interfejs użytkownika Rider-PI
- ✅ Kompleksowe testy jednostkowe (25 testów przechodzących)

## Szybki Start

### 1. Zainstaluj Zależności
```bash
pip install -r requirements.txt
```

### 2. Skonfiguruj Połączenie
Ustaw zmienne środowiskowe wskazujące na Twoje urządzenie Rider-PI:

```bash
export RIDER_PI_HOST="192.168.1.100"  # Zamień na IP Twojego Rider-PI
export RIDER_PI_PORT="8080"
export ZMQ_PUB_PORT="5555"
```

### 3. Uruchom Serwer
```bash
./run.sh
```

Lub bezpośrednio z Pythonem:
```bash
PYTHONPATH=. python -m pc_client.main
```

### 4. Dostęp do Interfejsu Użytkownika
Otwórz przeglądarkę pod adresem: `http://localhost:8000/`

## Architektura

```
┌─────────────────────────────────────────────┐
│           Urządzenie Rider-PI                │
│  ┌────────────┐      ┌────────────┐        │
│  │ REST API   │      │ ZMQ PUB    │        │
│  │ :8080      │      │ :5555      │        │
│  └────────────┘      └────────────┘        │
└─────────────────────────────────────────────┘
         │                    │
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────────┐
│         PC Client (WSL/Linux)                │
│  ┌────────────────────────────────────┐     │
│  │  Warstwa Adaptera                  │     │
│  │  • Klient REST (httpx)             │     │
│  │  • Subskrybent ZMQ (pyzmq)         │     │
│  └────────────────────────────────────┘     │
│                  │                           │
│                  ▼                           │
│  ┌────────────────────────────────────┐     │
│  │  Warstwa Cache (SQLite)            │     │
│  │  • Przechowuje bieżące stany       │     │
│  │  • Wygasanie oparte na TTL         │     │
│  └────────────────────────────────────┘     │
│                  │                           │
│                  ▼                           │
│  ┌────────────────────────────────────┐     │
│  │  Serwer Web (FastAPI)              │     │
│  │  • Serwuje pliki statyczne         │     │
│  │  • Udostępnia punkty końcowe API   │     │
│  │  • Auto-odświeżanie danych co 2s   │     │
│  └────────────────────────────────────┘     │
│                  │                           │
└─────────────────────────────────────────────┘
                   │
                   ▼
          Przeglądarka (localhost:8000)

```

## Przepływ Danych

1. **Synchronizacja REST (co 2s)**:
   - Zadanie w tle pobiera dane z REST API Rider-PI
   - Dane są cachowane w SQLite z TTL 30s
   - Punkty końcowe API serwują cachowane dane

2. **ZMQ w czasie rzeczywistym**:
   - Subskrybent łączy się z publisherem ZMQ Rider-PI
   - Nasłuchuje tematów: `vision.*`, `motion.*`, `robot.*`, `navigator.*`
   - Wiadomości są automatycznie cachowane

3. **Interfejs Web**:
   - Frontend odpytuje punkty końcowe API co 2s
   - Wyświetla cachowane dane z klienta PC
   - Nie wymaga bezpośredniego połączenia z Rider-PI

## Punkty Końcowe API

Wszystkie punkty końcowe replikują REST API Rider-PI:

- `GET /` - Serwuje dashboard view.html
- `GET /healthz` - Status zdrowia
- `GET /state` - Bieżący stan
- `GET /sysinfo` - Informacje systemowe
- `GET /vision/snap-info` - Informacje o zrzucie ekranu wizji
- `GET /vision/obstacle` - Dane wykrywania przeszkód
- `GET /api/app-metrics` - Metryki aplikacji
- `GET /api/resource/camera` - Status zasobu kamery
- `GET /api/bus/health` - Stan zdrowia magistrali komunikatów
- `GET /camera/placeholder` - Obraz zastępczy

## Opcje Konfiguracji

Zmienne środowiskowe:

| Zmienna | Domyślna | Opis |
|----------|---------|-------------|
| `RIDER_PI_HOST` | `localhost` | Adres IP Rider-PI |
| `RIDER_PI_PORT` | `8080` | Port REST API |
| `ZMQ_PUB_PORT` | `5555` | Port publishera ZMQ |
| `ZMQ_SUB_PORT` | `5556` | Port subskrybenta ZMQ |
| `SERVER_HOST` | `0.0.0.0` | Host serwera klienta PC |
| `SERVER_PORT` | `8000` | Port serwera klienta PC |
| `CACHE_DB_PATH` | `data/cache.db` | Ścieżka bazy danych SQLite |
| `CACHE_TTL_SECONDS` | `30` | TTL cache w sekundach |
| `LOG_LEVEL` | `INFO` | Poziom logowania |

## Testowanie

Uruchom testy jednostkowe:
```bash
pytest pc_client/tests/ -v
```

Pokrycie testów:
- ✅ Operacje cache (set, get, expire, cleanup)
- ✅ Adapter REST (wszystkie punkty końcowe)
- ✅ Subskrybent ZMQ (dopasowywanie tematów, handlery)

## Rozwiązywanie Problemów

### Błędy Połączenia
Jeśli widzisz błędy "All connection attempts failed":
1. Sprawdź, czy Rider-PI działa i jest dostępny
2. Sprawdź reguły firewall na PC i Rider-PI
3. Przetestuj łączność: `ping <RIDER_PI_HOST>`
4. Przetestuj REST API: `curl http://<RIDER_PI_HOST>:8080/healthz`

### Problemy z Połączeniem ZMQ
Jeśli subskrybent ZMQ nie otrzymuje wiadomości:
1. Sprawdź, czy porty ZMQ są otwarte: 5555, 5556
2. Sprawdź, czy broker ZMQ Rider-PI działa
3. Upewnij się, że tematy są publikowane na Rider-PI

### Interfejs Użytkownika się Nie Ładuje
Jeśli view.html się nie renderuje:
1. Sprawdź, czy katalog `web/` istnieje
2. Sprawdź, czy pliki statyczne są serwowane pod `/web/`
3. Sprawdź konsolę przeglądarki pod kątem błędów

## Następne Kroki

Przyszłe usprawnienia planowane:
- [ ] Provider Głosu (offload ASR/TTS do PC)
- [ ] Provider Wizji (przetwarzanie obrazów na GPU PC)
- [ ] Provider Tekstu (NLU/NLG z lokalnymi modelami)
- [ ] Kolejka Zadań (RabbitMQ/Redis + Celery)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Konteneryzacja Docker
- [ ] Bezpieczny tunel VPN (WireGuard)

## Struktura Plików

```
pc_client/
├── __init__.py              # Inicjalizacja pakietu
├── main.py                  # Punkt wejścia aplikacji
├── adapters/               # Adaptery danych
│   ├── __init__.py
│   ├── rest_adapter.py     # Klient REST API
│   └── zmq_subscriber.py   # Subskrybent ZMQ
├── api/                    # Serwer FastAPI
│   ├── __init__.py
│   └── server.py           # Implementacja serwera
├── cache/                  # Warstwa cache
│   ├── __init__.py
│   └── cache_manager.py    # Cache SQLite
├── config/                 # Konfiguracja
│   ├── __init__.py
│   └── settings.py         # Zarządzanie ustawieniami
└── tests/                  # Testy jednostkowe
    ├── __init__.py
    ├── test_cache.py
    ├── test_rest_adapter.py
    └── test_zmq_subscriber.py
```

## Wsparcie

W przypadku problemów lub pytań:
- Sprawdź główny [README.md](README.md)
- Przejrzyj [ARCHITEKTURA.md](ARCHITEKTURA.md)
- Zobacz specyfikacje API w [api-specs/](api-specs/)
