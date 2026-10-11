# Rider-PC operator panel

The panel uses the same views and decision contracts as Rider-Pi. PC API
availability and an active process do not prove actuator readiness. Pi provides
the authoritative safety state and task catalog.

## Views

| View | Data and actions |
| --- | --- |
| Overview `/view` | All 20 measurement, chart, image and diagnostic cards; an additional compact safety/STOP strip. |
| Tasks and control `/control` | Catalog v2, task options/resources, explicit plan/consent/owner/lease, bounded pulse, request history and ACK. |
| Devices `/devices` | Process owners/task consumers, camera RAW/PROC/SSD/tracker, battery/IMU, LCD and UART. |
| System `/system` | Visible Pi/PC CPU/RAM/disk/temperature/history, services and actual providers, graph, separate administration/autostart and manual resource recovery. |
| Navigation `/navigation` | Map/pose/path producer timestamps, explicit navigation owner preparation, start/STOP and return home. |
| Chat `/chat` | Text and optional TTS; only an explicit send prepares its required domain. |
| PC tools | Existing models, project, status, Google Home, Assistant and separate Chat PC remain available. |

Opening a view or changing a selection starts no task, model or actuator.
System defaults to read only. Cards have no start/stop click handlers.
A separate switch enables administration in the current tab. Every service
request includes a host; identity is `host:unit`. Application providers have a
distinct type and no fictional systemd unit. Logs are GET-only, on demand, keyed by host/unit, restricted to the configured PC units or Pi inventory. Journal reads are bounded to 2 seconds, 50 lines and 64 KiB; missing permission is an error.

### Complete measurement dashboard

The heading and browser title identify **Rider-PC: Overview**. All five original
rows remain directly visible on `/view`; basic readings do not require following
links or opening raw JSON:

| Row | Four cards |
| --- | --- |
| 1 | Pi system; Pi devices; Pi CPU/MEM; RAW camera. |
| 2 | Pi Health/BUS; obstacle; ROI histogram; PROC camera. |
| 3 | Pi API counters; snapshot ages; PC GPU; SSD/OBST image. |
| 4 | PC system; actual PC services/providers; PC CPU/MEM; TRACKER. |
| 5 | MCP registry statistics; tools; invocation history; MCP configuration. |

CPU/MEM and GPU charts contain the latest **60 samples**, not a guaranteed
60-second interval. Missing readings create gaps, not zeroes. Memory/storage
use MiB/GiB; load 1/5/15 is system load average, not CPU percentage. Pi system
cards consume flat `/sysinfo` fields; Health reads `devices` and `bus`.
PC API liveness is the separate `/health/live` source.

Each IMU/battery channel retains its own timestamp, readiness and error. A fault
in another channel does not hide a valid reading. SDK battery fractions convert
to percentages only within 0..1; legacy `battery_pct` already represents percent.
IMU shows raw SDK values, especially `yaw_raw`; legacy wrapped yaw is explicitly
labelled. These values do not establish robot position or physical calibration.

`received_at` describes the last successful response in the PC clock domain,
and never changes source `observed_at`/`ts`. Source failure retains previous
values marked stale/offline rather than supplying default OK. Missing, stale or
erroneous obstacle observations show `present=unknown`, not a claim of a clear
physical scene. LCD `power_known=false` means unknown power regardless of its
owner or configured state.

Overview refreshes existing image files; its switch stops image refresh only.
It starts no capture/task. Historical images are dimmed and labelled as not the
current robot scene. Image failures use bounded retries. Core reads run about
every 2 seconds; PC/MCP diagnostics about every 7 seconds. Hidden tabs pause
reads. Counters and ACK do not confirm physical completion; the dashboard grants
no ARM. Devices keeps its separate image preview disabled by default.

## Preparing motion

1. Prepare the robot, free space, power cable and STOP procedure.
2. In the same view enter a specific plan, choose the owner and a lease up to
   30 seconds, then explicitly confirm consent. ARM itself sends no motion.
