# Rider-PC contracts and Pi data

Rider-PC follows the [Rider-Pi contract specification](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/api-specs/contracts.md). Envelope version1 is independent of safety1 and catalog/tasks/services2. Existing URLs and domain data remain available. New clients request `Accept: application/vnd.rider.api+json;version=1`; legacy clients receive the compatibility projection.

## Boundary and observations

RestAdapter negotiates and unpacks Pi data once. It preserves the full source metadata, original observation times, upstream status, error code and operation confirmation. Transport reception/attempt time is separate. Pending202 remains pending; timeout is unknown and never retried automatically. Mutation bodies retain their original generation, seq, source, request_id, ts and TTL; a read-only compatibility preflight does not invent authority.

Local PC domains use the same envelope and their own host/source/time. Pi failure does not invalidate independently obtained PC metrics. Local network, MCP, project, knowledge and assistant data retain their existing payloads.

Battery canonical unit is ratio[0,1]. Legacy REST battery_pct=1 means1%, not100%. BUS units are adapted by topic/schema. SDK axes use sdk_raw and unverified physical validity. Every channel has its own timestamp and quality. Missing/null never falls back to another field or reception time; zero/false remain valid. One failed channel retains healthy battery and other axes.

Services use host:unit identity, active_state/sub_state/load_state/unit_file_state and process_running. Process existence, model loaded, domain ready, start availability and operator permission are separate. Peer connectivity does not prove model readiness. Missing metrics are not fabricated.

## Screens, events and media

All20 existing overview cards, four charts and four previews remain, together with request confirmation and other pages. Shared observation rules are used by Overview, Devices and Calibration. PassiveS6 shows valid matching map/pose/HOME/plan without ARM; changed profile/reference/frame invalidates previous geometry. Configuration save/applied and physical measurement readiness remain separate.

ZMQ subscribes to actual prefixes; a bounded explicit topic filter includes telemetry, motion state/ACK, robot.pose, mapper.map.data, navigation, tracking and feature state. Bounded cache updates fan out to SSE. Reconnect and receipt never refresh source observations; queue gaps are explicit.

RAW, PROC, SSD, OBST and TRACKER have distinct sources and metadata. OBST uses obst_annot; SSD remains /vision/ssd. Image and metadata share the same source selection. Placeholder/archive/missing frames do not prove a live camera. Reads never start capture. History labels describe its actual duration or last60 samples, with gaps for null/stale. CPU/RAM use percent, ROI/edge ratios, memory MiB/GiB.

The Polish [contract document](../../docs_pl/api-specs/contracts.md) contains the complete card manifest. Endpoint definitions, including optional/separate applications, are checked against the instantiated API registry; a source declaration does not imply every optional service is running.

## Acceptance and release

The two repositories share identical synthetic tests/fixtures/contracts/rider-v1.json for healthy/partial data, pending/rejected operations, unknown time, cache/transport failure, service rows, frames and legacy units. Fixtures do not validate physical measurements.

Implement and test both scopes locally in existing WSL virtualenvs, then preview both panels against real data before GitHub publication. Automated tests use isolated mocks. Robot acceptance stays read-only with ESTOP and zero output. Physical motion requires separate explicit operator consent. No global or heavy device dependencies are introduced. LCD orientation remains sideways with270-degree compensation.

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
