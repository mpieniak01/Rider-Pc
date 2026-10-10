# Development

Rider-Pi i Rider-PC są osobnymi repozytoriami. Wspólny workspace VS Code
nie zmienia katalogu terminala ani wybranego interpretera. Polecenia wykonuj
z właściwego repozytorium i korzystaj z jego środowiska.

```bash
pwd
git status --short --branch
git fetch origin
git log --oneline HEAD..origin/main
.venv/bin/python --version
.venv/bin/python -m pip check
```

Przed aktualizacją sprawdź niezapisane zmiany i stashe. Na czystym `main`
używaj `git pull --ff-only`; wcześniejsze prace zachowuj zamiast resetować.
Zmiany aplikacji prowadź na osobnej gałęzi, z odpowiednimi kontrolami
i review w PR. Same porządki dokumentacyjne mogą trafić bezpośrednio
na `main`, jeżeli właściciel repozytorium tak poleci.

## Konfiguracja i notatki lokalne

Korzystamy ze zwykłych lokalnych plików env. `.env`, prywatne `.env.*`,
`evn.ssh.local` i `config/local/` zawierają ustawienia developera i sekrety.
Nie trafiają do Git, załączników PR, logów ani paczek wdrożeniowych.
Publiczne `.env.example` i `.env.*.example` zawierają wyłącznie placeholdery.
Zachowuj istniejący `.env`; nie nadpisuj go szablonem.

Prywatny plik SSH powinien mieć uprawnienia `600`. Hasło wpisuj w lokalnym
edytorze, bez przekazywania go w argumentach poleceń lub dokumentacji.
Zwykły SSH nie wczytuje automatycznie `evn.ssh.local`.

Plany zadań zapisuj w ignorowanym `docs_pl/_to_do/`, a ukończone notatki
i audyty sesji w `docs_pl/_done/`. Nie tworzymy ich angielskich kopii. Utrzymywane instrukcje i potrzebne obrazy
publikuj zgodnie z [polityką dokumentacji](POLITYKA_DOKUMENTACJI.md).
Przed commitem sprawdź `git diff --cached --name-status` oraz
`git diff --cached --check`. Nie dodawaj plików lokalnych przez `git add -f`.

## Środowisko PC, kontrole i panel

Używaj Pythona 3.11. Przeczytaj [współtworzenie](CONTRIBUTING.md)
i [konfigurację](KONFIGURACJA.md). Dane modeli i logi pozostają lokalne.
Odczyt środowiska nie wymaga reinstalacji stosu ML ani pobierania modeli.

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
make test
```

Przy zmianie API lub UI dobieraj powiązane testy kontraktowe i przeglądarkowe.
Dla CSS wykonaj `npm run lint:css` oraz `npm run css:size` w istniejącym
środowisku Node. Dokumentacja wymaga sprawdzenia linków i zakresu publikacji.
Wyniki konkretnego uruchomienia zapisuj lokalnie. Mocki i cache telemetrii
nie potwierdzają działania rzeczywistych modeli ani poleceń na robocie.

Uruchom aplikację z katalogu repozytorium i jego konfiguracji:

```bash
.venv/bin/python -m pc_client.main
```

Domyślny panel to `http://localhost:8000`; port ustawia `SERVER_PORT`.
Start aplikacji może wczytać modele i połączyć skonfigurowane usługi.
API robota jest osobną usługą na Pi, zwykle na porcie `8080`.
Przed użyciem ruchu przeczytaj [integrację z Pi](INTEGRACJA_OFFLOAD_PC.md).

## Kreator zadań i lokalne plany

Kreator może tworzyć zgłoszenia i gałęzie GitHub. Plany
w `docs_pl/_to_do/` pozostają lokalne. Ustaw `TASK_AUTO_INIT_ENABLED=false`
w lokalnym `.env` i nie zaznaczaj automatycznej inicjalizacji: historyczny
inicjalizator próbuje także commitować plan. Zwykłe `git add` odrzuca ten
ignorowany katalog; nie obchodź tej ochrony. Plan twórz lokalnie, a commituj
wynikową dokumentację projektową i implementację.
