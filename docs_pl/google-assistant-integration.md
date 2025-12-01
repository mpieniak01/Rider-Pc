# Integracja Google Assistant API w Rider-PC

## Opis

Panel Google Assistant umożliwia wysyłanie komend tekstowych do Google Assistant API,
sterowanie urządzeniami smart home zdefiniowanymi w statycznej konfiguracji.

## Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                     Rider-PC Dashboard                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              web/assistant.html (UI)                     │    │
│  │  - Kafelki urządzeń z ON/OFF                            │    │
│  │  - Suwak jasności                                        │    │
│  │  - Historia komend                                       │    │
│  │  - Własne komendy tekstowe                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        pc_client/api/routers/assistant_router.py        │    │
│  │  - GET  /api/assistant/status                           │    │
│  │  - GET  /api/assistant/devices                          │    │
│  │  - GET  /api/assistant/device/{id}                      │    │
│  │  - POST /api/assistant/command                          │    │
│  │  - POST /api/assistant/custom                           │    │
│  │  - GET  /api/assistant/history                          │    │
│  │  - POST /api/assistant/reload                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        pc_client/services/google_assistant.py           │    │
│  │  - Wczytywanie urządzeń z TOML                          │    │
│  │  - Tryb testowy (mock) / produkcyjny                    │    │
│  │  - Historia komend                                       │    │
│  │  - Optymistyczne statusy                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        config/google_assistant_devices.toml             │    │
│  │  - Statyczna mapa urządzeń                              │    │
│  │  - Komendy ON/OFF/dock/brightness                       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Wymagania wstępne

### 1. Konfiguracja środowiska

Upewnij się, że masz zainstalowane wymagane pakiety:
```bash
pip install fastapi uvicorn httpx tomli
```

### 2. Zmienne środowiskowe

Dodaj do `.env`:
```bash
# Włączenie usługi Google Assistant
GOOGLE_ASSISTANT_ENABLED=true

# Tryb testowy (true = mock, false = rzeczywiste API)
GOOGLE_ASSISTANT_TEST_MODE=true

# Ścieżka do konfiguracji urządzeń
GOOGLE_ASSISTANT_DEVICES_CONFIG=config/google_assistant_devices.toml

# Konfiguracja OAuth (wymagane dla trybu produkcyjnego)
# GOOGLE_ASSISTANT_TOKENS_PATH=config/local/google_assistant_tokens.json
# GOOGLE_ASSISTANT_PROJECT_ID=your-project-id
# GOOGLE_ASSISTANT_CLIENT_ID=your-client-id.apps.googleusercontent.com
# GOOGLE_ASSISTANT_CLIENT_SECRET=your-client-secret

# Identyfikatory urządzenia z Actions on Google
# GOOGLE_ASSISTANT_DEVICE_MODEL_ID=rider-pc-panel-model
# GOOGLE_ASSISTANT_DEVICE_ID=rider-pc-panel-device
# Preferowany język zapytań (np. pl-PL, en-US)
# GOOGLE_ASSISTANT_LANGUAGE=pl-PL
```

### 3. Tryb produkcyjny (połączenie z prawdziwym Assistant API)

