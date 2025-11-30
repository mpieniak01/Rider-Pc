# Plan: Rider-PC – natywne logowanie i integracja Google Home

## Status: W TRAKCIE REALIZACJI

## Zrealizowane (PR #107)

### ✅ 1. Architektura i zależności
- [x] Moduł `pc_client/services/google_home.py` z OAuth 2.0 + PKCE
- [x] Konfiguracja przez zmienne środowiskowe w Settings
- [x] Używamy czystego `httpx` dla komunikacji z SDM API (bez dodatkowych zależności google-auth)

### ✅ 2. Przepływ OAuth na Rider-PC
- [x] Endpoint `GET /api/home/auth/url` buduje adres logowania Google (PKCE, state)
- [x] Endpoint `GET /api/home/auth/callback` obsługuje redirect z Google
- [x] Endpoint `POST /api/home/auth/logout` do wylogowania
- [x] Weryfikacja `state` (CSRF protection) w pamięci serwera

### ✅ 3. Serwis Google Home
- [x] Metody: `is_configured()`, `is_authenticated()`, `start_auth_session()`, `complete_auth(code)`, `list_devices()`, `send_command()`, `get_status()`
- [x] Zapisywanie tokenów w `config/local/google_tokens_pc.json`
- [x] Odświeżanie tokenów na 401
- [x] Cachowanie listy urządzeń (5 minut TTL)
- [x] Tryb testowy (`GOOGLE_HOME_TEST_MODE=true`) dla developmentu

### ✅ 4. API FastAPI
- [x] Refaktoryzacja `home_router.py` - najpierw lokalny serwis, potem RestAdapter jako fallback
- [x] Rozróżnianie stanów: `not_configured`, `not_authenticated`, `authenticated`
- [x] `/api/home/status` zwraca szczegółowy stan konfiguracji

### ✅ 7. Konfiguracja i dokumentacja
- [x] Nowy rozdział `docs_pl/google-home-integration.md`
- [x] Zaktualizowany `.env.example` z instrukcjami konfiguracji

### ✅ 8. Testy
- [x] Testy jednostkowe dla GoogleHomeService (21 testów)
- [x] Testy integracyjne dla endpointów OAuth (7 nowych testów)

## Do zrobienia (przyszłe PR)

### 5. UX w `web/google_home.html`
- [ ] Przycisk „Zaloguj przez Google" z przekierowaniem na `auth_url`
- [ ] Sekcja konfiguracji gdy brak Client ID/Secret/Project ID
- [ ] Stany `logowanie trwa` i `logowanie zakończone`
- [ ] Widok profilu użytkownika po zalogowaniu

### 6. Realna integracja SDM
- [ ] Testy manualne na fizycznym domu
- [ ] Weryfikacja mapowania komend OnOff, Brightness, Thermostat, StartStop, Dock
- [ ] Logi akcji do `logs/google_home/actions.log`

### 9. Sprzątanie
- [ ] Oznaczenie `RestAdapter.post_home_*` jako legacy
- [ ] Aktualizacja `config/google_bridge.toml`

---

## Cel
Zapewnić, aby użytkownik mógł w całości z poziomu przeglądarki Rider-PC:
- przejść pełny przepływ OAuth 2.0 (bez tunelowania do Rider-Pi),
- zobaczyć stan autoryzacji i listę urządzeń w czasie rzeczywistym,
- wykonywać faktyczne komendy Google Smart Device Management (SDM) kierowane z Rider-PC prosto do Google Home.
- Podkreślamy, że użytkownik oczekuje integracji z **fizycznym domem** (realne konto Google Home, prawdziwe urządzenia), a nie z trybem piaskownicy czy mockami – tryb testowy służy jedynie do developmentu.

## Stan obecny
- UI Rider-PC (`web/google_home.html`) renderuje wszystko lokalnie, ale REST API jedynie proxy-je żądania do Rider-Pi przez `RestAdapter` (`pc_client/api/routers/home_router.py`, `pc_client/adapters/rest_adapter.py`).
- Rider-Pi posiada kompletny moduł `services/api_core/google_home_api.py` + endpointy `/api/home/*` (`services/api_server.py:470-520`), jednak PC nie ma własnego klienta SDM ani bibliotek Google.
- W repo Rider-PC znajdują się repliki konfigów (`config/google_bridge.toml`) i mocki urządzeń, ale brak rzeczywistych tokenów / flow w kliencie PC.

