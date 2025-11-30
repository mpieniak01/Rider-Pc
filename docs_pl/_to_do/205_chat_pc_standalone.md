# 205 — Chat PC (Standalone UI + logika lokalna)

## Kontekst
- Aktualny ekran `web/chat.html` i endpoint `/api/chat/send` zostały zaprojektowane jako klon Rider-PI – cała logika czatu miesza tryb proxy (Rider-PI) z lokalnym `TextProvider`.
- W wizji (`wizja_domen_Rider-PC.md`) zakładamy autonomię Rider-PC, ale brak osobnej ścieżki UX/API powoduje, że przy wyłączonym Rider-Pi czat nie działa i użytkownik traci dostęp do lokalnych modeli (Ollama/mock).
- Chcemy zacząć od stworzenia jednoznacznej historii produktowej: „Chat PC” jako ekran i zestaw API działający w 100% lokalnie, niezależnie od Rider-Pi.

## Stos techniczny – stan obecny
- **Backend FastAPI** (`pc_client/api/server.py`) – serwuje API + pliki statyczne, lifecycle w `pc_client/api/lifecycle.py` startuje adaptery/providery.
- **Chat API** (`pc_client/api/routers/chat_router.py`) – jeśli `TextProvider` aktywny, obsługuje zapytanie lokalnie; w innym razie proxy przez `RestAdapter` (`pc_client/adapters/rest_adapter.py`).
- **TextProvider** (`pc_client/providers/text_provider.py`) – głównie Ollama (`ollama.chat`), konfiguracja w `config/providers.toml` + `Settings`.
- **Voice/Vision** (`pc_client/providers/voice_provider.py`, `vision_provider.py`) – analogiczne podejście, health przez `voice_router.py`, `provider_router.py`.
- **ModelManager** (`pc_client/core/model_manager.py`) – skanuje `data/models/`, odpytuje Ollamę (`scan_ollama_models`) i zasila `/api/models/*` (`pc_client/api/routers/model_router.py`).
- **Front-end** – pliki w `web/` wykorzystujące `web/assets/dashboard-common.css`; dzisiejszy czat to `web/chat.html`, inwentarz modeli `web/models.html`.
- **Testy** – pytest (`tests/`), Playwright (`tests/e2e/test_web_screens.py`), narzędzia CSS (`scripts/css_audit.py`, `scripts/css_coverage.py`).
- **Run dev** – `python -m pc_client.main` (mock), z `ENABLE_TEXT_OFFLOAD=true` + działającą Ollamą dostajemy lokalny chat.

## Zakres (planowany pod PR)

### 1. Frontend (web)
- [x] Dodać nowy widok `web/chat-pc.html` (lub przebudować istniejący) z przełącznikiem „Źródło odpowiedzi: PC / Rider-Pi”.
- [x] Wyświetlać status modeli lokalnych (telemetria `TextProvider`, ikony health) + komunikat gdy Rider-Pi jest odłączony.
- [x] Pokazywać nazwę/wersję aktualnego modelu tekstowego oraz wysyłać powiadomienia przy przełączeniu instancji (żeby użytkownik widział zmianę kontekstu).
- [x] Uporządkować lokalne storage historii, żeby tryb PC nie mieszał wiadomości z trybem proxy.
- [x] Zapewnić komplet kanałów przetwarzania jak w obecnym czacie: wejście mowa→tekst (ASR), odpowiedź tekst→tekst, wyjście tekst→mowa (TTS) z przełącznikiem TTS i listą providerów lokalnych.

### 2. Backend FastAPI (Rider-PC)
- [x] Rozszerzyć router `chat_router.py`: jawny parametr `mode=pc|proxy`, walidacja i komunikaty błędów (np. 503 gdy brak providerów lokalnych).
- [x] Zapewnić health endpoint (np. `/api/providers/text`) zwracający `initialized`, model, engine — do wykorzystania przez UI.
- [x] Ujednolicić kanały przetwarzania: dodać/lokalizować endpointy dla ASR (`/api/voice/asr`), TTS (`/api/voice/tts`) i tekst→tekst tak, by Chat PC mógł działać w 100% lokalnie.
- [x] jeśli Rider-Pi jest offline, RestAdapter powinien zwrócić błąd, a logika biznesowa w endpoint'cie API powinna ten błąd obsłużyć. 

