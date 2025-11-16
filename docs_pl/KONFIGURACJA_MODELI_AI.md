# Przewodnik Konfiguracji Modeli AI dla Rider-PC

Ten przewodnik opisuje jak skonfigurować i używać modeli AI zintegrowanych w Fazie 4.

## Przegląd

Rider-PC wspiera trzy domeny providerów AI:
1. **Głos**: ASR (Mowa-na-Tekst) i TTS (Tekst-na-Mowę)
2. **Wizja**: Wykrywanie Obiektów i Przetwarzanie Klatek
3. **Tekst**: Generowanie Tekstu LLM i NLU

Wszyst providerzy wspierają **automatyczny fallback do trybu mock** jeśli modele są niedostępne.

---

## Szybki Start (Tryb Mock)

Dla rozwoju i testowania bez pobierania modeli:

```bash
# Nie wymaga konfiguracji! Providerzy automatycznie używają trybu mock
python -m pc_client.main
```

---

## Konfiguracja Provider Głosu

### ASR (Automatyczne Rozpoznawanie Mowy) - Whisper

**Opcja 1: Automatyczna (Zalecana)**
```bash
# Modele pobierają się automatycznie przy pierwszym użyciu
# Nie wymaga ręcznej konfiguracji
```

**Opcja 2: Wstępne Pobieranie**
```python
import whisper
whisper.load_model("base")  # Pobiera ~140MB
```

**Dostępne Modele**:
- `tiny`: 39M parametrów, ~75MB - Najszybszy, niższa dokładność
- `base`: 74M parametrów, ~140MB - **Zalecana** równowaga
- `small`: 244M parametrów, ~460MB - Lepsza dokładność
- `medium`: 769M parametrów, ~1.5GB - Wysoka dokładność
- `large`: 1550M parametrów, ~2.9GB - Najlepsza dokładność

### TTS (Tekst-na-Mowę) - Piper

**Instalacja**:
```bash
# Ubuntu/Debian
sudo apt install piper-tts

# Lub pobierz binarny z: https://github.com/rhasspy/piper
```

