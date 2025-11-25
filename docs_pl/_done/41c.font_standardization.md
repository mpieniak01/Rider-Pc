## Plan: Standaryzacja czcionek etykiet (Rider-PC + Rider-Pi)

### Cel
Ujednolicić rozmiary i styl czcionek etykiet (nagłówki kart, klucze w układzie `key-value`, ikony statusów) na wszystkich ekranach panelu operatora w obu repozytoriach: `Rider-Pc` oraz `Rider-Pi`.

### Zakres
1. **Analiza aktualnego stanu**
   - Zebrać listę plików CSS/HTML definiujących układy `key-value` i etykiety (control, view, system, navigation, home, chat, google_home, providers).
   - Zidentyfikować zmienne/klasy wspólne (`.c-kv`, `.c-card`, `.c-hint`, `.c-pill`) oraz lokalne.

2. **Projekt standardu**
   - Zaproponować globalne zmienne (np. `--font-label`, `--font-body`, `--font-hint`).
   - Określić zasady: etykiety `key-value` (np. w kaflach „System”, „System PC”, listach usług) jedna wartość (np. 13px), tytuły sekcji 16px, nagłówki 24px.

3. **Implementacja (Rider-PC)**
   - W `web/assets/dashboard-common.css` wprowadzić nowe zmienne + globalne klasy dla etykiet.
   - Przepiąć `view.css`, `control.css`, `system.css`, `home.css`, `google-home.css`, `chat.css` na te klasy.
   - Test: lokalny `make start`, ręczne sprawdzenie ekranów.

4. **Implementacja (Rider-Pi)**
   - Lustrzana zmiana w `Rider-Pi/web/assets/...` (te same zmienne i klasy).
   - Zachować identyczne nazwy, by utrzymać spójność.

5. **Testy / QA**
   - Ruchowe przejście po wszystkich ekranach, weryfikacja, że etykiety są jednakowej wielkości i czytelne.
   - Uzupełnienie `docs_pl/NOTATKI_REPLIKACJI.md` i README o informację o standardzie czcionek.

### Uwagi
- Zmiana dotyka wielu plików CSS; rekomendowane jest etapowanie (najpierw PC, potem Pi) przy zachowaniu tej samej gałęzi (`main`).
- Warto przygotować screenshoty przed/po dla archiwizacji w PR.
