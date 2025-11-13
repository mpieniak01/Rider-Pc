# Przewodnik Integracji Rider-PC z Rider-PI

## Przegląd

Kompleksowy przewodnik integracji klienta Rider-PC z urządzeniem Rider-PI.

## Architektura Integracji

```
┌─────────────────────────────────────────────┐
│           Urządzenie Rider-PI                │
│  ┌────────────┐      ┌────────────┐        │
│  │ REST API   │      │ ZMQ PUB    │        │
│  │ :8080      │      │ :5555      │        │
│  └─────┬──────┘      └──────┬─────┘        │
└────────┼────────────────────┼───────────────┘
         │                    │
         │    VPN/mTLS        │
         │                    │
┌────────┼────────────────────┼───────────────┐
│        ▼                    ▼                │
│  ┌────────────┐      ┌────────────┐        │
│  │ REST       │      │ ZMQ SUB    │        │
│  │ Adapter    │      │ :5556      │        │
│  └─────┬──────┘      └──────┬─────┘        │
│        │                    │                │
│        └────────┬───────────┘                │
│                 ▼                            │
│         ┌──────────────┐                     │
│         │  Cache       │                     │
│         │  (SQLite)    │                     │
│         └──────┬───────┘                     │
│                │                              │
│        ┌───────┴────────┐                   │
│        ▼                 ▼                   │
│  ┌──────────┐     ┌──────────┐             │
│  │ FastAPI  │     │ Providers │             │
│  │ Server   │     │ (AI)      │             │
│  └────┬─────┘     └──────┬────┘             │
│       │                   │                   │
│       ▼                   ▼                   │
│  ┌────────────────────────────┐             │
│  │     Telemetry (ZMQ PUB)    │             │
│  └─────────────┬───────────────┘             │
└────────────────┼─────────────────────────────┘
                 │
                 ▼
         Rider-PI (Results)
```

## Wymagania Wstępne

### Sprzęt
- Urządzenie Rider-PI (Raspberry Pi 4/5)
- PC z Windows 11 + WSL2 lub Linux/macOS
- Sieć LAN lub VPN między urządzeniami

### Oprogramowanie
- Rider-PI: Python 3.9+, Redis, systemd services
- PC: Python 3.9+, WSL2 (Windows), Redis/RabbitMQ

## Krok 1: Przygotowanie Rider-PI

### 1.1 Sprawdź Usługi

```bash
# Na Rider-PI
sudo systemctl status rider-api
sudo systemctl status rider-broker
sudo systemctl status rider-vision
```

### 1.2 Weryfikuj Punkty Końcowe

```bash
# Testuj REST API
curl http://localhost:8080/healthz

# Sprawdź ZMQ broker
ss -tlnp | grep 5555
ss -tlnp | grep 5556
```

### 1.3 Konfiguruj Firewall

```bash
# Otwórz porty dla PC
sudo ufw allow from 10.0.0.2 to any port 8080  # REST API
sudo ufw allow from 10.0.0.2 to any port 5555  # ZMQ PUB
sudo ufw allow from 10.0.0.2 to any port 5556  # ZMQ SUB
```

## Krok 2: Przygotowanie PC

### 2.1 Klonuj Repozytorium

```bash
git clone https://github.com/mpieniak01/Rider-Pc.git
cd Rider-Pc
```

### 2.2 Utwórz Środowisko Wirtualne

```bash
python3.9 -m venv venv
source venv/bin/activate  # Windows: venv\Scriptsctivate
```

### 2.3 Zainstaluj Zależności

```bash
pip install -r requirements.txt
```

## Krok 3: Konfiguracja Sieci

### Opcja A: Sieć Lokalna (Development)

```bash
# .env
RIDER_PI_HOST=192.168.1.100  # IP Rider-PI w LAN
RIDER_PI_PORT=8080
SECURE_MODE=false
```

### Opcja B: VPN (Production)

Zobacz `KONFIGURACJA_BEZPIECZENSTWA_SIECI.md` dla szczegółów WireGuard VPN.

```bash
# .env
RIDER_PI_HOST=10.0.0.1  # IP VPN Rider-PI
RIDER_PI_PORT=8080
SECURE_MODE=false  # VPN zapewnia szyfrowanie
```

## Krok 4: Konfiguracja Providerów

### 4.1 Włącz Providerów

```bash
# .env
ENABLE_PROVIDERS=true
ENABLE_TASK_QUEUE=true
ENABLE_TELEMETRY=true
```

### 4.2 Wybierz Backend Kolejki

**Redis (Development):**
```bash
TASK_QUEUE_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

**RabbitMQ (Production):**
```bash
TASK_QUEUE_BACKEND=rabbitmq
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_VHOST=rider_pc
RABBITMQ_USER=rider_user
RABBITMQ_PASSWORD=secure_password
```

### 4.3 Konfiguruj Providerów

Edytuj pliki w `config/`:
- `voice_provider.toml` - Konfiguracja ASR/TTS
- `vision_provider.toml` - Konfiguracja wykrywania
- `text_provider.toml` - Konfiguracja LLM

**Dla mock mode (bez prawdziwych modeli):**
```toml
[voice]
use_mock = true

