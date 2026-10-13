# Rider-PC motion and observation policy

Rider-Pi owns calibration, named profiles, direction mapping, smoothing, motion
replacement and the hardware watchdog. Rider-PC reads the robot contract and
forwards operator intent. It stores no independent robot calibration.

## Control

- Both Control and Calibration use manual settings v2 from
  `GET /api/calibration/controls`: units, display factors, ranges, control modes,
  named profiles and revision. Save and profile operations use the same Pi endpoint.
- Editing is a draft. Explicit Save requires the original revision. Conflicts
  require reviewing current values; a slider change never starts motion.
- Motion sends direction, mode (pulse/hold/release), device_settings and revision.
  PC does not derive vx/yaw or calculate a second ramp.
- Mouse/touch and keyboard holding renew at the interval advertised by Pi, with
  one request in flight and only the latest pending intent. Release decelerates
  without disarming. STOP cancels renewal immediately and retains its independent
  path without negotiation, a fresh clock or an authorization envelope.
- Operator arming remains explicit. Test permission remains independent. Hidden
  tabs and lost focus cancel held input, without renewing an old gesture.
- The proxy preserves generation, sequence, timestamp and TTL, and validates
  only the envelope format. Pi makes the final decision. Request dispatch or
  an SDK acknowledgement does not establish physical completion.
- Height, balance and figures use the same capability gate and commands as the
  Pi panel. Capability availability comes from Pi, never from a PC assumption.

## Observation

Concurrent identical REST reads share one transfer within the PC adapter. Every
consumer receives a separate copy with the original source and receipt times.
Completed safety reads are not cached. Writes invalidate in-flight read sharing;
they are never combined or replayed.

The catalogue shares a one-second browser snapshot and a bounded canonical
contract proof. STOP/disarm/ESTOP bypass proof negotiation. Local PC features do
not depend on robot contract negotiation.

Overview: telemetry 1 s; Pi system 2 s; vision 2 s only with an active camera;
catalogue/metrics and PC inventory 10 s. Idle/unknown camera gets one metadata
read and no repeated obstacle reads. Pi CPU charts reuse hist_ts and hist_cpu_peak from the Pi sampler; gaps are
visible and no second CPU measurement is requested. LCD accepts confirmed GPIO
backlight observations and renders ON/OFF. Existing shared server snapshots and binary
frame reuse remain in effect.

REST safety polling and BUS/SSE events still coexist deliberately: safety clock
negotiation is not replaced with a cached BUS timestamp. A future single collector
with demand-based subscriptions must preserve these clock/TTL guarantees.

## Verification

Use isolated fixtures for arming, arrows, held input, STOP and settings writes.
Physical motion tests require a separate operator decision. Read-only live checks
may compare revisions, units and executor confirmation without sending motion.

## Permission and connectivity

Rider-Pi's sole motion executor decides ARM and validates every actuator request.
The PC forwards explicit operator envelopes without fetching telemetry first.
Failed observations retain the last reported permission and original timestamps,
with `stale=true`; they never synthesize DISARMED. The panel identifies last known
permission separately from execution readiness and connection availability.
STOP remains independent of observation and no failed request is replayed.
Deploy the executor-owned permission contract on Pi before deploying this client.
