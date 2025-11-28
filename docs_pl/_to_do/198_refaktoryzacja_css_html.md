# Refaktoryzacja CSS/HTML – dashboard Rider-PC

## Kontekst i cele
- Każda z podstron (`web/*.html`) posiada obecnie własny arkusz (`web/assets/*.css`) z dużą liczbą dedykowanych klas (np. `body[data-page="control"] .panel-row`). Powoduje to brak spójności, nadmiar kodu i trudność w wdrażaniu nowych ekranów.
- `web/assets/dashboard-common.css` zawiera zalążek wspólnych komponentów (`.c-card`, `.c-pill`, layouty `l-row`, `l-grid`), ale nie obejmuje całego systemu wizualnego.
- Celem jest ujednolicenie wyglądu i struktury HTML między ekranami poprzez utworzenie spójnego systemu design tokens + komponenty + layouty + utilsy, a następnie uproszczenie per‑page CSS wyłącznie do drobnych wariantów.

## Plan działania

### 1. Audyt i katalog elementów UI
1.1. Zmapować elementy wspólne i unikalne na podstawie `web/assets/*.css` i `web/*.html` (karty, listy danych, status bary, panele formularzy, siatki przycisków, listy usług, listy modeli).
1.2. Zanotować wszystkie zmienne CSS i wartości stałe (kolory, odstępy, promienie, cienie) używane w arkuszach per‑strona – posłużą do stworzenia katalogu design tokens.
1.3. Uporządkować powtarzające się layouty (np. `.panel-row` vs `.l-row`, różne warianty `.wrap`, `.section`) i określić, gdzie potrzebne są nowe utility (np. `.cluster`, `.flow`, `.pad-lg`).

### 2. Design tokens i warstwa bazowa
2.1. Wydzielić plik `web/assets/css/tokens.css` z definicją zmiennych (`:root { --color-bg-1; ... }`) i tematów (np. `body[data-theme="dark"]`).
2.2. Doprecyzować typografię, siatkę odstępów, promienie, wagi fontów, ustandaryzować nazewnictwo (np. `--space-xxs`, `--space-lg`, `--font-ui-sm`).
2.3. Zaktualizować `dashboard-common.css`, aby korzystał wyłącznie z nowych tokenów oraz importował `tokens.css`; usunąć duplikaty wartości zakodowanych na stałe.
2.4. Przygotować krótką dokumentację tokenów (tabela w README / Storybook-lite) dla deweloperów frontu.

### 3. Architektura arkuszy i moduły wspólne
3.1. Rozdzielić wspólne style na moduły (np. `base.css`, `layout.css`, `components.css`, `utilities.css`) + pliki per-komponent, ładowane przez bundler lub importy CSS.
3.2. Zaprojektować standardowe layouty (`.layout-page`, `.layout-main`, `.section`, `.surface`, `.cluster`, `.stack`, `.auto-grid`) i ujednolicić markup wokół `<main>`/`<section>` zamiast luźnych `<div class="wrap">`.
3.3. Uporządkować komponenty atomowe/molekularne: przyciski, badge/pills, listy `kv`, `statusbar`, tabele, formularze, obrazki (`c-thumb`, `cam-card`). Zapewnić konfigurowalne warianty poprzez klasy modyfikujące (`.is-warn`, `.is-compact`, `.has-divider`).
3.4. Zdefiniować utilities (np. `.u-muted`, `.u-flex-between`, `.u-gap-sm`) i zastąpić nimi ad-hoc klasy per-strona.

### 4. Refaktoryzacja HTML (wspólne fragmenty)
4.1. Wykorzystać `web/dashboard_menu_template.html` i `web/dashboard_footer_template.html` jako jedyne źródła dla menu/stopki, rozszerzając je o nowe klasy/layout aby nie powielać markup w stronach (`data-dashboard-menu-target`, `data-dashboard-footer-target`).
4.2. W każdej stronie wprowadzić ustandaryzowany szkielet: `<body data-page="...">`, `<header class="layout-header">`, `<main class="layout-main">`, `<section class="surface">` itd. Zminimalizuje to różnice między plikami HTML.
4.3. Zamienić niestandardowe klasy (np. `.panel-row`, `.feature-row`, `.model-card`) na komponenty katalogowe, zachowując identyfikatory `id` tylko tam, gdzie wymaga tego JS.
4.4. Uporządkować semantykę nagłówków (`h1`..`h3`), list (`<dl>` dla par klucz-wartość zamiast `div.c-kv` gdy to możliwe), formularzy (`<label>`, `<fieldset>`), aby ułatwić stylowanie globalnymi regułami.

