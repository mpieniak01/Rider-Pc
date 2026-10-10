# Zarządzanie usługami i zasobami

Rider-PC obserwuje skonfigurowane lokalne jednostki systemd oraz inwentarz
otrzymany z Rider-Pi. Katalog jednostek, targetów, zadań i zasobów robota jest
utrzymywany na Pi i pobierany przez HTTP; PC nie przechowuje jego produkcyjnej kopii.

## Źródło i tożsamość

Każdy wiersz ma `host`, `unit`, `identity=host:unit`, `source`,
`observed_at`, `stale` i `offline`. Identyczna nazwa na Pi i PC oznacza dwie
pozycje. Po awarii połączenia znane jednostki Pi pozostają widoczne jako unknown
z ostatnią obserwacją i błędem. Nowy czas odpowiedzi PC nie odmładza danych Pi.
Jeżeli Pi nie było jeszcze odczytane, pole `hosts.pi.offline` pokazuje brak
połączenia, a pusty inwentarz nie jest potwierdzeniem sprawnego robota.

`active`, `sub`, `load/installed` oraz `enabled` mają odrębne znaczenie.
Active jednostki nie potwierdza gotowości całego zadania, włączenia napędów,
aktualnego obrazu ani wolnego urządzenia.

## Konfiguracja PC

```dotenv
MONITORED_SERVICES=
NON_ACTUATING_SERVICES=
SYSTEMD_USE_SUDO=true
AUTO_HEAL_ENABLED=true
MAX_RETRY_COUNT=1
RETRY_WINDOW_SECONDS=300
TEST_MODE=false
```

`MONITORED_SERVICES` to jawna lista lokalnych unitów. Pusta lista daje pusty
inwentarz PC. Brak działającego systemd daje unknown, bez zastępowania go
fikcyjnym Redis, Prometheus, kolejką czy providerami.
`NON_ACTUATING_SERVICES` jest sprawdzonym podzbiorem tej listy: dopiero jawnie
znane usługi bez napędów mogą być uruchamiane/restartowane/włączane w autostarcie.
Żądanie lokalnej administracji wskazuje `host: pc`. Uprawnienia sudo ogranicza
administrator do potrzebnych konkretnych jednostek i działań.

`TEST_MODE=true` wybiera jawny demonstracyjny manager oraz MockRestAdapter
podczas startu aplikacji. Każdy taki wiersz ma `source: demo`. To nie jest stan
systemu operacyjnego. Dla automatycznych testów wymagane są także rzeczywiste
blokady połączeń opisane w [bezpiecznym kliencie](BEZPIECZNY_KLIENT_ROBOTA.md).

Provider już utworzony w aplikacji ma `kind: application_provider`,
`source: application` i nie posiada akcji systemctl. Gotowość wynika z jego
inicjalizacji. Stan wyboru providera na Pi pochodzi z Pi; brak połączenia nie
zmienia wyboru i nie kończy się lokalnym OK.

## Odczyty i działania

- `GET /svc`: lista PC i Pi oraz stan połączenia obu hostów.
- `GET /api/services/graph`: graf, węzły z tożsamością host/unit i źródłem.
- `GET /api/logic/catalog`: katalog Pi v2; starszy serwer może go nie obsługiwać.
- `GET /api/resource/{name}`: rzeczywista obserwacja zasobu; błąd oznacza
  unknown, a nie free. Kamera korzysta z tego samego kontraktu.
- `POST /svc/{unit}`: jawne `action` i `host`; unknown/stale/legacy
  nie zezwala na start/restart/enable.
- `POST /api/resource/{name}`: jawna operacja stop/release przekazywana do Pi;
  klient nie udaje, że zakończył właściciela zasobu.

Karty System służą do odczytu. Start zadania ruchowego jest odrębny od
podglądu obrazu oraz odczytu urządzenia i wymaga właściwej bramy bezpieczeństwa.
Zasoby i zależności usług są rozstrzygane na Pi; PC nie wykonuje lokalnego
force-kill robota ani nie traktuje zatrzymania targetu jako dowodu zwolnienia
wszystkich członków. Jupyter jest narzędziem uruchamianym ręcznie na życzenie;
klient nie zmienia bootu, Wi-Fi, SSH, splash ani orientacji LCD.

## Retry

Watchdog działa poza trybem testowym. Lista monitorowana pochodzi z managera.
Retry dotyczy tylko `source: systemd`, `host: pc`, `can_move: false`,
świeżego stanu failed i intencji active. Początkowe failed/unknown bez wcześniejszej
gotowości nie jest automatycznie uruchamiane. Stop/disable zapisuje intencję
stopped i wyklucza retry nawet wtedy, gdy polecenie zatrzymania się nie powiedzie.
Pi i providery aplikacji nie są sterowane watchdogiem.
