# Integracja Google Home w Rider-PC

Ten dokument opisuje jak skonfigurować i używać integracji Google Home / Smart Device Management (SDM) bezpośrednio z Rider-PC.

## Spis treści

1. [Przegląd](#przegląd)
2. [Wymagania](#wymagania)
3. [Konfiguracja Google Cloud](#konfiguracja-google-cloud)
4. [Konfiguracja Device Access](#konfiguracja-device-access)
5. [Konfiguracja Rider-PC](#konfiguracja-rider-pc)
6. [Uruchomienie](#uruchomienie)
7. [Rozwiązywanie problemów](#rozwiązywanie-problemów)

## Przegląd

Rider-PC może bezpośrednio komunikować się z API Google Smart Device Management, umożliwiając:
- Wyświetlanie listy urządzeń Google Home
- Sterowanie urządzeniami (światła, termostaty, odkurzacze)
- Pełny przepływ OAuth 2.0 z PKCE bezpośrednio z przeglądarki

### Tryby pracy

| Tryb | Opis | Konfiguracja |
|------|------|--------------|
| **Lokalny** | Rider-PC komunikuje się bezpośrednio z Google SDM API | `GOOGLE_HOME_LOCAL_ENABLED=true` |
| **Proxy** | Rider-PC przekazuje żądania do Rider-Pi (legacy) | `GOOGLE_HOME_LOCAL_ENABLED=false` |
| **Testowy** | Rider-PC używa mock urządzeń | `GOOGLE_HOME_TEST_MODE=true` |

## Wymagania

### Konto Google
- Konto Google z dostępem do Google Home
- Urządzenia smart home dodane do aplikacji Google Home

### Google Cloud Console
- Projekt w Google Cloud Console
- Włączone API: Smart Device Management API
- OAuth 2.0 Client ID typu "Web Application"

### Device Access Console
- Konto dewelopera w Device Access ($5 jednorazowa opłata)
- Projekt Device Access połączony z domem

## Konfiguracja Google Cloud

### Krok 1: Utwórz projekt

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Utwórz nowy projekt lub wybierz istniejący
3. Zanotuj **Project ID**

### Krok 2: Włącz API

1. W menu bocznym wybierz "APIs & Services" → "Library"
2. Wyszukaj "Smart Device Management API"
3. Kliknij "Enable"

### Krok 3: Utwórz OAuth Client

1. Przejdź do "APIs & Services" → "Credentials"
2. Kliknij "Create Credentials" → "OAuth client ID"
3. Wybierz typ: **Web application**
4. Nazwa: `Rider-PC Google Home`
5. W sekcji "Authorized redirect URIs" dodaj:
   ```
   http://localhost:8000/api/home/auth/callback
   https://<twoj-pc-host>/api/home/auth/callback
   ```
6. Zapisz **Client ID** i **Client Secret**

## Konfiguracja Device Access

### Krok 1: Zarejestruj się jako deweloper

1. Przejdź do [Device Access Console](https://console.nest.google.com/device-access)
2. Zapłać jednorazową opłatę $5 USD
3. Zaakceptuj warunki użytkowania

### Krok 2: Utwórz projekt

1. Kliknij "Create project"
2. Podaj nazwę projektu
3. Wprowadź OAuth Client ID z Google Cloud Console
4. Zapisz **Project ID** (format: `projects/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Krok 3: Połącz dom

1. W Device Access Console wybierz projekt
2. Kliknij "Link account"
3. Autoryzuj dostęp do swojego konta Google Home
4. Wybierz urządzenia, które chcesz udostępnić

## Konfiguracja Rider-PC

### Plik .env

Dodaj następujące zmienne do pliku `.env`:

```bash
# Włącz lokalną integrację Google Home
GOOGLE_HOME_LOCAL_ENABLED=true

# OAuth Client ID z Google Cloud Console
GOOGLE_HOME_CLIENT_ID=xxxxxxxxxx.apps.googleusercontent.com

# OAuth Client Secret z Google Cloud Console
GOOGLE_HOME_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx

# Project ID z Device Access Console
GOOGLE_HOME_PROJECT_ID=projects/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# URL callbacku OAuth (musi być zgodny z Google Cloud Console)
GOOGLE_HOME_REDIRECT_URI=http://localhost:8000/api/home/auth/callback

# Ścieżka do pliku z tokenami (opcjonalnie)
GOOGLE_HOME_TOKENS_PATH=config/local/google_tokens_pc.json

# Tryb testowy - używa mock urządzeń (opcjonalnie)
GOOGLE_HOME_TEST_MODE=false
```

### Uprawnienia katalogów

Upewnij się, że katalog `config/local/` istnieje i ma odpowiednie uprawnienia:

```bash
mkdir -p config/local
chmod 700 config/local
```

## Uruchomienie

### Krok 1: Uruchom Rider-PC

```bash
python -m uvicorn pc_client.main:app --host 0.0.0.0 --port 8000
```

### Krok 2: Otwórz panel Google Home

Przejdź do: `http://localhost:8000/web/google_home.html`

### Krok 3: Zaloguj się

1. Kliknij przycisk "Zaloguj przez Google"
2. W nowym oknie zaloguj się na swoje konto Google
3. Zaakceptuj uprawnienia dla Device Access
4. Zostaniesz przekierowany z powrotem do Rider-PC

### Krok 4: Steruj urządzeniami

Po pomyślnym zalogowaniu zobaczysz listę swoich urządzeń Google Home i możesz nimi sterować.

## Rozwiązywanie problemów

### Błąd: "not_configured"

**Problem**: Brakuje wymaganych zmiennych środowiskowych.

**Rozwiązanie**: Sprawdź, czy wszystkie wymagane zmienne są ustawione w `.env`:
- `GOOGLE_HOME_CLIENT_ID`
- `GOOGLE_HOME_CLIENT_SECRET`
- `GOOGLE_HOME_PROJECT_ID`
- `GOOGLE_HOME_REDIRECT_URI`

### Błąd: "invalid_state"

**Problem**: Token CSRF wygasł lub jest nieprawidłowy.

**Rozwiązanie**: 
1. Odśwież stronę Google Home
2. Kliknij ponownie "Zaloguj przez Google"
3. Upewnij się, że nie masz otwartych wielu okien logowania

### Błąd: "token_exchange_failed"

**Problem**: Nie udało się wymienić kodu autoryzacji na tokeny.

**Rozwiązanie**:
1. Sprawdź, czy `GOOGLE_HOME_CLIENT_SECRET` jest poprawny
2. Upewnij się, że `GOOGLE_HOME_REDIRECT_URI` jest zgodny z konfiguracją w Google Cloud Console
3. Sprawdź logi serwera dla szczegółowych informacji

### Błąd: "not_authenticated"

**Problem**: Sesja wygasła lub brak tokenów.

**Rozwiązanie**:
1. Kliknij "Wyloguj" a następnie "Zaloguj przez Google"
2. Sprawdź, czy plik `config/local/google_tokens_pc.json` istnieje
3. Usuń plik tokenów i zaloguj się ponownie

### Brak urządzeń na liście

**Problem**: Po zalogowaniu lista urządzeń jest pusta.

**Rozwiązanie**:
1. Sprawdź, czy urządzenia są widoczne w aplikacji Google Home
2. Upewnij się, że urządzenia zostały wybrane podczas autoryzacji Device Access
3. Przejdź do Device Access Console i sprawdź, czy konto jest połączone

### Błąd: "quota_exceeded"

**Problem**: Przekroczono limit zapytań do API.

**Rozwiązanie**:
1. Poczekaj kilka minut przed ponowną próbą
2. Sprawdź limity w Google Cloud Console → APIs & Services → Smart Device Management API

## Bezpieczeństwo

### Tokeny

- Tokeny są przechowywane lokalnie w `config/local/google_tokens_pc.json`
- Plik ten zawiera wrażliwe dane - nie commituj go do repozytorium
- Katalog `config/local/` jest domyślnie w `.gitignore`

### HTTPS w produkcji

Dla środowisk produkcyjnych:
1. Skonfiguruj certyfikat SSL
2. Zmień `GOOGLE_HOME_REDIRECT_URI` na adres HTTPS
3. Zaktualizuj konfigurację w Google Cloud Console

### Uprawnienia

Rider-PC prosi o następujące uprawnienia:
- `https://www.googleapis.com/auth/sdm.service` - dostęp do Smart Device Management API

Nie przechowujemy ani nie przetwarzamy żadnych innych danych z konta Google.

## API Reference

### GET /api/home/status

Zwraca stan autoryzacji:

```json
{
  "configured": true,
  "authenticated": true,
  "test_mode": false,
  "profile": {"email": "user@example.com"},
  "auth_url_available": true
}
```

### GET /api/home/auth/url

Rozpoczyna przepływ OAuth i zwraca URL autoryzacji:

```json
{
  "ok": true,
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "...",
  "expires_at": 1234567890.0
}
```

### GET /api/home/auth/callback

Endpoint callbacku OAuth. Przekierowuje do `/web/google_home.html?auth=success` po pomyślnej autoryzacji.

### POST /api/home/auth/logout

Czyści tokeny autoryzacji:

```json
{
  "ok": true,
  "message": "Tokens cleared"
}
```

### GET /api/home/devices

Zwraca listę urządzeń:

```json
{
  "ok": true,
  "devices": [
    {
      "name": "enterprises/xxx/devices/xxx",
      "type": "sdm.devices.types.LIGHT",
      "traits": {...},
      "room": "Living Room",
      "structure": "Home"
    }
  ]
}
```

### POST /api/home/command

Wysyła komendę do urządzenia:

```json
{
  "deviceId": "enterprises/xxx/devices/xxx",
  "command": "action.devices.commands.OnOff",
  "params": {"on": true}
}
```

Odpowiedź:
```json
{
  "ok": true,
  "device": "...",
  "command": "..."
}
```