### 3. Inicjalizacja i konfiguracja
- [x] W `Settings` ustawić sensowne defaulty (`ENABLE_PROVIDERS=true`, `ENABLE_TEXT_OFFLOAD=true` w trybie dev/standalone).
- [x] Dodać osobny plik konfiguracyjny `config/providers_text_local.toml` (model, temperatura, host) + opis w `KONFIGURACJA_MODELI_AI.md`.
- [x] Rozszerzyć lifecycle o logi kiedy provider lokalny się nie startuje + proponowane akcje (np. brak Ollama → fallback mock + ostrzeżenie do UI).
- [x] Zaprojektować mechanizm diagnostyki: logi startu/ładowania modeli (Ollama, Piper), endpointy health (`/api/providers/text/status`, `/api/providers/voice/status`) i komunikaty błędów zrozumiałe dla UI (np. „Ollama offline”, „brak modelu głosowego”).

### 4. Telemetria/testy/dokumentacja
- [x] Testy API (pytest) dla nowych ścieżek: lokalny sukces, brak promptu, brak providerów, tryb proxy.
- [x] Scenariusz manualny „Rider-Pi offline" w `docs_pl/SZYBKI_START.md` (jak uruchomić Chat PC standalone).
- [x] Zaktualizować `wizja_domen_Rider-PC.md` o rozdział „Chat PC (Standalone)" po implementacji.
- [ ] Wbudować funkcję benchmarkową (UI + API) do przełączania modeli, wysyłania próbek testowych, mierzenia latencji i oceny odpowiedzi; wyniki zapisujemy w telemetry/logach.

### 5. Integracja z modułem Project/PR editor
Integracja Chat PC z edytorem projektów i PR to kluczowa funkcjonalność łącząca możliwości lokalnych modeli AI z przepływem pracy nad kodem i dokumentacją.

**Cel**: umożliwić AI (przez Chat PC) automatyczne generowanie i ulepszanie treści PR, komentarzy oraz dokumentacji na podstawie szkiców, bazy wiedzy i kontekstu projektu.

**Zakres zadań**:
- [x] Zaprojektować interfejs komunikacji między Chat PC a modułem Project/PR editor (API, eventy, współdzielone dane).
- [x] Dodać endpoint `/api/chat/pc/generate-pr-content` przyjmujący szkic PR i kontekst (powiązane issues, historia zmian, baza wiedzy).
- [x] Rozbudować UI Chat PC o sekcję „Asystent PR" z możliwością:
  - [x] Wczytania szkicu PR (tekst lub link do issue/draftu).
  - [ ] Podglądu sugerowanych zmian przed zatwierdzeniem.
  - [ ] Wyboru bazy wiedzy/dokumentów referencyjnych do kontekstu.
- [ ] Zaimplementować logikę łączenia szkiców z bazą wiedzy (RAG lub prompt engineering) w `TextProvider`.
- [x] Dodać testy jednostkowe i integracyjne dla nowych endpointów i logiki generowania treści PR.
- [x] Opisać przepływ pracy „AI-assisted PR editing" w dokumentacji (`docs_pl/SZYBKI_START.md` lub dedykowany plik).

## Wytyczne UI / JS / CSS
- Szablon: korzystamy z `web/templates/dashboard_base.html` (strukturę `.layout-*`) i komponentów opisanych w `docs_pl/styleguide.md` + `web/assets/dashboard-common.css`.
- CSS: nowy arkusz `web/assets/pages/chat-pc.css` zawiera tylko unikalne reguły; wspólne elementy (`c-card`, `c-status-msg`, `l-grid`, `installed-models-table`) reużywamy – bez inline-styles i duplikacji.
- JS: modułowa struktura jak w `web/chat.html`/`web/models.html` – IIFE, selektory na starcie, helpery `callChat`/`renderStatus`, brak zbędnych globali.
- Testy wizualne: pamiętamy o trybie `?audit=1` (obsługa placeholderów), żeby `scripts/css_audit.py` i Playwright mogły robić screenshoty.