## Wymagania docelowe
1. OAuth 2.0 typu „web application”/PKCE startowany z Rider-PC i kończony callbackiem obsłużonym również na Rider-PC (`https://<pc-host>/api/home/auth/callback`).
2. Tokeny Google są przechowywane lokalnie po stronie PC (np. `config/local/google_tokens_pc.json`) i automatycznie odświeżane.
3. Endpointy `/api/home/status`, `/devices`, `/command` w Rider-PC używają lokalnego serwisu Google Home bez pośrednictwa Rider-Pi. (Proxy do Pi traktujemy jako tryb legacy/offline.)
4. UI otrzymuje jasne stany (`brak konfiguracji`, `gotowy do logowania`, `logowanie w toku`, `zalogowany`, `błąd SDM`) oraz może zainicjować logowanie jednym kliknięciem (przeglądarka przekierowana na stronę Google).
5. Dokumentacja i testy opisują jak skonfigurować identyfikator OAuth, Device Access Project ID i ścieżki SDM.

## Najważniejsze luki
1. **Brak modułu Google Home w Rider-PC.** Obecnie nie ma kodu, który buduje `Authorization Code` flow, rozmawia z `https://smartdevicemanagement.googleapis.com/v1/...` czy przechowuje tokeny.
2. **Flow OAuth wymaga ręcznego tunelowania do Rider-Pi.** `InstalledAppFlow.run_local_server()` działa wyłącznie na Pi i jest niewidoczny dla przeglądarki PC → nie spełnia nowego wymagania „wszystko z przeglądarki”.
3. **Brak endpointów `auth/url` i `auth/callback` po stronie PC.** UI nie ma jak pobrać linku ani zaworu stanu.
4. **Konfiguracja (Client ID/Secret, Device Access Project ID) nie jest opisana dla Rider-PC.** `config/google_bridge.toml` jest jedynie kopią z Rider-Pi i nie jest używany.
5. **Brak testów/regresji.** Nie da się zweryfikować poprawności przepływu OAuth i wywołań SDM bez nowego serwisu + mocków.

## Plan działania - PR
### 1. Architektura i zależności
- Dodać do Rider-PC zależności `google-auth`, `google-auth-oauthlib`, `google-api-python-client` (lub czysty `httpx` dla SDM) w `requirements.txt`.
- Zaprojektować moduł `pc_client/services/google_home.py` inspirowany `Rider-Pi/services/api_core/google_home_api.py`, ale dostosowany do web-app flow (Authorization Code + PKCE).
- Ustalić pliki konfiguracyjne: `config/google_home.toml` (nowy) oraz `config/local/google_home.toml` z polami: `client_id`, `client_secret`, `project_id`, `sdm_enterprise_id`, `redirect_base_url`.
- Przenieść (lub przepisać) brakujące helpery z Rider-Pi: `build_auth_url_preview`, cache komend, magazyn tokenów, logowanie do journald → w Rider-PC powinna istnieć równoważna warstwa usługowa, aby UI nie zależał od `RestAdapter`.
- W `config/local/` przewidzieć sekcję z realnymi identyfikatorami Device Access (enterpriseId, structureId, nazwy pomieszczeń) – musimy je pozyskać z faktycznego konta Google Home, żeby później mapować urządzenia z prawdziwego domu użytkownika.

### 2. Przepływ OAuth na Rider-PC
- Endpoint `GET /api/home/auth/url` (nowy) buduje adres logowania Google (PKCE, state) i zwraca JSON: `{ok, auth_url, expires_at}`.
- Endpoint `GET /api/home/auth/callback` obsługuje redirect z Google (parametry `code`, `state`), wymienia code na tokeny i zapisuje refresh token w magazynie (np. `config/local/google_tokens_pc.json`).
- Endpoint `POST /api/home/auth` pozostaje, ale w wariancie webowym może służyć tylko do ręcznego „restartu” flow lub force-refresh.
- Dodać middleware/sesję (signed cookies) do weryfikacji `state` i ochrony przed CSRF.
- Po udanym logowaniu zapisać profil użytkownika (adres e-mail konta Google, nazwa projektu Device Access) i pokazać go w UI, aby użytkownik widział z którym domem jest połączony.
- Dodać narzędzie CLI/diagnostyczne (`python -m pc_client.services.google_home doctor`), które sprawdzi ważność tokenów, dostępność Device Access API i poprawność konfiguracji – to pozwoli szybciej diagnozować problemy na prawdziwym środowisku.

