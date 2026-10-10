# Szybki start Rider-PC

## Opcja 1: Docker (Zalecane)

Jeżeli nie ma lokalnego `.env`, utwórz go z publicznego szablonu i ustaw własne
adresy oraz opcje providerów. Zachowaj istniejący `.env`.
Przed startem stosu przejrzyj [konfigurację](KONFIGURACJA.md):

```bash
docker compose up -d
```

Stos może uruchomić modele i usługi pomocnicze. Sprawdź konfigurację oraz
publikowane porty przed użyciem. W istniejącym WSL korzystaj z polecenia
lokalnego poniżej, które omija ponowną instalację przez launcher stosu.

## Opcja 2: Lokalne środowisko deweloperskie

```bash
.venv/bin/python --version
.venv/bin/python -m pip check
```

Zachowaj istniejący `.env`. Nie wykonuj ponownej instalacji pełnego stosu ML wyłącznie w celu sprawdzenia środowiska. Instrukcja [development](development.md) opisuje zakresy i polecenia testowania.

## Uruchomienie do walidacji

Po sprawdzeniu konfiguracji:

```bash
.venv/bin/python -m pc_client.main
```

Proces ładuje `.env` i skonfigurowane providery. Panel przy `SERVER_PORT=8000` jest pod `http://localhost:8000/`. Bezpośrednie polecenie korzysta z SERVER_PORT. Launcher stosu może instalować zależności; przejrzyj go przed użyciem.

Po podłączeniu robota sprawdź jego adres, port 8080 oraz `PC_PUBLIC_BASE_URL`, który musi wskazywać rzeczywisty adres panelu dostępny z Pi. Przy odłączonym robocie dane z cache lub mocka nie potwierdzają stanu urządzenia.

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

Uruchom pełen zestaw (jednostkowe + UI/E2E):
```bash
pytest -v
```

Podział na kategorie (markery ustawiane automatycznie w tests/conftest.py):
```bash
# tylko testy API/jednostkowe
pytest -m api
# tylko testy UI/E2E (Playwright)
pytest -m ui
```

Pokrycie testów:
- ✅ Operacje cache (set, get, expire, cleanup)
- ✅ Adapter REST (wszystkie punkty końcowe)
- ✅ Subskrybent ZMQ (dopasowywanie tematów, handlery)
 - ✅ UI/E2E (Playwright) dla panelu web

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

## Workflow deweloperski: nowe zadanie

Kreator w zakładce „Projekt” pozwala utworzyć Issue i wybrać gałąź Git.
Wymaga skonfigurowanej [integracji GitHub](KONFIGURACJA.md#integracja-z-github).
Wybierz tytuł i opis, następnie pozostanie na obecnej gałęzi, nową gałąź
`feat/<numer-issue>-<slug>` lub istniejącą gałąź. Przed przełączeniem
zachowaj niezapisane zmiany.

Plany w `docs_pl/_to_do/` są lokalne. Ustaw `TASK_AUTO_INIT_ENABLED=false`
w lokalnym `.env` i pozostaw opcję „Zainicjuj automatycznie” wyłączoną.
Historyczny inicjalizator tworzy plan i próbuje wykonać commit; aktualne reguły
Git ignorują ten katalog, więc zwykłe dodanie planu zostanie odrzucone.
Nie obchodź reguły przez `git add -f`. Plan zapisuj lokalnie, a do commita
dodawaj wynikową dokumentację projektu i implementację.

Szczegóły opisują [development](development.md) i
[polityka dokumentacji](POLITYKA_DOKUMENTACJI.md).

## Chat PC Standalone

Rider-PC oferuje tryb Chat PC Standalone, który umożliwia korzystanie z lokalnych modeli AI (Ollama) bez połączenia z Rider-Pi. Jest to idealne rozwiązanie do:
- Pracy offline
- Testowania lokalnych modeli LLM
- Przetwarzania wrażliwych danych bez wysyłania ich na zewnętrzne serwery

### Wymagania

1. **Ollama** - lokalny serwer modeli LLM
   ```bash
   # Instalacja Ollama (Linux)
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Uruchom serwer
   ollama serve
   
   # Pobierz model (zalecany dla szybkiego działania)
   ollama pull llama3.2:1b
   ```

2. **Konfiguracja środowiska**
   ```bash
   export ENABLE_PROVIDERS=true
   export ENABLE_TEXT_OFFLOAD=true
   # Opcjonalnie: użyj dedykowanej konfiguracji
   export TEXT_PROVIDER_CONFIG=config/providers_text_local.toml
   ```

### Uruchomienie

```bash
# Standardowe uruchomienie z obsługą Chat PC
ENABLE_PROVIDERS=true ENABLE_TEXT_OFFLOAD=true python -m pc_client.main
```

### Interfejs Chat PC

1. Otwórz przeglądarkę: `http://localhost:8000/chat-pc`
2. Wybierz tryb:
   - **PC** - wymuszony tryb lokalny (tylko Ollama)
   - **Auto** - automatyczny wybór (preferuje lokalny, fallback na proxy)
   - **Proxy** - wymuszony tryb przez Rider-Pi
3. Status providera wyświetla się na górze strony:
   - Model (np. `llama3.2:1b`)
   - Silnik (`ollama` lub `mock`)
   - Dostępność

### API Endpointy

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/chat/pc/send` | POST | Czat wyłącznie lokalny (503 jeśli brak providera) |
| `/api/chat/send` | POST | Czat z automatycznym wyborem trybu (parametr `mode`) |
| `/api/providers/text` | GET | Status providera tekstowego |
| `/api/chat/pc/generate-pr-content` | POST | Generowanie treści PR z AI |

### Asystent PR

Chat PC zawiera wbudowaną funkcję generowania treści Pull Requestów:

1. Rozwiń sekcję "Asystent PR" na stronie `/chat-pc`
2. Wprowadź szkic zmian
3. Wybierz styl (Szczegółowy/Zwięzły/Techniczny) i język
4. Kliknij "Generuj PR"

API:
```bash
curl -X POST http://localhost:8000/api/chat/pc/generate-pr-content \
  -H "Content-Type: application/json" \
  -d '{
    "draft": "Dodaję nową funkcję X do modułu Y",
    "style": "detailed",
    "language": "pl"
  }'
```

### Rozwiązywanie Problemów (Chat PC)

**Provider niedostępny (status 503)**
- Sprawdź czy Ollama działa: `curl http://localhost:11434/api/tags`
- Upewnij się że model jest pobrany: `ollama list`
- Sprawdź zmienne środowiskowe: `ENABLE_PROVIDERS=true`, `ENABLE_TEXT_OFFLOAD=true`

**Wolne odpowiedzi**
- Użyj mniejszego modelu: `ollama pull llama3.2:1b`
- Sprawdź obciążenie GPU/CPU

**Brak odpowiedzi w trybie proxy**
- Sprawdź połączenie z Rider-Pi: `curl http://<RIDER_PI_HOST>:8080/healthz`

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
