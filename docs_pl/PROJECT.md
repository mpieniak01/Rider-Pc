# Wizja Rider-PC i ekosystemu

Rozwijamy osobistego robota edukacyjnego oraz środowisko AI do jego obsługi.
Pierwsza wersja skupiała sterowanie i aplikacje na Rider-Pi. Rider-PC przenosi
panel operatora oraz cięższe obliczenia na komputer, zachowując aplikacje
urządzenia. Docelowo Venom ma odpowiadać za nadrzędne sterowanie;
integracja i szczegółowy kontrakt Venoma pozostają odłożone.

| Filar | Odpowiedzialność |
| --- | --- |
| Rider-Pi | Sterowniki, sensory, wykonanie ruchu, kamera, audio, LCD i lokalne aplikacje |
| Rider-PC | Panel operatora, komunikacja z Pi, modele AI, lokalny czat i narzędzia PC |
| Venom | Planowane nadrzędne sterowanie i koordynacja |

Fizyczne wykonanie i lokalne zabezpieczenia pozostają na Pi. Rider-PC może
działać bez robota w zakresie lokalnego czatu i narzędzi komputerowych;
sterowanie sprzętem wymaga połączenia z Rider-Pi. Wybór providera PC
nie przenosi sterowników urządzenia na komputer.

## Kierunki rozwoju

| Domena | Zakres |
| --- | --- |
| Robot | Panel, telemetria, scenariusze i sterowanie przez adaptery REST/ZMQ |
| Modele lokalne | LLM, wizja, ASR/TTS i Chat PC |
| AI-FORGE | Planowane zbiory danych, trening i adaptacja modeli |
| Zarządzanie PC | Usługi, zasoby, logi, diagnostyka; docelowo samonaprawa |
| Web Intelligence | Planowane wyszukiwanie i analiza źródeł |
| Smart Home | Integracje urządzeń i scen domowych |
| Rutyny i zadania | Planowane harmonogramy oraz automatyzacje użytkownika |
| Wiedza | Dokumenty, embeddingi i kontekst dla modeli |
| Flows Engine | Planowane przepływy łączące domeny |

Tabela opisuje zakres produktu i kierunek prac. Obecność routera, providera
lub ekranu w kodzie nie oznacza ukończenia całej domeny. Kolejka obliczeń AI
nie jest harmonogramem rutyn użytkownika. Panel i cache nie potwierdzają
wykonania polecenia na fizycznym robocie.

## Komunikacja i weryfikacja

REST obsługuje status oraz polecenia, a ZMQ zdarzenia i zadania AI.
Rider-Pi wybiera providerów głosu, wizji i tekstu. Negocjacja możliwości,
heartbeat i fallback wymagają testów także przy utracie połączenia z PC.
Mocki w testach nie zastępują uruchomienia modelu ani kontroli na urządzeniu.

Architekturę opisuje [ARCHITEKTURA](ARCHITEKTURA.md), kontrakty
[integracja offload](INTEGRACJA_OFFLOAD_PC.md), a sposób pracy
[development](development.md). Backlogi i wyniki poszczególnych sprawdzeń
pozostają lokalne zgodnie z [polityką dokumentacji](POLITYKA_DOKUMENTACJI.md).
