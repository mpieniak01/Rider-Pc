# API sterowania

Rider-PC przekazuje żądania do Rider-Pi. Testy napędów są wyłącznie ręczne po
zgodzie operatora na plan próby. Przykładowe pola opisują kontrakt, nie procedurę
automatycznego uruchamiania urządzenia. Zobacz [bezpieczny klient](../BEZPIECZNY_KLIENT_ROBOTA.md).

## Stan

`GET /api/control/state` zwraca obserwację Pi oraz `source`, `observed_at`,
`stale` i `offline`. Pole `safety` ma wersję 1, stan
DISARMED/ARMED/ESTOP, `ready`, `can_move`, `read_only`, `owner`,
`generation`, `last_seq` i metadane ACK. Brak wersji daje UNKNOWN/read-only.

## Koperta konkretnego potwierdzenia

Wszystkie żądania aktuatorów oraz arm/clear zawierają:

| Pole | Reguła |
| --- | --- |
| `generation` | Generacja z aktualnego stanu Pi; PC jej nie tworzy |
| `seq` | Dodatnia liczba całkowita większa od ostatniej sekwencji |
| `source` | `manual` dla HTTP operatora |
| `ts` | Skończony czas UNIX potwierdzenia |
| `ttl_ms` | Liczba całkowita 1–500; przeterminowane żądanie odrzucone |

PC sprawdza kopertę i przekazuje ją bez zmiany. Nie odświeża starego żądania
po STOP lub ponownym arm. Bez tych metadanych starszy UI pozostaje odczytowy.
STOP można wysłać bez koperty.

## Zgoda i zatrzymanie

`POST /api/safety` przyjmuje `action: arm|disarm|estop|clear_estop`.
Arm i clear wymagają wyraźnego `operator_consent: true`, niepustego
`operator_plan` oraz koperty. Arm wskazuje `owner: manual|follow_me|navigation`
i `lease_s` ograniczony przez Pi do 30 sekund. Clear pozostawia napędy rozbrojone.
Disarm/estop nie potrzebują potwierdzonej gotowości. PC niczego nie uzbraja
podczas startu aplikacji, wyboru widoku, zadania, kamery ani providera.

## Aktuatory

`POST /api/control` przyjmuje `cmd: move|spin|height|balance|action|stop`
oraz pola właściwe dla komendy (np. vx/yaw/duration, height, enabled, action).
Jednostki i limity napędów pochodzą z Pi, a nie z domyślnych parametrów klienta.
Ruch wymaga świeżej bramy ARMED, ready=true, can_move=true i właściciela manual.
Wysokość, balans i gotowe akcje podlegają tej samej regule.

`GET /api/motion/queue` przekazuje stan kolejki Pi. Pole
`local_request_history` opisuje żądania PC i odpowiedzi, nie wykonanie na UART.
Brak Pi daje stale/offline, bez lokalnego potwierdzenia zatrzymania.

## Zadania i śledzenie

- `GET /api/logic/features`, `/summary`, `/catalog`: katalog i stan Pi v2.
- `POST /api/logic/feature/{name}`: `enabled` musi być boolean. Start wymaga
  jawnego can_move. Dla ruchu także koperty i zgodnego motion_owner.
- `POST /api/vision/tracking/mode`: mode face/hand/none; aktywne śledzenie
  wymaga właściciela follow_me. Wyłączenie nie uzbraja napędów.
- `POST /api/navigator/start`, `/stop`: jawny start/stop zadania s9_navigation.
- `POST /api/navigator/return_home`: koperta i właściciel navigation;
  tylko potwierdzona odpowiedź Pi, bez lokalnej symulacji.

Katalog starszego Pi można odczytać, ale brak potwierdzonej zdolności v2 nie
autoryzuje startu. Usługi i zasoby opisuje [osobny kontrakt](../ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md).

## Wynik

Odpowiedź Pi zachowuje kod HTTP i pola `ok`, `confirmed`, `pending`,
`request_id`, `ack`, `safety` i `physical_completion`, jeśli są dostępne.
HTTP 202 oznacza oczekiwanie na ACK. HTTP 409 oznacza odmowę bramy, nieznaną
zdolność albo starą kopertę. HTTP 503 oznacza brak połączenia; 502 błąd proxy.
Sukces HTTP nie jest dowodem zakończenia fizycznego ruchu.
