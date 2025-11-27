# Konfiguracja Rider-PC

Centralny hub dokumentacji konfiguracyjnej dla systemu Rider-PC Client.

## Przegląd

Rider-PC wymaga konfiguracji w kilku obszarach, zależnie od używanych funkcji i środowiska wdrożenia. Ten dokument służy jako przewodnik po wszystkich aspektach konfiguracji.

## Podstawowa Konfiguracja

### Zmienne Środowiskowe

Podstawowe zmienne konfiguracyjne znajdują się w pliku `.env`:

```bash
# Połączenie z Rider-PI
RIDER_PI_HOST=192.168.1.100
RIDER_PI_PORT=8080

# Konfiguracja ZMQ
ZMQ_PUB_PORT=5555
ZMQ_SUB_PORT=5556

# Serwer lokalny
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Cache
CACHE_DB_PATH=data/cache.db
CACHE_TTL_SECONDS=30

# Logowanie
LOG_LEVEL=INFO
```

### Tryby Uruchomienia

- **Tryb Docker**: Zalecany dla produkcji - zobacz [SZYBKI_START.md](SZYBKI_START.md#opcja-1-docker-zalecane)
- **Tryb Lokalny**: Dla rozwoju - zobacz [SZYBKI_START.md](SZYBKI_START.md#opcja-2-lokalne-środowisko-deweloperskie)

## Przewodniki Konfiguracyjne

### 1. Modele AI

**Dokument**: [KONFIGURACJA_MODELI_AI.md](KONFIGURACJA_MODELI_AI.md)

Konfiguracja trzech domen providerów AI:
- **Provider Głosu**: Whisper (ASR) + Piper (TTS)
- **Provider Wizji**: YOLOv8 dla detekcji obiektów
- **Provider Tekstu**: Ollama (LLM) dla generowania tekstu

Zawiera:
- Instalację modeli (automatyczna vs. ręczna)
- Wybór wariantów modeli (tiny/base/small/medium/large)
- Konfigurację trybu mock dla testowania
- Optymalizację wydajności i pamięci

### 2. Bezpieczeństwo Sieci

**Dokument**: [KONFIGURACJA_BEZPIECZENSTWA.md](KONFIGURACJA_BEZPIECZENSTWA.md)

Bezpieczne kanały komunikacji między Rider-PI a PC:
- **Tryb Development**: Połączenie nieszyfrowane dla sieci lokalnej
- **WireGuard VPN**: Zalecany dla produkcji - nowoczesny, lekki protokół
- **Mutual TLS (mTLS)**: Dla środowisk wymagających wzajemnego uwierzytelniania

Zawiera:
- Instalację i konfigurację WireGuard
- Generowanie certyfikatów mTLS
- Konfigurację firewall
- Automatyczny start i monitoring

### 3. Kolejka Zadań

**Dokument**: [KONFIGURACJA_KOLEJKI_ZADAN.md](KONFIGURACJA_KOLEJKI_ZADAN.md)

Konfiguracja brokera kolejki zadań dla przetwarzania asynchronicznego:
- **Redis**: Zalecany dla rozwoju - prosty, szybki
- **RabbitMQ**: Zalecany dla produkcji - zaawansowane funkcje

Zawiera:
- Instalację i konfigurację Redis/RabbitMQ
- Kolejki priorytetowe (1-10)
- Persystencję i niezawodność
- Optymalizację wydajności
- Backup i recovery

Mapowanie priorytetów:
- Priorytet 1-2: Krytyczne (unikanie przeszkód)
- Priorytet 3-4: Wysokie (sterowanie)
- Priorytet 5-6: Normalne (ASR/TTS)
- Priorytet 7-8: Niskie (generowanie tekstu)
- Priorytet 9-10: Tło (logowanie)

### 4. Monitoring

**Dokument**: [KONFIGURACJA_MONITORINGU.md](KONFIGURACJA_MONITORINGU.md)

Kompleksowy monitoring z Prometheus i Grafana:
- **Prometheus**: Zbieranie i przechowywanie metryk
- **Grafana**: Wizualizacja i dashboardy
- **Node Exporter**: Metryki systemowe
- **Alertmanager**: Zarządzanie alertami

Zawiera:
- Instalację stosu monitoringu
- Konfigurację reguł alertów
- Kluczowe metryki do monitorowania
- Gotowe dashboardy Grafana
- Rozwiązywanie problemów

Kluczowe alerty:
- Wysoka długość kolejki zadań
- Circuit breaker otwarty
- Niska szybkość przetwarzania
- Wysokie użycie pamięci
- Wysoki wskaźnik awarii zadań

## Pliki Konfiguracyjne

### Struktura Katalogów

```
config/
├── providers.toml          # Konfiguracja providerów AI (głos, wizja, tekst)
├── .env                    # Zmienne środowiskowe
└── grafana-dashboard.json  # Dashboard Grafana

.env.example               # Przykładowa konfiguracja
```

### Plik providers.toml

Scentralizowana konfiguracja wszystkich providerów AI:

```toml
[voice]
asr_model = "base"
tts_model = "en_US-lessac-medium"
sample_rate = 16000
use_mock = false

[vision]
detection_model = "yolov8n"
confidence_threshold = 0.5
max_detections = 10
use_mock = false

[text]
model = "llama3.2:1b"
max_tokens = 512
temperature = 0.7
ollama_host = "http://localhost:11434"
use_mock = false
enable_cache = true
```

## Scenariusze Konfiguracyjne

### Development (Lokalne środowisko)

```bash
# Minimal setup dla rozwoju
ENABLE_PROVIDERS=false       # Używaj trybu mock
SECURE_MODE=false            # Bez szyfrowania w sieci lokalnej
ENABLE_TASK_QUEUE=false      # Przetwarzanie synchroniczne
ENABLE_TELEMETRY=false       # Wyłącz telemetrię
LOG_LEVEL=DEBUG              # Szczegółowe logi
```

### Production (Docker Compose)

```bash
# Pełna funkcjonalność
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=true
ENABLE_VISION_OFFLOAD=true
ENABLE_VOICE_OFFLOAD=true
ENABLE_TEXT_OFFLOAD=true
SECURE_MODE=true             # WireGuard VPN
LOG_LEVEL=INFO
```

### Testing (CI/CD)

```bash
# Minimalne zależności
ENABLE_PROVIDERS=true
use_mock=true                # W providers.toml
ENABLE_TASK_QUEUE=true
TASK_QUEUE_BACKEND=redis
ENABLE_TELEMETRY=false
LOG_LEVEL=WARNING
```

## Porty i Usługi

| Usługa | Port | Typ | Opis |
|--------|------|-----|------|
| **Rider-PC UI** | 8000 | Lokalny | Web UI FastAPI |
| **Rider-Pi API** | 8080 | Zdalny | REST API robota |
| **ZMQ PUB** | 5555 | Zdalny | Publikacja zdarzeń z Pi |
| **ZMQ SUB** | 5556 | Zdalny | Subskrypcja odpowiedzi |
| **ZMQ Telemetria** | 5557 | Lokalny | Publikacja wyników z PC |
| **Redis** | 6379 | Lokalny | Broker kolejki zadań |
| **Prometheus** | 9090 | Lokalny | Metryki |
| **Grafana** | 3000 | Lokalny | Dashboardy |
| **Ollama** | 11434 | Lokalny | LLM API |

## Rozwiązywanie Problemów

### Problemy z Połączeniem

1. Sprawdź zmienne środowiskowe (`RIDER_PI_HOST`, `RIDER_PI_PORT`)
2. Weryfikuj dostępność sieci: `ping $RIDER_PI_HOST`
3. Testuj REST API: `curl http://$RIDER_PI_HOST:8080/healthz`
4. Sprawdź porty ZMQ: `ss -tulnp | grep 5555`
5. Zobacz logi: `LOG_LEVEL=DEBUG python -m pc_client.main`

### Problemy z Providerami

1. Sprawdź czy modele są zainstalowane
2. Weryfikuj konfigurację w `config/providers.toml`
3. Testuj w trybie mock: `use_mock = true`
4. Sprawdź logi providera: `grep "\[provider\]" logs/panel-*.log`
5. Monitoruj metryki: `curl http://localhost:8000/metrics | grep provider`

### Problemy z Kolejką

1. Sprawdź czy Redis działa: `redis-cli ping`
2. Monitoruj długość kolejki: `redis-cli LLEN task_queue:priority:5`
3. Zobacz zadania w kolejce: `redis-cli KEYS "task_queue:*"`
4. Sprawdź workery: `grep "\[worker\]" logs/panel-*.log`

## Zarządzanie Lokalnymi Usługami Systemowymi

### Przegląd

Rider-PC może zarządzać lokalnymi usługami systemd na systemach Linux. Umożliwia to dashboardowi uruchamianie, zatrzymywanie i restartowanie usług systemowych jak `rider-task-queue.service` czy `rider-voice.service`.

### Konfiguracja

Aby włączyć rzeczywiste zarządzanie usługami systemd, ustaw następujące zmienne środowiskowe:

```bash
# Lista jednostek systemd do monitorowania i kontrolowania (oddzielona przecinkami)
MONITORED_SERVICES=rider-pc.service,rider-voice.service,rider-task-queue.service

# Czy używać sudo dla poleceń systemctl (domyślnie: true)
# Ustaw na false jeśli Rider-PC działa jako root
SYSTEMD_USE_SUDO=true
```

### Konfiguracja Sudoers

Ponieważ operacje systemd wymagają podwyższonych uprawnień, musisz skonfigurować dostęp sudo bez hasła dla użytkownika uruchamiającego Rider-PC. Pozwala to aplikacji wykonywać polecenia `systemctl` bez pytania o hasło.

1. Utwórz plik sudoers dla Rider-PC:

```bash
sudo visudo -f /etc/sudoers.d/rider-pc
```

2. Dodaj następujące reguły (zamień `rider` na nazwę użytkownika uruchamiającego Rider-PC):

> **Uwaga**: Te reguły zakładają, że `systemctl` znajduje się w `/usr/bin/systemctl`. Jeśli na Twoim systemie jest inaczej, sprawdź lokalizację poleceniem `which systemctl` i odpowiednio dostosuj ścieżki.

```sudoers
# Pozwól użytkownikowi rider zarządzać usługami Rider bez hasła
rider ALL=(root) NOPASSWD: /usr/bin/systemctl start rider-*, \
                           /usr/bin/systemctl stop rider-*, \
                           /usr/bin/systemctl restart rider-*, \
                           /usr/bin/systemctl enable rider-*, \
                           /usr/bin/systemctl disable rider-*
```

3. Ustaw prawidłowe uprawnienia:

```bash
sudo chmod 440 /etc/sudoers.d/rider-pc
```

Przykładowy plik konfiguracyjny sudoers jest dostępny w repozytorium: `scripts/setup/rider-sudoers.example`

### Zachowanie na Różnych Platformach

| Platforma | Zachowanie |
|-----------|------------|
| **Linux + systemd** | Rzeczywista kontrola usług przez `systemctl` |
| **Linux bez systemd** | Tryb symulowany/mock |
| **Windows** | Tylko tryb symulowany/mock |
| **macOS** | Tylko tryb symulowany/mock |
| **Docker** | Zależy od konfiguracji kontenera; zazwyczaj tryb mock |

W trybie symulowanym dashboard pokazuje domyślne usługi z symulowanymi stanami. Akcje kontroli usług aktualizują stan w pamięci bez wpływu na rzeczywisty system.

### Względy Bezpieczeństwa

- Nadawaj dostęp sudoers tylko dla konkretnych usług, które chcesz kontrolować
- Unikaj używania wildcardów w regułach sudoers dla systemctl; prefiks `rider-*` jest dopuszczalny dla wygody, ale dla większego bezpieczeństwa zaleca się jawne wyliczenie usług
- Regularnie audytuj które usługi są kontrolowalne
- Rozważ uruchamianie Rider-PC na dedykowanym koncie użytkownika

## Integracja z GitHub

### Przegląd

Rider-PC wspiera integrację z GitHub dla śledzenia zadań i funkcji dashboardu projektowego. Integracja obejmuje:
- **Dashboard Projektu** - przeglądanie otwartych zgłoszeń (Issues) z GitHub
- **Kreator Zadań** - tworzenie nowych Issues bezpośrednio z interfejsu Rider-PC
- **Auto-init** - automatyczne tworzenie branchy i plików dokumentacji

Integracja odczytuje poświadczenia ze zmiennych środowiskowych, dzięki czemu sekrety nie trafiają do plików konfiguracyjnych.

### Generowanie Personal Access Token (PAT)

1. Przejdź do **GitHub Settings** → **Developer settings** → **Personal access tokens**
   - Klasyczne tokeny: https://github.com/settings/tokens
   - Fine-grained tokeny (zalecane): https://github.com/settings/tokens?type=beta

2. Kliknij **"Generate new token"**

3. Nadaj tokenowi opisową nazwę, np. `rider-pc-integration`

4. Ustaw czas wygaśnięcia (zalecane: 90 dni, maksymalnie 1 rok)

5. Wybierz wymagane uprawnienia:
   - Dla **klasycznych tokenów**: zaznacz scope `repo` (pełen dostęp do prywatnych repozytoriów) lub `public_repo` (tylko publiczne)
   - Dla **fine-grained tokenów**: wybierz repozytorium i ustaw uprawnienia:
     - `Contents`: Read and write (dla tworzenia branchy i plików)
     - `Issues`: Read and write (dla tworzenia i przeglądania Issues)
     - `Metadata`: Read-only (wymagane)

6. Kliknij **"Generate token"** i **natychmiast skopiuj** wygenerowany token (nie będzie ponownie widoczny)

### Konfiguracja Zmiennych Środowiskowych

Ustaw następujące zmienne środowiskowe dla integracji z GitHub:

```bash
# Wymagane: GitHub Personal Access Token
GITHUB_TOKEN=ghp_twoj_token_tutaj

# Wymagane: Właściciel repozytorium (nazwa użytkownika lub organizacji)
GITHUB_REPO_OWNER=twoja-nazwa-uzytkownika

# Wymagane: Nazwa repozytorium
GITHUB_REPO_NAME=twoje-repo

# Opcjonalne: TTL cache dla odpowiedzi API GitHub w sekundach (domyślnie: 300)
GITHUB_CACHE_TTL_SECONDS=300
```

### Konfiguracja Auto-init (Kreator Zadań)

Opcjonalne zmienne do konfiguracji funkcji automatycznej inicjalizacji zadań:

```bash
# Włącz/wyłącz funkcję auto-init (domyślnie: true)
TASK_AUTO_INIT_ENABLED=true

# Ścieżka do katalogu dokumentacji zadań (domyślnie: docs_pl/_to_do)
TASK_DOCS_PATH=docs_pl/_to_do

# Prefiks dla nowych branchy (domyślnie: feat)
# Wynikowa nazwa: feat/<numer-issue>-<slug-tytulu>
TASK_BRANCH_PREFIX=feat
```

### Konfiguracja w .bashrc / .zshrc

Dla bezpiecznej konfiguracji, dodaj zmienne do pliku konfiguracyjnego powłoki:

```bash
# ~/.bashrc lub ~/.zshrc
# Konfiguracja GitHub dla Rider-PC
# UWAGA: Nigdy nie commituj tego pliku do repozytorium!

export GITHUB_TOKEN="ghp_twoj_prawdziwy_token"
export GITHUB_REPO_OWNER="twoja-nazwa-uzytkownika"
export GITHUB_REPO_NAME="twoje-repo"
```

Po edycji pliku, przeładuj konfigurację:

```bash
source ~/.bashrc  # lub source ~/.zshrc
```

### Sprawdzanie Statusu Konfiguracji

Klasa `Settings` udostępnia właściwość `is_github_configured` do sprawdzenia, czy wszystkie wymagane pola GitHub są ustawione (token, właściciel i nazwa repozytorium):

```python
from pc_client.config.settings import settings

if settings.is_github_configured:
    print("Integracja z GitHub jest w pełni skonfigurowana")
else:
    print("Konfiguracja GitHub niekompletna - sprawdź token, właściciela i nazwę repo")
```

### Względy Bezpieczeństwa

- **Nigdy nie commituj tokenów**: Przechowuj `GITHUB_TOKEN` tylko w zmiennych środowiskowych lub bezpiecznych menedżerach sekretów
- **Używaj minimalnych uprawnień**: Nadawaj tylko uprawnienia potrzebne do Twojego przypadku użycia
- **Rotuj tokeny**: Okresowo regeneruj swój token GitHub (zalecane co 90 dni)
- **Używaj fine-grained tokenów**: Rozważ użycie fine-grained personal access tokens dla lepszego bezpieczeństwa
- **Nie używaj pliku .env w produkcji**: Plik `.env` jest wygodny dla rozwoju, ale w produkcji użyj bezpieczniejszych metod

### Zachowanie na Różnych Platformach

| Środowisko | Zachowanie |
|------------|------------|
| **Lokalne środowisko deweloperskie** | Ustaw zmienne w `~/.bashrc` lub `~/.zshrc` (nie w plikach repo) |
| **Docker** | Przekaż przez sekcję environment w `docker-compose.yml` lub plik `.env` (nie commituj) |
| **CI/CD** | Użyj sekretów repozytorium |
| **Produkcja** | Użyj bezpiecznego zarządzania sekretami (np. HashiCorp Vault) |

## Dalsze Informacje

- **Szybki Start**: [SZYBKI_START.md](SZYBKI_START.md)
- **Architektura**: [ARCHITEKTURA.md](ARCHITEKTURA.md)
- **Integracja Offload**: [INTEGRACJA_OFFLOAD_PC.md](INTEGRACJA_OFFLOAD_PC.md)
- **Zarządzanie Usługami**: [ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md](ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md)

## Status Dokumentacji

- ✅ Konfiguracja Modeli AI
- ✅ Konfiguracja Bezpieczeństwa Sieci
- ✅ Konfiguracja Kolejki Zadań
- ✅ Konfiguracja Monitoringu
- ✅ Hub Konfiguracyjny (ten dokument)
- ✅ Zarządzanie Lokalnymi Usługami Systemowymi
- ✅ Integracja z GitHub

**Ostatnia aktualizacja**: 2025-11-27
