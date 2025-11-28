# Finalizacja migracji CSS dashboardu Rider-PC (2025-11)

## Zakres
- wszystkie widoki `web/*.html` korzystają z `web/templates/dashboard_base.html` i klas `.page-*`.
- per-page CSS znajduje się w `web/assets/pages/*.css` (każdy < 150 linii kodu, raport `npm run css:size`).
- `dashboard-common.css` zawiera wyłącznie importy modułów + aliasy `.page-title`, `.page-title-text`, `.brand-accent`.
- nowe narzędzia: `npm run lint:css`, `npm run css:size`, `npm run css:audit` (`logs/css_audit_summary.json`).

## Walidacja
1. `npm install`
2. `npm run lint:css` / `npm run lint:css:fix`
3. `npm run css:size`
4. `./.venv/bin/python scripts/css_audit.py` (lub `npm run css:audit` na WSL2) – screenshoty w `logs/css_audit/*.png`.

## Notatki
- przy pracy na WSL, jeśli `npm run css:audit` nie widzi `.venv`, uruchom `./.venv/bin/python scripts/css_audit.py`.
- raport statycznych selektorów: `logs/css_static_usage.json`.
- dalsze czyszczenie: obserwować pliki `pages/models.css`, `pages/system.css`, `pages/view.css` (najwięcej nieużywanych klas wg raportu).