3. Require fresh ARMED, `ready`, `hardware_ready`, verified actuator capability
   and the correct owner. A separate action sends a pulse or starts a task.
4. Use STOP. STOP/disarm/ESTOP immediately revoke the local generation.
   Connection/focus loss or a hidden tab suspends control and attempts STOP.
   Consent and targets are not carried between views.

W/S/A/D and arrows work only in Tasks and control with manual ownership.
Inputs, selects, modifiers and repeated key events are ignored. Space outside
fields sends STOP. Physical actuator trials remain manual and operator approved;
general software tests never run them.

The UI confirms the Pi clock using GET `server_time`. RTT over 500 ms, expired
clock confirmation, unknown v1 or UNKNOWN permits read only. A command envelope
is created once at the operator's confirmation:
`request_id, source:manual, generation, seq, ts, ttl_ms`. Sequence is nonnegative
and increases within the generation; TTL is at most 500 ms. PC never refreshes
an old request. Canonical `action` is supported alongside legacy `cmd`.

`pending`/HTTP 202 means awaiting ACK. Only a terminal ACK matching request,
action, source, sequence, generation and timestamp confirms SDK acceptance.
Physical completion stays `physical_completion:unverified`. Network failure
leaves an unknown result.

## Tasks, domains and devices

Task rows and `option_schema` come only from Pi catalog v2. Unknown `can_move`,
missing installation, stale data and errors disable Start. Requested, starting,
ready, partial, failed, stopping and stopped are separate from process state.

Text/vision/voice domain host and health are read only. Explicitly start the
required catalog task and domain option. The new panel does not use the legacy
global AI switch. Chat explicitly uses the Pi proxy path; separate Chat PC
preserves local text functionality.

Devices camera preview defaults to off. Refresh changes image polling in this tab,
neither starts capture nor stops its task. URLs must be local camera routes.
Preserve the sideways display's established 270° compensation, splash and startup
sequence. The panel never rotates LCD. The motion executor alone owns UART.

Start/stop/restart and enable/disable are separate actions. Moving autostart
is blocked. End a task before stopping a shared service. Forced resource recovery
requires fresh owner data, selected PIDs, the exact resource name and explicit
consent; API protections for UART/LCD/base services still apply.

## Verification and maintenance

Small vanilla JS modules in `web/assets/operator` require no framework or new
libraries. Polling has timeouts, deduplication, backoff and no overlapping
requests; hidden tabs suspend polling and SSE.

