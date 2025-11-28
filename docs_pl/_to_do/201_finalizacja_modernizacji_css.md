# Finalizacja przejścia na nowe style dashboardu

## Dlaczego powstał ten dokument
Mamy już nowy system styli (`web/assets/css/*`) i wspólny szablon, ale w repo wciąż żyją stare arkusze per‑strona i selektory `body[data-page]`. Celem tego planu jest zamknięcie migracji: doprowadzenie do sytuacji, w której wszystkie ekrany korzystają wyłącznie z modularnych styli, a katalog `web/assets` nie zawiera martwych/zdublowanych plików.

## Etapy końcowe

### 1. Inwentaryzacja styli
- [x] Wygenerować listę wszystkich plików CSS: `ls web/assets/*.css` + `ls web/assets/css/*.css`.
- [x] Dla każdego pliku wypisać (w tabeli) czy jest:
  - **Core** (moduły `css/`),
  - **Per-page aktywny** (np. `system.css`),
  - **Legacy/martwy** (brak importu w HTML/JS).
- [x] Zanotować, które strony nadal importują `body[data-page]` i ile linii ma każdy arkusz (orientacyjnie `wc -l`).

#### Status 1. (2025-03-??)

| Plik | Linijki | Klasa | Importy |
| --- | --- | --- | --- |
| `web/assets/css/tokens.css` | core | ✔ | importowany przez `dashboard-common.css` |
| `web/assets/css/base.css` | core | ✔ | jw. |
| `web/assets/css/layout.css` | core | ✔ | jw. |
| `web/assets/css/components.css` | core | ✔ | jw. |
| `web/assets/css/utilities.css` | core | ✔ | jw. |
| `web/assets/css/menu.css` | core | ✔ | jw. |
| `web/assets/css/footer.css` | core | ✔ | jw. |
| `web/assets/home.css` | 45 | per-page (aktywny) | `home.html`, `google_home.html` |
| `web/assets/system.css` | 149 | per-page (aktywny) | `system.html` |
| `web/assets/view.css` | 163 | per-page (aktywny) | `view.html` |
| `web/assets/control.css` | 66 | per-page (aktywny) | `control.html` |
| `web/assets/navigation.css` | 60 | per-page (aktywny) | `navigation.html` |
| `web/assets/models.css` | 143 | per-page (aktywny) | `models.html` |
| `web/assets/project.css` | 115 | per-page (aktywny) | `project.html` |
| `web/assets/google-home.css` | 128 | per-page (aktywny) | `google_home.html` |
| `web/assets/chat.css` | 146 | per-page (aktywny) | `chat.html` |
| `web/assets/dashboard-common.css` | 200 | glue (legacy aliasy + importy) | wszystkie strony |

Wszystkie pliki z `web/assets/*.css` są wciąż importowane – brak „martwych” arkuszy, ale każdy poza `dashboard-common.css` powinien zostać przeniesiony do docelowego katalogu `pages/` i zredukowany do wariantów. Żadne HTML nie zostało jeszcze przełączone z `body[data-page=\"...\"]` na `.page-*`.

### 2. Pokrycie selektorów
- [x] Na lokalnym stacku uruchomić analizę (tymczasowo skrypt `scripts/css_static_usage.py` – statyczne porównanie klas/ID względem HTML).
- [ ] (docelowo) uruchomić pełne DevTools/Playwright CSS coverage i przeprocesować raport.
- [x] Wyniki opisać w `_to_do`/`styleguide` i dołączyć do PR jako referencję.

#### Przygotowanie do 2.
- lokalny stack startujemy `make start` (panel 8080) → potem w Chrome/Edge `Ctrl+Shift+P` → „Show Coverage”.
- skrypt Playwright (do dopisania) powinien przejść kolejno `/web/home.html`, `/web/system.html`, `/web/control.html`, `/web/view.html`, `/web/navigation.html`, `/web/models.html`, `/web/project.html`, `/web/chat.html`, `/web/google_home.html`. Każdy run: `page.goto("http://localhost:8080/web/...")`, screenshot do `tmp/css-audit`.
- listę klas dynamicznych do whitelisty już mamy częściowo: `is-*`, `has-*`, `status-*`, `svc-*`, `nav-status-*`, `c-pill`, `c-legend`, `spinner`. Po coverage należy sprawdzić czy coś jeszcze się pojawia (zwłaszcza id generowane w JS).

