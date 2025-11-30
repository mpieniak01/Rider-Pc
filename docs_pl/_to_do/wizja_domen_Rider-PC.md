# Rider-PC – Domeny (nowa kolejność, wersja rozszerzona)

Poniższe domeny są uporządkowane zgodnie z **priorytetami realizacji**. Każda została teraz rozpisana szczegółowo na podstawie wszystkich wcześniejszych ustaleń i całej logiki Rider-OS.

---

## **1. Domena – Robot (Rider-Pi Control)**

### **Opis**

Centralna domena operacyjna, w której Rider-PC kontroluje Rider-Pi jako końcówkę sensoryczno-aktuatorową. Robot przestaje być „mózgiem” – staje się fizyczną częścią Twojego systemu nerwowego.

### **Zakres funkcji**

* Sterowanie usługami i funkcjami robota (tracker, kamera, TTS Pi, tryby).
* Integracja z bus ZMQ do ruchu: drive, stop, obrót, follow-me.
* Pobieranie statusu z Rider-Pi: `/api/system/status`, `/api/features`.
* Sterowanie kamerą, zapytania o snapshoty, analiza obrazu.
* Interpretacja danych sensorycznych: offsety, wykrycia twarzy/obiektów.
* Reakcja na zdarzenia z robota: wykryty ruch, brak offsetu, błędy trackerów.

### **Cele**

* Rider-PC staje się autonomicznym mózgiem robota.
* Robot wykonuje komendy, a PC podejmuje decyzje.

---

## **2. Domena – Modele Lokalnie (Local LLM/ML Runtime)**

### **Opis**

Warstwa wykonywania dużych modeli lokalnie (LM Studio, Ollama, pythonowe silniki). To Twoja prywatna infrastruktura AI bez kosztów w chmurze.

### **Zakres funkcji**

* Uruchamianie i wybór lokalnych modeli (LLM, vision, audio).
* API OpenAI-compatible lokalnego backendu.
* Cache kontekstów i analiza kosztów tokenów.
* Integracja z MCP jako „dostawca modeli”.

### **Cele**

* Wszystkie długie procesy AI wykonują się na Twoim PC lokalnie i bez limitów.
* Zero kosztów operacyjnych poza energią.

### **Nowe inicjatywy (2025)**

* **Chat PC (Standalone)** – osobny ekran `chat-pc.html` z pełną obsługą kanałów mowa↔tekst↔mowa, działający nawet przy wyłączonym Rider-Pi. Backend Rider-PC udostępnia `/api/chat/pc/send`, lokalne ASR/TTS i health-checki providerów.

#### Zaimplementowane funkcjonalności Chat PC (Standalone):

**Backend (FastAPI):**
  * `/api/chat/pc/send` – endpoint czatu działający wyłącznie lokalnie (bez proxy)
  * `/api/chat/send` z parametrem `mode=pc|proxy|auto` – elastyczny wybór źródła
  * `/api/providers/text` – status providera tekstowego (model, silnik, dostępność)
  * `/api/providers/voice` – status providera głosowego (ASR/TTS, dostępność)
  * `/api/voice/asr` – endpoint rozpoznawania mowy (speech-to-text)
  * `/api/voice/tts` – synteza mowy (text-to-speech)
  * `/api/chat/pc/generate-pr-content` – generowanie treści PR z pomocą AI

**Frontend (`web/chat-pc.html`):**
  * Przełącznik trybu: PC / Auto / Proxy z zapisem preferencji
  * Status providera tekstowego i głosowego z wizualnymi wskaźnikami
  * Nagrywanie mowy (ASR) z przyciskiem „🎤 Mów"
  * Odczytywanie odpowiedzi (TTS) z checkbox
  * Sekcja „Asystent PR" do generowania treści PR na podstawie szkiców
  * Oddzielna historia wiadomości w sessionStorage (izolacja od klasycznego czatu)

**Diagnostyka i fallback:**
  * Rozszerzone logowanie inicjalizacji providerów
  * Automatyczny fallback do trybu mock przy błędzie Ollama/Whisper/Piper
  * Komunikaty diagnostyczne dla UI (hint do naprawy problemu)

