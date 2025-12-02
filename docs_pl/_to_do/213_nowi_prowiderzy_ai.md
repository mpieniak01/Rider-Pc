# 213 – Integracja nowych providerów AI (Gemini + ChatGPT)

## Cel
Zapewnić Rider-PC dostęp do dwóch niezależnych providerów modeli językowych:

1. **Gemini API (najnowsze wydanie)** – wykorzystywane do zadań konwersacyjnych, RAG oraz generowania PR.
   - **Wspierane modele**: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-1.5-pro-vision` (multimodalny). Lista modeli będzie rozszerzana zgodnie z dokumentacją Google.
2. **OpenAI ChatGPT API** – fallback lub alternatywa dla lokalnych modeli oraz Gemini, z obsługą funkcji reasoning/tool-call.

Docelowo UI (Chat PC, PR Assistant, Benchmark) ma umożliwiać wybór źródła odpowiedzi i raportować koszt/czas.

### Kryteria sukcesu
- Użytkownik może zdefiniować profil „pipeline’u” (ASR/LLM/TTS) łączący lokalny Rider-PC, Gemini i ChatGPT bez restartu usług.
- Chat PC/PR Assistant/Benchmark pokazują skąd pochodzi odpowiedź, a telemetria raportuje koszt/czas per provider.
- MCP działa identycznie niezależnie od wybranego backendu.
- Nie pojawia się dodatkowa infrastruktura – wszystko w ramach istniejącego serwera Rider-PC.

## Status
> **Uwaga:** Poniższe statusy będą aktualizowane w trakcie realizacji zadania PR #213.

- [ ] Spec integracji Gemini (autoryzacja, modele, limity).
- [ ] Spec integracji ChatGPT (opłaty, modele reasoning).
- [ ] Wymagania UI (przełącznik providerów w Chat PC / Asystent PR / Benchmark).
- [ ] Plan testów i tryb mock.

## Zakres (szablon do rozbudowy)
1. **Warstwa konfiguracyjna**
   - Nowe sekcje w `config/providers.toml` oraz `.env.example`:
     - `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_ENDPOINT`.
     - `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`.
   - Przełącznik `TEXT_PROVIDER_BACKENDS = ["local", "gemini", "chatgpt"]`.

   > **Uwaga dot. nazewnictwa providerów AI:**
   > - W plikach konfiguracyjnych (`.env`, `providers.toml`) oraz identyfikatorach kodowych używamy wyłącznie małych liter: `"local"`, `"gemini"`, `"chatgpt"`.
   > - W UI oraz dokumentacji wyświetlamy nazwy providerów w formacie CamelCase: `"Gemini"`, `"ChatGPT"`, `"Local"`.
   > - Dzięki temu unikamy niejednoznaczności i błędów przy mapowaniu wartości między warstwami systemu.
2. **Providerzy**
   - `GeminiProvider` – klasa w `pc_client/providers` z obsługą:
     - OAuth/API key.
     - modeli tekstowych + audio (jeśli dostępne).
     - kosztów i throttlingu.
   - `ChatGPTProvider` – analogiczny provider z obsługą funkcji reasoning/tool-call.
   - Adapter w `TextProvider` umożliwiający wybór backendu per-zadanie (`mode: gemini`).
3. **UI / API**
   - Zakładka **Projekt → Modele AI / Ustawienia AI** – główne miejsce zarządzania konfiguracją backendów. Administrator wybiera domyślne profile (np. lokalny, hybrydowy Gemini, hybrydowy ChatGPT) oraz przypisuje pipeline (ASR, LLM, TTS). **Uwaga: Klucze API są zarządzane wyłącznie przez pliki `.env` lub `ai_credentials.toml` – UI nie umożliwia ich wprowadzania ani zapisywania.**
   - Chat PC: tylko odczytuje bieżący profil; w UI wyświetla „Źródło: PC lokalny / Gemini / ChatGPT” z ewentualnym ostrzeżeniem (brak klucza, quota). Nie przełącza globalnej konfiguracji.
   - PR Assistant i Benchmark: również odczytują profil i jedynie w trybie ręcznym pozwalają wybrać inny backend dla pojedynczej operacji (bez zapisu globalnego).
   - `/api/models/active` i `/api/providers/text` – dodanie informacji o zewnętrznych providerach.
4. **Telemetria i koszty**
   - Metryki per-provider (`tasks_processed_total{provider="gemini"}`).
   - Logowanie kosztów w `logs/providers-costs.log`.
5. **Tryb offline/mock**
   - Symulator odpowiedzi dla Gemini/ChatGPT, aby UI można było testować bez kluczy.
   - Dokumentacja jak aktywować mock (`use_mock = true`).
6. **Bezpieczeństwo**
   - Przechowywanie kluczy w `.env` (zalecane) oraz wsparcie dla pliku `~/.config/rider-pc/ai_credentials.toml`.
     - **Format pliku `ai_credentials.toml`:** plik w formacie TOML, zawierający klucze w postaci:
       ```toml
       GEMINI_API_KEY = "twój_klucz_gemini"
       OPENAI_API_KEY = "twój_klucz_openai"
       ```
     - **Uprawnienia pliku:** plik musi mieć uprawnienia 0600 (tylko odczyt/zapis dla właściciela). Zalecane polecenie:
       ```bash
       chmod 600 ~/.config/rider-pc/ai_credentials.toml
       ```
     - **Kolejność ładowania kluczy:** domyślnie najpierw ładowane są wartości z `.env`, a następnie (jeśli nie znaleziono klucza) z `ai_credentials.toml`. Klucz z `.env` ma wyższy priorytet.
   - Komunikaty w UI gdy klucz wygasł lub quota wyczerpana.

## Integracje API – procesy i wymagania (dla Copilot/GitHub)
Aby agent kodowania (np. GitHub Copilot) mógł automatycznie rozszerzać Rider-PC, dokument musi jednoznacznie definiować każdy przepływ API. Poniżej opis techniczny integracji:

### Gemini
1. **Autoryzacja**
   - `GEMINI_API_KEY` przechowywany w `.env`.
   - Klucz API przekazujemy jako parametr query string: `?key=<API_KEY>`. Nie używamy nagłówka `x-goog-api-key` dla standardowego klucza API.
   - Nagłówek `Authorization: Bearer <token>` stosujemy wyłącznie w trybie OAuth2 (Service Account). Opcjonalnie można dodać nagłówek `x-goog-api-client` z metadanymi klienta.
   - Opcjonalnie tryb OAuth (Service Account) – generujemy JWT oraz token dostępu.
2. **Wysyłanie żądań**
   - Tekst: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
   - Audio/ASR/TTS: te same endpointy z odpowiednimi `mime_type`.
   - Payload:
     ```json
     {
       "systemInstruction": {"parts": [{"text": "<prompt systemowy + MCP>"}]},
       "contents": [
         {"role": "user", "parts": [{"text": "<prompt użytkownika>"}]}
       ],
       "generationConfig": {"temperature": 0.7, "topP": 0.95},
       "tools": [
         {
           "functionDeclarations": [
             {"name": "system.get_time", "description": "...", "parameters": {...}}
           ]
         }
       ]
     }
     ```
   > **Uwaga:** W Gemini API rola `"system"` nie istnieje w `contents`. Instrukcje systemowe przekazujemy przez osobne pole `systemInstruction`.
3. **Obsługa odpowiedzi**
   - Parsujemy `candidates[].content.parts`. Jeśli część ma `functionCall`, wykonujemy MCP i dodajemy `functionResponse`.
   - Audio (`inline_data`) zapisujemy po `base64` do pliku `.wav`.
   - Błędy mapujemy na `TaskStatus.FAILED` wraz z `error_code`, `retry_after`.
   - **Obsługa rate limiting i quota:**
     - HTTP 429 (Too Many Requests): odczytujemy nagłówek `Retry-After` i stosujemy exponential backoff.
     - Quota wyczerpana (kod 429 lub 503): wyświetlamy komunikat w UI, logujemy do `logs/providers-errors.log`.
     - Mechanizm retry: domyślnie 3 próby z opóźnieniem 1s, 2s, 4s (exponential backoff).

### OpenAI ChatGPT
1. **Autoryzacja**
   - `OPENAI_API_KEY` w `.env`.
   - Nagłówki: `Authorization: Bearer <key>`.
2. **Wysyłanie żądań**
   - Tekst: `POST https://api.openai.com/v1/chat/completions`.
   - Audio: `POST https://api.openai.com/v1/audio/transcriptions` lub `/speech`.
   - Payload:
     ```json
     {
       "model": "gpt-4o",
       "messages": [
         {"role": "system", "content": "<system prompt + MCP>"},
         {"role": "user", "content": "<prompt>"}
       ],
       "temperature": 0.7,
       "tools": [
         {
           "type": "function",
           "function": {"name": "system.get_time", "description": "...", "parameters": {...}}
         }
       ]
     }
     ```
