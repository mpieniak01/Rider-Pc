## Etap 2 – Backend / API (feature/control-sync-plan)

### Zrealizowany zakres
- Dodano moduł `pc_client/api/sse_manager.py`, który centralizuje buforowanie, subskrypcje oraz retry/backoff dla `/events`. FastAPI server inicjalizuje go w `app.state`, a `control_router` wykorzystuje go zarówno przy publikowaniu zdarzeń, jak i przy obsłudze SSE.
- Rozszerzono `RestAdapter` o metody `get_logic_features`, `get_logic_summary` oraz alias `get_svc_diagnostics`.
- W `control_router` udostępniono nowe endpointy proxy `GET /api/logic/features` i `GET /api/logic/summary` z lokalnym fallbackiem bazującym na stanie `control_state` i liście usług.
- Lokalne fallbacki korzystają z prostych blueprintów funkcji (manual, tracking, recon) oraz streszczają status usług (`services_total`, `services_active`, `status`).
- Usunięto `event_subscribers` z `app.state` na rzecz `SseManager`, co upraszcza routing i poprawia odporność na błędy SSE.

### Następne kroki
- Przenieść panel scenariuszy do frontendowego `web/control` i wykorzystać nowe endpointy.
- Zaimplementować degradację UI + komunikaty offline opisane w planie (Faza 3).