**Dostępne Głosy**: Zobacz [Piper Voices](https://rhasspy.github.io/piper-samples/)

---

## Konfiguracja Provider Wizji

### Wykrywanie Obiektów - YOLOv8

**Opcja 1: Automatyczna (Zalecana)**
```bash
# Modele pobierają się automatycznie przy pierwszym użyciu
# Nie wymaga ręcznej konfiguracji
```

**Opcja 2: Wstępne Pobieranie**
```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # Pobiera ~6MB
```

**Dostępne Modele**:
- `yolov8n`: 3.2M parametrów, ~6MB - **Zalecany** najszybszy
- `yolov8s`: 11.2M parametrów, ~22MB - Mały, zbalansowany
- `yolov8m`: 25.9M parametrów, ~50MB - Średnia dokładność
- `yolov8l`: 43.7M parametrów, ~84MB - Duży, wysoka dokładność
- `yolov8x`: 68.2M parametrów, ~131MB - Extra duży, najlepsza dokładność

---

## Konfiguracja Provider Tekstu

### LLM - Ollama

**Instalacja**:

1. **Zainstaluj Ollama**:
   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Lub pobierz z: https://ollama.com/download
   ```

2. **Pobierz model**:
   ```bash
   # Lekki model (Zalecany dla PC)
   ollama pull llama3.2:1b  # ~1.3GB
   
   # Lub inne modele:
   ollama pull llama3.2:3b  # ~3.4GB
   ollama pull phi3:mini    # ~2.3GB
   ollama pull mistral:7b   # ~4.1GB
   ```

3. **Uruchom serwer Ollama**:
   ```bash
   ollama serve
   # Serwer działa na http://localhost:11434
   ```

4. **Weryfikuj**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

**Dostępne Modele**:
- `llama3.2:1b`: 1B parametrów - **Zalecany** najszybszy
- `llama3.2:3b`: 3B parametrów - Lepsza jakość
- `phi3:mini`: 3.8B parametrów - Microsoft, dobre rozumowanie
- `mistral:7b`: 7B parametrów - Wysoka jakość
- `llama3.1:8b`: 8B parametrów - Bardzo wysoka jakość

Zobacz wszystkie modele: https://ollama.com/library

---

## Konfiguracja (`config/providers.toml`)

### Provider Głosu (sekcja `[voice]`)
```toml
[voice]
asr_model = "base"              # Model Whisper
tts_model = "en_US-lessac-medium"  # Głos Piper
sample_rate = 16000
use_mock = false                # Ustaw true aby wymusić tryb mock
```

### Provider Wizji (sekcja `[vision]`)
```toml
[vision]
detection_model = "yolov8n"     # Model YOLO
confidence_threshold = 0.5      # Pewność detekcji
max_detections = 10
use_mock = false                # Ustaw true aby wymusić tryb mock
```

### Provider Tekstu (sekcja `[text]`)
```toml
[text]
model = "llama3.2:1b"           # Model Ollama
max_tokens = 512
temperature = 0.7
ollama_host = "http://localhost:11434"
use_mock = false                # Ustaw true aby wymusić tryb mock
enable_cache = true
```

---

## Konfiguracja Docker

### Używanie Pobranych Modeli

Edytuj `Dockerfile` aby odkomentować pobieranie modeli:
```dockerfile
# Pobierz modele AI (odkomentuj dla szybszego startu)
RUN python -c "import whisper; whisper.load_model('base')"
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Używanie Ollama w Docker

Dodaj do `docker-compose.yml`:
```yaml
environment:
  - OLLAMA_HOST=http://host.docker.internal:11434
```

Lub uruchom Ollama w Docker:
```yaml
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama-data:/root/.ollama
```

---

## Testowanie

### Testuj Provider Głosu
```python
from pc_client.providers import VoiceProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = VoiceProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.VOICE_ASR,
    payload={"audio_data": "base64_audio_here"}
)

result = await provider.process_task(task)
print(result.result["text"])
```

### Testuj Provider Wizji
```python
from pc_client.providers import VisionProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = VisionProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.VISION_DETECTION,
    payload={"image_data": "base64_image_here"}
)

result = await provider.process_task(task)
print(result.result["detections"])
```

### Testuj Provider Tekstu
```python
from pc_client.providers import TextProvider
from pc_client.providers.base import TaskEnvelope, TaskType

provider = TextProvider()
await provider.initialize()

task = TaskEnvelope(
    task_id="test-1",
    task_type=TaskType.TEXT_GENERATE,
    payload={"prompt": "Wyjaśnij nawigację robota"}
)

result = await provider.process_task(task)
print(result.result["text"])
```

---

## Wskazówki Wydajnościowe

### Optymalizacja CPU
- Używaj lekkich modeli (`yolov8n`, `whisper base`, `llama3.2:1b`)
- Zmniejsz współbieżne zadania w konfiguracji
- Włącz cachowanie dla powtarzających się zapytań

### Zarządzanie Pamięcią
- Monitoruj użycie pamięci modeli: `nvidia-smi` (GPU) lub `htop` (CPU)
- Dostosuj `max_concurrent_tasks` w oparciu o dostępny RAM
- Używaj mniejszych modeli jeśli pamięć ograniczona

### Przechowywanie
- Modele cachowane w:
  - Whisper: `~/.cache/whisper/`
  - YOLO: `~/.cache/ultralytics/`
  - Ollama: `~/.ollama/models/`
- Wyczyść cache jeśli miejsce na dysku ograniczone

---

## Rozwiązywanie Problemów

### Whisper nie może się załadować
```bash
# Przeinstaluj z konkretną wersją
pip install --upgrade openai-whisper

# Lub użyj trybu mock
use_mock = true
```

### Pobieranie YOLO kończy się niepowodzeniem
```bash
# Ręczne pobieranie
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Sprawdź połączenie internetowe
# Sprawdź miejsce na dysku
```

### Błąd połączenia Ollama
```bash
# Sprawdź czy Ollama działa
curl http://localhost:11434/api/tags

# Uruchom Ollama
ollama serve

# Sprawdź czy model jest pobrany
ollama list
```

### Brak pamięci
- Używaj mniejszych modeli
- Zmniejsz `max_concurrent_tasks`
- Włącz swap (WSL: zwiększ pamięć w `.wslconfig`)
- Używaj trybu mock dla testowania

---

## Lokalizacje Przechowywania Modeli

- **Whisper**: `~/.cache/whisper/`
- **YOLOv8**: `~/.cache/ultralytics/`
- **Ollama**: `~/.ollama/models/`
- **Piper**: Zależne od systemu, sprawdź `/usr/share/piper/`

Całkowite miejsce dla zalecanych modeli: ~2-3GB

---

## Następne Kroki

1. Wybierz tryb wdrożenia (mock lub prawdziwe modele)
2. Zainstaluj wymagane zależności
3. Zaktualizuj pliki konfiguracyjne
4. Testuj providerów indywidualnie
5. Wdróż z Docker Compose

Zobacz [WDROZENIE_ZAKONCZONE_FAZA4.md](PR/WDROZENIE_ZAKONCZONE_FAZA4.md) dla pełnego przewodnika wdrożenia.