3. **Obsługa odpowiedzi**
   - `choices[].message.tool_calls` → wykonujemy MCP i odpowiadamy jako `role: tool`.
   - Modele reasoning (`o1-preview`/`o1-mini`) automatycznie stosują rozumowanie; wymagają dłuższego `timeout_seconds` i mają ograniczenia w obsłudze narzędzi. Model `o3` został zapowiedziany, ale nie jest jeszcze dostępny w API – wsparcie zostanie dodane po jego udostępnieniu.
   - Raportujemy koszty (`usage.prompt_tokens`, `usage.completion_tokens`).
   - **Obsługa rate limiting i quota:**
     - HTTP 429 (Too Many Requests): odczytujemy nagłówek `Retry-After` i stosujemy exponential backoff.
     - Quota wyczerpana: wyświetlamy komunikat w UI, logujemy do `logs/providers-errors.log`.
     - Mechanizm retry: domyślnie 3 próby z opóźnieniem 1s, 2s, 4s (exponential backoff).

### Unified API Layer
- Interfejs `ExternalLLMProvider` z metodami `generate_text`, `transcribe_audio`, `synthesize_speech`.
- Każdy provider implementuje `prepare_request`, `send_request`, `parse_response`.
- Telemetria: `tasks_processed_total{provider="gemini"}` itd. + osobny log kosztów (`logs/providers-costs.log`).

