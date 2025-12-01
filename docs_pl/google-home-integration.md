# Integracja Google Home w Rider-PC

## Przegląd

Rider-PC oferuje natywną integrację z Google Home poprzez Smart Device Management (SDM) API.
Użytkownik może:
- Zalogować się przez Google bezpośrednio z przeglądarki
- Przeglądać listę urządzeń smart home
- Sterować urządzeniami (światła, termostaty, odkurzacze)

## Konfiguracja

### 1. Utwórz projekt OAuth w Google Cloud Console

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Utwórz nowy projekt lub wybierz istniejący
3. Włącz **Smart Device Management API**
4. Przejdź do **APIs & Services > Credentials**
5. Utwórz **OAuth 2.0 Client ID** typu **Web application**
6. Dodaj do **Authorized redirect URIs**:
   ```
   http://localhost:8000/api/home/auth/callback
   ```
   (zmień adres jeśli Rider-PC działa na innym hoście/porcie)

### 2. Zarejestruj projekt Device Access

1. Przejdź do [Google Device Access Console](https://console.nest.google.com/device-access)
2. Zapłać jednorazową opłatę rejestracyjną ($5 USD)
3. Utwórz nowy projekt
4. Zapisz **Project ID** (potrzebny później)
5. Połącz swoje konto Google Home z projektem

### 3. Skonfiguruj zmienne środowiskowe

Utwórz plik `.env` na podstawie `.env.example` i uzupełnij:

```bash
# Google Home Integration
GOOGLE_HOME_LOCAL_ENABLED=true
GOOGLE_CLIENT_ID=twoj-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=twoj-client-secret
GOOGLE_DEVICE_ACCESS_PROJECT_ID=twoj-project-id
GOOGLE_HOME_REDIRECT_URI=http://localhost:8000/api/home/auth/callback
```

### 4. Uruchom Rider-PC i zaloguj się

1. Uruchom serwer: `python -m pc_client.main`
2. Otwórz w przeglądarce: `http://localhost:8000/google_home`
3. Kliknij "Zaloguj przez Google"
4. Autoryzuj dostęp do urządzeń

## Endpointy API

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/home/status` | GET | Status konfiguracji i autoryzacji |
| `/api/home/auth/url` | GET | Pobierz URL do logowania OAuth |
| `/api/home/auth/callback` | GET | Callback OAuth (obsługiwany automatycznie) |
| `/api/home/auth` | POST | Zainicjuj flow logowania |
| `/api/home/devices` | GET | Lista urządzeń smart home |
| `/api/home/command` | POST | Wyślij komendę do urządzenia |
| `/api/home/logout` | POST | Wyloguj i usuń tokeny |

## Obsługiwane urządzenia i komendy

### Światła (LIGHT)
- OnOff - włączanie/wyłączanie
- Brightness - jasność (0-100%)
- ColorSetting - temperatura barwowa / kolor RGB

### Termostaty (THERMOSTAT)
- ThermostatMode - tryb (heat, cool, heatcool, off)
- ThermostatTemperatureSetpoint - temperatura docelowa

### Odkurzacze (VACUUM)
- StartStop - uruchom/zatrzymaj
- PauseUnpause - pauza
- Dock - wróć do stacji

## Tryby pracy

### Tryb lokalny (domyślny)
Rider-PC komunikuje się bezpośrednio z Google SDM API.
```bash
GOOGLE_HOME_LOCAL_ENABLED=true
```

### Tryb legacy (proxy przez Rider-Pi)
Rider-PC przekazuje żądania do Rider-Pi.
```bash
GOOGLE_HOME_LOCAL_ENABLED=false
```

### Tryb testowy
Używa mocków zamiast prawdziwego API (dla developmentu/CI).
```bash
GOOGLE_HOME_TEST_MODE=true
```

## Rozwiązywanie problemów

### Brak urządzeń po zalogowaniu
- Sprawdź czy urządzenia są dodane w aplikacji Google Home
- Upewnij się, że projekt Device Access ma połączone konto
- Zweryfikuj czy `GOOGLE_DEVICE_ACCESS_PROJECT_ID` jest poprawny

### Błąd "auth_env_missing"
Brakuje wymaganych zmiennych środowiskowych:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_DEVICE_ACCESS_PROJECT_ID`

### Błąd "invalid_state"
Token sesji wygasł. Rozpocznij proces logowania od nowa.

### Błąd "access_denied"
- Sprawdź czy refresh token jest ważny
- Wyloguj się i zaloguj ponownie

## Bezpieczeństwo

- Tokeny są przechowywane lokalnie w `config/local/google_tokens_pc.json`
- Plik z tokenami jest wykluczony z repozytorium (`.gitignore`)
- Używany jest flow OAuth 2.0 z PKCE dla zwiększonego bezpieczeństwa
- Parametr `state` chroni przed atakami CSRF
