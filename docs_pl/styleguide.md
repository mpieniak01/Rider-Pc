# Styleguide - Rider-PC Dashboard

Dokumentacja systemu projektowania CSS dla dashboardu Rider-PC.

## Architektura CSS

System CSS jest podzielony na moduły według następującej hierarchii:

```
web/assets/
├── dashboard-common.css     # Główny punkt wejścia (importuje moduły)
├── css/
│   ├── tokens.css          # Tokeny projektowe (kolory, odstępy, typografia)
│   ├── base.css            # Reset i style bazowe elementów
│   ├── layout.css          # Systemy layoutu (grid, flex, strona)
│   ├── components.css      # Komponenty UI (karty, przyciski, pill)
│   ├── utilities.css       # Klasy narzędziowe
│   ├── menu.css            # Komponent menu nawigacyjnego
│   └── footer.css          # Komponent stopki
├── home.css                # Style specyficzne dla strony Home
├── view.css                # Style specyficzne dla strony View
├── control.css             # Style specyficzne dla strony Control
└── ...                     # Inne arkusze stron (<150 linii)
```

## Tokeny projektowe

### Kolory

```css
/* Tła */
--color-bg-primary: #050b12;     /* Główne tło */
--color-bg-secondary: #0d1926;   /* Karty, panele */
--color-bg-surface: #0f2030;     /* Powierzchnie */
--color-bg-elevated: #0b1a27;    /* Elementy wyniesione */

/* Tekst */
--color-fg-primary: #e6eef7;     /* Główny tekst */
--color-fg-secondary: #b7cee3;   /* Tekst pomocniczy */
--color-fg-muted: #93a8c1;       /* Tekst wyciszony */

/* Akcent */
--color-accent: #7ec4ff;         /* Akcent główny */

/* Statusy */
--color-ok: #6de28a;             /* Sukces */
--color-warn: #f0c36d;           /* Ostrzeżenie */
--color-error: #ff8080;          /* Błąd */
--color-off: #b7cee3;            /* Nieaktywny */
```

### Odstępy

```css
--space-xxs: 4px;
--space-xs: 6px;
--space-sm: 8px;
--space-md: 12px;
--space-lg: 16px;
--space-xl: 18px;
--space-xxl: 24px;
--space-xxxl: 40px;
```

### Typografia

```css
--font-size-xs: 12px;
--font-size-sm: 13px;
--font-size-md: 14px;
--font-size-lg: 16px;
--font-size-xl: 18px;
--font-size-xxl: 24px;

--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
```

### Border Radius

```css
--radius-xs: 4px;
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 10px;
--radius-xl: 12px;
--radius-xxl: 16px;
--radius-pill: 999px;
```

## Komponenty

### Karta (c-card)

```html
<article class="c-card">
  <h3 class="c-card__title">Tytuł karty</h3>
  <p class="c-hint">Treść karty...</p>
</article>
```

### Przycisk (c-btn)

```html
<button class="c-btn">Przycisk</button>
<button class="c-btn c-btn-sm">Mały</button>
<button class="c-btn c-btn-primary">Główny</button>
```

### Pill/Badge (c-pill)

```html
<span class="c-pill">Domyślny</span>
<span class="c-pill is-ok">OK</span>
<span class="c-pill is-warn">Ostrzeżenie</span>
<span class="c-pill is-err">Błąd</span>
<span class="c-pill is-off">Wyłączony</span>
```

### Lista klucz-wartość (c-kv)

```html
<div class="c-kv">
  <div>Etykieta</div>
  <div>Wartość</div>
  <div>Inna etykieta</div>
  <div>Inna wartość</div>
</div>
```

### Pasek statusu (c-statusbar)

```html
<div class="c-statusbar">
  <span class="c-pill is-ok">VISION: ON</span>
  <span class="u-sep">•</span>
  <span class="u-muted">mode: tracking</span>
  <span class="u-spacer"></span>
  <span class="footer-version">...</span>
</div>
```

### Spinner

```html
<span class="c-spinner"></span>
<span class="c-spinner c-spinner--lg"></span>
```

## Layouty

### Grid responsywny

```html
<div class="l-grid">
  <div class="c-card">...</div>
  <div class="c-card">...</div>
  <div class="c-card">...</div>
</div>
```

### Wiersz flex

```html
<div class="l-row">
  <span>Element 1</span>
  <span class="u-spacer"></span>
  <button class="c-btn">Akcja</button>
</div>
```

### Stack (kolumna)

```html
<div class="l-stack">
  <div>Element 1</div>
  <div>Element 2</div>
</div>
```

### Panel dwukolumnowy

```html
<div class="panel-row">
  <div class="c-card">Lewy panel</div>
  <div class="c-card">Prawy panel</div>
</div>
```

## Klasy narzędziowe

### Tekst

```html
<span class="u-muted">Wyciszony tekst</span>
<span class="u-accent">Tekst akcentowy</span>
<span class="ok">Sukces</span>
<span class="warn">Ostrzeżenie</span>
<span class="err">Błąd</span>
```

### Marginesy