## Wytyczne implementacyjne (skrót)
1. **Brak nowych serwerów** – wszystko osadzamy w istniejącym Rider-PC (FastAPI, UI, CSS). Providerzy Gemini/ChatGPT = nowe klasy + konfiguracja, bez dodatkowych usług/systemd.
2. **UI korzysta z obecnych widoków** – przełączniki backendów trafiają do zakładki „Modele / Ustawienia AI” (`web/models.html` + `dashboard-common.css`). Chat PC pokazuje tylko aktywny profil (status-pill).
3. **Współpraca z MCP i pipeline** – rozszerzamy `voice_router`, `chat_router`, `TextProvider`, ale nie łamiemy istniejącego grafu mowa↔tekst. Każdy provider musi wspierać MCP tool-call.
4. **Autoryzacja wyłącznie z `.env` / `ai_credentials.toml`** – zero UI do wklejania kluczy.
5. **CSS/komponenty** – używamy istniejących klas (`c-card`, `c-form-group`, `c-select`, `c-pill`). Zero inline stylów.

## Ścieżki przetwarzania (mowa ↔ tekst ↔ mowa)
Chcemy traktować każdy etap pipeline’u jako niezależny provider z możliwością mieszania usług lokalnych i chmurowych:

| Etap | Rola | Domyślny provider | Alternatywy |
|------|------|-------------------|-------------|
| `voice.asr` | Mowa → tekst (wejście) | `VoiceProvider` (Whisper lokalny) | Gemini Speech API, OpenAI Realtime (transkrypcja) |
| `text.llm` | Tekst → tekst (główna odpowiedź) | `TextProvider` (Ollama) | Gemini, ChatGPT |
| `voice.tts` | Tekst → mowa (wyjście) | Piper lokalny | Gemini TTS (WaveNet), OpenAI TTS |

