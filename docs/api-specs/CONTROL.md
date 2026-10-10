# Control API

Rider-PC forwards requests to Rider-Pi. Physical actuator trials are manual
and require explicit operator consent to a specific trial plan. The fields
below describe the contract, not an automatic hardware procedure.
See the [safe client](../SAFE_ROBOT_CLIENT.md).

## State

`GET /api/control/state` returns Pi observations with `source`, `observed_at`,
`stale` and `offline`. Version 1 `safety` includes state DISARMED/ARMED/ESTOP,
`ready`, `can_move`, `read_only`, `owner`, `generation`, `last_seq`
and ACK metadata. Unknown contracts become UNKNOWN/read-only.

## Envelope from a specific confirmation

Every actuator request and arm/clear includes:

| Field | Rule |
| --- | --- |
| `generation` | Pi's current generation; PC never creates it |
| `seq` | Positive integer greater than the last sequence |
| `source` | `manual` for operator HTTP requests |
| `ts` | Finite UNIX confirmation timestamp |
| `ttl_ms` | Integer 1–500; expired requests are refused |

PC verifies and forwards the envelope unchanged. It cannot make an old request
fresh after STOP/re-arm. Older UIs without these fields remain read-only.
STOP may be sent without an envelope.

## Consent and stopping

`POST /api/safety` accepts `action: arm|disarm|estop|clear_estop`.
Arm/clear require explicit `operator_consent: true`, a nonempty
`operator_plan` and the envelope. Arm selects `owner: manual|follow_me|navigation`
and `lease_s`, capped by Pi at 30 seconds. Clear leaves actuators disarmed.
Disarm/estop do not require confirmed readiness. App startup, changing views,
tasks, cameras or providers never automatically arms the robot.

## Actuators

`POST /api/control` accepts `cmd: move|spin|height|balance|action|stop`
and command-specific fields (e.g. vx/yaw/duration, height, enabled, action).
Pi owns actuator units and limits, rather than client defaults. Motion requires
a fresh ARMED gate with ready=true, can_move=true and manual ownership.
Height, balance and predefined actions use this same gate.

`GET /api/motion/queue` forwards Pi's queue. `local_request_history` describes
PC requests and responses, not UART execution. Unavailable Pi yields stale/offline,
never a local claim that hardware stopped.

## Tasks and tracking

- `GET /api/logic/features`, `/summary`, `/catalog`: Pi catalog/state v2.
- `POST /api/logic/feature/{name}`: `enabled` must be boolean. Start requires
  explicit can_move. Moving tasks also need the envelope and matching motion_owner.
- `POST /api/vision/tracking/mode`: face/hand/none; active tracking requires
  follow_me ownership. Disabling never arms the robot.
- `POST /api/navigator/start`, `/stop`: explicit s9_navigation task start/stop.
- `POST /api/navigator/return_home`: envelope and navigation owner; confirmed
  Pi response only, never a local simulation.

Older Pi catalogs remain readable; missing v2 capabilities never authorize
start. See the separate [services/resources contract](../SERVICE_AND_RESOURCE_MANAGEMENT.md).

## Result

Pi responses retain HTTP status and `ok`, `confirmed`, `pending`,
`request_id`, `ack`, `safety` and `physical_completion` when available.
HTTP 202 means pending ACK. HTTP 409 indicates a gate refusal, unknown capability
or obsolete envelope. HTTP 503 means no connection; 502 indicates a proxy failure.
HTTP success does not prove that a physical movement completed.
