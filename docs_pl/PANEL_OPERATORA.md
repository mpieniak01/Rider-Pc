# Panel operatora Rider-PC

Panel ma ten sam podział i kontrakty decyzji co Rider-Pi. Robot jest fizycznym
urządzeniem; dostępność API PC ani aktywny proces nie potwierdzają gotowości
napędów. Stan i katalog Pi są źródłem danych.

## Widoki

| Widok | Dane i decyzje |
| --- | --- |
| Przegląd `/view` | Połączenie PC/Pi, aktualność baterii i zadań, blokada ruchu, STOP. |
| Zadania i sterowanie `/control` | Katalog v2, opcje i zasoby zadania; jawny plan/zgoda, właściciel i ograniczony impuls; historia żądań i ACK. |
| Urządzenia `/devices` | Właściciele procesów i konsumenci zadań, kamera/RAW/PROC/SSD/tracker, bateria/IMU, LCD i UART. |
| System `/system` | Usługi Pi/PC, rzeczywiste providery aplikacji, źródło i wiek odczytu, graf i szczegóły hostów, odrębna administracja/autostart i ręczne odzyskanie zasobu. |
| Nawigacja `/navigation` | Mapa, pozycja i trasa z czasami producenta; jawne przygotowanie właściciela navigation, start/STOP i powrót. |
| Chat `/chat` | Tekst i opcjonalne TTS; konkretna domena przygotowywana wyłącznie przy wysłaniu. |
| Narzędzia PC | Zachowane modele, projekt, statusy, Google Home, Assistant i osobny Chat PC. |

Otwarcie widoku i zmiana wyboru nie uruchamiają zadania, modelu ani aktuatora.
Domyślnie System jest odczytowy; karta nie ma akcji start/stop.
Administrację usługami włącza osobny przełącznik w tej karcie przeglądarki.
Każde żądanie wskazuje `host:unit`; identyczne nazwy jednostek na Pi i PC
nie są mieszane. Provider aplikacji ma własny typ i brak fikcyjnego systemd.

## Przygotowanie ruchu

1. Przygotuj robota, przestrzeń, przewód zasilający i sposób użycia STOP.
2. W tym samym widoku wpisz konkretny plan, wybierz właściciela i czas zgody
   do 30 sekund, następnie jawnie zaznacz zgodę. ARM nie wykonuje ruchu.
3. Sprawdź świeże ARMED, `ready`, `hardware_ready`, możliwości napędów i
   właściwego właściciela. Dopiero osobna akcja wysyła impuls lub start zadania.
4. Użyj STOP. STOP/disarm/ESTOP od razu unieważnia lokalną obsługę generacji;
   utrata połączenia, fokusu lub ukrycie widoku zawiesza sterowanie i próbuje STOP.
   Zgody i celów nie przenosi się między widokami.

W/S/A/D i strzałki działają tylko w Zadaniach i sterowaniu, przy właścicielu
manual. Pola tekstowe, select, modyfikatory i powtarzanie klawisza są pomijane.
Spacja poza polami wywołuje STOP. Wywołania fizycznych aktuatorów pozostają
ręczne i wymagają operatora; nie są częścią ogólnych testów oprogramowania.

UI potwierdza zegar Pi przez `server_time` przy GET stanu. RTT powyżej 500 ms,
stary zegar, brak v1 lub UNKNOWN daje odczyt. Koperta powstaje dokładnie przy
potwierdzeniu operatora: `request_id, source:manual, generation, seq, ts, ttl_ms`.
Sekwencja jest nieujemna i rośnie w generacji; TTL nie przekracza 500 ms.
PC przekazuje ją bez odświeżenia starego żądania. `action` jest formatem
kanonicznym, starsze `cmd` pozostaje zgodne z API.

`pending`/HTTP 202 oznacza oczekiwanie. Tylko zgodny terminalny ACK potwierdza
SDK; sprawdzane są identyfikator, akcja, źródło, sekwencja, generacja i czas.
Fizyczne zakończenie nadal ma `physical_completion:unverified`.
Błąd sieci pozostawia wynik nieznany, a nie zielony sukces.

## Zadania, domeny i urządzenia

Lista i `option_schema` pochodzą wyłącznie z katalogu v2 Pi. UI nie odtwarza
lokalnych blueprintów. Nieznane `can_move`, brak instalacji, stare dane i błędy
blokują start. Requested/starting/ready/partial/failed/stopping/stopped są
pokazywane oddzielnie od stanu procesu.

