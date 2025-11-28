# Zadanie #160: Zarządzanie Modelami AI (Model Registry Dashboard)

**Status:** ✅ Zakończone  
**Autor:** Copilot

---

## Analiza AS-IS

### Obecny stan

1. **Konfiguracja modeli** jest rozproszona w pliku `config/providers.toml`:
   - `[vision]` - konfiguracja modelu YOLO (`detection_model = "yolov8n"`)
   - `[voice]` - konfiguracja ASR/TTS (`asr_model`, `tts_model`)
   - `[text]` - konfiguracja LLM (`model = "llama3.2:1b"`)

2. **Brak widoczności** dla użytkownika:
   - Użytkownik nie widzi jakie modele są zainstalowane lokalnie
   - Brak informacji o aktywnych modelach w UI
   - Zmiana modeli wymaga edycji plików TOML i restartu

3. **Providerzy** zdefiniowani w `pc_client/providers/`:
   - `VisionProvider` - detekcja obiektów (YOLO)
   - `VoiceProvider` - ASR/TTS (Whisper/Piper)
   - `TextProvider` - LLM (Ollama/OpenAI)

### Zidentyfikowane braki

- Brak centralnego rejestru modeli
- Brak API do pobierania listy zainstalowanych modeli
- Brak UI do zarządzania modelami
- Brak możliwości przełączania modeli bez restartu

---

## Plan TO-BE

### 1. Backend: Model Manager (`pc_client/core/model_manager.py`)

Nowa klasa `ModelManager` odpowiedzialna za:
- Skanowanie katalogu `data/models/` w poszukiwaniu plików `.pt`, `.onnx`, `.tflite`
- Odczyt aktywnej konfiguracji z `config/providers.toml`
- Opcjonalne odpytywanie Ollama API o dostępne modele
- Metody do bezpiecznego zapisu konfiguracji

### 2. Backend: API Endpoints (`pc_client/api/routers/model_router.py`)

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/models/installed` | GET | Lista wykrytych modeli lokalnych |
| `/api/models/active` | GET | Aktualna konfiguracja aktywnych modeli |
| `/api/models/bind` | POST | Przypisanie modelu do slotu |

### 3. Frontend: Panel Modeli (`web/models.html`)

Widok podzielony na kategorie:
- **👁️ Wizja (Vision)** - YOLO, MediaPipe
- **🗣️ Mowa (Audio)** - Whisper (ASR), Piper (TTS)
- **💬 Tekst (LLM)** - Ollama, OpenAI, Gemini

---

## Kryteria akceptacji

- [x] Dokumentacja analizy AS-IS w `docs_pl/_to_do/`
- [x] W menu głównym widoczna pozycja "Modele"
- [x] Panel wyświetla aktualnie używane modele
- [x] Panel listuje pliki modeli z `data/models/`
- [x] API endpoint `/api/models/installed` działa poprawnie
- [x] API endpoint `/api/models/active` działa poprawnie
