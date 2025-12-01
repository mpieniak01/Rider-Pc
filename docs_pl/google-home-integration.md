# Integracja Google Home w Rider-PC

## Opis

Rider-PC obsługuje natywną integrację z Google Home poprzez Smart Device Management (SDM) API. 
Umożliwia to sterowanie urządzeniami Google Home bezpośrednio z poziomu przeglądarki Rider-PC,
bez konieczności pośrednictwa Rider-Pi.

## Tryby pracy

### 1. Tryb natywny (GOOGLE_HOME_LOCAL_ENABLED=true)

- OAuth 2.0 przepływ autoryzacji z PKCE bezpośrednio z Rider-PC
- Tokeny przechowywane lokalnie w `config/local/google_tokens_pc.json`
- Komunikacja bezpośrednio z Google SDM API
- Wymaga konfiguracji OAuth Client ID i Device Access Project

### 2. Tryb proxy (domyślny, GOOGLE_HOME_LOCAL_ENABLED=false)

- Rider-PC przekierowuje żądania do Rider-Pi
- Rider-Pi obsługuje autoryzację i komunikację z Google
- Nie wymaga lokalnej konfiguracji OAuth

### 3. Tryb testowy (GOOGLE_HOME_TEST_MODE=true)

- Używa symulowanych urządzeń do testów i rozwoju
- Nie wymaga prawdziwych danych logowania Google

## Konfiguracja trybu natywnego

### Krok 1: Utworzenie projektu Google Cloud

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Utwórz nowy projekt lub wybierz istniejący
3. Włącz API:
   - Smart Device Management API
   - OAuth 2.0

### Krok 2: Utworzenie OAuth Client ID

1. W Google Cloud Console przejdź do **APIs & Services → Credentials**
2. Kliknij **Create Credentials → OAuth client ID**
3. Wybierz typ aplikacji: **Web application**
4. Dodaj **Authorized redirect URIs**:
   ```
   http://localhost:8000/api/home/auth/callback
   ```
   Dla produkcji dodaj również:
   ```
   https://your-domain.com/api/home/auth/callback
   ```
5. Zapisz **Client ID** i **Client Secret**

### Krok 3: Rejestracja w Device Access Console