#### Wynik analizy statycznej (2025-03-??)
Skrypt: `.venv/bin/python scripts/css_static_usage.py` (porównuje definicje klas/ID w CSS z użyciem w `web/*.html`). Ograniczenia: nie wykrywa selektorów dynamicznych ani złożonych (np. `.c-card > .foo`), ale wskazuje gdzie jest największy nadmiar.

| Stylesheet | Klasy (def.) | Klasy (użyte) | ID (def.) | ID (użyte) | Uwagi |
| --- | --- | --- | --- | --- | --- |
| `assets/chat.css` | 17 | 9 | 5 | 0 | sporo nieużywanych – zweryfikować JS chat |
| `assets/control.css` | 28 | 23 | 7 | 1 | większość używana |
| `assets/dashboard-common.css` | 41 | 17 | 2 | 0 | najwięcej legacy aliasów |
| `assets/google-home.css` | 13 | 10 | 8 | 0 | ID prawdopodobnie z JS |
| `assets/home.css` | 5 | 5 | 2 | 0 | czysty |
| `assets/models.css` | 65 | 34 | 8 | 0 | ~50% selektorów do czyszczenia |
| `assets/navigation.css` | 8 | 4 | 4 | 1 | stare klasy layoutowe |
| `assets/project.css` | 44 | 20 | 14 | 1 | jw. |
| `assets/system.css` | 63 | 25 | 23 | 4 | największy dług (statusy/usługi) |
| `assets/view.css` | 26 | 15 | 16 | 0 | ID generowane przez JS? sprawdzić |

JSON z wynikami: `logs/css_static_usage.json`. Te dane posłużą do przygotowania listy selektorów do usunięcia lub przeniesienia do wspólnych modułów.

### 3. Uprzątnięcie per-page CSS
- [x] Każdy arkusz per-strona przenieść do folderu `web/assets/pages/` (łatwiej kontrolować co zostało).
- [x] W HTML zastąpić `body[data-page="x"]` klasą `.page-x` i korzystać z modułów (`tokens`, `components`).
- [ ] Zmniejszyć pliki per-strona do max 120–150 linii pozostawiając tylko warianty (np. kolory, specyficzne układy).
- [ ] Po migracji pary `HTML + CSS` odhaczyć na checkliście (np. tabela w tym pliku z kolumnami: „Strona”, „Czy używa tylko modułów?”, „Czy CSS < 150 linii?”, „Data review”).

| Strona / CSS | Status | Linijki / Notatki |
| --- | --- | --- |
| `chat.html` / `pages/chat.css` | ✅ | 146 linii (TTS layout, mieszczą się w limicie) |
| `control.html` / `pages/control.css` | ✅ | 83 linii; zawiera przeniesione klasy `.control-status`, `.motion-btn`, `.svc-select` |
| `google_home.html` / `pages/google-home.css` | ✅ | 128 linii |
| `home.html` / `pages/home.css` | ✅ | 45 linii |
| `models.html` / `pages/models.css` | ✅ | 142 linii (do dalszego odchudzania selektorów `provider-*` gdy JS zostanie uproszczony) |
| `navigation.html` / `pages/navigation.css` | ✅ | 60 linii |
| `project.html` / `pages/project.css` | ✅ | 114 linii |
| `system.html` / `pages/system.css` | ✅ | 148 linii (ok, ale warto docelowo <140) |
| `view.html` / `pages/view.css` | ✅ | 148 linii po redukcji selektorów; do dalszej obserwacji (sporo klas dynamicznych) |

**Notatki do etapu 3:** unikalne klasy z `dashboard-common.css` (np. `.control-status`, `.control-badge`, `.motion-btn`, `.svc-select`, `.feature-resource`) zostały przeniesione do `pages/control.css`; globalny arkusz zawiera już tylko importy + ogólne komponenty (`.page-title`, `.brand-accent`). `dashboard-common.css` ma obecnie 55 linii.

### 4. Usunięcie legacy w `dashboard-common.css`
- [x] Po potwierdzeniu, że wszystkie strony są na `.page-*`, usunąć fallbacki typu `.control-title`, `.ai-mode-row`, `.system-shell` itp. (dopisać listę w PR, żeby UX mógł zweryfikować).
- [x] Zredukować `dashboard-common.css` do samego `@import` + ewentualnie drobnych aliasów (`.page-title`, `.page-title-text`, `.brand-accent`).

