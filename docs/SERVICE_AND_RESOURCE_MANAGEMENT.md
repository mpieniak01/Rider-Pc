# Service and resource management

Rider-PC observes configured local systemd units and Rider-Pi's inventory.
Pi maintains the robot's unit, target, task and resource catalog. PC fetches it
over HTTP and does not maintain a production copy of robot startup units.

## Source and identity

Rows include `host`, `unit`, `identity=host:unit`, `source`, `observed_at`,
`stale` and `offline`. Identical names on Pi and PC are separate entries.
On connection loss known Pi units remain unknown, with the original observation
and error. A new PC response timestamp never makes Pi observations newer.
Before the first successful Pi read, `hosts.pi.offline` distinguishes an empty
inventory from a healthy robot.

`active`, `sub`, `load/installed` and `enabled` describe separate states.
An active unit does not prove task readiness, armed actuators, a current image
or a free device.

## PC configuration

```dotenv
MONITORED_SERVICES=
NON_ACTUATING_SERVICES=
SYSTEMD_USE_SUDO=true
AUTO_HEAL_ENABLED=true
MAX_RETRY_COUNT=1
RETRY_WINDOW_SECONDS=300
TEST_MODE=false
```

`MONITORED_SERVICES` explicitly lists local units. An empty list produces an
empty PC systemd inventory. Unavailable systemd produces unknown observations,
not fabricated Redis, Prometheus, queues or providers.
`NON_ACTUATING_SERVICES` is a verified subset of that list. Only explicitly
known non-actuating units may start, restart or be enabled at boot. Local
administration requests identify `host: pc`. Administrators restrict sudo to
the concrete units and operations required.

`TEST_MODE=true` chooses an explicit demo manager and MockRestAdapter at
application startup. Demo rows expose `source: demo`, never operating system
state. Automatic tests also require the connection barriers described in the
[safe client](SAFE_ROBOT_CLIENT.md).

Application providers use `kind: application_provider`, `source: application`
and no systemctl actions. Readiness follows initialization. Provider selections
on Pi come from Pi; an unavailable connection cannot change them or return a
local simulated success.

## Reads and actions

- `GET /svc`: PC/Pi inventory and per-host connectivity.
- `GET /api/services/graph`: nodes with host/unit identity and source.
- `GET /api/logic/catalog`: Pi catalog v2; older servers may not support it.
- `GET /api/resource/{name}`: observed resources; errors mean unknown, never free.
  Camera uses this same contract.
- `POST /svc/{unit}`: explicit `action` and `host`; unknown, stale and legacy
  capability data cannot authorize start/restart/enable.
- `POST /api/resource/{name}`: explicit stop/release forwarded to Pi.
  PC does not pretend a resource owner terminated locally.

System cards are read-only. Starting a moving task is separate from viewing an
image or reading device state and requires the proper safety gate. Pi resolves
resources and dependencies. PC does not force-kill robot processes locally or
treat target stop as proof that all members released their resources. Jupyter
is a manual, on-demand tool. The client preserves boot, Wi-Fi, SSH, splash and
the established LCD orientation.

## Retry

The watchdog runs outside test mode and uses the manager's configured list.
Retry requires `source: systemd`, `host: pc`, `can_move: false`, a fresh failed
state and active intent. Initially failed/unknown services without a previous
active observation are never auto-started. Stop/disable sets stopped intent
and suppresses retry even if the stop command fails. Pi and application
providers are not controlled by this watchdog.