## Polityka testowa
- **Testy jednostkowe**: rozszerzamy `tests/test_model_router.py` i dodajemy `tests/test_chat_router.py` (lokalny sukces, brak promptu, brak providera, tryb proxy).
- **Testy integracyjne/E2E**: Playwright obejmuje `/web/chat-pc.html` i zaktualizowane `models.html` (sekcje PC/Pi + status LLM). Smoke test w `tests/e2e/test_web_screens.py`.
- **Testy manualne**: checklisty w `docs_pl/SZYBKI_START.md` uzupełnione o scenariusz „Rider-Pi offline” i „przełączenie modelu lokalny ↔ chmurowy”.
- **Testy regresji CSS**: nowe strony dopisujemy do `scripts/css_audit.py` i `scripts/css_coverage.py`.
- **Benchmark modeli**: funkcja benchmarkowa ma swoje testy jednostkowe/integracyjne + scenariusz e2e klikający benchmark i sprawdzający logowanie metryk.
- **Minimalizacja kosztu testów modeli**: scenariusze dotykające realnych modeli uruchamiamy tylko na najmniejszej konfiguracji (np. `llama3`); pozostałe modele mockujemy.
- **Polityka udoskonalania modeli**: przygotowujemy prompt „systemowy” i bazę wiedzy (notatki, dokumenty) – benchmark powinien pozwalać wybrać prompt/kontekst, a logi muszą zapisywać, z czym test był wykonywany.

## Plan realizacji (kolejność lead PR)
0. **Audyt obecnego stosu modeli** – przejrzeć `pc_client/core/model_manager.py`, `pc_client/api/routers/model_router.py`, `web/models.html` (JS) i `web/chat.html`, żeby uniknąć kolejnego spaghetti przed refaktoryzacją.
1. **Backend foundation** – ustawienia + health endpoint + nowe ścieżki `/api/chat/pc/send`.
2. **UI** – nowy ekran `chat-pc.html` + aktualizacja `models.html` (sekcje PC/Pi, status wspólnego LLM, przełączniki) korzystające z endpointów z pkt 1.
3. **Testy + dokumentacja** – pytesty, manual checklist, update docs.
4. **Integracja z Project/PR editor** – implementacja API i UI dla asystenta PR zgodnie z sekcją 5 zakresu.
5. **Iteracja wizji** – po zamknięciu PR dopisać rozdział w wizji i przenieść dokument do `_done`.

## Definition of Done
- Lokalny czat działa przy wyłączonym Rider-Pi (manualny test: `python -m pc_client.main`).
- UI potwierdza aktywnego providera lokalnego i jasno komunikuje przełączenie na Rider-Pi.
- Nowy plan testów i konfiguracji opisany w dokumentacji; dokument można przenieść do `_done`.

## Ryzyka / otwarte pytania
- Ze względu na rozmiar modeli utrzymujemy pojedynczą instancję LLM współdzieloną między Rider-Pi i Rider-PC.
- W pamięci może być aktywny tylko jeden model – przełączanie oznacza przeładowanie i chwilową niedostępność (UX musi to pokazać).
- Ostatni klient „narzuca” model pozostałym; potrzebne komunikaty takeover i reset kontekstu.
- Czy chcemy już teraz wspierać wiele modeli (różne instancje Ollama) – na razie zakładamy pojedynczy provider.
- Zachowujemy obecny stos technologiczny (FastAPI + Ollama + Piper/Whisper + dashboard HTML/CSS/JS); każdą nową bibliotekę/API opisujemy w tym dokumencie przed wdrożeniem.

## Mapowanie faz rozwoju modeli tekstowych
- **Faza I – lokalne modele (ten plan)**: docelowy tryb działania – uruchamiamy `TextProvider`, nowy ekran `chat-pc.html` i wspólną instancję LLM ładowaną lokalnie.
- **Faza II – modele Gemini/OpenAI (opcja B)**: kanał komunikacji ze światem zewnętrznym, gdy chcemy porównać wyniki lub świadomie użyć chmury. Kod Rider-Pi obsługuje Gemini/OpenAI (`pc_client/api/routers/voice_router.py:107-137` – placeholdery w Rider-PC). Jeśli będzie potrzeba, dobudujemy mostek z Chat PC do istniejących usług chmurowych, ale nie jest to priorytet tej rundy.

## Proponowany opis PR
„Dodajemy plan i wizję Chat PC (Standalone) dla Rider-PC. Dokument `docs_pl/_to_do/205_chat_pc_standalone.md` zawiera zakres backendu, UI, telemetrii i polityki testowej (w tym benchmark modeli i integrację z Project/PR editor). `docs_pl/_to_do/wizja_domen_Rider-PC.md` został uzupełniony o sekcję "Nowe inicjatywy (2025)" w domenie Modele Lokalnie – opisuje Chat PC Standalone, wspólną instancję LLM i benchmark. Ten PR dostarcza dokumentację planu; szczegóły implementacyjne są w powyższych plikach, brak zmian w kodzie.”