`dashboard-common.css` zawiera teraz wyłącznie `@import` modułów oraz uniwersalne drobiazgi: `.page-title`, `.page-title-text`, `.brand-accent`. Wszystkie dawne komponenty per-strona (`control-status`, `motion-btn`, `system-shell`, `snapshot`, `network-card` itd.) przeniesiono do odpowiadających plików w `web/assets/pages/`.

### 5. Walidacja i CI
- [x] Dodać skrypt `npm run css:audit`, który odpala Playwright (headless) i generuje raport screenshotów + coverage.
- [x] Zweryfikować `npm run lint:css` i `npm run css:size` (wymagane `npm install`; raport w logach powyżej – wszystkie arkusze ≤150 linii).
- [ ] (NIE REALIZUJEMY w tej iteracji) W pipeline (GitHub Actions) dorzucić kroki: `npm run lint:css`, `npm run css:size`, `npm run css:audit` (przynajmniej smoke mode).
- [ ] (NIE REALIZUJEMY teraz) Przygotować checklistę testów manualnych: topowe przeglądarki, rozdzielczości mobilne/desktop, tryb ciemny (obecny) i ewentualny jasny.

`npm run css:audit` -> `.venv/bin/python scripts/css_audit.py`. (Na WSL, jeżeli `npm` odpala się w kontekście Windows/UNC i nie widzi `.venv`, uruchom po prostu `./.venv/bin/python scripts/css_audit.py` — efekt jest ten sam). Skrypt:
- wykonuje screenshoty (`logs/css_audit/*.png`) dla `/web/home.html`, `/system.html`, …, `/google_home.html`;
- odpala `scripts/css_static_usage.py` i zapisuje raport do `logs/css_static_usage.json`;
- generuje zbiorczy `logs/css_audit_summary.json`.

Na tym środowisku Playwright wymaga uruchomionej lokalnej usługi (`make start`). Polecenie `npm run css:audit` może zgłaszać ostrzeżenie „WSL 1” (brak Node instalacji systemowej), ale same screenshoty można uzyskać przez bezpośrednie `./.venv/bin/python scripts/css_audit.py`.

### 6. Dokumentacja końcowa
- [x] Uzupełnić `docs_pl/styleguide.md` o aktualny status (sekcja o `web/assets/pages`, komendy lint/size/audit i checklistę manualną).
- [x] Opisać w `docs_pl/_done/201_css_migracja_final.md` kiedy stary system został wygaszony i jakie kroki należy wykonać przy ewentualnym backporcie (pełni rolę changeloga dla migracji CSS).
- [x] Sporządzić szczegółową inwentaryzację arkuszy `pages/*.css` (pl. `docs_pl/_done/202_inwentaryzacja_css_pages.md`).

## Kryteria „Done”
1. W katalogu `web/assets` pozostają tylko: `css/`, `dashboard-common.css`, `pages/*.css` (maks. 150 linii każdy), `menu.js`, `footer.js`, `i18n.js`, `icons/`.
2. Żadne HTML nie używa `body[data-page]`; wszystkie czerpią klasy `.page-*`/`.layout-*` z `components/layout`.
3. Coverage raportuje <5% nieużytego CSS w modułach; per-page CSS ma <10% nieużytych selektorów.
4. Stylelint + `css:size` + `css:audit` przechodzą w CI, a wynik Playwrighta (screenshoty) jest załączany do PR.
5. Dokumentacja w `docs_pl/styleguide.md` i `_to_do` opisuje nowy workflow; stary plan (198/199) można oznaczyć jako zrealizowany.

## Ryzyka i uwagi
- Klasy generowane dynamicznie przez JS (np. `is-active`, `status-*`) muszą być uwzględnione w whitelistach PurgeCSS/Playwright – w przeciwnym wypadku usuniemy potrzebny CSS.
- Zanim usuniemy fallbacki z `dashboard-common.css`, trzeba zrobić smoke test wszystkich stron hostowanych na Rider-Pi i w środowiskach użytkowników.
- Jeśli w międzyczasie pojawi się tryb jasny, należy go oprzeć na tokenach (np. `data-theme="light"`) i pobierać kolory z `tokens.css` – nie dokładamy kolejnego „legacy” zestawu.

> Ten plik opisuje wyłącznie kroki organizacyjne (bez kodowania). Po zatwierdzeniu można rozbić go na konkretne zadania (np. ticket per strona, ticket per moduł).
