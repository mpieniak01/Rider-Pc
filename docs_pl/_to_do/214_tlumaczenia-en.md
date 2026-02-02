# Zadanie #214: Tłumaczenia EN – widoki Rider‑PC

**Status:** :white_check_mark: Zakończone (włączone do wydania zbiorczego #214/#215)
**Link:** (lokalnie – bez GitHub)
**Autor:** Nieprzypisane

## Cel
Uzupełnić brakujące tłumaczenia w wersji EN dla ekranów Rider‑PC (UI w `/web/*.html`) i przenieść ręczne napisy do słownika i18n.

## Zakres
Poniżej zebrane wymagania do przeniesienia do i18n + tłumaczenia EN:

### 1. assistant.html (Google Assistant panel)
- `title="Przeładuj konfigurację"` → “Reload configuration”
- Placeholder „Wpisz komendę, np. ‘Włącz wszystkie światła’” → “Type a command, e.g., ‘Turn on all lights’”
- Przyciski „Wyślij”, „⟳ Odśwież” (już w i18n) – uzupełnić brakujące konteksty.
- Statusy tekstowe z JS:
  - „Usługa Google Assistant jest wyłączona…” → “Google Assistant service is disabled. Set GOOGLE_ASSISTANT_ENABLED=true in .env.”
  - „Nie udało się załadować urządzeń” → “Failed to load devices.”
  - „Komenda nie powiodła się” → “Command failed.”
  - „Wysyłam komendę…” → “Sending command…”
  - „Błąd ładowania historii” → “Error loading history.”
  - „Przeładowuję konfigurację…” → “Reloading configuration…”

### 2. chat.html (Rider‑PI chat)
- Placeholder textarea: „Napisz wiadomość… (Enter = wyślij, Shift+Enter = nowa linia)” → “Type a message… (Enter = send, Shift+Enter = new line)”
- `#provider-hint`: „Ładuję listę providerów…” → “Loading provider list…”
- Buttons/labels: „Odśwież listę” → “Refresh list”, „Kliknij „Test”… ” → “Click “Test” to run a TTS probe…”
- Demo teksty: „Przykładowa wiadomość użytkownika.” → “Sample user message.” itd.
- Status strings in JS (serviceStateSummary, setStatus etc.):
  - „błąd” → “error”
  - „Brak providerów TTS…” → “No TTS providers available – using default mode.”
  - „Błąd połączenia” → “Connection error.”
  - „Ładuję…/Testuję…/Startuję…” etc.

### 3. chat-pc.html (lokalny chat)
- Teksty w nagłówku: „Czat działający lokalnie z modelami AI na Twoim PC” → “Chat running locally with on‑PC AI models.”
- Formularze PR assistant / benchmark:
  - „Podgląd”, „Odrzuć”, „Wygenerowana treść PR”, „Szczegółowy/Zwięzły” → “Preview”, “Discard”, “Generated PR content”, “Detailed/Concise”.
- Komunikaty JS:
  - „Brak providerów TTS – używam domyślnego Piper.” → “No TTS providers – falling back to default Piper.”
  - „Nieznany alias usługi” → “Unknown service alias.”
  - „Generuję…/Ładuję…” etc.
- Alerty: „Wprowadź szkic PR”, „Nie udało się uzyskać dostępu do mikrofonu” → “Enter the PR draft”, “Failed to access microphone”.

### 4. control.html (Control & providers)
- Sekcja kamery: „Podgląd kamery” → “Camera preview”.
- Ustawienia ruchu: „Prędkość skrętu/maksymalna”, „Skróty” → “Turning speed”, “Max speed”, “Shortcuts”.
- Tryby usług (tooltips):
  - „Stan 0 – Sterowanie ręczne” → “State 0 – Manual control”
  - „Śledzenie (twarz / dłoń)” → “Tracking (face / hand)”
  - „Włącza odometrię…” → “Enables odometry, mapper and starts the navigator.”
- Zasoby: „Diagnostyka zasobów”, kolumny „Zasób / Blokujące procesy / Stop usługi” → “Resource diagnostics / Blocking processes / Stop service.”
- Motion queue: „Brak zleceń ruchu.” → “No motion jobs.”
- Status hints w JS (np. showToast): „Usługi: … Brak zleceń ruchu.” etc.

### 5. navigation.html (mapa)
- Nagłówki UI: „Łączenie…/Połączono/Rozłączono/Błąd” → “Connecting…/Connected/Disconnected/Error”.
- Legendy: „Ścieżka (Plan)”, „Domyślna szerokość/wysokość”, „Przebita ścieżka” etc.
  - Use translations: “Path (Plan)”, “Default width/height”, “Traveled path”.

### 6. system.html (System graph)
- Link w menu: „Podgląd” → “Overview”.
- Status bar: „Ładowanie danych usług…” → “Loading service data…”.
- Card titles: „Usługi lokalne (PC) / Usługi na Rider-Pi”.
- Buttons: „Wyczyść log” → “Clear log”.
- Toasts: „Nie udało się skopiować”, „Robot Offline – Rider-Pi niedostępny”.
- Graph labels: „Połączenia →”, „Błąd”.
- Audit mode strings: „Tryb audytu CSS – dane przykładowe.”

### 7. models.html (Model manager)
- Opisy: „Centralne zarządzanie mózgiem…”, „Rider-PC Pipeline (Mózg)”.
- Status: „Ładowanie…”, „Zapisz konfigurację PC”, „Brak połączenia”, „Pi Połączony” etc.
- Hinty: „Pi używa wbudowanego… (niekonfigurowalne)” → “Pi uses a built-in lightweight model (not configurable).”
- Global statuses w JS: „Synchronizacja systemów…”, „Błąd inicjalizacji API”, „Odświeżanie Pi…”.

### 8. project.html (GitHub/project board)
- Buttons: „Utwórz nowe zadanie”, „Odśwież dane”, status line „Ładowanie zgłoszeń…”.
- Formularz: „Tytuł *”, placeholdery, „Zostań na obecnym branchu / Utwórz nowy branch / Przełącz na istniejący branch / Utwórz Zadanie”.
- Hints: „Automatyczna nazwa na podst. tytułu”, „Utwórz plik dokumentacji…”.
- Toasty/błędy w JS: „Tryb audytu CSS…”, „Błąd podczas pobierania danych”, „Wybierz istniejącą gałąź”.

### 9. view.html (Overview dashboard)
Większość jest już w i18n (dash.*). Upewnić się, że brakujące ręczne napisy mają tłumaczenia:
- `<title>Rider-PC: Przegląd` → `Rider-PC: Overview`.
- Hints: „Źródło:” (już w i18n).
- Muted placeholders: „Ładowanie…”, „Brak narzędzi”, „Brak wywołań”, „błąd”.
- JS fallbacki: `t('dash.mcp.loading') || 'Ładowanie...'` – uzupełnić w słowniku EN.

### 10. home.html / google_home.html
Większość tekstów ma `data-i18n`, ale w JS są wstawki:
- „Brak urządzeń”, „Błąd ładowania urządzeń” – dodać do `home.*` w `i18n.js`.

### 11. providers.html & mode.html
- „Panel Providers został scalony…” → “The Providers panel has been merged…”
- „Panel wyboru trybów… zostaniesz przekierowany” → “The AI modes selector has been merged with “Control”; you will be redirected automatically…”

### 12. templates/dashboard_base.html
- „Przykładowa wiadomość statusowa”, „Uruchomiono usługę.” → “Sample status message”, “Service started.”

## Rekomendacje wdrożeniowe
- Centralizuj teksty – każdy napis umieść w `I18N` (sekcje: `control`, `system`, `project`, `chat`, `chat_pc`, `models`).
- Placeholdery/`title` – dodać `data-i18n` lub atrybuty `data-i18n-placeholder`/`data-i18n-title`.
- Teksty JS – zastąpić literały funkcjami `t('key')` z fallbackiem.
- Nazwy ekranów/menu – upewnić się, że klucze w `nav` są kompletne i używane.
- Lista kontrolna – po dodaniu tłumaczeń przejść UI w trybie `?lang=en` i sprawdzić: `/view`, `/control`, `/navigation`, `/system`, `/models`, `/project`, `/assistant`, `/chat`, `/chat-pc`, `/google_home`, `/mode`, `/providers`.

## Plan realizacji (postęp)
- [x] Uzupełnić i18n + podpiąć brakujące napisy w: navigation, providers, mode, chat, chat‑pc, system, models, project, template.
- [x] Dokończyć podmianę pozostałych literałów PL w JS (chat/chat‑pc/control/system) na `t('...')`.
- [x] Przegląd UI w trybie `?lang=en` i dopisanie brakujących kluczy.
