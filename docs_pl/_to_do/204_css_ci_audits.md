# CI: CSS lint/size/audit

## Kontekst
- Lokalnie mamy komplet narzędzi (`npm run lint:css`, `npm run css:size`, `npm run css:audit`) i uruchamiamy je ręcznie przy refaktoryzacjach.
- Nie zostały jeszcze wpięte w pipeline GitHub Actions (celowo — najpierw chcieliśmy ustabilizować makiety i coverage).

## Zadanie
- [ ] Przygotować job w workflow (np. `dashboard-ui.yml`), który dla PR-ów UI:
  - instaluje zależności front-end (`npm ci`);
  - uruchamia kolejno `npm run lint:css`, `npm run css:size` i `npm run css:audit` w trybie headless (logi + artefakty screenshotów).
- [ ] Zabezpieczyć pipeline przed flaky przypadkami (wykorzystać `TEST_MODE`, ustawić `PLAYWRIGHT_BROWSERS_PATH=0` + cache).
- [ ] Dołączyć do summary PR krótkie zestawienie (liczba linii CSS, coverage <80 %) – można parsować `logs/css_audit_summary.json`.

## Notatki
- Docelowo job ma działać jako smoke test (nie blokujemy release, ale wymagamy przejścia przed merge).
- Dodatkowe makiety / seeded data są już gotowe (MockRestAdapter + `css_audit.py`), więc pipeline operuje na tych samych danych co developerzy.
