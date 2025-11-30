# Inwentaryzacja arkuszy `web/assets/pages/*.css`

| Strona | Arkusz | Kluczowe nadpisania (`--*`) | Główne unikalne komponenty / sekcje | Uwagi do standaryzacji |
| --- | --- | --- | --- | --- |
| `chat.html` | `pages/chat.css` (~147 linii) | `--page-max-width: 980px`, `--page-padding`, `--chat-mine/bot/err` | `.chat-head`, `.status`, `.board` + `.msg.*`, `.compose-row`, `.providers-card` | kandydat na komponenty „chat board” i „provider list” (można współdzielić z innymi widokami voice/AI) |
| `control.html` | `pages/control.css` (~86 linii) | `--page-max-width: 1100px`, `--page-padding`, `--card-*` | `.control-title/status/badge`, `.cam-card`, `.motion-grid` + `.motion-btn`, `.feature-list`, `.svc-table` + `.svc-select`, `.balance-control-row` | logiczny moduł „motion controls” + toolbar usług; docelowo przenieść część do komponentów |
| `google_home.html` | `pages/google-home.css` (~129 linii) | `--page-max-width: 1100px`, `--card-radius: var(--radius-xxl)` | `.btn-auth`, `.device-grid` + `.device-card`, `.control-row`, warianty `.c-status-msg` | podobne do integracji chat/voice – warto spiąć w wspólny template „device control” |
| `home.html` | `pages/home.css` (~46 linii) | `--page-max-width: 900px`, `--card-*` | tylko `c-data-list` i `c-code-block` w wariancie – wzorcowy przykład minimalnego arkusza | brak działań |
| `models.html` | `pages/models.css` (~143 linii) | brak nowych `--*`, własny kontener `.models-shell` | `.status-line`, `.models-section`, `.provider-card`, `.active-model-card`, `.model-card`, `.installed-models-table`, `.category-badge` | duplikaty struktur kart/sekcji – do rozważenia komponenty „provider card”, „installed table” |
| `navigation.html` | `pages/navigation.css` (~61 linii) | `--page-padding` | `.nav-status-dot`, `#canvas-container`, wariant `.c-legend__dot` | bardzo lekki – jedyne customy to status i płótno na mapę |
| `project.html` | `pages/project.css` (~115 linii) | `--page-max-width: 1100px`, `--grid-min: 320px` | `.project-header`, `.issues-grid`, `.issue-card`, `.progress-*`, `.toast`, `.modal-*` | toast + modal warto wynieść do wspólnych komponentów wizualnych |
| `system.html` | `pages/system.css` (~153 linii) | brak nowych `--*`, `.system-shell` (max 1200px) | `.location-block`, `.service-node`, `.status-pill`, `.network-card`, `.log-panel` | największy arkusz; priorytet przy odbudowie komponentów (node, network card) |
| `view.html` | `pages/view.css` (~149 linii) | `--muted`, `--accent`, `--grid-gap`, `--label/value-color` | `.cam-badge`, `.pc-service-list`, `.pc-status`, `.pc-service-dot`, warianty legend | po redukcji 148 linii; czeka na wydzielenie legend/kafla kamery |

> Stan na 2025-11-28 – wszystkie arkusze mieszczą się w limicie 150 linii kodu (`npm run css:size`).