### 3. Serwis Google Home
- Metody: `is_configured()`, `is_authenticated()`, `start_auth_session()`, `complete_auth(code)`, `list_devices()`, `send_command(device_id, command, params)`, `get_profile()`.
- Po sukcesie zapisywać token metadata (`refresh_token`, `expiry`, `scopes`) w katalogu `config/local/`.
- Implementować odświeżanie tokenów na 401 i cachowanie ostatniej listy urządzeń (tak jak `Rider-Pi/_save_command_cache`).
- Udokumentować mapowanie komend/traits (OnOff, Brightness, ColorSetting, ThermostatMode, StartStop, Dock) i przygotować checklistę testów na fizycznych urządzeniach (lampy, termostaty, odkurzacze) – każda komenda musi mieć obserwowalny efekt w realnym domu.
- Opcjonalnie zaplanować integrację z Device Access Pub/Sub (webhook) – jeśli w przyszłości chcemy odbierać powiadomienia o zmianach stanu bez odpytywania API.

### 4. API FastAPI
- `pc_client/api/routers/home_router.py` do refaktoryzacji: w pierwszej kolejności używa lokalnego serwisu; `RestAdapter` do Rider-Pi pozostaje jako fallback (`if not settings.google_home_local_enabled`).
- Nowe odpowiedzi muszą rozróżniać błędy konfiguracji (`auth_env_missing`), błędy użytkownika (`access_denied`), błędy SDM (`quota_exceeded`, `device_offline`).
- Dostarczyć streaming logowania: `/api/home/status` powinien zwracać m.in. `{"configured": true, "authenticated": false, "auth_url_available": true, "profile": null}`.
- `/api/home/devices` ma zwracać metadane z Device Access (structure, room, customName, traits), aby UI mógł pokazać prawdziwe nazwy pokoi/urządzeń z domu użytkownika.
- `/api/home/command` powinien logować każdą akcję (czas, użytkownik, deviceId, parametry, wynik) do `logs/google_home/actions.log`, co pozwoli audytować sterowanie fizycznymi urządzeniami.

### 5. UX w `web/google_home.html`
- Przycisk „Zaloguj przez Google” ma przekierować użytkownika na `auth_url` (pełne okno/przekierowanie), po powrocie `auth=success` w URL lub `state` w localStorage, i automatycznie odświeżyć `checkAuth()`.
- Dodać sekcję konfiguracji: gdy brak Client ID/Secret/Project ID → w kartach pokazać komunikat + link do dokumentacji konfiguracyjnej.
- Zapewnić stany `logowanie trwa` i `logowanie zakończone`, w tym countdown, link do „Wyświetl aktywne sesje Google”.
- Po udanym logowaniu UI musi pokazać prawdziwą listę urządzeń z domu (nazwa + pokój) wraz z filtrem po pomieszczeniach i wyszukiwarką – użytkownik ma od razu widzieć swoje realne urządzenia.
- Dodać widok historii (ostatnie N komend z Rider-PC) z informacją czy SDM potwierdził wykonanie – to ułatwia diagnozę, gdy fizyczne urządzenie nie reaguje.

### 6. Realna integracja SDM
- W serwisie użyć końcówek:
  - `GET https://smartdevicemanagement.googleapis.com/v1/enterprises/{project-id}/devices`
  - `POST https://smartdevicemanagement.googleapis.com/v1/{device}:executeCommand`
  - (opcjonalnie) `GET structures`, `GET rooms` jeśli chcemy rozszerzyć UI.
- Parametry (Device Access Project ID) przechowujemy w konfiguracji, walidujemy przy starcie.
- Wprowadzić `GOOGLE_HOME_TEST_MODE` umożliwiający korzystanie z mocków (jak `MockRestAdapter`) w CI.
- Przygotować procedurę biznesową: jak zarejestrować projekt Device Access, wnieść opłatę, dodać własny dom do projektu i pozyskać identyfikatory struktur. Bez tych kroków realne urządzenia nie będą widoczne w Rider-PC.
- Testy manualne na fizycznym domu: 1) zaloguj konto Google, 2) zweryfikuj, że lista urządzeń pokrywa się z aplikacją Google Home, 3) wykonaj komendy (włącz światło, zmień temperaturę, rozpocznij sprzątanie) i potwierdź fizyczny efekt, 4) sprawdź logi Rider-PC.