Fixture scenarios cover clocks/generations/ACK, old contracts, System read only,
host identity, administration and lazy preview. Use the existing local WSL venv:
[runtime and test dependencies](CONTRIBUTING.md#minimal-runtime-and-wsl-tests).

```sh
node --experimental-vm-modules --test tests/operator_panel.test.mjs tests/operator_panel_shared_review.test.mjs
RIDER_ENABLE_API_TESTS=1 .venv/bin/python -m pytest pc_client/tests tests --ignore=tests/e2e
.venv/bin/python -m pytest tests/e2e
```

API and isolation policy: [safe robot client](SAFE_ROBOT_CLIENT.md).

## Local PC providers

Disabled domains do not import heavy AI libraries. Explicit PC startup switches
and provider configuration select the required backend; opening a panel does not.
In the voice TOML select `domain = "asr"`, `"tts"` or `"voice"` (both domains by
default), or `domains = ["tts"]`. `asr_model_path` selects an existing Whisper
`.pt` file; otherwise the local `~/.cache/whisper/<asr_model>.pt` cache is checked.
`tts_model_path` selects a Piper `.onnx` file with its `.onnx.json` configuration.
Only selected models are validated and loaded. TTS does not import Whisper and ASR
does not import Piper. Missing modules/assets or inference errors make that domain
unavailable; another working domain may remain available. `initialized` does not
mean both domains are ready. API and heartbeat expose separate ASR/TTS capabilities.

Vision requires existing `detection_model_path` weights or a local
`<detection_model>.pt` file; YOLO never automatically downloads weights.
Optional MediaPipe loads only with `enable_tracking = true`. Text checks the
selected local Ollama model metadata without downloading it. Real NLU remains
unavailable until implemented. A real backend failure never creates a successful
mock reply. Demo requires explicit `use_mock = true` or `*_MODEL=mock`, carries
`source:demo` and simulation metadata. Panel startup and automated tests install
no packages or models. Use only the needed runtime in its own environment according
to the dependency policy; WSL tests inject fake backends.

Passive synchronization never powers off LCD or releases resources. Such changes
require a separate operator action and preserve display orientation/startup.

Vision offload preserves camera `observed_at`, or its original legacy timestamp/ts only when that field is absent. Queue results and publication never refresh the observation. Unknown capture time means `data_ready:false`; simulated results remain diagnostic and do not enter robot enhanced/tracking topics. ROI and bounding box estimates do not prove range or navigation calibration.

Map, pose and path observation age is separate from measurement usability. Explicit stale/offline/error or unavailable data stays dimmed/unknown even at a recent timestamp; unknown packets and null snapshots expire old geometry. Quality changes at the same timestamp redraw the view. A freshly observed FAILED/IDLE task status remains visible when its sensors are not ready.
## Cached camera and image-only range

`/camera/last` preserves the original `Last-Modified` source time. Missing or invalid source time stays unknown: GET/HEAD omit `Last-Modified` and report `X-Camera-Observation-Valid: false`; receipt time is a separate cache diagnostic. A known peer timestamp is preserved even when clock alignment is unconfirmed, and does not establish freshness. The initial placeholder has no measurement time. Bounding-box distance heuristics are explicitly unverified (`range_verified: false`, `distance_source: bbox_area_heuristic`, `distance_unit: unverified`) and cannot establish calibrated navigation range.


### Presentation and source guards

Provider cards read actual /providers/capabilities, including the separately
owned text provider and individual ASR/TTS capabilities. Initialization alone
does not mean readiness. Cached health after source failure remains unknown. System refresh preserves expanded source/autostart/log
details by host/unit; logs are fetched only on request. Navigation history is
visible separately from motion ACKs. A cached proxy failure invalidates retained
geometry without refreshing its original time. Explicit unknown observation
time remains unknown after age refresh. The demo catalog uses canonical
s9_navigation; demo input provenance survives real-provider processing and
cannot publish physical vision/tracking topics.

Only a finite fresh Pi server_time permits configuration while DISARMED.
PC time cannot replace missing Pi time. Failure of a nondefault text backend
does not change readiness of the selected default backend.

CI explicitly enables lightweight offline API fixtures with
RIDER_ENABLE_API_TESTS=1 in the unit job. Redis/provider integration flags remain
disabled; these fixtures require no additional models or packages.

## E2E browser lifecycle

E2E owns a local demo server and closes each browser context before the browser
and Playwright driver, including failures. Keep Chromium's standard renderer
processes: forced single-process mode can crash on shutdown with active operator
frames and consume the driver's 30-second exit fallback. CI prints setup/call/
teardown durations and explicitly loads its 60-second per-test timeout plugin;
the overall E2E job budget remains 10 minutes. Reproduce using the existing WSL
venv/browser cache, without installing dependencies or contacting hardware:

```sh
CI=true PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/e2e \
  -p pytest_asyncio.plugin -p pytest_timeout --timeout=60 --timeout-method=thread --durations=30
```

Vision inference failures remain unavailable until the configured real detector completes inference and postprocessing successfully. That recovery clears its inference error; unavailable/uninitialized backends and successful demo tasks cannot clear a real-backend failure. Task input provenance still controls physical publication independently of provider readiness.

An empty exception message uses its exception type as the failure diagnostic, so a failed real task cannot report ready because its error string is blank.
