## Etap 3 – Frontend (web/control)

### Zakres wdrożony
- Zaktualizowano `web/control.html`, synchronizując go z wariantem Rider-Pi:
  - dodano panel scenariuszy/targetów z auto-odświeżaniem i akcjami start/stop,
  - przerobiono karty funkcji (Zero/Tracking/Rekon) na nową logikę, w tym obsługę selektora trybów oraz statusów,
  - wprowadzono nowy układ diagnostyki (tabela usług w `<details>`, rozbudowana kolejka ruchu z powodem i timestamptem, komunikaty telemetryczne),
  - uproszczono obsługę SSE i refreshów kamery, eliminując ręczne guardy `remoteOnline`,
  - dostosowano UI zasobów, logów i providerów do nowego interfejsu Rider-Pi.

### Do potwierdzenia / dalsze kroki
- Testy manualne UI (scenariusze, SSE, kolejka ruchu) po stronie PC.
- Ewentualne poprawki tłumaczeń/CSS, jeśli w Rider-Pi pojawiły się dodatkowe pliki.
