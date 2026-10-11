# Rider-PC contracts and Pi data

Rider-PC follows the [Rider-Pi contract specification](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/api-specs/contracts.md). Envelope version 1 is independent of safety 1 and catalog/tasks/services 2. Existing URLs and domain data remain available. New clients request `Accept: application/vnd.rider.api+json;version=1`; legacy clients receive the compatibility projection.

## Boundary and observations

RestAdapter negotiates and unpacks Pi data once. It preserves the full source metadata, original observation times, upstream status, error code and operation confirmation. Transport reception/attempt time is separate. Pending 202 remains pending; timeout is unknown and never retried automatically. Mutation bodies retain their original generation, seq, source, request_id, ts and TTL; a read-only compatibility preflight does not invent authority.

Local PC domains use the same envelope and their own host/source/time. Pi failure does not invalidate independently obtained PC metrics. Local network, MCP, project, knowledge and assistant data retain their existing payloads.

Battery canonical unit is ratio [0,1]. Legacy REST battery_pct=1 means 1%, not 100%. BUS units are adapted by topic/schema. SDK axes use sdk_raw and unverified physical validity. Every channel has its own timestamp and quality. Missing/null never falls back to another field or reception time; zero/false remain valid. One failed channel retains healthy battery and other axes.

Services use host:unit identity, active_state/sub_state/load_state/unit_file_state and process_running. Process existence, model loaded, domain ready, start availability and operator permission are separate. Peer connectivity does not prove model readiness. Missing metrics are not fabricated.

## Screens, events and media

All 20 existing overview cards, four charts and four previews remain, together with request confirmation and other pages. Shared observation rules are used by Overview, Devices and Calibration. Passive S6 shows valid matching map/pose/HOME/plan without ARM; changed profile/reference/frame invalidates previous geometry. Configuration save/applied and physical measurement readiness remain separate.

ZMQ subscribes to actual prefixes; a bounded explicit topic filter includes telemetry, motion state/ACK, robot.pose, mapper.map.data, navigation, tracking and feature state. Bounded cache updates fan out to SSE. Reconnect and receipt never refresh source observations; queue gaps are explicit.

RAW, PROC, SSD, OBST and TRACKER have distinct sources and metadata. OBST uses obst_annot; SSD remains /vision/ssd. Image and metadata share the same source selection. Placeholder/archive/missing frames do not prove a live camera. Reads never start capture. History labels describe its actual duration or last 60 samples, with gaps for null/stale. CPU/RAM use percent, ROI/edge ratios, memory MiB/GiB.

The Polish [contract document](../../docs_pl/api-specs/contracts.md) contains the complete card manifest. Endpoint definitions, including optional/separate applications, are checked against the instantiated API registry; a source declaration does not imply every optional service is running.

## Acceptance and release

The two repositories share identical synthetic tests/fixtures/contracts/rider-v1.json for healthy/partial data, pending/rejected operations, unknown time, cache/transport failure, service rows, frames and legacy units. Fixtures do not validate physical measurements.

Implement and test both scopes locally in existing WSL virtualenvs, then preview both panels against real data before GitHub publication. Automated tests use isolated mocks. Robot acceptance stays read-only with ESTOP and zero output. Physical motion requires separate explicit operator consent. No global or heavy device dependencies are introduced. LCD orientation remains sideways with 270-degree compensation.

See [safe robot client](../SAFE_ROBOT_CLIENT.md) and [operator panel](../OPERATOR_PANEL.md).



## Registered endpoint inventory

Generated from the instantiated FastAPI route table without starting runtime services. This includes local routes, Pi proxy routes, UI entry points and the static mount. It is an inventory, not evidence that an optional provider is configured or ready. HEAD is listed only where explicitly registered.

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


## Operation confirmation

Control, service, resource, task, calibration activation and Pi proxy configuration commands require confirmation. Ordinary local writes and generation (chat, profile save, backend selection and PC model binding) keep their HTTP result without a fabricated ACK. Explicit upstream operation metadata is preserved. SSE resumes after a process change emit transport.gap even before the first new sample; event_id is an opaque cursor, never an observation timestamp.

Local service actions use ack_kind=systemd_command_completed (demo_state_applied in simulation). This confirms completion of the administrative command, not process readiness or robot motion; service_readiness remains unverified. Remote ACKs are preserved only from the Pi response.


## Motion panel scope
- Overview, Devices and Chat expose observations and non-actuating operations, without motion consent forms or STOP shortcuts. Their state observer may provide measurements but does not send commands on focus loss.
- Navigation remains a passive visualizer without an ARM form. Its task catalog shows only non-actuating tasks. Autonomous motion remains unavailable pending manual characterization.
- Control and Calibration require local consent, a short lease, STOP, the correct owner and fresh state for actuator operations.
- System opens as diagnostics. Consent and STOP controls appear after enabling administration because starting/restarting some services can actuate the robot.
- Clearing ESTOP requires an explicit operator plan and consent. It ends in DISARMED and never automatically arms. ARM requires renewed consent.
- Contract negotiation and state refresh finish before constructing the 500 ms command envelope. Existing commands are never restamped or automatically retried.
- Command time uses a separate estimate from the Pi safety response. Observations from other hosts cannot change this estimate.