### Konfiguracja bazowa
- Nowa struktura w `providers.toml`:
  ```toml
  [voice]
  asr_backend = "local"    # local | gemini | chatgpt
  tts_backend = "local"    # local | gemini | chatgpt

  [text]
  llm_backend = "local"    # local | gemini | chatgpt | auto
  ```
- UI (Chat PC, PR Assistant, Benchmark, Voice panel) dostaje przełączniki:
  - `ASR źródło` (lokalne / Gemini / ChatGPT).
  - `LLM źródło` (lokalne / Gemini / ChatGPT / Auto).
  - `TTS źródło` (lokalne / Gemini / ChatGPT).
  - Możliwość zapisania profili (np. „Tryb lokalny”, „Tryb hybrydowy Gemini”, „Tryb eksperymentalny ChatGPT”).

### Dane techniczne
- `voice_router` rozszerzamy o parametry `backend` – przy wywołaniu `/api/voice/asr` i `/api/voice/tts` backend wybierany z kolejności:
  1. `payload.backend`
  2. profil użytkownika (sesja)
  3. globalna konfiguracja (`voice.asr_backend`)
- `chat_router` przekazuje w `TaskEnvelope.meta` informacje o wybranym backendzie, co pozwoli trzymać telemetrię.
- `TextProvider` pozostaje centralnym dispatcherem:
  - tryb `local` → istniejąca logika (Ollama + MCP).
  - tryb `gemini` → `GeminiProvider.generate`.
  - tryb `chatgpt` → `ChatGptProvider.generate`.
  - tryb `auto` → polityka wyboru (np. `local` → `gemini` → `chatgpt` w razie błędów).
- Pipeline mowy/stt/tts zapisujemy jako graf w `pc_client/providers/pipeline_config.py`, aby w przyszłości dołożyć np. Amazon Polly.

### Integracja z MCP
- MCP (lokalny `pc_client/mcp`) traktujemy jako wspólną warstwę narzędziową niezależnie od backendu LLM.
- Scenariusze:
  - **Lokalny LLM** – narzędzia MCP wywoływane tak jak dziś (tool-call z odpowiedzi modelu).
  - **Gemini / ChatGPT** – jeśli backend wspiera tool calling (Gemini 1.5 Pro, GPT-4o), przekazujemy definicje MCP jako „available tools”. W razie braku wsparcia interpreter zwraca do TextProvidera odpowiedni prompt („Jeśli potrzebujesz narzędzia, poproś Ridera aby wykonał `system.get_time`”).
  - **Hybrydowy tryb** – jeśli zewnętrzny model zwróci żądanie, którego nie obsłuży (np. `robot.move` z confirm), TextProvider wykonuje MCP lokalnie i injektuje wynik jako kolejną wiadomość (tak jak w trybie lokalnym).
- Wymagania:
  - serializacja JSON Schema narzędzi MCP do formatu wymaganego przez Gemini/ChatGPT (nazwa, opis, parametry).
  - logi `mcp-tools.log` oznaczają źródło (`source_backend: gemini/chatgpt/local`), żebyśmy wiedzieli, kto poprosił o narzędzie.
  - tryb mock: symulacja tool-call przy wyłączonych usługach.

## Otwarte pytania
- Czy Gemini ma być wykorzystywane również do generowania obrazów/głosu?
- Czy ChatGPT reasoning (`o1-preview`/`o1-mini`) wymagają specjalnych limitów czasu lub interakcji z MCP?
- Jak mapować funkcje tool-call Gemini/ChatGPT na nasze MCP?
- Czy potrzebujemy dedykowanego modułu rozliczającego koszty (np. per-user, per-task)?

## Kolejne kroki
1. Zbieranie pełnych wymagań API (dokumentacja Gemini i OpenAI).
2. Przygotowanie konfiguracji środowiskowej i pipeline’u testów.
3. Rozbicie na iteracje (np. najpierw Gemini, potem ChatGPT).
