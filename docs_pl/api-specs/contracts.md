# Kontrakty Rider-PC i odbiór danych Pi

Rider-PC używa [standardu Rider-Pi](https://github.com/mpieniak01/Rider-Pi/blob/main/docs_pl/api-specs/contracts.md). Koperta HTTP ma envelope_version=1, a domeny safety=1 oraz catalog/tasks/services=2 zachowują niezależne wersje. Każdy istniejący endpoint i odbiorca zachowuje dane oraz funkcję; poniższy manifest jest kryterium kompletności panelu.

## Odpowiedź i proxy

Na istniejących adresach nowy klient żąda `Accept: application/vnd.rider.api+json;version=1`. Odpowiedź zawiera meta, ok, data, error, operation. Brak negocjacji otrzymuje projekcję legacy w okresie aktualizacji. Nie powielamy całego payloadu w dwóch formatach.

RestAdapter jest jedyną granicą negocjacji i rozpakowania danych Pi. Zachowuje domain contract_id/version, host/source, pierwotne observed_at i jakość; osobne meta.transport zapisuje czas odbioru, próby i status upstream. Upstream 202 pozostaje pending, a 4xx/5xx zachowuje status i konkretny kod błędu. Timeout oznacza unknown bez automatycznej powtórki.

Polecenie aktuatora zachowuje oryginalne generation, seq, source, request_id, ts i ttl_ms. Odczyt wersji/zdolności może poprzedzać jawne polecenie, ale nie tworzy nowej zgody ani generacji. Przy nieznanym lub nieobsługiwanym standardzie mutacja jest odrzucona. Zwykłe GET nie rozpoczyna ruchu, kamer, ładowania modeli ani operacji chmurowej.

Źródła lokalne PC używają tej samej koperty i własnego host/source/time. Błąd Pi nie unieważnia niezależnych danych PC. Zachowane rodziny lokalne to rider.network, rider.mcp, rider.project, rider.knowledge i rider.assistant.

## Pomiary i gotowość

Bateria Pi w kanonicznym sensor_quality.sensors.battery ma unit=ratio w zakresie 0..1. Starsze REST battery_pct jest procentem: 1 oznacza 1%, a nie 100%. Stary temat BUS z ratio ma nazwany adapter. Skala nie jest odgadywana z wartości.

Roll/pitch/yaw SDK mają sdk_raw i physical_validity=unverified. Każdy kanał zachowuje swój observed_at, ready/stale/offline/error oraz identity, jeżeli producent je dostarczył. Błąd jednego kanału nie usuwa zdrowej baterii. Null nie zastępuje się innym polem lub czasem publikacji. Zero i false są prawidłowymi wartościami.

Usługa używa identity=host:unit, active_state/sub_state/load_state/unit_file_state i process_running. Proces uruchomiony, model załadowany, producent gotowy, dostępność startu i uprawnienie operatora są osobnymi informacjami. Peer reachable nie potwierdza domain ready. Brak danych nie staje się fałszywym CPU 5% lub latency 15 ms.

S6 pokazuje pasywne mapowanie/planowanie bez ARM. Plan/map/pose/HOME muszą mieć zgodną kalibrację, referencję i świeżą ramę; zmiana ramy unieważnia wcześniejsze dane. Nie oznacza to zgody na autonomię. Ekran kalibracji wykorzystuje istniejące API profili i jawne akcje operatora; przechowywanie profilu nie dowodzi fizycznego pomiaru.

## BUS, SSE i obrazy

ZMQ SUBSCRIBE używa rzeczywistych przedrostków, a nie tekstu z gwiazdką. Jawna lista tematów po odbiorze obejmuje telemetry, motion state/ACK, robot.pose, mapper.map.data, navigator.state/path, tracking i feature state. Aktualizacja ograniczonego cache trafia do SSE. Przeciążenie kolejki jest jawne; odczyt po reconnect nie odnawia czasu źródła.

RAW, PROC, SSD, OBST i TRACKER są osobnymi strumieniami. OBST używa obst_annot, SSD używa /vision/ssd. Metadane i obraz wybierają ten sam plik/producent. Brak klatki, placeholder lub archiwalny plik nie jest zdrową kamerą; GET nie uruchamia capture. Jawny odczyt archiwum wymaga oznaczenia.

Wykresy zachowują wszystkie serie; null/stale daje przerwy, a oś opisuje rzeczywisty czas albo ostatnie 60 próbek. Skale CPU/RAM to %, ROI/edge to ratio, pamięć to MiB/GiB. Przegląd zachowuje identyfikację Rider-PC, wszystkie poniższe karty i panel potwierdzeń.

## Zachowane karty

### Manifest kart Przeglądu PC

20 oryginalnych kart oraz historia ACK i status operatora. Statusy safety/połączenia/zadań oraz stopka są wymagane także wtedy, gdy nie mają klasy c-card.

| Karta | Identyfikatory elementów | Źródła | Zachowana funkcja |
| --- | --- | --- | --- |
| 1. System | ci_host, ci_cpu, ci_load, ci_mem, ci_disk, ci_os, ci_fw, pi-source-age | /sysinfo; /state; /healthz | System Pi, source i czas Pi |
| 2. Urządzenia | d_cam, d_lcd, d_xgo_imu, d_xgo_pose, d_xgo_batt, d_temp | /api/control/state; /state; /healthz | niezależne Observation; kamera/LCD/temperatura |
| 3. Historia (60 s) — CPU / MEM | chart | /sysinfo | hist_cpu/hist_mem i czas próbek Pi |
| 4. Kamera … | camBadge, img_cam, leg_cam_txt | /vision/snap-info; /vision/cam | Frame raw proxied z Pi |
| 5. Health | h_status, h_uptime, h_msg, h_hb | /healthz; /api/bus/health | API/BUS Pi, nie gotowość wszystkich sensorów |
| 6. Obstacle | obs_present, obs_conf, obs_edge, obstacle-source-age | /vision/obstacle | present/confidence/edge ratio i source age |
| 7. ROI histogram — edges | binsCanvas, binsLegendTxt | /vision/obstacle | diag.bins/t_low/t_high/edge_ratio_raw |
| 8. Kamera — PROC | img_proc, leg_proc_txt | /vision/snap-info; /vision/edge | Frame proc |
| 9. API Metrics | metric_control, metric_navigator, metric_voice, metric_google_home, metric_chat, metric_face, metric_total_errors | /api/app-metrics | prawdziwe liczniki interaktywnych API Pi |
| 10. Snap freshness | age_raw, age_proc | /vision/snap-info | wszystkie stream identities i czasy; brak restamp |
| 11. GPU (60 s) | chartGpu | /status/system-pc | GPU util/memory oraz lokalne próbki; brak GPU jawny |
| 12. Camera — OBST (annot) | img_obst, leg_obst_txt | /vision/snap-info; /snapshots/obst_annot.jpg; /vision/ssd | OBST/SSD odrębne; niezmieniona funkcja podglądu i rzeczywisty podpis |
| 13. System PC | pcHostInfo, pcCpu, pcLoad, pcMem, pcDisk, pcGpuUtil, pcGpuMem, pcOs, pcDistro, pcUptime, pc-source-age | /status/system-pc | CPU/load/RAM/dysk/GPU/OS/distro/uptime i source time PC |
| 14. Usługi PC | pcServiceList | /svc; /health/live | real PC services/providers, host:unit/kind/ready/error |
| 15. Historia (60 s) — PC CPU / MEM | chartPc | /status/system-pc | historia PC CPU/RAM, do 60 próbek |
| 16. Camera — TRACKER (Follow Me) | img_tracker, leg_tracker_txt | /vision/snap-info; /vision/tracker | Frame tracker, bez automatycznego startu |
| 17. MCP Tools | mcpTotalTools, mcpInvocations, mcpLastTool, mcpStatus | /api/mcp/stats | stats.total_tools/invocation_count/last_invoked_tool + availability |
| 18. Lista narzędzi | mcpToolsList | /api/mcp/tools | tools.name/description/args_schema/permissions/count |
| 19. Ostatnie wywołania | mcpRecentCalls | /api/chat/pc/mcp-history | historia TextProvider, odrębna od /api/mcp/history |
| 20. Konfiguracja MCP | mcpStandalone, mcpPort | /api/mcp/resources | resources.config.mcp_standalone/mcp_port i registry facts |
| 21. Żądania i potwierdzenia | request-history, last-event | /events; jawne żądania/ACK | request history i exact ACK |

Pi ma wykresy chart i binsCanvas oraz podglądy img_cam/img_proc/img_obst/img_tracker. PC ma także chartGpu i chartPc. Nagłówki zachowują nazwę Rider-Pi lub Rider-PC i Przegląd. Nie usuwamy kart ani nie zastępujemy pomiarów odnośnikiem do innego widoku.



## Odbiór i wydanie

Te same synthetic golden fixtures znajdują się w tests/fixtures/contracts/rider-v1.json obu repozytoriów. Obejmują częściowe dane, pending/rejected, null czasu, awarię transportu, usługi, różne strumienie i oba legacy formaty baterii. Nie są pomiarami fizycznymi.

Najpierw oba zakresy lokalnie WSL, potem podgląd Pi/PC na rzeczywistych danych i dopiero publikacja na GH. Testy automatyczne WSL używają izolowanych mocków. Odbiór robota jest odczytowy, z ESTOP i zerowym wyjściem; ruch wymaga osobnej, konkretnej zgody operatora. Ciężkie zależności pozostają w istniejących venv WSL. LCD zachowuje montaż bokiem i kompensację 270°.

Powiązane: [bezpieczny klient](../BEZPIECZNY_KLIENT_ROBOTA.md), [panel](../PANEL_OPERATORA.md), [polityka dokumentacji](../POLITYKA_DOKUMENTACJI.md).



## Inwentarz zarejestrowanych endpointów

Inwentarz wygenerowano z tabeli tras utworzonej aplikacji FastAPI bez uruchamiania usług. Obejmuje lokalne trasy, proxy Pi, wejścia panelu i zasoby statyczne. Obecność endpointu nie dowodzi skonfigurowania ani gotowości opcjonalnego dostawcy. HEAD wykazano tylko tam, gdzie został jawnie zarejestrowany.

| Methods | Path | Handler / route | Type |
| --- | --- | --- | --- |
| GET, HEAD | `/openapi.json` | `openapi` | Route |
| GET, HEAD | `/docs` | `swagger_ui_html` | Route |
| GET, HEAD | `/docs/oauth2-redirect` | `swagger_ui_redirect` | Route |
| GET, HEAD | `/redoc` | `redoc_html` | Route |
| GET | `/healthz` | `healthz` | APIRoute |
| GET | `/health/live` | `health_live` | APIRoute |
| GET | `/health/ready` | `health_ready` | APIRoute |
| GET | `/state` | `state` | APIRoute |
| GET | `/sysinfo` | `sysinfo` | APIRoute |
| GET | `/vision/snap-info` | `vision_snap_info` | APIRoute |
| GET | `/vision/obstacle` | `vision_obstacle` | APIRoute |
| GET | `/api/app-metrics` | `app_metrics` | APIRoute |
| GET | `/status/system-pc` | `system_pc_status` | APIRoute |
| GET | `/api/resource/camera` | `camera_resource` | APIRoute |
| GET | `/api/bus/health` | `bus_health` | APIRoute |
| GET | `/camera/placeholder` | `camera_placeholder` | APIRoute |
| GET | `/metrics` | `metrics` | APIRoute |
| GET | `/api/status/version` | `version_info` | APIRoute |
| GET | `/api/config/network` | `network_config` | APIRoute |
| GET | `/api/status/network` | `network_status` | APIRoute |
| GET | `/api/google/status` | `google_feed_status` | APIRoute |
| GET | `/api/google/raw/last.json` | `google_feed_last` | APIRoute |
| GET | `/api/proxy/pi/status` | `pi_model_status` | APIRoute |
| POST | `/api/proxy/pi/set-model` | `pi_model_binding_unavailable` | APIRoute |
| GET | `/providers/capabilities` | `providers_capabilities` | APIRoute |
| GET | `/api/providers/capabilities` | `providers_capabilities_api` | APIRoute |
| POST | `/providers/text/generate` | `providers_text_generate` | APIRoute |
| POST | `/api/providers/text/generate` | `providers_text_generate_api` | APIRoute |
| PATCH | `/api/providers/text/backend` | `update_text_provider_backend` | APIRoute |
| GET | `/api/system/ai-mode` | `get_ai_mode_route` | APIRoute |
| PUT | `/api/system/ai-mode` | `put_ai_mode_route` | APIRoute |
| POST | `/api/system/ai-mode` | `post_ai_mode_route` | APIRoute |
| GET | `/api/providers/state` | `providers_state` | APIRoute |
| PATCH | `/api/providers/{domain}` | `update_provider` | APIRoute |
| GET | `/api/providers/health` | `providers_health` | APIRoute |
| GET | `/api/services/graph` | `services_graph` | APIRoute |
| GET | `/vision/cam` | `vision_cam_proxy` | APIRoute |
| GET | `/vision/obst` | `vision_obst_proxy` | APIRoute |
| GET | `/vision/ssd` | `vision_ssd_proxy` | APIRoute |
| GET | `/vision/edge` | `vision_edge_proxy` | APIRoute |
| GET | `/vision/tracker` | `vision_tracker_proxy` | APIRoute |
| GET | `/snapshots/{snapshot_path:path}` | `snapshots_proxy` | APIRoute |
| POST | `/api/safety` | `safety_action` | APIRoute |
| POST | `/api/control` | `api_control_endpoint` | APIRoute |
| GET | `/api/motion/queue` | `api_motion_queue` | APIRoute |
| GET | `/api/control/state` | `api_control_state` | APIRoute |
| POST | `/api/vision/tracking/mode` | `update_tracking_mode` | APIRoute |
| POST | `/api/logic/feature/{name}` | `feature_toggle` | APIRoute |
| GET | `/api/logic/features` | `logic_features` | APIRoute |
| GET | `/api/logic/summary` | `logic_summary` | APIRoute |
| GET | `/api/logic/catalog` | `logic_catalog` | APIRoute |
| GET | `/api/navigator/status` | `navigator_status` | APIRoute |
| POST | `/api/navigator/config` | `navigator_config` | APIRoute |
| POST | `/api/navigator/start` | `navigator_start` | APIRoute |
| POST | `/api/navigator/stop` | `navigator_stop` | APIRoute |
| POST | `/api/navigator/return_home` | `navigator_return_home` | APIRoute |
| GET | `/api/resource/{resource_name}` | `get_resource_status` | APIRoute |
| POST | `/api/resource/{resource_name}` | `update_resource` | APIRoute |
| GET | `/svc` | `list_services` | APIRoute |
| GET | `/api/services` | `list_services_alias` | APIRoute |
| GET | `/api/services/systemd` | `list_services_alias` | APIRoute |
| GET | `/api/systemd/services` | `list_services_alias` | APIRoute |
| GET | `/api/services/{unit}/logs` | `service_logs` | APIRoute |
| POST | `/svc/{unit}` | `control_service` | APIRoute |
| POST | `/api/services/action` | `api_service_action_alias` | APIRoute |
| POST | `/api/services/systemd/action` | `api_service_action_alias` | APIRoute |
| POST | `/api/systemd/action` | `api_service_action_alias` | APIRoute |
| GET | `/camera/last` | `camera_last` | APIRoute |
| HEAD | `/camera/last` | `camera_last_head` | APIRoute |
| GET | `/events` | `events` | APIRoute |
| GET | `/api/calibration/profiles/{digest}` | `configuration_snapshot` | APIRoute |
| GET | `/api/calibration/profiles` | `configuration_snapshot` | APIRoute |
| GET | `/api/calibration/state` | `configuration_snapshot` | APIRoute |
| GET | `/api/odometry/state` | `configuration_snapshot` | APIRoute |
| POST | `/api/calibration/activate` | `configuration_request` | APIRoute |
| POST | `/api/calibration/profiles` | `configuration_request` | APIRoute |
| POST | `/api/odometry/reference` | `configuration_request` | APIRoute |
| GET | `/api/voice/providers` | `voice_providers` | APIRoute |
| POST | `/api/voice/providers/test` | `voice_providers_test` | APIRoute |
| POST | `/api/voice/tts` | `voice_tts` | APIRoute |
| POST | `/api/voice/asr` | `voice_asr` | APIRoute |
| GET | `/api/providers/voice` | `providers_voice_status` | APIRoute |
| POST | `/api/chat/send` | `chat_send` | APIRoute |
| POST | `/api/chat/pc/send` | `chat_pc_send` | APIRoute |
| GET | `/api/providers/text` | `providers_text_status` | APIRoute |
| GET | `/api/providers/text/external` | `providers_text_external_status` | APIRoute |
| GET | `/api/chat/pc/mcp-history` | `get_mcp_call_history` | APIRoute |
| POST | `/api/chat/pc/generate-pr-content` | `generate_pr_content` | APIRoute |
| POST | `/api/benchmark/models` | `benchmark_models` | APIRoute |
| GET | `/api/knowledge/documents` | `list_knowledge_documents` | APIRoute |
| POST | `/api/chat/pc/preview-pr-changes` | `preview_pr_changes` | APIRoute |
| GET | `/api/project/issues` | `get_project_issues` | APIRoute |
| POST | `/api/project/refresh` | `refresh_project_issues` | APIRoute |
| GET | `/api/project/meta` | `get_project_meta` | APIRoute |
| POST | `/api/project/create-task` | `create_task` | APIRoute |
| GET | `/api/models/installed` | `get_installed_models` | APIRoute |
| GET | `/api/models/active` | `get_active_models` | APIRoute |
| POST | `/api/models/bind` | `bind_model` | APIRoute |
| GET | `/api/models/summary` | `get_models_summary` | APIRoute |
| POST | `/api/knowledge/reindex` | `reindex_knowledge_base` | APIRoute |
| GET | `/api/knowledge/search` | `search_knowledge_base` | APIRoute |
| GET | `/api/knowledge/status` | `knowledge_base_status` | APIRoute |
| GET | `/api/home/status` | `home_status` | APIRoute |
| GET | `/api/home/devices` | `home_devices` | APIRoute |
| POST | `/api/home/command` | `home_command` | APIRoute |
| POST | `/api/home/auth` | `home_auth` | APIRoute |
| GET | `/api/assistant/status` | `assistant_status` | APIRoute |
| GET | `/api/assistant/devices` | `assistant_devices` | APIRoute |
| GET | `/api/assistant/device/{device_id}` | `assistant_device` | APIRoute |
| POST | `/api/assistant/command` | `assistant_command` | APIRoute |
| POST | `/api/assistant/custom` | `assistant_custom` | APIRoute |
| GET | `/api/assistant/history` | `assistant_history` | APIRoute |
| POST | `/api/assistant/reload` | `assistant_reload` | APIRoute |
| GET | `/api/mcp/tools` | `list_tools` | APIRoute |
| GET | `/api/mcp/resources` | `get_resources` | APIRoute |
| POST | `/api/mcp/tools/invoke` | `invoke_tool` | APIRoute |
| GET | `/api/mcp/stats` | `get_stats` | APIRoute |
| GET | `/api/mcp/history` | `get_invocation_history` | APIRoute |
| mount | `/web` | `web` | Mount |
| GET | `/` | `handler` | APIRoute |
| GET | `/view` | `handler` | APIRoute |
| GET | `/control` | `handler` | APIRoute |
| GET | `/devices` | `handler` | APIRoute |
| GET | `/mode` | `handler` | APIRoute |
| GET | `/navigation` | `handler` | APIRoute |
| GET | `/calibration` | `handler` | APIRoute |
| GET | `/system` | `handler` | APIRoute |
| GET | `/home` | `handler` | APIRoute |
| GET | `/google_home` | `handler` | APIRoute |
| GET | `/assistant` | `handler` | APIRoute |
| GET | `/chat` | `handler` | APIRoute |
| GET | `/chat-pc` | `handler` | APIRoute |
| GET | `/providers` | `handler` | APIRoute |
| GET | `/project` | `handler` | APIRoute |
| GET | `/models` | `handler` | APIRoute |


## Potwierdzenie operacji

Polecenia sterowania, usług, zasobów, zadań, aktywacji kalibracji i konfiguracji proxy Pi wymagają potwierdzenia. Zwykłe lokalne zapisy i generowanie (np. czat, zapis profilu, wybór backendu i wiązanie modelu PC) zachowują wynik HTTP bez sztucznego ACK. Jawna operation upstream pozostaje zachowana. Wznowienie SSE po zmianie procesu emituje transport.gap także przed pierwszą nową próbką; event_id jest nieprzezroczystym kursorem, nie czasem pomiaru.

Potwierdzenie lokalnej akcji usługi ma ack_kind=systemd_command_completed (w symulacji demo_state_applied). Potwierdza zakończenie komendy administracyjnej, nie gotowość procesu ani ruch robota; service_readiness pozostaje unverified. Zdalny ACK jest zachowany wyłącznie z odpowiedzi Pi.


## Zakres panelu ruchu
- Przegląd, Urządzenia i Chat: odczyty oraz operacje bez napędów; bez formularza zgody, przycisków ruchu i skrótu STOP. Obserwator stanu może dostarczać pomiary, ale nie wysyła poleceń po utracie fokusu.
- Nawigacja pozostaje pasywnym wizualizatorem. Bez formularza ARM; katalog tego widoku pokazuje tylko zadania bez ruchu. Autonomia nadal wymaga ręcznej charakterystyki i pozostaje niedostępna.
- Sterowanie i Kalibracja: lokalna zgoda, krótkie uzbrojenie, STOP, właściwy właściciel i świeży stan wymagane dla napędów.
- System: diagnostyka domyślnie; kontrolki zgody i STOP widoczne dopiero po włączeniu administracji, ponieważ start/restart określonych usług może uruchomić napędy.
- Zwolnienie ESTOP jest jawną operacją operatora z planem i potwierdzeniem. Kończy się stanem DISARMED; nie uzbraja automatycznie. ARM wymaga ponownego potwierdzenia.
- Sprawdzenie kontraktu i odświeżenie stanu odbywają się przed utworzeniem polecenia z TTL 500 ms. Nie odmładza się gotowych poleceń ani nie powtarza żądań automatycznie.
- Czas poleceń pochodzi z osobnego oszacowania zegara odpowiedzi bezpieczeństwa Pi. Odczyty innych hostów nie zmieniają tego oszacowania.


## Sterowanie ręczne i prosta kalibracja reakcji

Widok podstawowy zawiera kamerę, strzałki i STOP oraz suwaki jazdy, skrętu i reakcji.
Czas kliknięcia znajduje się w ustawieniach zaawansowanych. Suwaki prędkości ustawiają
następną pojedynczą próbę; rampa zaczyna obowiązywać po zapisaniu i zastosowaniu.
Ręczne sterowanie wymaga uzbrojenia jednym globalnym przyciskiem po prawej. Nie ma dodatkowej zgody przy każdej strzałce.
Zmiana suwaka, odczyt, zapis, zastosowanie lub powrót wersji nie uruchamiają ruchu.
Nie ma automatycznego powtarzania ani sekwencji kalibracyjnej.

Opcjonalny obiekt profilu interaction zapisuje linear_speed i turn_speed (0–1)
oraz pulse_duration (0.01–0.25 s). Wykonawca udostępnia go w
motion.calibration.interaction; Pi i PC odczytują te same ustawienia z Pi.
Parametry nie stanowią zgody na ruch. Stare profile bez tego obiektu pozostają czytelne.
Rampa i pułap polecenia zachowują dotychczasowy format motion i ograniczenia wykonawcy.
Przyjęcie ustawień nadal wymaga potwierdzenia obu modułów, niezależnie od gotowości
metrycznej odometrii. Zwykłe strojenie nie wymaga dystansu, kątów, HOME ani tabel m/s.

### Mapowanie do SDK Rider 1.4.2

Identyfikator: rider-1.4.2-levels-v2.
- linear_step: podpisany poziom polecenia −127..127, nie licznik obrotów.
- Parametr przekazany do rider_move_x: linear_step * 1.5 / 127, zakres ±1.5.
- turn_step: podpisany poziom −70..70; parametr skrętu SDK ma tę samą wartość.
- motion.output.units = command_levels; mapping_id, linear_sdk_value i
  turn_sdk_value opisują mapowanie, nie zmierzoną prędkość ani ukończenie ruchu.
- Neutralny bajt rejestrów prędkości to 128. Adapter koryguje zaokrąglanie SDK
  w swoim kontrolowanym hooku; nie modyfikuje zainstalowanej biblioteki.
- Czas ogranicza długość polecenia. Prędkość ogranicza jego wartość.
- Pomiary odometrii wymagają conditions.command_mapping zgodnego z tym identyfikatorem.
  Dawne zapisy pozostają do wglądu, lecz bez zgodności skali model jest niegotowy.
  Zmiana mapowania wymaga nowych pomiarów; nie migrujemy współczynników automatycznie.

Formularze pomiarów, odometrii, HOME i diagnostyka pozostają w zwiniętej części
zaawansowanej. Ocena operatora „za szybko / za wolno” służy dopasowaniu sterowania;
nie potwierdza metrycznej odometrii ani autonomii.

## Globalne uzbrojenie panelu i oddzielna zgoda testowa

Jeden przycisk po prawej pokazuje potwierdzony stan wykonawcy: czerwony
„Robot rozbrojony”, zielony „Robot uzbrojony”. Kliknięcie czerwonego jest
zgodą operatora na ręczne sterowanie z panelu; kliknięcie zielonego wysyła STOP.
Kasowanie programowego ESTOP i ARM odbywa się po jednym świadomym kliknięciu,
sekwencyjnie, dopiero po świeżym potwierdzeniu DISARMED. Zewnętrzny ESTOP,
brak sprzętu, brak świeżego zegara lub brak potwierdzenia nadal blokują ARM.
Uzbrojenie nie wywołuje ruchu. Panel używa arming_mode=operator: uzbrojenie trwa do STOP lub rozbrojenia
przez operatora, bez limitu czasu i bez automatycznego odnawiania. Przejście do innego widoku nie wysyła STOP.

Kontrakt bezpieczeństwa dodaje execution_context (panel/test),
panel_motion_enabled i test_motion_enabled. Panel wysyła execution_context=panel.
Zgoda panelu nie uprawnia poleceń testowych, nawet z test_operator_consent=true.
Ręczna fizyczna próba ma osobną sesję execution_context=test i jawne
test_operator_consent=true przy ARM i każdym poleceniu ruchu. Sesja testowa
nie uprawnia panelu. Jedna sesja wykonawcy zapobiega równoległemu sterowaniu.
STOP zawsze unieważnia obie flagi.

Automatyczne pytest/CI pozostaje izolowane: prawdziwy SDK, porty sprzętowe,
SSH i sieć robota są zablokowane niezależnie od obu flag. Flaga zgody testowej
nie wyłącza tej izolacji. Skrypt manual_motion-probe.py wymaga obecnego
operatora, terminala i wpisania jednorazowego potwierdzenia; po próbie wysyła STOP.

Panel: arming_mode=operator, lease_remaining_s=null. Zmiana widoku i fokusu nie rozbraja robota. Próby testowe pozostają w trybie timed, z osobną zgodą. Błędy sprzętu i zewnętrzny ESTOP nadal wymuszają zatrzymanie; stare dane blokują nowe polecenia.

A bounded panel movement pulse stops the drive when it ends, while operator arming remains active for the next click. STOP/disarm revokes the session; test sessions keep their timeout behavior.


## Shared manual controls
GET/POST /api/calibration/controls exposes the Pi-owned rider.manual_settings v1 object: revision, values, limits, observed_at, actuation=false. values contains linear_speed, turn_speed, pulse_duration, speed_limit, linear_rate and turn_rate. POST accepts revision plus a values patch, writes atomically, requires an idle executor and never sends an actuator command. Stale writes return 409.
Both Pi and PC control/calibration views poll this same object and disable movement while changes are pending or data is missing/stale. Every operator movement carries direction and settings_revision with the exact shared vx/yaw/duration. The executor rejects obsolete revisions and inconsistent values. Opening a view, importing a draft, or reading a historical profile never replaces live settings. Explicit activation of a saved profile updates the shared settings.
Default pulse is 0.25 s; software ramps are 3 linear / 4 turn normalized units per second, with the existing speed cap 0.6 and pulse cap 0.25 s retained. Turn mapping v3 uses 180 native SDK units at normalized 1; old physical measurements for mapping v2 must not be reused as verified v3 data. A reversal writes a neutral drive command before ramping in the newly requested direction, without disarming the panel. These are software defaults, not physically measured calibration.