Domeny text/vision/voice i ich Pi/PC/health są odczytowe. Uruchomienie wybranej
domeny odbywa się przez jawny start konkretnego zadania i jego opcję z katalogu.
Legacy globalne przełączanie AI nie jest używane przez nowy panel.
Chat jawnie używa ścieżki proxy Pi; osobny Chat PC pozostaje dostępną lokalną funkcją.

Podgląd kamery jest domyślnie wyłączony. Włączenie odświeża tylko obraz w karcie,
nie uruchamia capture i nie zatrzymuje zadania przy wyłączeniu. URL musi wskazywać
lokalną trasę kamery. Ekran robota jest zamontowany bokiem; zachowaj ustaloną
kompensację 270°, splash i sekwencję startową. Panel nie obraca LCD.
UART ma jednego właściciela — wykonawcę ruchu; telemetria pochodzi z BUS.

Administracja rozdziela start/stop/restart od enable/disable.
Ruchowe autostarty są zablokowane. Zakończ zadanie przed zatrzymaniem wspólnej
usługi. Wymuszone zwolnienie zasobu wymaga świeżych właścicieli, wybranych PID,
wpisania nazwy zasobu i osobnej zgody; API nadal chroni UART/LCD/usługi bazowe.

## Weryfikacja i utrzymanie

Lekki frontend to moduły vanilla JS w `web/assets/operator`, bez frameworka,
nowych bibliotek i nowych pakietów na Pi. Odczyty mają limit czasu, deduplikację,
backoff i nie nakładają się; ukryte karty zatrzymują polling i SSE.

