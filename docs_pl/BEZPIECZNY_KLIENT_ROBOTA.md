# Bezpieczny klient robota

Rider-PC pośredniczy w poleceniach i pokazuje stan Rider-Pi. Gotowość serwera PC
nie potwierdza gotowości napędów. Źródłem stanu napędów i katalogu zadań jest Pi.

## Testy i zgoda operatora

Automatyczne testy używają atrap REST/SDK/BUS. Root `conftest.py` blokuje
prawdziwy TCP, ZMQ, pliki urządzeń, SDK robota i komendy SSH/systemd.
Interpreter potomny otrzymuje te same bariery przez `sitecustomize`; wyłączenie
bootstrapu Pythona i niejawne wywołania powłoki są odrzucane.
Samodzielny CSS audit używa tego samego modułu izolacji. Jedyny wyjątek TCP
to port lokalnego serwera uruchomionego przez fixture E2E; przeglądarka również
odrzuca ruch do innych adresów. Samo `TEST_MODE=true` nie zapewnia izolacji.

Próby fizycznych aktuatorów (jazda, obrót, wysokość, balans, gotowe akcje i zadania
ruchowe) są wyłącznie ręczne, po zgodzie operatora na konkretny plan próby.
Nie należą do pytest, E2E, CI, ogólnej diagnostyki ani wdrożenia. Zgoda na kamerę,
odczyt stanu, start serwera lub publikację kodu nie oznacza zgody na napędy.
Robot podłączony kablem wymaga przygotowanej przestrzeni. Ekran, splash i ustalona
orientacja LCD nie są zmieniane przez klienta ani testy.

## Kontrakt bezpieczeństwa v1

`GET /api/control/state` przekazuje pole `safety` z Pi:

- `contract_version: 1`, `state: DISARMED|ARMED|ESTOP`;
- `ready`, `can_move`, `read_only`, `observed_at`;
- `owner: manual|follow_me|navigation`, `generation`, `last_seq`;
- dodatkowy ACK, stan sprzętu, powód blokady i okres ważności pozostają w odpowiedzi.

Brak znanej wersji daje `UNKNOWN` i odczyt bez zdolności sterowania.
PC przed każdym poleceniem wymagającym napędów pobiera stan Pi. Wymaga
`ARMED`, jawnych `ready=true` i `can_move=true`, właściwego właściciela,
ważnej generacji oraz obserwacji nie starszej niż trzy sekundy.
Stan stale/offline, niepoprawne pola i nieznana zdolność powodują HTTP 409.

`POST /api/safety` przekazuje `action: arm|disarm|estop|clear_estop`.
Arm/clear wymagają `operator_consent: true` i niepustego `operator_plan`;
Pi dodatkowo weryfikuje właściciela i ogranicza czas zgody.
PC nigdy nie uzbraja robota automatycznie i nie tworzy generacji. Każde żądanie
aktuatora oraz arm/clear musi zawierać kopertę konkretnego potwierdzenia:
`generation` z Pi, rosnące `seq`, `source: manual`, skończone `ts` oraz
`ttl_ms` od 1 do 500. PC sprawdza ją i przekazuje bez odświeżania czasu lub
zamiany generacji. Stare polecenie nie może stać się nowe po STOP/ponownym arm.
Starszy panel bez tych danych pozwala na odczyt i STOP.

STOP można wysłać bez odczytu gotowości. Brak połączenia nadal oznacza odmowę,
a nie lokalne potwierdzenie zatrzymania sprzętu. Odpowiedź Pi, w tym HTTP 202,
`confirmed`, `pending`, `ack` i `physical_completion`, jest zachowywana.
Przyjęcie żądania nie dowodzi zakończenia fizycznego ruchu.

## Katalog v2 i dane offline

`/api/logic/catalog`, `/api/logic/features`, `/api/logic/summary` oraz `/svc`
obsługują kontrakt v2 Pi. Start zadania wymaga znanego `can_move`; dla ruchu
również `motion_owner` zgodnego z bramą. Start/restart usług wymaga znanej
zdolności v2. Nie wolno włączyć autostartu zadania zdolnego do ruchu.
Niezainstalowana lub nieaktualna pozycja nie daje gotowości.

Starsza wersja Pi pozostaje dostępna do odczytu. Brak kontraktu nie jest
zastępowany lokalnym katalogiem ani symulowanym sukcesem. Po awarii odczytu
ostatni inwentarz zostaje z pierwotnym `observed_at`, `stale/offline` i błędem.
Brama wtedy pokazuje `UNKNOWN`; zasób nie jest przedstawiany jako wolny.
Historia żądań PC jest oddzielona od kolejki/ACK Pi.

## Usługi PC i watchdog

Zobacz [zarządzanie usługami](ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md).
System jest widokiem odczytowym: kliknięcie karty nie wysyła POST.
Zmiany usług są jawnymi żądaniami API ze wskazaniem hosta; tożsamość to
`host:unit`. Provider aplikacji jest oznaczony `application_provider`,
nie jest wymyśloną jednostką systemd.

Watchdog monitoruje ten sam skonfigurowany zestaw co manager. Próbuje ponownie
jedynie rzeczywistą lokalną usługę bez aktuatorów, która wcześniej była aktywna
lub została jawnie uruchomiona. Stan inactive, unknown, offline, demo, brak
konfiguracji i intencja stop/disable nie uruchamiają retry. Watchdog nie zarządza
Pi, nie odtwarza zgody, zadań zakończonych ani komend ruchu.

Jawne ARM oraz kasowanie E-Stop przyjmują świeży znany stan `DISARMED`/`ESTOP`, nawet gdy `read_only:true` opisuje zablokowane aktuatory. Ruch wymaga `read_only:false`, `ARMED`, `ready:true` i `can_move:true`. Brak kontraktu lub stan `UNKNOWN` zawsze blokuje ARM.

Pakiety runtime i testowe są rozdzielone przez środowisko i włączone funkcje;
zobacz [minimalny runtime i testy w WSL](CONTRIBUTING.md#minimalny-runtime-i-testy-w-wsl).

Nowy [panel operatora](PANEL_OPERATORA.md) stosuje ten kontrakt; zegar UI jest potwierdzany przez server_time Pi i ograniczony RTT. Ruch wymaga także hardware_ready:true. System udostępnia oddzielne jawne przyciski administracyjne, nigdy akcję po kliknięciu karty.
