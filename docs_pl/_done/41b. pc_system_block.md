## Zadanie: Blok „System PC” na mini dashboardzie

> Dotyczy wyłącznie środowiska Rider-PC (FastAPI + frontend). Endpoint **nie** trafia na Rider-Pi – implementujemy go jedynie po stronie panelu PC, aby operator widział parametry hosta PC.

### Zakres
1. Dodać endpoint `GET /status/system-pc` w `status_router`, zwracający lokalne parametry hosta (CPU, load, pamięć, dysk, uptime).
   - Wydzielić helper (np. `pc_client/utils/system_info.py`) z psutil/os-readings.
   - Wynik przechowywać w CacheManagerze (`pc_sysinfo`) z TTL ≈5 s, aby UI nie sondował intensywnie.
2. `web/view.html`:
   - HTML: w sekcji „System PC” dodać wiersze na CPU/MEM/DISK/Uptime.
   - JS: rozdzielić dotychczasowe `refreshPcSystem()` na `refreshPcHealth()` (status live/ready) oraz `refreshPcSystemMetrics()` (dane /status/system-pc).
   - Uaktualnić `renderPcServices` tylko o statusy usług; nowy blok System PC wyświetli liczby analogiczne do bloku „System”.
3. Testy:
   - FastAPI unit test `tests/test_status_router.py` dla `GET /status/system-pc` z mockiem warstwy psutil.
   - E2E smoke (manual) – panel view pokazuje nowe wartości.
4. Dokumentacja:
   - Dopisać wzmiankę w `docs_pl/NOTATKI_REPLIKACJI.md` oraz `docs_pl/_to_do/etap5_testy_i_docs.md` o nowym API i UI.
5. Dependencies:
   - Jeśli korzystamy z `psutil`, dopisać do `requirements.txt` i wspomnieć w README (instalacja).

### Realizacja
- ✅ `requirements(.ci).txt` rozszerzone o `psutil==6.1.0`.
- ✅ Nowy moduł `pc_client/utils/system_info.py` + endpoint `GET /status/system-pc` (cache 5 s) oraz test `tests/test_status_system_pc.py` (mock metryk).
- ✅ `web/view.html`/`view.css` – sekcja „System PC” pokazuje CPU/load/pamięć/dysk/temperaturę/uptime + statusy `/health/*`; lista „Usługi PC” monitoruje panel, Prometheus, Grafanę, Redis.
- ✅ `docs_pl/NOTATKI_REPLIKACJI.md` zaktualizowane o wzmiankę nt. nowego API.