* **Wspólna instancja LLM** – Rider-PC i Rider-Pi korzystają z jednego załadowanego modelu Ollama; przełączanie modeli (benchmark, wybór w UI) jest kontrolowane przez Rider-PC i czytelnie sygnalizowane wszystkim klientom.
* **Benchmark + baza wiedzy** – wbudowane narzędzia do porównywania modeli, logowania latencji i jakości odpowiedzi, z opcją podania promptów pozycjonujących i kontekstu z modułu Knowledge/Project.
* **Integracja z modułem Project/PR editor** – Chat PC potrafi czytać szkice PR, łączyć je z bazą wiedzy i generować finalną treść bezpośrednio w procesie tworzenia PR.

---

## **3. Domena – Przetwarzanie i Trenowanie Modeli (AI-FORGE)**

### **Opis**

Najbardziej zaawansowana domena Rider-PC – miejsce, gdzie system uczy się z danych. Tworzysz własne modele wizji, języka, zachowania i preferencji.

### **Zakres funkcji**

* Budowanie datasetów z obrazów Rider-Pi.
* Trenowanie modeli wizji: pokój, obiekty, zmiany w środowisku, gesty.
* Trenowanie modeli językowych na Twoich notatkach i stylu analitycznym.
* Automatyczna analiza Twoich interakcji → preferencje.
* Modele rozpoznające anomalie w pokoju.
* Detektory stanów: „pokój OK”, „coś się zmieniło”.

### **Cele**

* Rider-PC staje się systemem samo-uczącym.
* Modele adaptują się do Ciebie i Twojego otoczenia.

---

## **4. Domena – Zarządzanie PC (System Control)**

### **Opis**

Warstwa systemowa odpowiadająca za kontrolę Twojego środowiska komputerowego. To „nerwy i autonomiczny nadzór operacyjny”.

### **Zakres funkcji**

* Uruchamianie, restart, stop usług systemowych.
* Diagnostyka komponentów: CPU, RAM, dysk, procesy.
* Analiza logów systemowych i logów Rider-PC.
* Diagnostyka sieci: ping, curl, połączenia lokalne.
* Integracje z repo Rider-Pi: status, testy, analizy błędów.
* Samonaprawa systemu: wykrycie problemu → propozycja patcha.

### **Cele**

* Rider-PC „monitoruje siebie”, zgłasza błędy i proponuje naprawy.
* To fundament funkcji self-debugging.

---

## **5. Domena – Przeszukiwanie Sieci (Web Intelligence)**

### **Opis**

Warstwa inteligencji informacyjnej – analiza internetu dla Twoich projektów, artykułów i teorii.

### **Zakres funkcji**

* Wyszukiwanie informacji.
* Pobieranie artykułów i streszczanie ich.
* Analiza źródeł (nauka, technologie, fizyka falowa, kosmologia).
* Monitorowanie tematów (np. unifikacja grawitacji i EM).
* Tworzenie baz wiedzy na podstawie sieci.

### **Cele**

* Rider-PC wspiera Twoje badania, publikacje i procesy analityczne.

---

## **6. Domena – Inteligentny Dom (Smart Home)**

### **Opis**

Integracja Rider-PC z elementami Twojego środowiska domowego.

### **Zakres funkcji**

* Sterowanie oświetleniem, temperaturą i urządzeniami.
* Sceny i tryby automatyczne („relax”, „focus”, „night”).
* Integracja z Home Assistant lub urządzeniami API.

### **Cele**

* Dom staje się rozszerzeniem Rider-PC.
* Robot + PC + Dom → jeden organizm.

---

## **7. Domena – Rutyny i Zadania (Tasks & Routines)**

### **Opis**

Warstwa automatyzacji życia codziennego.

### **Zakres funkcji**

* Zadania do wykonania i checklisty.
* Rutyny automatyczne zależne od pory dnia lub zdarzeń.
* Integracja z przepływami i zdarzeniami systemu.

### **Cele**

* Rider-PC odciąża Cię od zarządzania codziennością.

---

## **8. Domena – Informacja i Wiedza (Notes, Logs, Knowledge)**

### **Opis**

Domena odpowiedzialna za budowanie pamięci długotrwałej systemu – centrum Twojej wiedzy i procesów analitycznych.

