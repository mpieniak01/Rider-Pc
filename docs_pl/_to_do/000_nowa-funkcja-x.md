# Zadanie #151: Nowa Funkcja X

**Status:** :hourglass_flowing_sand: W trakcie
**Link:** https://github.com/mpieniak01/rider-pc/issues/151
**Autor:** Nieprzypisane

## Cel
(brak opisu)

## Plan Realizacji
- [ ] Analiza
- [ ] Implementacja
- [ ] Testy

## Audyt środowiska / req

### Stan repozytorium
- `git status -sb` → `## main...origin/main` z lokalnym diffem ograniczonym do tego req (`D docs_pl/_to_do/151_nowa-funkcja-x.md`, `?? docs_pl/_to_do/000_nowa-funkcja-x.md`).

### Środowisko wykonawcze
- System bazowy: Ubuntu 24.04.3 LTS (`lsb_release -a`), Docker CLI 28.2.2 – dostępne tylko stare `docker-compose 1.29.2`, polecenie `docker compose` nie istnieje.
- Python: `python` nie jest zmapowany; dostępny `python3 3.12.3` oraz `pip 24.0`. Skrypty wywołujące `python` wymagają aliasu lub instalacji `python-is-python3`.
- Node toolchain: `node 18.19.1`, `npm 9.2.0`. Lokalne `node_modules` istnieją, ale brak możliwości weryfikacji aktualności pakietów offline.
- `pip list --outdated` i `npm outdated` kończą się błędami sieciowymi (`EAI_AGAIN`, brak DNS do PyPI/npm) – audyt wersji zależy od odblokowania dostępu do rejestrów.

### Co trzeba zaktualizować / „podbić stos”
- Doinstalować Compose v2 (plugin `docker compose`) lub aliasować polecenia z Makefile/dokumentacji na `docker-compose`, aby pipeline Dockera był zgodny z bieżącą składnią.
- Zapewnić alias `python`/`pip` (np. `sudo apt install python-is-python3`) i odświeżyć wirtualne środowiska `.venv` oraz `node_modules`, bo projekt nie był aktualizowany od miesięcy.
- Po odblokowaniu sieci uruchomić `npm outdated`, `npm audit`, `pip list --outdated`, `pip-audit` i zaktualizować kluczowe zależności (`fastapi`, `uvicorn`, `redis`, `celery`, `torch`, `stylelint`, `ollama`, `prometheus-client`, itp.) pod Python 3.12.
- Zweryfikować `requirements*.txt` i `package-lock.json` vs. realne środowisko; możliwe, że wersje (np. `grpcio`, `protobuf`, modele vision/audio) wymagają rewizji przed wdrożeniem nowej funkcji X.