### 5. Migracja poszczególnych ekranów na system komponentów
| Strona | Aktualne bolączki | Cel refaktoryzacji |
| --- | --- | --- |
| `control.html` + `assets/control.css` | wiele zagnieżdżonych klas `body[data-page="control"] ...`, własne definicje kart, gridów ruchu, kontrolek formularzy | wykorzystać `.surface`, `.cluster`, `.form-field`, `.control-grid`; zredukować CSS do definicji specyficznych elementów (np. układ joysticka) i przenieść resztę do komponentów wspólnych |
| `home.html` + `assets/home.css` | duplikaty `c-card`, `c-kv`, brak semantyki listy statusów | zastąpić `data-list` nowym komponentem `c-data-list`, usunąć niepotrzebne style, użyć komponentu `c-code-block` dla `pre` |
| `system.html`, `providers.html`, `models.html`, `project.html` | powtarzalne listy kart, tablice statusów, filtry | znormalizować markup listy przez `c-collection` + `c-collection__item`; przenieść wspólne style tabelaryczne do modułu `tables.css`; zdefiniować warianty badge dla stanów usług |
| `view.html`, `mode.html`, `navigation.html` | specjalne układy (podglądy, matryce elementów) stylowane lokalnie | opisać jako rozszerzenia layoutów (`.layout-split`, `.layout-board`) i komponentów mediów (`.media-frame`, `.media-actions`) |
| `chat.html`, `google_home.html` | proste strony, ale korzystają z innych zestawów kolorów/typografii | po migracji powinny importować tylko `base + components` + 1 mały plik wariantowy (np. `chat.css` < 150 linii) |

### 6. Sprzątanie i kontrola długu CSS
6.1. Po migracji stron usunąć zbędne klasy `body[data-page]` i zastąpić je neutralnymi modyfikatorami (`.page-control`).
6.2. Użyć narzędzi (np. `rg`/`csstree`/`stylelint --report-unused-disable-directives`) do wykrycia nieużywanych selektorów i wartości; wygenerować raport z listą do usunięcia.
6.3. Wprowadzić Stylelint/Prettier dla CSS + HTML (konfiguracja w `package.json` lub `pyproject` jeśli istnieje bundler) oraz CI check dla wielkości arkuszy.
6.4. Dodać testy wizualne w podstawowej formie (np. Percy/Playwright screenshot lub choćby `npm script` renderujący strony w headless Chrome i porównujący rozmiary CSS).

### 7. Dokumentacja i wdrożenie
7.1. Przygotować mini „UI kit” w `docs_pl` (np. `styleguide.md` + statyczna `styleguide.html`) z przykładami komponentów i klas pomocniczych.
7.2. Opisać proces dodawania nowej strony: które pliki importować, jak nazywać klasy, gdzie dopisywać warianty.
7.3. Zaplanować rollout: migracja stron w porcjach (np. `home + system`, potem `control`, potem reszta), każdej zmianie towarzyszy test manualny i screenshoty referencyjne.
7.4. Po wdrożeniu monitorować logi frontu oraz feedback UX – zebrać listę poprawek dla ewentualnej iteracji 2 (np. jasny motyw, responsywne usprawnienia).
7.5 Weryfikacja i modernizacja istniejących testów, w tym audyt i aktualizacja testów E2E w odpowiedzi na zmiany w selektorach i strukturze DOM.

## Kryteria akceptacji
- Każdy ekran korzysta z tych samych tokenów, layoutów i komponentów, a dedykowane arkusze zawierają wyłącznie logikę unikatową dla danej funkcji (< ~150 linii na stronę).
- Menu, stopka, karty, listy statusów, przyciski i badge wyglądają identycznie na wszystkich stronach i są konfigurowane przez klasy modyfikujące.
- Łatwość dodania nowego ekranu: wystarczy skopiować szablon `layout-page.html`, przypisać klasy komponentów i ewentualnie dopisać kilka reguł.
- Stylelint + testy wizualne w pipeline pilnują regresji oraz wielkości CSS.
- Komponenty i layouty są zgodne ze standardami dostępności (np. WCAG 2.1 AA) i przetestowane pod kątem nawigacji klawiaturą oraz działania z czytnikami ekranu.
