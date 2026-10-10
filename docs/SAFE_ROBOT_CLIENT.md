# Safe robot client

Rider-PC forwards commands and displays Rider-Pi observations. A healthy PC API
does not prove actuator readiness. Pi owns the authoritative safety gate and task catalog.

## Tests and operator consent

Automatic tests use isolated REST/SDK/BUS doubles. Root `conftest.py` blocks
real TCP, ZMQ, device files and SSH/systemd commands. The only TCP exception is
the local server port allocated by the E2E fixture; browser requests to other
origins are aborted as well. `TEST_MODE=true` alone does not isolate hardware.

Physical actuator trials (drive, turn, height, balance, actions and moving tasks)
are manual and require explicit operator consent to the specific trial plan.
They never belong to pytest, E2E, CI, general diagnostics or deployment.
Consent to camera access, status reads, server startup or publishing code does
not authorize actuators. A tethered robot needs prepared space. The client and
tests preserve boot, splash and the established LCD orientation.

## Safety contract v1

`GET /api/control/state` forwards Pi's `safety` object:

- `contract_version: 1`, `state: DISARMED|ARMED|ESTOP`;
- `ready`, `can_move`, `read_only`, `observed_at`;
- `owner: manual|follow_me|navigation`, `generation`, `last_seq`;
- ACK, hardware state, blocking reason and lease metadata remain in the response.

Unknown contract versions become `UNKNOWN` with read-only capabilities.
Before each actuator request PC reads Pi's gate and requires `ARMED`, explicit
`ready=true` and `can_move=true`, the correct owner, an issued generation and
an observation no more than three seconds old. Stale/offline or invalid fields
refuse the operation with HTTP 409.

`POST /api/safety` forwards `action: arm|disarm|estop|clear_estop`. Arm/clear
require `operator_consent: true` and a nonempty `operator_plan`; Pi also checks
owner and lease bounds. PC never arms automatically or creates a generation. Every actuator and arm/clear
request needs the envelope from that specific operator confirmation: Pi-issued
`generation`, increasing `seq`, `source: manual`, finite `ts` and
`ttl_ms` from 1 to 500. PC verifies and forwards these without changing their
generation or timestamp. Old requests never become fresh after STOP/re-arm.
Older panels without this metadata remain readable and may send STOP.

STOP does not require a readiness read. No connection still means failure,
rather than a local claim that hardware stopped. Pi responses retain HTTP 202,
`confirmed`, `pending`, `ack` and `physical_completion`. Accepting a request
does not prove completion of a physical movement.

## Catalog v2 and offline data

`/api/logic/catalog`, `/api/logic/features`, `/api/logic/summary` and `/svc`
accept Pi contract v2. Task start requires an explicit `can_move`; moving
tasks also require `motion_owner` matching the gate. Service start/restart
requires confirmed v2 capabilities. Moving services cannot be enabled at boot.
Missing or stale inventory does not prove readiness.

Older Pi versions remain readable. Missing contracts never fall back to a
different local catalog or simulated success. Failed reads retain the last
inventory with its original `observed_at`, stale/offline and error flags.
The gate becomes `UNKNOWN`; a resource is not presented as free. PC request
history remains separate from Pi queue and actuator ACK.

## PC services and watchdog

See [service management](SERVICE_AND_RESOURCE_MANAGEMENT.md). System cards are
read-only: clicking a card never sends POST. Explicit administration identifies
the host; identity is `host:unit`. An application provider is labelled
`application_provider` and is not a fabricated systemd service.

The watchdog uses the manager's configured inventory. It retries only a real,
local, non-actuating systemd service previously observed active or explicitly
started. Inactive, unknown, offline, demo, unconfigured and operator stop/disable
states never cause retry. It does not control Pi, restore consent, revive
finished tasks or replay motion commands.

Explicit ARM and E-Stop clearing accept a fresh known `DISARMED`/`ESTOP` state even when `read_only:true` describes inhibited actuators. Movement requires `read_only:false`, `ARMED`, `ready:true`, and `can_move:true`. A missing contract or `UNKNOWN` state always blocks ARM.

Child Python interpreters receive the same network/device/SDK guards through sitecustomize. Disabling that bootstrap or launching an unapproved shell is forbidden. The standalone CSS audit uses the same isolation module.

See the project policy for [minimal runtime and WSL test dependencies](CONTRIBUTING.md#minimal-runtime-and-wsl-tests).

The new [operator panel](OPERATOR_PANEL.md) confirms its clock using Pi server_time and a bounded RTT. Actuation also requires hardware_ready:true. Separate administration buttons do not turn service cards into actions.
