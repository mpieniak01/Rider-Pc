## Etap 5 – Testy i dokumentacja

### Testy
- Dodano `tests/test_logic_endpoints.py`, który weryfikuje lokalne fallbacki `/api/logic/features` oraz `/api/logic/summary` (w tym obecność scenariuszy S0/S3/S4).
- Testy korzystają z `create_app()` i działają w trybie pure-local (bez zdalnego adaptera), co zabezpiecza kontrakt wymagany przez nowy panel scenariuszy.

### Dokumentacja
- `docs_pl/NOTATKI_REPLIKACJI.md` uaktualniono o aktualną strukturę katalogu `web/` (nowe CSS-y i informacja o scaleniu panelu Mode/Providers z `/control`).

### TODO / rekomendacje
- Rozszerzyć testy UI (np. Playwright) o sanity check panelu scenariuszy i odświeżania `/svc`.
- Dopisać checklistę wydania (np. `docs_pl/_to_do/checklist_control.md`) po zakończeniu QA.