```html
<div class="u-mt-lg">Margines górny duży</div>
<div class="u-mb-xl">Margines dolny bardzo duży</div>
```

### Flexbox

```html
<div class="u-flex u-items-center u-gap-md">...</div>
<div class="u-flex-between">...</div>
```

## Tworzenie nowej strony

1. Skopiuj szablon `web/layout-page.html`
2. Zmień `data-page="page-name"` na unikalną nazwę
3. Zaktualizuj tytuł i treść
4. Jeśli potrzebne są style specyficzne:
   - Utwórz `web/assets/page-name.css`
   - Utrzymuj plik poniżej **150 linii**
   - Używaj tokenów i istniejących komponentów
   - Dodaj import w HTML

```html
<link rel="stylesheet" href="/web/assets/dashboard-common.css">
<link rel="stylesheet" href="/web/assets/page-name.css">
```

## Kryteria akceptacji

- ✓ Każdy ekran używa tych samych tokenów i komponentów
- ✓ Dedykowane arkusze CSS < 150 linii
- ✓ Menu, stopka, karty wyglądają identycznie na wszystkich stronach
- ✓ Łatwe dodanie nowego ekranu (kopiowanie szablonu)
- ✓ Stylelint w pipeline pilnuje regresji

## Narzędzia

```bash
# Zainstaluj zależności (wymagane przed pierwszym uruchomieniem)
npm install

# Sprawdź styl CSS
npm run lint:css

# Napraw automatycznie problemy ze stylem
npm run lint:css:fix

# Sprawdź rozmiar plików CSS (strony < 150 linii)
npm run css:size

# Za pomocą Makefile
make lint-css   # = npm run lint:css
make css-size   # = npm run css:size
```

## Migracja istniejących stron

### Plan migracji (fazy)

1. **Faza A – podstawowe widoki**: `home.html`, `system.html`, `providers.html`
   - Mało JS, dobre do walidacji layoutu i stylów
   - Rezultat: potwierdzony wygląd kart/statusów

2. **Faza B – widoki sterowania**: `control.html`, `mode.html`, `navigation.html`
   - Więcej interakcji; potrzeba przetestować bindingi JS po zmianie DOM
   - Rezultat: zgodność z nowym szablonem + testy manualne ruchu/trybów

3. **Faza C – pozostałe**: `view.html`, `project.html`, `models.html`, `chat.html`, `google_home.html`
   - Finalne porządki, usunięcie legacy CSS

### Kroki migracji strony

1. **Podmień kontener główny**: `.wrap` → `.layout-main`
2. **Podmień klasy komponentów**: `.card` → `.c-card`, `.pill` → `.c-pill`
3. **Zastosuj modyfikatory stanu**: `.is-ok`, `.is-warn`, `.is-err` zamiast `.ok`, `.warn`, `.err`
4. **Użyj prefiksów utility**: `.u-muted`, `.u-gap-md` zamiast `.muted`, `.gap`
5. **Ogranicz CSS strony**: Utrzymuj plik poniżej 150 linii, tylko unikalne style
6. **Usuń selektory `body[data-page="..."]`**: Użyj klas modyfikujących lub neutralnych nazw

### Legacy class fallbacks

Dla kompatybilności wstecznej plik `dashboard-common.css` zawiera aliasy dla starych klas:

| Klasa legacy | Odpowiednik / Fallback |
|--------------|------------------------|
| `.wrap` | `.layout-main` |
| `.card` | `.c-card` |
| `.pill.ok` | `.c-pill.is-ok` |
| `.btn` | `.c-btn` |
| `.muted` | `.u-muted` |
| `.spinner` | `.c-spinner` |

Pełna lista w `web/assets/css/README.md`.

## Zweryfikowane strony

Status migracji stron dashboardu:

| Strona | Status | Uwagi |
|--------|--------|-------|
| `home.html` | ✅ Kompatybilna | Używa nowych tokenów i fallbacków |
| `control.html` | ✅ Kompatybilna | Panel sterowania działa bez regresji |
| `system.html` | ✅ Kompatybilna | Status sieci i usług renderuje się poprawnie |
| `models.html` | ✅ Kompatybilna | Tabele modeli wyświetlają się prawidłowo |
| `view.html` | ✅ Kompatybilna | Karty i wykresy bez zmian wizualnych |
| `project.html` | ✅ Kompatybilna | Lista issues działa |
| `chat.html` | ✅ Kompatybilna | Interfejs czatu bez regresji |
| `google_home.html` | ✅ Kompatybilna | Siatka urządzeń działa |
| `providers.html` | ⚠️ Legacy | Strona wymieniona w Faza A; status migracji do potwierdzenia |
| `mode.html` | ⚠️ Legacy | Strona wymieniona w Faza B; status migracji do potwierdzenia |
| `navigation.html` | ⚠️ Legacy | Używa utility Tailwind-like; wymaga pełnej migracji |

### Znane różnice

- Spacing może różnić się o ±2px ze względu na ujednolicenie tokenów
- Kolory pozostają zgodne dzięki aliasowi `--bg`, `--fg`, `--accent`
- Animacje i przejścia używają ustandaryzowanych tokenów `--transition-*`