1. **Zarejestruj urządzenie w Actions on Google**
   - W Google Cloud Console utwórz projekt + klienta OAuth (Desktop app).
   - W [Actions on Google](https://console.actions.google.com/) dodaj *Device Model* (zapamiętaj `GOOGLE_ASSISTANT_DEVICE_MODEL_ID`).
   - Zarejestruj fizyczne urządzenie (`GOOGLE_ASSISTANT_DEVICE_ID`), powiąż je z modelem.

2. **Uzyskaj token odświeżania**
   - Użyj `google-auth-oauthlib` lub skryptu `google-oauthlib-tool --scope https://www.googleapis.com/auth/assistant-sdk-prototype ...`.
   - Zapisz wynik w `config/local/google_assistant_tokens.json` w formacie:
```json
{
  "refresh_token": "ya29...",
  "client_id": "your-client-id.apps.googleusercontent.com",
  "client_secret": "your-client-secret",
  "token_uri": "https://oauth2.googleapis.com/token",
  "scopes": [
    "https://www.googleapis.com/auth/assistant-sdk-prototype"
  ]
}
```
   - Plik trafia do `.gitignore` (nie commituj).

3. **Wyłącz tryb testowy**
   - Ustaw `GOOGLE_ASSISTANT_TEST_MODE=false`.
   - `GOOGLE_ASSISTANT_ENABLED=true` – po restarcie panelu `/api/assistant/status` pokaże `live_ready=true`.

4. **Wymagane pakiety**
   - `google-auth`, `google-auth-oauthlib`, `google-assistant-grpc`, `grpcio`.
   - Są już dodane do `requirements*.txt`, więc `pip install -r requirements.txt` pobierze je automatycznie.

5. **Diagnostyka**
   - Endpoint `/api/assistant/status` informuje czy dostępne są biblioteki (`libs_available`) oraz czy tokeny zostały poprawnie wczytane (`live_ready`).
   - Logi serwisu (`logs/panel-8080.log`) pokażą szczegóły błędu RPC lub odświeżania tokenu.


## Konfiguracja urządzeń

Urządzenia są zdefiniowane w pliku `config/google_assistant_devices.toml`.
Każdy wpis zawiera:

```toml
[[devices]]
id = "pokoj_lights"                    # Unikalny identyfikator
label = "Pokój Lights"                  # Nazwa wyświetlana w UI
assistant_name = "Pokój Lights"         # Nazwa w Google Home
room = "Pokój"                          # Pokój (opcjonalne)
category = "lights"                     # Kategoria: lights, vacuum, air_purifier, camera, scene
supports_brightness = true              # Czy obsługuje jasność (opcjonalne)
on_command = "Włącz Pokój Lights"       # Komenda włączenia
off_command = "Wyłącz Pokój Lights"     # Komenda wyłączenia
brightness_template = "Ustaw jasność Pokój Lights na {value}%"  # Szablon jasności (opcjonalne)
dock_command = ""                       # Komenda powrotu do stacji (dla odkurzaczy)
notes = "Grupa światła w pokoju"        # Notatki (opcjonalne)
```

### Kategorie urządzeń

| Kategoria       | Ikona | Opis                    | Dodatkowe komendy     |
|-----------------|-------|-------------------------|-----------------------|
| `lights`        | 💡    | Oświetlenie            | brightness_template   |
| `vacuum`        | 🧹    | Odkurzacz              | dock_command          |
| `air_purifier`  | 🌬️    | Oczyszczacz powietrza  | -                     |
| `camera`        | 📷    | Kamera/monitoring      | -                     |
| `scene`         | 🎬    | Scena/automatyzacja    | -                     |
| `thermostat`    | 🌡️    | Termostat              | -                     |

## Endpointy API

### GET /api/assistant/status

Zwraca status integracji.

**Odpowiedź:**
```json
{
  "ok": true,
  "enabled": true,
  "test_mode": true,
  "config_path": "config/google_assistant_devices.toml",
  "config_exists": true,
  "devices_count": 6,
  "history_count": 0
}
```

### GET /api/assistant/devices

Lista wszystkich urządzeń.

**Odpowiedź:**
```json
{
  "ok": true,
  "devices": [
    {
      "id": "pokoj_lights",
      "label": "Pokój Lights",
      "assistant_name": "Pokój Lights",
      "room": "Pokój",
      "category": "lights",
      "on_command": "Włącz Pokój Lights",
      "off_command": "Wyłącz Pokój Lights",
      "supports_brightness": true,
      "brightness_template": "Ustaw jasność Pokój Lights na {value}%",
      "status": "unknown"
    }
  ]
}
```

### POST /api/assistant/command

Wysyła komendę do urządzenia.

**Body:**
```json
{
  "device_id": "pokoj_lights",
  "action": "on",
  "params": {}
}
```

**Akcje:**
- `on` - włączenie urządzenia
- `off` - wyłączenie urządzenia
- `brightness` - ustawienie jasności (wymaga `params.value`)
- `dock` - powrót odkurzacza do stacji

**Odpowiedź (tryb testowy):**
```json
{
  "ok": true,
  "response": "[TEST MODE] Command sent: Włącz Pokój Lights",
  "command": "Włącz Pokój Lights",
  "mode": "test"
}
```

### POST /api/assistant/custom

Wysyła własną komendę tekstową.

**Body:**
```json
{
  "text": "Wyłącz wszystkie światła"
}
```

### GET /api/assistant/history

Historia komend (domyślnie 20 ostatnich).

**Query params:**
- `limit` - maksymalna liczba wpisów (domyślnie 20)

**Odpowiedź:**
```json
{
  "ok": true,
  "history": [
    {
      "timestamp": 1701432000.123,
      "device_id": "pokoj_lights",
      "action": "on",
      "command_text": "Włącz Pokój Lights",
      "success": true,
      "response": "[TEST MODE] Command sent: Włącz Pokój Lights"
    }
  ]
}
```

### POST /api/assistant/reload

Przeładowuje konfigurację urządzeń z pliku.

## Panel UI

Panel dostępny pod adresem `/assistant`:

### Funkcje

1. **Status usługi** - wskaźnik w nagłówku (Aktywny/Tryb testowy/Wyłączony)
2. **Kafelki urządzeń** - przyciski ON/OFF, suwak jasności, status
3. **Własne komendy** - pole tekstowe do wysyłania dowolnych komend
4. **Historia** - ostatnie 10 komend z oznaczeniem sukcesu/błędu
5. **Odświeżanie** - przycisk do przeładowania konfiguracji

### Statusy urządzeń

- 🟢 Zielony - urządzenie włączone
- ⚫ Szary - urządzenie wyłączone
- 🟡 Żółty - status nieznany

Statusy są aktualizowane optymistycznie po wysłaniu komendy.

## Tryb testowy vs produkcyjny

### Tryb testowy (`GOOGLE_ASSISTANT_TEST_MODE=true`)

- Nie wymaga konfiguracji OAuth
- Symuluje odpowiedzi API
- Używany do rozwoju i testowania UI

### Tryb produkcyjny (`GOOGLE_ASSISTANT_TEST_MODE=false`)

> **Uwaga:** Pełna integracja z Google Assistant API wymaga:
> - Projektu w [Actions on Google](https://console.actions.google.com/)
> - Aktywnego Google Assistant API
> - Konfiguracji OAuth 2.0
> - Tokenów w `config/local/google_assistant_tokens.json`

Szczegóły konfiguracji produkcyjnej: patrz sekcja "Przyszłe rozszerzenia".

## Przyszłe rozszerzenia

### 1. Rzeczywista integracja z Google Assistant API

Implementacja wymaga:
- `google-assistant-sdk` lub `grpcio` + protobuf
- OAuth flow (InstalledAppFlow)
- Klient gRPC dla `converse` API
- Obsługa odświeżania tokenów

### 2. Integracja głosowa

- MediaRecorder w przeglądarce
- Endpoint `/api/assistant/voice`
- Odtwarzanie odpowiedzi audio

### 3. Dodatkowe funkcje

- Logowanie komend do pliku
- Metryki w `/health`
- Więcej kategorii urządzeń (thermostat, media player)

## Rozwiązywanie problemów

### Usługa wyłączona

Sprawdź w `.env`:
```bash
GOOGLE_ASSISTANT_ENABLED=true
```

### Brak urządzeń

Sprawdź czy plik `config/google_assistant_devices.toml` istnieje i jest poprawny.
Użyj przycisku "Przeładuj konfigurację" w UI.

### Błędy komend

W trybie testowym komendy zawsze zwracają sukces.
W trybie produkcyjnym sprawdź tokeny OAuth i połączenie z API.

## Porównanie: Google Assistant API vs Smart Device Management (SDM)

| Aspekt              | Assistant API                    | SDM API                         |
|---------------------|----------------------------------|---------------------------------|
| Urządzenia          | Wszystkie w Google Home          | Tylko Nest i wybrane            |
| Feedback            | Brak real-time                   | Real-time statusy               |
| Komendy             | Tekstowe/głosowe                 | Strukturalne (JSON)             |
| Konfiguracja        | Prostsza (OAuth)                 | Wymaga Device Access Project    |
| Use case            | Szybkie sterowanie, sceny        | Precyzyjne kontrolowanie Nest   |

Panel Google Assistant jest komplementarny do istniejącej integracji SDM
(strona `/google_home`).
