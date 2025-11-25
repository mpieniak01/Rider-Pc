## Etap 4 – Pozostałe widoki web

### Co zostało przeniesione
- Zastąpiono `navigation.html`, `system.html`, `view.html`, `home.html`, `chat.html` i `google_home.html` wersjami z Rider-Pi, aby UI i skrypty były spójne (Tailwindowe wizualizacje nawigacji, nowy layout statusów, odświeżone karty Google Home/Chat).
- Wymieniono katalog `web/assets` na wersję z Rider-Pi (CSS-y `navigation.css`, `view.css`, `system.css`, `home.css`, `chat.css`, `google-home.css`, ujednolicone `dashboard-common.css`, `i18n.js`, `menu.js`), usuwając przestarzałe `mode.css`/`mode.js`.
- Menu (`dashboard_menu_template.html`) nie pokazuje już zakładki „Tryb”; `mode.html` i `providers.html` stały się prostymi stronami przekierowującymi do `/control`, bo provider/AI mode panel funkcjonuje teraz w głównym ekranie.

### Uwagi / TODO
- Wymaga smoke testu UI (ładowanie zasobów, nowe style).
- Jeżeli backend Rider-PC nie obsługuje jeszcze `/ws/navigation`, należy odnotować ograniczenie w dokumentacji/systemie backlogowym.