Izolowane scenariusze obejmują zegary/generacje/ACK, nieznany kontrakt,
readonly System, granice hostów, administrację i lazy preview.
Używaj istniejącego lokalnego venv WSL zgodnie z
[minimalnym runtime i testami](CONTRIBUTING.md#minimalny-runtime-i-testy-w-wsl).

```sh
node --experimental-vm-modules --test tests/operator_panel.test.mjs
RIDER_ENABLE_API_TESTS=1 .venv/bin/python -m pytest pc_client/tests tests --ignore=tests/e2e
.venv/bin/python -m pytest tests/e2e
```

Reguły izolacji i zgodności API: [bezpieczny klient](BEZPIECZNY_KLIENT_ROBOTA.md).

Logi usługi odczytujemy wyłącznie na żądanie (GET, host/jednostka), ze skonfigurowanych jednostek PC albo inwentarza Pi. Odczyt dziennika ograniczamy do 2 sekund, 50 linii i 64 KiB; brak uprawnień jest błędem.

## Lokalne providery PC

Wyłączona domena nie importuje ciężkich bibliotek AI. Jawne przełączniki uruchomienia
PC i konfiguracja providera wybierają wymagany backend; sam widok panelu tego nie robi.
Dla głosu ustaw w pliku TOML `domain = "asr"`, `"tts"` lub `"voice"`
(domyślnie obie domeny), ewentualnie `domains = ["tts"]`.
`asr_model_path` wskazuje istniejący plik Whisper `.pt`; bez tej opcji sprawdzany
jest lokalny cache `~/.cache/whisper/<asr_model>.pt`.
`tts_model_path` wskazuje model Piper `.onnx` z plikiem `.onnx.json`.
Wybrany model jest weryfikowany i ładowany do pamięci. TTS nie importuje Whisper,
ASR nie importuje Piper. Brak modułu, modelu lub błąd wykonania oznacza niedostępność
tej domeny. Druga działająca domena może pozostać dostępna; `initialized` nie oznacza,
że obie są gotowe. API i heartbeat pokazują osobne `capabilities.asr/tts`.

Wizja wymaga istniejącego `detection_model_path` (lub lokalnego pliku
`<detection_model>.pt`); YOLO nie pobiera wag automatycznie. Opcjonalne MediaPipe
jest ładowane tylko przy `enable_tracking = true`. Tekst sprawdza wybrany lokalny
model Ollama przez odczyt metadanych; nie pobiera go. Prawdziwy NLU pozostaje
niedostępny, dopóki nie ma implementacji. Awaria rzeczywistego backendu nie tworzy
udanej odpowiedzi mock. Demo wymaga jawnego `use_mock = true` lub wyboru
`*_MODEL=mock`, ma źródło `demo` i metadane symulacji. Nie instalujemy dodatkowych
paczek ani modeli przy starcie panelu lub w testach. Włączaj tylko potrzebny runtime
we własnym środowisku zgodnie z polityką zależności; testy WSL korzystają z atrap.

Pasywna synchronizacja danych nie gasi LCD ani nie zwalnia zasobów. Te zmiany
wymagają osobnego działania operatora; orientacja i start ekranu pozostają zachowane.

Offload wizji zachowuje oryginalne `observed_at` kamery (lub jej starszy timestamp/ts, gdy pole nie występuje). Wynik kolejki i publikacja nie odmładzają pomiaru. Nieznany czas daje `data_ready:false`; symulowane wyniki pozostają diagnostyką i nie trafiają do tematów enhanced/tracking robota. ROI oraz przybliżenia rozmiaru bbox nie potwierdzają odległości ani kalibracji nawigacji.

Wiek obserwacji mapy, pozycji i trasy jest oddzielny od przydatności pomiaru. Jawne stale/offline/error lub brak gotowych danych przygaszają widok także przy świeżym czasie; nieznany pakiet i pusty snapshot wygaszają dawną geometrię. Zmiana jakości przy tym samym czasie odświeża rysunek. Świeży stan zadania FAILED/IDLE pozostaje widoczny, gdy czujniki nie są gotowe.
## Bufor kamery i odległość z obrazu

`/camera/last` zachowuje źródłowy czas `Last-Modified`. Brak lub niepoprawny czas pozostaje nieznany: GET/HEAD pomijają `Last-Modified` i raportują `X-Camera-Observation-Valid: false`; czas odbioru jest osobną diagnostyką bufora. Znany czas źródła zachowujemy także bez potwierdzonej synchronizacji zegarów; nie dowodzi on świeżości. Początkowy obraz zastępczy nie ma czasu pomiaru. Heurystyka odległości z obszaru ramki jest jawnie niezweryfikowana (`range_verified: false`, `distance_source: bbox_area_heuristic`, `distance_unit: unverified`) i nie stanowi skalibrowanego pomiaru dla nawigacji.


### Prezentacja i pochodzenie danych

Karty providerów odczytują rzeczywiste /providers/capabilities, także osobny
provider tekstu i gotowość domen ASR/TTS. Sama inicjalizacja nie oznacza gotowości.
Buforowane health po błędzie źródła pozostaje unknown. System zachowuje rozwinięcie
danych źródłowych, autostartu i logów według hosta i jednostki; logi pobiera wyłącznie
na żądanie. Historia nawigacji jest widoczna osobno od ACK ruchu. Błąd proxy unieważnia
geometrię bez odmładzania czasu źródłowego. Jawnie nieznany czas obserwacji pozostaje
nieznany po odświeżeniu wieku. Katalog demo stosuje kanoniczne s9_navigation;
pochodzenie klatki demonstracyjnej przetrwa rzeczywisty provider i blokuje publikację
na fizyczne tematy wizji/śledzenia.

Konfiguracja przy DISARMED wymaga skończonego, świeżego server_time Pi.
Czas PC nie zastępuje brakującego czasu Pi. Awaria niedomyślnego backendu tekstowego
nie zmienia gotowości wybranego backendu domyślnego.

CI włącza lekkie, izolowane fixture API przez RIDER_ENABLE_API_TESTS=1 w zadaniu
jednostkowym. Flagi integracji Redis/providerów pozostają wyłączone; nie są potrzebne
dodatkowe modele ani pakiety. Wspólne regresje interfejsu uruchamia polecenie:
node --experimental-vm-modules --test tests/operator_panel.test.mjs tests/operator_panel_shared_review.test.mjs.

## Cykl życia przeglądarki E2E

E2E uruchamia własny lokalny serwer demo i zamyka kontekst przeglądarki przed
przeglądarką i sterownikiem Playwright, także po błędzie. Zachowujemy standardowe
procesy renderowania Chromium: wymuszony single-process potrafi wywołać awarię
przy zamykaniu aktywnych widoków operatora i zużyć 30-sekundowy awaryjny czas
zamknięcia sterownika. CI pokazuje czasy setup/call/teardown i jawnie ładuje plugin
z limitem 60 sekund na test; budżet całego zadania E2E pozostaje 10 minut.
Odtworzenie używa istniejącego venv i cache przeglądarki w WSL, bez instalacji
pakietów i bez łączenia ze sprzętem:

```sh
CI=true PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/e2e \
  -p pytest_asyncio.plugin -p pytest_timeout --timeout=60 --timeout-method=thread --durations=30
```