### 7. Konfiguracja i dokumentacja
- Przygotować nowy rozdział w `docs_pl/google-home-integration.md` opisujący „tryb Rider-PC” z krokami:
  1. Utwórz OAuth Client typu „Web application” w Google Cloud Console.
  2. Dodaj `https://<pc-host>/api/home/auth/callback` do `Authorized redirect URIs`.
  3. Ustaw `GOOGLE_DEVICE_ACCESS_PROJECT_ID`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` w pliku `.env` / toml.
  4. Zrestartuj Rider-PC i kliknij „Zaloguj”.
- Opisać różnice między trybem PC a trybem Pi (legacy) oraz sposób migracji istniejących tokenów.
- Dodać instrukcję „Połącz dom z Device Access”: linki do konsoli Google, wymagane urządzenia, ograniczenia (tylko jedno konto Google, płatność 5 USD), jak uzyskać `enterpriseId` i `project_id`.
- Przygotować FAQ operacyjne: brak urządzeń po logowaniu, reset tokenów, migracja konfiguracji na nowy komputer, odłączenie Rider-PC od konta Google.

### 8. Testy i monitoring
- Jednostkowe: mock `google.oauth2.id_token` / `httpx` do SDM, testy dla serwisu (odświeżanie tokenów, obsługa błędów 401/403).
- Integracyjne: test FastAPI `/api/home/*` przy użyciu `TestClient`, wstrzykiwanie fałszywego serwisu (Dependency Override).
- E2E UI (opcjonalnie): Playwright – klik logowania i sprawdzenie, że po callbacku liste devices się pojawia (z użyciem fake SDM).
- Monitoring: zliczać błędy `home.auth_fail`, `home.devices_fetch_fail` w metrykach `view.html`.
- Upewnić się, że cały zestaw testów istniejący dla Rider-Pi (`services/api_core/google_home_api.py`, `services/api_server.py`) ma odpowiedniki w Rider-PC; jeżeli kopiujemy kod, kopiujemy także testy (`Rider-Pi/tests/test_google_home_api.py`, `tests/test_api_server_google_home.py`) i dostosowujemy je do fastapi.
- W `web/view.html` dodać metryki telemetryczne (`home.devices_count`, `home.commands_ok`, `home.commands_err`, `home.last_sync`), by użytkownik widział czy integracja działa po podłączeniu prawdziwych urządzeń.
- Przygotować scenariusz testów akceptacyjnych na realnym domu i logować wyniki (co najmniej raz na sprint) w sekcji dokumentacji – to potwierdzi, że cel biznesowy „steruję urządzeniami domowymi przez Rider-PC” jest osiągnięty.

### 9. Sprzątanie
- Jeśli Rider-PC ma działać niezależnie, `RestAdapter.post_home_*` można oznaczyć jako legacy lub całkiem usunąć po migracji.
- Zaktualizować `config/google_bridge.toml` → przenieść do archiwum lub zastąpić nowym `config/google_home.toml`.
- Upewnić się, że systemd/usługi `rider-google-bridge` są opisane jako opcjonalne, ponieważ Rider-PC będzie bezpośrednio rozmawiał z Google.

### 10. Migracja API Google Home z Rider-Pi
- Przejrzeć pełny zestaw modułów Rider-Pi związanych z Google Home (`services/api_core/google_home_api.py`, `services/api_server.py`, `apps/google_bridge/*`, dokumentacja i testy) i zdecydować, które elementy kopiujemy 1:1, a które przepisujemy (np. serwis API vs. worker bridge).
- Uzupełnić Rider-PC o brakujące struktury konfiguracyjne (`config/google_bridge.toml`, `config/local/google_bridge.toml`, katalog `data/google/*`) tak, aby środowisko uruchomieniowe PC było gotowe na te same dane co Pi.
- Dopisać checklistę wdrożeniową: `pip install -r requirements.txt`, `python -m pc_client.services.google_home migrate` (narzędzie inicjalizujące katalog tokenów), wygenerowanie pliku `.env` z parametrami Device Access, restart procesu FastAPI.
- Dokumentacyjnie wskazać, że bez pełnej instalacji API (biblioteki + moduły + konfiguracje z Rider-Pi) Rider-PC nie będzie w stanie zestawić sesji SDM – trzeba więc traktować Rider-Pi jako źródło prawdy i sukcesywnie portować wszystkie elementy, aż parzystość funkcjonalna zostanie osiągnięta.
- Po zakończeniu migracji kodu wykonać pełną regresję na prawdziwym środowisku (Rider-PC w domu, zalogowane konto Google, komendy na urządzeniach) i porównać zachowanie z Rider-Pi – dopiero wtedy uznamy, że cel biznesowy został osiągnięty.

Po wdrożeniu powyższych kroków Rider-PC staje się samodzielnym klientem Google Home: użytkownik loguje się standardowym oknem Google, a wszystkie urządzenia i komendy trafiają bezpośrednio z PC do Smart Device Management API.***