### **Zakres funkcji**

* Zbieranie i organizowanie notatek.
* Embeddingi notatek i dokumentów.
* Analiza dokumentacji Rider-Pi.
* Zapis informacji z interakcji.
* Tworzenie chronologii projektu.

### **Cele**

* Rider-PC wie, kim jesteś, jak myślisz i jak pracujesz.

---

## **9. Domena – Konfiguracje, Wizadry i Przepływy (Flows Engine)**

### **Opis**

Najbardziej „meta” domena Rider-OS – system, który projektuje samego siebie poprzez przepływy logiczne, zdarzenia i kreatory.

### **Zakres funkcji**

* Tworzenie przepływów automatyzacji (trigger → actions → effects).
* Projektowanie scenariuszy dla robota, domu, PC i modeli.
* Kreatory konfiguracji dla nowych trybów działania.
* Zapisywanie przepływów w formacie `.yaml`.
* Integracja z domenami 1–8.

### **Cele**

* Rider-PC staje się systemem **self-orchestrating**.
* Możesz tworzyć AI-automaty bez pisania kodu.

---


# Diagram architektury Rider-PC / Rider-OS

Poniższy diagram przedstawia pełny przepływ informacji, podział odpowiedzialności i relacje między domenami Rider-PC a Rider-Pi.

```
                     +---------------------------------------------+
                     |          Klienci / Interfejsy AI/IO         |
                     |   (ChatGPT, lokalny web, voice, itp.)       |
                     +---------------------------------------------+
                           +---------------+-----------------+
                                           |
                                           v
+--------------------------------------------------------------------------------------+
|                                  RIDER-PC (OS)                                       |
|--------------------------------------------------------------------------------------|
|                                                                                      |
|  +------------------------+     +-------------------------+     +-----------------+  |
|  |  Domena 2: Modele      |     |  Domena 3: Trening      |     |  Domena 4: PC   |  |
|  |  Lokalnie (LLM/ML)     |     |  i Przetwarzanie        |     |  System Control |  |
|  |------------------------|     |-------------------------|     |-----------------|  |
|  | • LM Studio / Ollama   |     | • Dataset Builder       |     | • systemd       |  |
|  | • lokalny runtime      |     | • trening modeli wizji  |     | • repo testy    |  |
|  | • inference backend    |     | • trening modeli języka |     | • logi / diag   |  |
|  +------------------------+     +-------------------------+     +-----------------+  |
|                                                                                      |
|  +------------------------+     +------------------------+      +-----------------+  |
|  |  Domena 1: Robot       |     | Domena 5: Web Search   |      | Domena 6: Dom   |  |
|  |  (Rider-Pi Control)    |     |  (Web Intelligence)    |      |  (Smart Home)   |  |
|  |------------------------|     |------------------------|      |-----------------|  |
|  | • sterowanie Pi        |     | • wyszukiwanie         |      | • światła/sceny |  |
|  | • bus ZMQ              |     | • analiza artykułów    |      | • integracje    |  |
|  | • sensory → PC         |     | • monitoring tematów   |      |                 |  |
|  +------------------------+     +------------------------+      +-----------------+  |
|                                                                                      |
|  +------------------------+     +------------------------+      +-----------------+  |
|  | Domena 7: Rutyny       |     | Domena 8: Wiedza        |     | Domena 9: Flow  |  |
|  | i Zadania              |     |  (Notes/Logs)           |     |  Engine         |  |
|  |------------------------|     |-------------------------|     |---------------- |  |
|  | • automaty             |     | • notatki               |     | • przepływy     |  |
|  | • checklisty           |     | • pamięć długotrwała    |     | • kreatory      |  |
|  | • harmonogramy         |     | • embeddings            |     | • orchestration |  |
|  +------------------------+     +-------------------------+     +-----------------+  |
|                                                                                      |
+--------------------------------------------------------------------------------------+
                                             |
                                             v
                         +----------------------------------------+
                         |      Warstwa efektorów / akcji         |
                         |  (Rider-Pi, Smart Home, PC, Notatki,   |
                         |   Repozytoria, Powiadomienia, itp.)    |
                         +----------------------------------------+
```