## Manual control and response tuning

The main calibration view provides the camera, direction arrows, STOP, travel/turn
speed sliders and response ramps. Click duration is an advanced setting.
Speed sliders select the next manual trial; ramps apply only after saving and
explicit activation. Manual control uses the single global arm/disarm button;
there is no additional per-arrow consent. Reading, sliders, save, apply and rollback never start movement.
There are no automatic repeats or calibration sequences.

The optional profile object interaction contains linear_speed, turn_speed (0–1)
and pulse_duration (0.01–0.25 s). Both clients read shared Pi settings from
motion.calibration.interaction. They do not grant motion authority.
Legacy profiles remain readable. Existing motion ramps and executor ceilings
stay authoritative. Application still needs both consumer confirmations;
manual response tuning does not require measured odometry or HOME.

Mapping rider-1.4.2-levels-v2 reports signed linear_step command levels in
−127..127, converted to native SDK input by level * 1.5 / 127.
Signed turn_step is −70..70 and corresponds to native SDK turn input.
motion.output.units is command_levels; mapping_id, linear_sdk_value and
turn_sdk_value describe commands, never measured velocity or wheel encoders.
The guarded write hook rounds around protocol neutral 128, including STOP;
the installed vendor library is not modified. Pulse duration bounds time;
command magnitude bounds requested speed.
Measured odometry requires matching conditions.command_mapping.
Old measurements remain inspectable but cannot verify the changed mapping.
Coefficients are never converted automatically.

Measurement tables, pose/HOME, import and detailed observations are advanced
facilities. Operator judgement tunes manual control without verifying metric
odometry or enabling autonomy.

## Global panel arming and separate test permission

The single button on the right displays the confirmed executor state:
red "Robot disarmed", green "Robot armed". Clicking red grants manual panel
permission; clicking green sends STOP. Clearing software ESTOP and ARM follow
one explicit click, sequentially, only after a fresh DISARMED confirmation.
External ESTOP, unavailable hardware, an unconfirmed clock or a missing
confirmation still block ARM. Arming does not move the robot. The panel uses arming_mode=operator: permission remains until operator STOP
or disarming, without a timer or automatic renewal. Changing views does not send STOP.

The safety contract adds execution_context (panel/test), panel_motion_enabled
and test_motion_enabled. The panel sends execution_context=panel. Panel consent
cannot authorize test commands, even with test_operator_consent=true.
A manual physical probe uses its own execution_context=test session and explicit
test_operator_consent=true at ARM and every motion attempt. A test session cannot
authorize panel controls. A single executor session prevents simultaneous control.
STOP invalidates both flags.

Automated pytest/CI remains isolated: real SDK, hardware devices, SSH and robot
network access are blocked independently of either flag. Test consent does not
disable isolation. manual_motion-probe.py requires a present operator, an
interactive terminal and a one-time typed approval; it sends STOP after the probe.

Panel: arming_mode=operator, lease_remaining_s=null. View and focus changes do not disarm. Physical test sessions remain timed with separate consent. Hardware faults and external ESTOP still stop the executor; stale data blocks new commands.

A bounded panel movement pulse stops the drive when it ends, while operator arming remains active for the next click. STOP/disarm revokes the session; test sessions keep their timeout behavior.


## Shared manual controls
GET/POST /api/calibration/controls exposes the Pi-owned rider.manual_settings v1 object: revision, values, limits, observed_at, actuation=false. values contains linear_speed, turn_speed, pulse_duration, speed_limit, linear_rate and turn_rate. POST accepts revision plus a values patch, writes atomically, requires an idle executor and never sends an actuator command. Stale writes return 409.
Both Pi and PC control/calibration views poll this same object and disable movement while changes are pending or data is missing/stale. Every operator movement carries direction and settings_revision with the exact shared vx/yaw/duration. The executor rejects obsolete revisions and inconsistent values. Opening a view, importing a draft, or reading a historical profile never replaces live settings. Explicit activation of a saved profile updates the shared settings.
Default pulse is 0.25 s; software ramps are 3 linear / 4 turn normalized units per second, with the existing speed cap 0.6 and pulse cap 0.25 s retained. Turn mapping v3 uses 180 native SDK units at normalized 1; old physical measurements for mapping v2 must not be reused as verified v3 data. A reversal writes a neutral drive command before ramping in the newly requested direction, without disarming the panel. These are software defaults, not physically measured calibration.
