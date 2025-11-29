# Zlecenie: refaktoryzacja CSS/HTML dashboardu Rider-PC

## Kontekst
- Gałąź `copilot/refactor-css-html-dashboard` z PR #84 wprowadza modularny zestaw arkuszy (`css/tokens.css`, `css/base.css`, `css/layout.css`, `css/components.css`, `css/utilities.css`, `css/menu.css`, `css/footer.css`) oraz nowy szablon `web/layout-page.html`, ale nie została wdrożona ze względu na regresje wizualne.
- Plany architektoniczne znajdują się w `docs_pl/_to_do/198_refaktoryzacja_css_html.md` (system design tokens + komponenty) i `docs_pl/_to_do/199_migracja_szablonu_dashboard.md` (migracja istniejących ekranów). To zlecenie ma je przekuć na konkretną implementację.

## Cel
Dostarczyć działający, kompatybilny zestaw styli + szablonów, który można wdrożyć bez psucia istniejących ekranów, oraz przygotować grunt pod kolejne migracje stron.

## Zakres prac dla agenta
1. **Stabilizacja design tokens oraz bazowych plików CSS**
   - Uzupełnić brakujące zmienne (np. `--font-size-body`) i zweryfikować, że wszystkie użyte aliasy mają definicje.
   - Zapewnić, że `dashboard-common.css` importuje moduły, ale nadal dostarcza brakujące klasy legacy (np. `.control-title`, `.panel-row`) dopóki strony nie zostaną zmigrowane.
   - Utrzymać dotychczasowe kolory/odstępy jako wartości domyślne (`:root`).
2. **Mapowanie i fallbacki dla istniejących klas**
   - Dla każdej klasy używanej w aktualnych HTML (`web/*.html`) zapewnić regułę albo alias w nowych modułach. Lista startowa: `.control-status`, `.control-badge`, `.ai-mode-row`, `.ai-mode-actions`, `.cam-frame`, `.motion-btn`, `.svc-select`, `.feature-resource`, `.system-shell`, `.models-shell`, `.project-header`, `data-list`, `.snapshot`, `.status-pill`, `.svc-state-*`, `.svc-desc-*`, `.status-msg`, `.thumb`, `.log-panel`, `.network-card`, itd.
   - Utworzyć tabelę w komentarzu lub krótkim README (`web/assets/README.md`), która opisuje, które klasy są legacy i gdzie znajdują się ich odpowiedniki.
3. **Szablon bazowy i struktura HTML**
   - Utrzymać `web/layout-page.html` jako wzorzec, ale nie wymuszać jego użycia automatycznie. Przygotować mechanizm, który pozwala stopniowo migrować strony (np. dokumentacja + snippet).
   - Zweryfikować `dashboard_menu_template.html` i `dashboard_footer_template.html`, aby korzystały z nowych klas menu/footer, ale pozostawały kompatybilne z dotychczasowym markupiem w stronach.
4. **Narzędzia i kontrola jakości**
   - Dokończyć konfigurację Stylelint (`.stylelintrc.json`, `package.json`) oraz skrypt `scripts/check-css-size.js`; dodać opis uruchamiania do `README` lub `docs_pl/styleguide.md`.
   - Zapewnić, że `Makefile` cele `lint-css` i `css-size` działają w świeżym repo (npm install + node scripts).
5. **Test kompatybilności**
   - Ręcznie (lub poprzez prosty test w Headless Chrome) zweryfikować, że strony `web/home.html`, `web/control.html`, `web/system.html`, `web/models.html` wyglądają jak przed zmianami. W przypadku drobnych różnic (np. spacing ±2px) należy je udokumentować.
   - Dołączyć do opisu PR listę testów oraz screenshoty (jeśli dostępne).

## Kryteria akceptacji
- `npm run lint:css` i `npm run css:size` przechodzą lokalnie.
- `dashboard-common.css` + moduły dają identyczny lub minimalnie różny render ekranów przed migracją; żadna kluczowa sekcja (kamera, tabele usług, statusy) nie traci stylów.
- Legacy klasy mają opisane fallbacki i pozostają dostępne do czasu pełnej migracji (wg planu 199).
- Dokumentacja (`docs_pl/styleguide.md` lub nowy plik) opisuje strukturę modułów CSS, sposób korzystania z tokenów oraz instrukcję migracji strony na nowy szablon.

## Dostarczane artefakty
- Zaktualizowane pliki CSS/HTML (w tym `dashboard-common.css`, `web/assets/css/*`, wszystkie arkusze per-strona).
- Zaktualizowany `docs_pl/styleguide.md` z opisem architektury.
- Notatka w PR (lub osobny `docs_pl/_to_do/xxx`) z listą ekranów zweryfikowanych manualnie oraz znanych różnic.
