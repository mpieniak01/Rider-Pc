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

## Workflow Deweloperski: Rozpoczynanie Nowego Zadania

Rider-PC oferuje zintegrowany kreator zadań, który automatyzuje tworzenie nowych branchy i plików dokumentacji. Dzięki temu można szybko rozpocząć pracę nad nowym zadaniem bezpośrednio z interfejsu webowego.

### Wymagania Wstępne

1. Skonfigurowana integracja z GitHub (zobacz [KONFIGURACJA.md](KONFIGURACJA.md#integracja-z-github))
2. Uruchomiony serwer Rider-PC

### Krok po Kroku: Tworzenie Nowego Zadania

1. **Otwórz zakładkę "Projekt"**
   - W interfejsie Rider-PC (`http://localhost:8000`) przejdź do sekcji "Projekt" 
   - Zobaczysz listę otwartych zgłoszeń (Issues) z GitHub

2. **Kliknij "+ Nowe Zadanie"**
   - W prawym górnym rogu kliknij przycisk "+ Nowe Zadanie"
   - Otworzy się formularz kreatora zadań

3. **Wypełnij dane zadania**
   - **Tytuł** (wymagane): Krótki, opisowy tytuł zadania
   - **Opis**: Szczegółowy opis (obsługuje Markdown)
   - **Tagi**: Wybierz odpowiednie etykiety (labels)
   - **Przypisz do**: Opcjonalnie przypisz do współpracownika

4. **Wybierz kontekst GIT**

   Masz trzy opcje:
   
   - **Zostań na obecnym branchu**: Zadanie zostanie utworzone, ale nie zmieni się aktualny branch
   
   - **Utwórz nowy branch z main** (zalecane dla nowych funkcji):
     - Automatycznie utworzy branch o nazwie `feat/<numer-issue>-<slug-tytulu>`
     - Zaznacz opcję **"Zainicjuj automatycznie"** aby dodatkowo:
       - Utworzyć plik dokumentacji w `docs_pl/_to_do/<numer-issue>-<slug>.md`
       - Wykonać pierwszy commit z tym plikiem
   
   - **Przełącz na istniejący branch**: Wybierz branch z listy rozwijanej

5. **Kliknij "Utwórz Zadanie"**
   - System utworzy Issue na GitHub
   - Jeśli wybrano "Utwórz nowy branch" + "Zainicjuj automatycznie":
     - Zostanie utworzony nowy branch
     - Pojawi się plik dokumentacji w `docs_pl/_to_do/`
     - Zostanie wykonany pierwszy commit

### Co Się Dzieje Automatycznie?

Gdy wybierzesz opcję "Utwórz nowy branch" + "Zainicjuj automatycznie":

1. **Tworzenie Issue** - Na GitHub powstaje nowe zgłoszenie z podanym tytułem i opisem

2. **Tworzenie Brancha** - Z brancha `main` powstaje nowy branch:
   ```
   feat/<numer-issue>-<slug-tytulu>
   ```
   Przykład: `feat/42-dodaj-nowy-endpoint`

3. **Tworzenie Pliku Dokumentacji** - W katalogu `docs_pl/_to_do/` powstaje plik:
   ```
   <numer-issue>-<slug>.md
   ```
   Przykład: `docs_pl/_to_do/42-dodaj-nowy-endpoint.md`
   
   Plik zawiera szablon dokumentacji zadania z linkiem do Issue.

4. **Pierwszy Commit** - Automatyczny commit z wiadomością:
   ```
   docs: init task #<numer> - <tytuł>
   ```

### Rozwiązywanie Problemów

- **"GitHub nie skonfigurowany"**: Sprawdź zmienne środowiskowe `GITHUB_TOKEN`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME`
- **Błąd przy tworzeniu brancha**: Upewnij się, że token ma uprawnienia `repo` lub `Contents: Read and write`
- **Konflikt przy przełączaniu brancha**: Zapisz lokalne zmiany przed utworzeniem nowego zadania

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
