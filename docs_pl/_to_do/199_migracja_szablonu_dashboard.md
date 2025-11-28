# Migracja ekranów dashboardu do wspólnego szablonu

## Kontekst i cel
- Aktualny plan refaktoryzacji CSS/HTML (plik 198_refaktoryzacja_css_html.md) skupia się na ujednoliceniu stylów, ale wymaga osobnego trackingu migracji istniejących stron na nowy szablon.
- Chcemy zdefiniować bazowy layout (`dashboard_base.html`) i przenieść wszystkie podstrony (`web/*.html`) tak, by korzystały z tych samych komponentów, struktur i importów.

## Zakres prac
1. Zaprojektować plik `web/templates/dashboard_base.html` (lub równoważny include) z następującymi elementami:
   - `<body data-page="..." class="page page-...">`
   - `<header class="layout-header">` z miejscem na menu osadzane poprzez `data-dashboard-menu-target`.
   - `<main class="layout-main">` dzielone na `<section class="surface">` i opcjonalne `<aside>`.
   - `<footer>` z kontenerem na `data-dashboard-footer-target`.
   - Sloty na moduły JS (`<script type="module" src="..."></script>`), które strony będą wypełniać.
2. Ujednolicić markup poszczególnych sekcji: nagłówki (`<hgroup>`), kolekcje danych (`<section class="surface surface--table">`), formularze (`<form class="form-grid">`), moduły mediów (`<div class="media-frame">`).
3. Przygotować utilities do szybkiego pozycjonowania (np. `.cluster`, `.stack`, `.flow`, `.auto-grid`) aby zastąpić lokalne klasy (`.panel-row`, `.motion-grid`).

## Checklist migracyjny dla każdej strony
- [ ] Podpiąć strukturę z `dashboard_base.html` zamiast lokalnego `<div class="wrap">`.
- [ ] Zamienić stare klasy layoutowe na komponenty/utility (`.surface`, `.cluster`, `.form-field`).
- [ ] Zredukować arkusz per-strona do wariantów (max ~150 linii) i upewnić się, że nie zawiera selektorów `body[data-page=...]`.
- [ ] Zweryfikować, że wspólne komponenty (`.c-card`, `.c-pill`, `.c-statusbar`, `c-data-list`) renderują się poprawnie.
- [ ] Zaktualizować komentarz w nagłówku HTML z informacją o migracji + dodać wpis do changelog.
- [ ] Wykonać manualny smoke test i porównać screenshoty przed/po (narzędzie Playwright lub ręcznie).

## Harmonogram migracji (fazy)
1. **Faza A – podstawowe widoki**: `home.html`, `system.html`, `providers.html`.
   - Mało JS, dobre do walidacji layoutu i stylów.
   - Rezultat: potwierdzony wygląd kart/statusów.
2. **Faza B – widoki sterowania**: `control.html`, `mode.html`, `navigation.html`.
   - Więcej interakcji; potrzeba przetestować bindingi JS po zmianie DOM.
   - Rezultat: zgodność z nowym szablonem + testy manualne ruchu/trybów.
3. **Faza C – pozostałe i specjalne**: `view.html`, `project.html`, `models.html`, `chat.html`, `google_home.html`.
   - Finalne porządki, w tym usunięcie legacy CSS i potwierdzenie, że lekkie strony (chat/google) używają tylko base + małych wariantów.

## Kryteria zakończenia migracji
- Wszystkie strony używają `dashboard_base.html` i wspólnych komponentów; brak unikalnych struktur menu/stopki.
- Per‑page CSS nie przekracza ~150 linii i składa się głównie z modyfikatorów.
- Brak selektorów `body[data-page=...]`; w zamian klasy `.page-...` lub modyfikatory komponentów.
- Zaktualizowany changelog i dokumentacja (w tym przewodnik jak dodać nową stronę w oparciu o szablon).
- Zespół potwierdził wizualnie zmianę (screenshoty przed/po) i brak regresji funkcjonalnych.

## Ryzyka i zależności
- Zależność od ukończenia design tokens (`web/assets/css/tokens.css`) i komponentów współdzielonych.
- Możliwe konflikty z istniejącym JS, który wybiera elementy po starych klasach; wymaga analizy przed migracją.
- Potrzeba zsynchronizowania zmian z zespołem backend (np. endpointy `fetch` w JS) aby uniknąć deployu połowy stron.