1. Przejdź do [Google Device Access Console](https://console.nest.google.com/device-access)
2. Zaakceptuj warunki użytkowania (wymagana jednorazowa opłata 5 USD)
3. Utwórz nowy projekt:
   - Podaj nazwę projektu
   - Wprowadź OAuth Client ID z kroku 2
4. Zapisz **Project ID** (będzie to `GOOGLE_DEVICE_ACCESS_PROJECT_ID`)

### Krok 4: Połączenie urządzeń

1. W Device Access Console wybierz swój projekt
2. Kliknij **Link Account** i zaloguj się kontem Google powiązanym z Google Home
3. Wybierz urządzenia, które chcesz udostępnić

### Krok 5: Konfiguracja Rider-PC

Dodaj do pliku `.env` (lub zmiennych środowiskowych):

```bash
# Włączenie trybu natywnego
GOOGLE_HOME_LOCAL_ENABLED=true

# OAuth 2.0 credentials
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Device Access Project ID
GOOGLE_DEVICE_ACCESS_PROJECT_ID=your-project-id

# Redirect URI (musi zgadzać się z konfiguracją OAuth)
GOOGLE_REDIRECT_URI=http://localhost:8000/api/home/auth/callback

# Ścieżka do pliku tokenów (opcjonalnie)
GOOGLE_TOKENS_PATH=config/local/google_tokens_pc.json
```

### Krok 6: Uruchomienie i autoryzacja

1. Uruchom Rider-PC: `python -m pc_client.main`
2. Otwórz przeglądarkę: `http://localhost:8000/google_home`
3. Kliknij **Sign in with Google**
4. Zaloguj się i udziel uprawnień
5. Po przekierowaniu powinieneś zobaczyć listę urządzeń

## Endpointy API

### GET /api/home/status

Zwraca status autoryzacji i konfiguracji:

```json
{
  "configured": true,
  "authenticated": true,
  "auth_url_available": false,
  "profile": {
    "email": "user@gmail.com",
    "name": "Jan Kowalski"
  },
  "scopes": ["https://www.googleapis.com/auth/sdm.service"],
  "test_mode": false
}
```

### GET /api/home/auth/url

Zwraca URL do rozpoczęcia autoryzacji OAuth:

```json
{
  "ok": true,
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random-state-token",
  "expires_at": 1701234567.89
}
```

### GET /api/home/auth/callback

Endpoint callback dla OAuth. Automatycznie przekierowuje do `/google_home?auth=success` lub `?auth=error`.

### POST /api/home/auth

Rozpoczyna przepływ autoryzacji lub zwraca URL do przekierowania.

### POST /api/home/auth/clear

Czyści zapisane tokeny i wylogowuje użytkownika.

### GET /api/home/devices

Zwraca listę urządzeń z Google Home:

```json
{
  "ok": true,
  "devices": [
    {
      "name": "enterprises/project-id/devices/device-id",
      "type": "sdm.devices.types.LIGHT",
      "traits": {
        "sdm.devices.traits.OnOff": {"on": true},
        "sdm.devices.traits.Brightness": {"brightness": 70}
      }
    }
  ]
}
```

### POST /api/home/command

Wysyła komendę do urządzenia:

```json
{
  "deviceId": "enterprises/project-id/devices/device-id",
  "command": "action.devices.commands.OnOff",
  "params": {"on": true}
}
```

## Obsługiwane urządzenia i komendy

### Światła (LIGHT)
- `OnOff` - włącz/wyłącz
- `BrightnessAbsolute` - ustaw jasność (0-100)
- `ColorAbsolute` - ustaw kolor (temperatureK lub spectrumRgb)

### Termostaty (THERMOSTAT)
- `ThermostatTemperatureSetpoint` - ustaw temperaturę docelową
- `ThermostatSetMode` - zmień tryb (heat/cool/heatcool/off)

### Odkurzacze (VACUUM)
- `StartStop` - rozpocznij/zatrzymaj sprzątanie
- `PauseUnpause` - wstrzymaj/wznów
- `Dock` - wróć do stacji dokującej

## Rozwiązywanie problemów

### Brak urządzeń po zalogowaniu

1. Sprawdź czy urządzenia są połączone z kontem Google Home
2. Upewnij się, że urządzenia zostały wybrane w Device Access Console
3. Odśwież listę urządzeń w aplikacji Google Home

### Błąd "auth_env_missing"

Ustaw wszystkie wymagane zmienne środowiskowe:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_DEVICE_ACCESS_PROJECT_ID`

### Błąd "invalid_state" lub "session_expired"

Sesja autoryzacji wygasła. Rozpocznij proces logowania od nowa.

### Błąd 401 podczas pobierania urządzeń

Token wygasł i nie udało się go odświeżyć. Wyczyść tokeny i zaloguj się ponownie:
```bash
rm config/local/google_tokens_pc.json
```

### Błąd "redirect_uri_mismatch"

URI przekierowania nie zgadza się z konfiguracją OAuth Client:
1. Sprawdź wartość `GOOGLE_REDIRECT_URI`
2. Dodaj dokładnie ten sam URI w Google Cloud Console

## Bezpieczeństwo

- Tokeny OAuth są przechowywane lokalnie w `config/local/`
- Plik `config/local/` jest wykluczony z Git (.gitignore)
- Używamy PKCE dla dodatkowego bezpieczeństwa
- Client Secret nie powinien być udostępniany publicznie

## Migracja z Rider-Pi

Jeśli wcześniej używałeś integracji Google Home przez Rider-Pi:

1. Możesz kontynuować używanie trybu proxy (domyślny)
2. Aby przejść na tryb natywny:
   - Skonfiguruj OAuth Client dla Rider-PC
   - Ustaw `GOOGLE_HOME_LOCAL_ENABLED=true`
   - Zaloguj się ponownie przez przeglądarkę

Tokeny z Rider-Pi nie są kompatybilne z Rider-PC ze względu na różne OAuth Client ID.