[vision]
use_mock = true

[text]
use_mock = true
```

## Krok 5: Uruchom Klienta PC

### 5.1 Start Kolejki Zadań

**Redis:**
```bash
sudo systemctl start redis-server
```

**RabbitMQ:**
```bash
sudo systemctl start rabbitmq-server
```

### 5.2 Uruchom Aplikację

```bash
python -m pc_client.main
```

### 5.3 Weryfikuj

```bash
# Sprawdź logi
tail -f logs/rider-pc.log

# Testuj API
curl http://localhost:8000/healthz

# Sprawdź metryki
curl http://localhost:8000/metrics
```

## Krok 6: Weryfikacja Integracji

### 6.1 Test Połączenia REST

```bash
# Z PC do Rider-PI
curl http://${RIDER_PI_HOST}:8080/healthz
curl http://${RIDER_PI_HOST}:8080/state
```

### 6.2 Test Subskrypcji ZMQ

```bash
# Sprawdź logi dla wiadomości ZMQ
tail -f logs/rider-pc.log | grep "\[zmq\]"
```

### 6.3 Test Providerów

```python
# Test voice provider
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = VoiceProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.VOICE_ASR,
    payload={"audio_data": "test"}
)

result = await provider.process_task(task)
print(result)
```

### 6.4 Test End-to-End

1. Uruchom Rider-PI
2. Uruchom Rider-PC
3. Otwórz UI Rider-PC: http://localhost:8000
4. Sprawdź czy dane się aktualizują
5. Wyślij zadanie do providera
6. Weryfikuj wynik w logach

## Krok 7: Konfiguracja Monitoringu

### 7.1 Uruchom Prometheus

```bash
sudo systemctl start prometheus
# Dostęp: http://localhost:9090
```

### 7.2 Uruchom Grafana

```bash
sudo systemctl start grafana-server
# Dostęp: http://localhost:3000 (admin/admin)
```

### 7.3 Skonfiguruj Dashboardy

1. Dodaj Prometheus jako data source w Grafana
2. Importuj `config/grafana-dashboard.json`
3. Weryfikuj metryki przepływają

## Przepływy Danych

### 1. Synchronizacja Stanu

```
Rider-PI → REST /state → PC Cache → UI aktualizacja
         ↓ (co 2s)
```

### 2. Zdarzenia Czasie Rzeczywistym

```
Rider-PI → ZMQ PUB (vision.obstacle) → PC SUB → Cache → UI
```

### 3. Offload Zadania

```
Rider-PI → REST /provider/task → Task Queue → Worker → Provider → Result → ZMQ → Rider-PI
```

## Rozwiązywanie Problemów

### Nie Można Połączyć się z Rider-PI

```bash
# Ping test
ping ${RIDER_PI_HOST}

# Port test
nc -zv ${RIDER_PI_HOST} 8080

# Sprawdź firewall
sudo ufw status

# Sprawdź routing
ip route
```

### ZMQ Nie Otrzymuje Wiadomości

```bash
# Sprawdź czy broker działa na Rider-PI
ssh rider-pi "sudo systemctl status rider-broker"

# Sprawdź porty
ssh rider-pi "ss -tlnp | grep 5555"

# Test ZMQ subscriptions
python -c "import zmq; ..."
```

### Provider Nie Działa

```bash
# Sprawdź logi
grep "\[provider\]" logs/rider-pc.log

# Sprawdź circuit breaker
curl http://localhost:8000/metrics | grep circuit_breaker

# Sprawdź kolejkę
redis-cli LLEN task_queue:priority:5
```

## Najlepsze Praktyki

### Bezpieczeństwo
1. Używaj VPN lub mTLS w produkcji
2. Nie commituj sekretów do git
3. Regularnie aktualizuj zależności
4. Monitor logów dla nietypowej aktywności

### Wydajność
1. Używaj Redis dla małych wdrożeń
2. RabbitMQ dla dużej skali
3. Tunuj rozmiary puli połączeń
4. Monitor wykorzystania zasobów

### Niezawodność
1. Włącz circuit breakers
2. Konfiguruj timeouty odpowiednio
3. Implementuj retry logic
4. Monitoruj metryki i alerty

### Operacje
1. Używaj systemd dla auto-restart
2. Rotuj logi
3. Backup konfiguracji
4. Dokumentuj zmiany

## Dodatkowe Zasoby

- `KONFIGURACJA_BEZPIECZENSTWA_SIECI.md` - Konfiguracja VPN/mTLS
- `KONFIGURACJA_KOLEJKI_ZADAN.md` - Redis/RabbitMQ setup
- `KONFIGURACJA_MONITORINGU.md` - Prometheus/Grafana
- `PRZEWODNIK_IMPLEMENTACJI_PROVIDEROW.md` - Providerzy AI

---

**Status**: Gotowe do Produkcji ✅  
**Czas Konfiguracji**: ~2 godziny  
**Złożoność**: Średnia  
**Data**: 2025-11-12
