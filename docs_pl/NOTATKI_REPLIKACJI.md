# Notatki Replikacji UI i Kontraktu API

## Przegląd
Ten dokument opisuje pliki zreplikowane z [Rider-Pi](https://github.com/mpieniak01/Rider-Pi) do repozytorium Rider-Pc w celu umożliwienia rozwoju klienta PC.

## Zreplikowane Katalogi

### 1. `web/` - Komponenty Interfejsu Frontend (14 plików)
Cel: Zapewnia interfejs webowy dla replikacji UI 1:1 na kliencie PC.

**Struktura:**
```
web/
├── assets/
│   ├── dashboard-common.css       # Wspólne style dashboardu
│   ├── i18n.js                    # Wsparcie internacjonalizacji (PL/EN)
│   ├── menu.js                    # Dynamiczny loader menu
│   ├── icons/
│   │   ├── flag-en.svg            # Flaga języka angielskiego
│   │   └── flag-pl.svg            # Flaga języka polskiego
│   └── riderai_logi.svg           # Logo RiderAI
├── chat.html                      # Interfejs czatu głosowego i tekstowego
├── control.html                   # Panel sterowania ruchem robota
├── dashboard_menu_template.html   # Szablon menu wielokrotnego użytku
├── google_home.html               # Interfejs integracji Google Home
├── home.html                      # Główna strona lądowania
├── navigation.html                # Interfejs nawigacji autonomicznej (Rekonesans)
├── system.html                    # Status systemu i diagnostyka
└── view.html                      # Mini dashboard z metrykami i kamerą
```

**Kluczowe Funkcje:**
- Responsywny design dashboardu z ciemnym motywem
- Wsparcie wielu języków (Polski/Angielski)
- Wizualizacja danych w czasie rzeczywistym
- Integracja strumienia kamery
- Wyświetlanie metryk systemowych
- Śledzenie metryk API

**Notatki Integracyjne:**
- Te pliki powinny być połączone z **lokalnym Buforem/Cache** (Redis/SQLite) zamiast bezpośrednio z backendem Rider-PI
- Interfejs oczekuje danych z punktów końcowych takich jak `/healthz`, `/state`, `/sysinfo`, `/vision/snap-info`
- Pliki statyczne są serwowane ze ścieżki `/web/`
- Mechanizmy auto-odświeżania (≈2s) dla danych na żywo

### 2. `config/` - Pliki Konfiguracji Providerów (30 plików)
Cel: Definiuje konfiguracje providerów i parametry dla negocjacji kontraktu między PC a Rider-PI.

**Struktura:**
```
config/
├── agent/                         # Konfiguracja testów agenta
│   ├── constraints.txt            # Ograniczenia pakietów Python
│   ├── requirements-test.txt      # Zależności testowe
│   └── run_tests.sh              # Skrypt wykonania testów
├── alsa/                          # Konfiguracja audio
│   ├── aliases.toml              # Aliasy urządzeń ALSA
│   ├── asoundrc.wm8960           # Konfiguracja kodeka audio WM8960
│   ├── mpg123.sh                 # Skrypt odtwarzacza MP3
│   ├── preflight.sh              # Kontrole wstępne audio
│   ├── wm8960-apply.sh           # Zastosuj ustawienia WM8960
│   └── wm8960-mixer.sh           # Kontrole miksera WM8960
├── local/                         # Lokalne nadpisania konfiguracji
│   └── .gitignore                # Ignoruj lokalne pliki konfiguracyjne
├── camera.toml                    # Konfiguracja kamery
├── camera.toml.example            # Szablon konfiguracji kamery
├── choreography.toml              # Mapowania zdarzeń na akcje
├── face.toml                      # Konfiguracja animacji twarzy robota
├── google_bridge.toml             # Konfiguracja mostu Google Home
├── google_bridge.toml.example     # Szablon mostu Google
├── jupyter.toml                   # Konfiguracja notebooka Jupyter
├── jupyter.toml.example           # Szablon Jupyter
├── motion.toml                    # Konfiguracja sterowania ruchem
├── motion.toml.example            # Szablon konfiguracji ruchu
├── motion_actions.toml            # Predefiniowane akcje ruchu
├── vision.toml.example            # Szablon konfiguracji modułu wizji
├── voice.toml                     # Aktywna konfiguracja głosu
├── voice_gemini_example.toml      # Przykład głosu Google Gemini
├── voice_gemini_file.toml         # Konfiguracja oparta na pliku Gemini
├── voice_local_file.toml          # Lokalne przetwarzanie głosu
├── voice_openai_file.toml         # Konfiguracja oparta na pliku OpenAI
├── voice_openai_streaming.toml    # Konfiguracja streamingu OpenAI
├── voice_openai_streaming_fallback.toml  # OpenAI z fallbackiem
└── voice_web.toml.example         # Szablon głosu opartego na web
```

**Kluczowe Kategorie Konfiguracji:**

**Providerzy Głosu:**
- Wiele opcji providerów: OpenAI, Google Gemini, przetwarzanie lokalne
- Tryby streamingu i oparte na plikach
- Mechanizmy fallback
- Parametry ASR (Automatyczne Rozpoznawanie Mowy) i TTS (Tekst-na-Mowę)
- Konfiguracja VAD (Wykrywanie Aktywności Głosu)

**Providerzy Wizji:**
- Konfiguracja wykrywania krawędzi
- Parametry wykrywania przeszkód
- Ustawienia modelu SSD (Single Shot Detection)
- Przetwarzanie klatek kamery
- Zarządzanie zrzutami ekranu

**Konfiguracja Ruchu:**
- Parametry sterowania balansem
- Akcje ruchu i choreografia
- Odpowiedzi ruchu sterowane zdarzeniami

**Notatki Integracyjne:**
- Kopiuj szablony z `*.toml.example` do `config/local/*.toml` dla dostosowania
- Lokalne konfiguracje są w gitignore aby zapobiec commitowaniu wrażliwych danych
- Używaj tych konfiguracji do definiowania domyślnych wyborów providerów dla klienta PC
- Konfiguruj parametry konektora PC dla negocjacji kontraktu

### 3. `api-specs/` - Dokumentacja API (3 pliki)
Cel: Służy jako kontrakty API dla generacji klienta REST i testów kontraktowych.

**Struktura:**
```
api-specs/
├── README.md        # Przegląd API i wspólne wzorce
├── control.md       # API ruchu i sterowania robota
└── navigator.md     # API nawigacji autonomicznej
```

**Kategorie API:**

**API Sterowania** (`/api/control`):
- Ogólne komendy sterowania (drive, stop, spin)
- Sterowanie balansem (`/api/control/balance`)
- Regulacja wysokości (`/api/control/height`)
- Wzorce komend z prędkością liniową (lx) i prędkością kątową (az)

**API Nawigatora** (`/api/navigator`):
- Start/stop nawigacji autonomicznej
- Zarządzanie konfiguracją
- Funkcja powrotu do domu
- Aktualizacje statusu w czasie rzeczywistym

**Wspólne Wzorce:**
- Wsparcie CORS na wszystkich punktach końcowych
- Standardowy format odpowiedzi JSON: `{"ok": true/false, "data": {...}}`
- Pola timestamp w formacie Unix epoch
- Integracja magistrali ZMQ dla komend
- Wsparcie preflightu HTTP (OPTIONS)

**Notatki Integracyjne:**
- Używaj tych specyfikacji do generacji klienta REST z `httpx` (async)
- Implementuj testy kontraktowe do weryfikacji kompatybilności API
- Bazowy URL: `http://robot-ip:8080`
- Wszystkie punkty końcowe wspierają OPTIONS dla preflightu CORS

## Statystyki Plików
- **Całkowita liczba skopiowanych plików:** 47
- **web/:** 14 plików (HTML, CSS, JavaScript, SVG)
- **config/:** 30 plików (TOML, skrypty shell)
- **api-specs/:** 3 pliki (Dokumentacja Markdown)

## Informacje Źródłowe
- **Repozytorium Źródłowe:** https://github.com/mpieniak01/Rider-Pi
- **Repozytorium Docelowe:** https://github.com/mpieniak01/Rider-Pc
- **Data Replikacji:** 2025-11-12
- **Cel:** Umożliwienie rozwoju klienta PC z replikacją UI 1:1 i integracją API

## Następne Kroki

### 1. Implementacja Adaptera API
- Generuj klienta REST z specyfikacji API używając `httpx`
- Implementuj gniazdo ZMQ SUB dla tematów magistrali (`vision.*`, `voice.*`, `motion.state`, `robot.pose`)
- Twórz testy kontraktowe oparte na dokumentacji api-specs
- Obsługuj punkty końcowe REST: `/healthz`, `/api/control`, `/api/chat/*`, itp.
- Mapuj tematy ZMQ na lokalne zdarzenia domenowe

### 2. Implementacja Bufora/Cache
- Skonfiguruj Redis lub SQLite dla lokalnego buforowania danych
- Cachuj stany ekranów i zrzuty
- Buforuj surowe strumienie danych dla providerów
- Implementuj szybkie przywracanie UI
- Obsługuj synchronizację danych z Rider-PI

### 3. Integracja UI
- Skonfiguruj serwer web (FastAPI) aby serwował pliki z `web/`
- Połącz UI z lokalnym Buforem/Cache zamiast bezpośrednio z Rider-PI
- Implementuj punkty końcowe danych których oczekuje UI
- Włącz aktualizacje w czasie rzeczywistym przez WebSocket lub polling
- Testuj wszystkie strony dashboardu pod kątem funkcjonalności

### 4. Konfiguracja Providera
- Przejrzyj i dostosuj pliki konfiguracyjne dla środowiska PC
- Kopiuj odpowiednie pliki `*.toml.example` do `config/local/`
- Konfiguruj Provider Głosu dla offloadu ASR/TTS
- Konfiguruj Provider Wizji dla przetwarzania obrazów
- Konfiguruj Provider Tekstu dla zadań NLU/NLG
- Skonfiguruj odkrywanie i negocjację providerów

## Dodatkowe Zasoby
- [Architektura Rider-Pc](ARCHITEKTURA.md)
- [Następne Kroki Rider-Pc](PRACE_PRZYSZLE.md)
- [Architektura Urządzenia Rider-PI](ARCHITEKTURA_RIDER_PI.md)
- [Projekt Rider-Pi](https://github.com/mpieniak01/Rider-Pi)
