# Rider-PC operator panel

The panel uses the same views and decision contracts as Rider-Pi. PC API
availability and an active process do not prove actuator readiness. Pi provides
the authoritative safety state and task catalog.

## Views

| View | Data and actions |
| --- | --- |
| Overview `/view` | PC/Pi connection, battery and task freshness, motion block and STOP. |
| Tasks and control `/control` | Catalog v2, task options/resources, explicit plan/consent/owner/lease, bounded pulse, request history and ACK. |
| Devices `/devices` | Process owners/task consumers, camera RAW/PROC/SSD/tracker, battery/IMU, LCD and UART. |
| System `/system` | Pi/PC services and actual application providers, provenance/age, host details/graph, separate administration/autostart and manual resource recovery. |
| Navigation `/navigation` | Map/pose/path producer timestamps, explicit navigation owner preparation, start/STOP and return home. |
| Chat `/chat` | Text and optional TTS; only an explicit send prepares its required domain. |
| PC tools | Existing models, project, status, Google Home, Assistant and separate Chat PC remain available. |

Opening a view or changing a selection starts no task, model or actuator.
System defaults to read only. Cards have no start/stop click handlers.
A separate switch enables administration in the current tab. Every service
request includes a host; identity is `host:unit`. Application providers have a
distinct type and no fictional systemd unit. Logs are GET-only, on demand, keyed by host/unit, restricted to the configured PC units or Pi inventory. Journal reads are bounded to 2 seconds, 50 lines and 64 KiB; missing permission is an error.

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

Camera preview defaults to off. Refresh changes image polling in this tab,
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
[runtime and test dependencies](CONTRIBUTING.md#minimal-runtime-and-tests-in-wsl).

```sh
node --experimental-vm-modules --test tests/operator_panel.test.mjs
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
