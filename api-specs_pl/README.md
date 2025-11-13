# Dokumentacja REST API Rider-Pi

Ten katalog zawiera dokumentację dla punktów końcowych REST API Rider-Pi.

## Serwer API

Serwer API działa na porcie **8080** i udostępnia punkty końcowe REST do sterowania robotem oraz dostępu do informacji systemowych.

**Usługa:** `rider-api.service`  
**Punkt wejścia:** `services/api_server.py`  
**Bazowy URL:** `http://robot-ip:8080`

## Dostępne Punkty Końcowe

### Podstawowe API
- [API Sterowania](STEROWANIE.md) - Ruch i sterowanie robotem
- [API Nawigatora](NAWIGATOR.md) - Nawigacja autonomiczna (tryb Rekonesans)

<!-- Następujące pliki dokumentacji API są planowane do przyszłej dokumentacji: -->
<!-- - [API Kamery](camera.md) - Dostęp do kamery i systemu wizji -->
<!-- - [API Czatu](chat.md) - Interfejs czatu głosowego i tekstowego -->
<!-- - [API Twarzy](face.md) - Sterowanie animacją twarzy robota -->
<!-- - [API Google Home](google-home.md) - Integracja z Google Home -->

### Stan Zdrowia i Status
- `GET /healthz` - Sprawdzenie stanu zdrowia systemu
- `GET /api/status` - Szczegółowy status systemu
- `GET /api/app-metrics` - Metryki aplikacji (liczniki OK/Error dla interaktywnych API)

## Metryki Aplikacji

### GET /api/app-metrics

Zwraca metryki dla interaktywnych punktów końcowych API, śledząc udane (OK) i nieudane (Error) żądania.

**Nie wymaga uwierzytelniania.**

**Żądanie:**
```bash
GET /api/app-metrics
```

**Odpowiedź:**
```json
{
  "ok": true,
  "metrics": {
    "control": {
      "ok": 42,
      "error": 3
    },
    "navigator": {
      "ok": 15,
      "error": 0
    },
    "voice": {
      "ok": 28,
      "error": 2
    },
    "google_home": {
      "ok": 10,
      "error": 1
    },
    "chat": {
      "ok": 5,
      "error": 0
    },
    "face": {
      "ok": 12,
      "error": 0
    }
  },
  "total_errors": 6
}
```

**Monitorowane Grupy API:**

- **Control:** `/api/control`, `/api/cmd`, `/api/control/balance`, `/api/control/height`
- **Navigator:** `/api/navigator/start`, `/api/navigator/stop`, `/api/navigator/config`, `/api/navigator/return_home`
- **Voice:** `/api/voice/capture`, `/api/voice/say`, `/api/voice/tts`, `/api/voice/asr`
- **GoogleHome:** `/api/home/command`
- **Chat:** `/api/chat/send`
- **Face:** `/face/render`, `/face/play`, `/face/stop`, `/api/draw/face`

**Uwaga:** Punkty końcowe systemowe (sprawdzenie zdrowia, zapytania o status, strumienie kamery, itp.) **nie są** liczone w tych metrykach. Tylko interaktywne akcje inicjowane przez użytkownika są śledzone.

**Wyświetlane na:** Główny dashboard pod `/view` w karcie "API Metrics".

## Wspólne Wzorce

### Wsparcie CORS
Wszystkie punkty końcowe API wspierają CORS (Cross-Origin Resource Sharing) i odpowiadają na żądania preflight OPTIONS.

### Format Odpowiedzi
Większość punktów końcowych zwraca odpowiedzi JSON:

```json
{
  "ok": true,
  "data": { ... }
}
```

Odpowiedzi błędów:

```json
{
  "ok": false,
  "error": "Komunikat błędu"
}
```

### Znaczniki Czasowe
Wszystkie zdarzenia i komendy zawierają pole `ts` (timestamp) w formacie Unix epoch (sekundy od 1970-01-01).

## Serwowanie Plików Statycznych

Serwer API również serwuje pliki statyczne:

- `/` - Serwuje pliki z katalogu `web/`
- `/camera/last` - Ostatnia przechwycona klatka kamery
- `/files/*` - Pliki z `data/` i `snapshots/`

## Integracja z Magistralą

Wiele punktów końcowych API publikuje komendy do wewnętrznej magistrali komunikatów ZMQ. Zobacz `common/bus.py` dla definicji tematów i formatów payloadów.

## Zobacz Również

- [ARCHITEKTURA.md](../docs_pl/ARCHITEKTURA.md) - Ogólna architektura systemu
- [common/bus.py](../../common/bus.py) - Definicje tematów magistrali
- [services/api_server.py](../../services/api_server.py) - Implementacja serwera API
