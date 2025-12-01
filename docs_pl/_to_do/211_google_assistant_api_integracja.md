# 211 – Integracja Google Assistant API w Rider-PC

## Cel
Zaprojektować i wdrożyć prosty panel webowy sterujący urządzeniami przez Google Assistant API. Panel ma używać zdefiniowanej ręcznie listy urządzeń (mapy nazw), wysyłać odpowiednie komendy tekstowe/głosowe i optymistycznie aktualizować stan.

## Zakres
- Rider-PC (FastAPI + UI web) — obsługa logowania, wysyłania komend, podglądu historii.
- Statyczna konfiguracja urządzeń po stronie PC (np. `config/google_assistant_devices.toml`).
- Brak Rider-Pi (komunikacja bezpośrednio z Assistantem).
- Dokumentacja i narzędzia CLI do diagnozy (np. test komendy, test audio).

## Założenia
1. Korzystamy z Google Assistant SDK (gRPC) i mechanizmu OAuth 2.0 (implicit/installed app).
2. Komendy mają być wysyłane zarówno w trybie głosowym, jak i tekstowym (np. wpisanie „Wyłącz wszystkie światła”).
3. Użytkownik może wskazać profil (konto Google), które obsługuje jego dom.
4. Tokeny przechowujemy lokalnie (`config/local/google_assistant_tokens.json`, gitignore).
5. Zachowujemy możliwość fallbacku do SDM dla urządzeń wspieranych, ale panel Assistant będzie działał bez realtime feedbacku.

## Plan działania
1. **Analiza SDK i ograniczeń Google**
   - Sprawdzić aktualne warunki korzystania z Assistant SDK (rejestracja projektu, ograniczenia platformowe, limity).
   - Zebrać wymagane zależności (grpcio, google-assistant-sdk, porównanie z istniejącymi libs).
   - Określić, jakie urządzenia/akcje można wspierać (np. `Converse` API vs. `Device Request`).

2. **Konfiguracja Google Cloud / Actions**
   - Instrukcja krok po kroku: utworzenie projektu w [Actions on Google](https://console.actions.google.com/), włączenie Google Assistant API, skonfigurowanie OAuth.
   - Uzyskanie `client_id`, `client_secret`, `project_id`.
   - Przygotowanie pliku `.env` / `config/google_assistant.toml` z wymaganymi polami.

3. **Statyczna mapa urządzeń (`config/google_assistant_devices.toml`)**
   - Każdy wpis zawiera `id`, `label`, `assistant_name`, `room`, `category`, `on_command`, `off_command` oraz opcjonalne pola (`brightness_template`, `dock_command`).
   - Dodatkowe komendy są powiązane z kategorią urządzenia: np. pole `dock_command` występuje dla odkurzaczy (`category = vacuum`), a inne typy mogą mieć własne opcjonalne komendy (np. `pause_command` dla urządzeń multimedialnych). Warto sprawdzić, które kategorie obsługują konkretne pola w pliku konfiguracyjnym.
   - W repo istnieje startowa lista Twoich urządzeń z Google Home (Pokój Lights, oczyszczacz Xiaomi, Monitoring, Oczyszczacz, odkurzacz Xiaomi H40, scena Pokój Nest) — gotowa do modyfikacji.
   - Ten plik jest źródłem prawdy dla panelu; nie próbujemy pobierać listy urządzeń przez API Google.

4. **Moduł usługowy `pc_client/services/google_assistant.py`**
   - Obsługa OAuth (InstalledAppFlow) lub dedykowanego narzędzia `google-auth-oauthlib`.
   - Wymiana tokenu na access token i odświeżanie.
   - Wczytywanie i walidacja `config/google_assistant_devices.toml`, cache w pamięci + hot-reload przy zmianach.
   - Metody:
     - `list_devices()` – zwraca katalog z aliasami, nazwą wyświetlaną i komendami ON/OFF.
     - `send_command(device_id, action)` – buduje tekst (np. „Włącz Pokój Lights”) i wysyła do Assistant API.
     - `send_custom_text(text)` – umożliwia wpisanie dowolnej komendy.
   - Obsługa `gRPC` `converse` API, odbiór odpowiedzi tekstowej/audio.

5. **API FastAPI i UI**
   - Endpointy: `/api/assistant/devices` (lista statyczna), `/api/assistant/command` (ON/OFF/custom), `/api/assistant/auth/*`.
   - UI: kafelki urządzeń (nazwa, status lokalny, przyciski ON/OFF, opcjonalny input tekstowy + historia).
   - Lokalne statusy aktualizujemy optymistycznie po wysłaniu komendy (np. ON = zielony, OFF = szary).
   - Rejestrowanie historii wysłanych komend do `logs/google_assistant/commands.log`.

6. **Integracja głosowa (opcjonalna w późniejszym etapie)**
   - MediaRecorder w przeglądarce → endpoint `/api/assistant/voice` → wysyłka audio do Assistant API.
   - Odtwarzanie odpowiedzi audio w UI (jeśli strumień zwraca audio). Etap 1 może ograniczyć się do komend tekstowych.

7. **Testy**
   - Jednostkowe: mock gRPC klienta, testy odświeżania tokenów, obsługa błędów.
   - Integracyjne: tryb testowy z lokalnym stubem.
   - E2E/manual: checklista w docs (`send text command`, `voice command`, `token refresh`).

8. **Dokumentacja**
   - Nowy rozdział `docs_pl/google-assistant-integration.md` (prerekwizyty, konfiguracja, ograniczenia).
   - Uzupełnienie `.env.example` oraz `README`.
   - Porównanie: kiedy używać Assistant API vs. SDM.

9. **Migracja / Rollout**
   - Flagi konfiguracyjne: `GOOGLE_ASSISTANT_ENABLED`, `GOOGLE_ASSISTANT_TEST_MODE`.
   - Instrukcja wdrożeniowa (backup, migracja tokenów, restart usług).
   - Monitoring (metryki /health, logi).

## Ryzyka / pytania
- Google sukcesywnie ogranicza Assistant SDK; trzeba potwierdzić dostępność i zasady (np. tylko urządzenia dedykowane). Czy nasze use-case’y spełniają warunki?
- Wymagania sprzętowe (nagrywanie audio, TLS). Czy Rider-PC ma mikrofon/głośnik pod ręką?
- Licencje i regulaminy – czy komercyjne użycie jest dozwolone?

## Definition of Done
1. CLI/serwis potrafi zalogować użytkownika i zapisać token.
2. Endpoint `/api/assistant/command` przyjmuje tekst i zwraca wynik z Asystenta.
3. UI pozwala wysłać tekstową komendę i pokazuje odpowiedź.
4. Testy jednostkowe + manualna checklista przechodzą.
5. Dokumentacja konfiguracji i wdrożenia jest kompletna w `docs_pl`.
6. Plik `.env.example` został zaktualizowany o nowe klucze konfiguracyjne Google Assistant z komentarzami.
