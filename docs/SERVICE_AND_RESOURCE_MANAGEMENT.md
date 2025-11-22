# Service and Resource Management (systemd) – Rider-Pi (repo state)

Document recreated based on real units and targets from `systemd/` in Rider-Pi. Removed imaginary targets (`rider-manual.target`, `rider-autonomy.target` etc.). The "Proposals" section at the end shows potentially missing profiles, but these are things yet to be created.

## Current Targets (existing in repo)

| Target | What it starts (Wants/After) | Autostart | Use case | Start/stop command |
| --- | --- | --- | --- | --- |
| `rider-minimal.target` | Minimal set: broker, API, vision, splash/post-splash | YES (WantedBy=multi-user.target) | Basic robot startup (web + bus + dispatcher) | `systemctl enable --now rider-minimal.target` / `systemctl stop rider-minimal.target` |
| `rider-dev.target` | `jupyter.service` (+ GUI dependencies) | NO (enable manually) | Developer profile with JupyterLab | `systemctl start rider-dev.target` / `systemctl stop rider-dev.target` |

## Services from repo and autostart recommendations

| Service (systemd unit) | Role | Autostart (recommended) | Resources / notes | Related UI functions |
| --- | --- | --- | --- | --- |
| `rider-api.service` | HTTP/SSE API | YES (core) | CPU; After=network-online | All API/health tiles |
| `rider-broker.service` | ZMQ Broker (XSUB/XPUB) | YES (core) | CPU; After=network-online | All motion/vision functions |
| `rider-web-bridge.service` | HTTP→ZMQ motion bridge | YES (core) | CPU; Wants=network-online | Motion control from UI |
| `rider-vision.service` | Vision Dispatcher | YES (core/minimal) | Camera/GPU; may conflict with preview/tracker | Basic vision preview/analysis |
| `rider-vision-offload.service` | Offload Dispatcher | NO (optional) | GPU/CPU; if using offload | Vision offload |
| `rider-choreographer.service` | Event orchestration | NO/MODE | CPU; depends on broker | Automata/Event pilot |
| `rider-motion-bridge.service` | Motion/XGO – telemetry and control | YES (motion) | CPU; After=broker | Sending motion commands from UI |
| `rider-odometry.service` | Odometry | YES (motion/autonomy) | CPU; After=broker, motion-bridge | Position diagnostics |
| `rider-mapper.service` | SLAM / occupancy map | NO/MODE | CPU; After=broker, odometry | Reconnaissance mode/autonomy |
| `rider-obstacle.service` | Obstacle detection (ROI on edge preview) | NO/MODE | Camera + CPU/GPU; After=edge-preview | Reconnaissance mode/autonomy |
| `rider-navigator.service` | Autonomous navigator | NO/MODE | CPU; After=broker/motion/vision/obstacle/odometry/mapper | Reconnaissance mode (autonomous) |
| `rider-cam-preview.service` | Raw camera preview | NO (diag/manual) | Camera – exclusive access | Camera preview (tile) |
| `rider-edge-preview.service` | Preview with edge filter | NO (diag) | Camera + CPU/GPU; conflicts with other previews | Filtered preview (diag) |
| `rider-ssd-preview.service` | SSD preview with boxes | NO (diag) | Camera + GPU; one camera service at a time | SSD preview (diag) |
| `rider-tracker.service` | MediaPipe Tracker (face/hand) | NO (feature) | Camera + GPU/CPU; preferred vs preview | `Follow Face` / `Follow Hand` |
| `rider-tracking-controller.service` | Rotation controller "Follow Me" | NO (feature) | CPU; After=tracker | `Follow Face` / `Follow Hand` (motion controller) |
| `rider-face.service` | Face renderer on LCD | NO/MODE | 2" LCD; After=api | Face display (LCD) |
| `rider-google-bridge.service` | Google Home integration | NO (optional) | External network; may use audio | GH integration |
| `rider-voice-web.service` | Voice Web API (Piper TTS + Vosk ASR) | NO (enable on demand) | Microphone + speaker | Voice control (web) |
| `rider-voice.service` | CLI voice assistant (based on voice-web) | NO (enable on demand) | Microphone + speaker; After=voice-web | Voice control (CLI) |
| `rider-post-splash.service` | Post-splash (after API/IP) | With minimal | Lightweight; WantedBy=rider-minimal.target | Info screen after boot |
| `rider-boot-splash.service` | Splash on boot | With minimal | Lightweight; cleanup + LCD off | Startup screen |
| `wifi-unblock.service` | Wi-Fi unblock | YES (system) | Started before network | — |
| `jupyter.service` | JupyterLab DEV | NO (dev target only) | Used by `rider-dev.target` | Dev |

Autostart legend: "YES (core)" – suggested in every boot; "NO/MODE" – enable in specific profile (autonomy/diag/feature). The "Related UI functions" column maps tiles: `Follow Face/Follow Hand` → tracker + tracking-controller; "Reconnaissance mode (autonomous)" → navigator + obstacle + mapper + odometry (+ motion/vision as dependencies).

## UI Functions vs Started Services

"Functions" tiles don't execute motion/vision logic themselves – they call the Rider-Pi API, which starts/stops systemd units. Explicit button mapping Start/Stop:

| UI Function | `Start` starts services | `Stop` stops | Resources / conflicts | Operational notes |
| --- | --- | --- | --- | --- |
| `Follow Face` | `rider-tracker.service`, `rider-tracking-controller.service`, `rider-motion-bridge.service` (+ core) | Same: tracker + tracking-controller (+ motion-bridge if not shared) | Camera, CPU/GPU; conflict with other camera services (cam/edge/ssd/vision) | Make sure camera is free; when busy, stop preview/vision or use lock. Controller sends motion commands via motion-bridge. |
| `Follow Hand` | As above: `rider-tracker`, `rider-tracking-controller`, `rider-motion-bridge` (tracker in hand mode) | As above | Camera, CPU/GPU; conflict with preview/vision | Same pipeline, different tracker mode; don't run parallel with camera previews. |
| `Reconnaissance mode (autonomous)` | `rider-motion-bridge`, `rider-odometry`, `rider-mapper`, `rider-edge-preview`, `rider-obstacle`, `rider-vision`, `rider-navigator` (+ core) | Same: navigator + obstacle + mapper + odometry + motion-bridge (+ vision/edge-preview if started from mode) | Camera, CPU/GPU; conflict with other previews (cam/ssd) | Edge-preview needed for obstacle; vision for navigator; odometry+mapper for planning. Before start, free camera from other services. |

If UI gets new tiles, add row with list of units started/stopped by `Start`/`Stop` buttons.

## Resource Reservation (current state vs. recommendation)

| Resource | Services using it | Recommendation (to add) | Operational note |
| --- | --- | --- | --- |
| Camera (`/dev/video0`) | `rider-cam-preview`, `rider-edge-preview`, `rider-ssd-preview`, `rider-tracker`, `rider-vision` | Add `Conflicts=` between camera services or lock `/run/rider/camera.lock` | Run only one camera service at a time; tracker has priority over preview |
| Microphone | `rider-voice-web`, `rider-voice`, `rider-google-bridge` (if listening) | `Conflicts=rider-voice-web.service rider-voice.service` | Choose one voice stack; the other remains `inactive` |
| Speaker | `rider-voice-web`, `rider-voice`, `rider-google-bridge` | As above + volume limiter in UI | Pause TTS when changing stack |
| 2" LCD | `rider-face.service`, (splash/post-splash) | `Conflicts=` if other LCD consumers appear | Currently no competition |

Example override for camera services:
```
[Unit]
Requires=dev-video0.device
After=dev-video0.device
Conflicts=rider-cam-preview.service rider-edge-preview.service rider-ssd-preview.service rider-vision.service

[Service]
Restart=on-failure
RestartSec=1
StartLimitIntervalSec=60
StartLimitBurst=5
```

## Operational Procedures (based on existing targets)

| Activity | Steps | Notes |
| --- | --- | --- |
| Start minimal profile | `systemctl start rider-minimal.target` | Basic set (broker+API+vision+splash) |
| Developer profile | `systemctl start rider-dev.target` | Starts Jupyter; stop after session |
| Enable voice control | `systemctl start rider-voice-web.service` (or `.service` + `.socket`) | Make sure microphone/speaker free; don't run `rider-voice.service` in parallel |
| "Follow Face/Hand" mode | `systemctl start rider-tracker.service rider-tracking-controller.service` | If camera busy with preview/vision – free resource and retry start |
| Autonomous mode (manual set) | `systemctl start rider-motion-bridge rider-odometry rider-mapper rider-obstacle rider-navigator` | Start in given order; make sure vision/edge-preview available |
| Image diagnostics | `systemctl start rider-edge-preview.service` or `rider-ssd-preview.service` | After tests `systemctl stop ...` to release camera |

## Minimal Unit Settings (recommendations to implement)

- `Restart=on-failure`, `RestartSec=1`, `StartLimitIntervalSec` + `StartLimitBurst` (most units already have restart; worth adding limits).
- `After=network-online.target` and `After=dev-video0.device` for camera services.
- Optional services (voice, preview, integrations) – don't enable in autostart; activate per mode.
- Keep autostart in `rider-minimal.target`; `rider-dev.target` only when you need DEV environment.

## Proposed Missing Targets (to create, if desired)

| Proposed target | What it groups | What for | Status |
| --- | --- | --- | --- |
| `rider-autonomy.target` | motion-bridge, odometry, mapper, obstacle, navigator, vision | Single start for autonomy | To create (doesn't exist in repo) |
| `rider-voice.target` | voice-web **or** voice (audio exclusivity) | Quick enable of voice control | To create |
| `rider-diagnostics.target` | edge-preview, ssd-preview, cam-preview | Diagnostic sessions, locks camera | To create |

## Deployment Order Checklist

1. Verify which services are actually in `enable` (default WantedBy=multi-user.target); keep autostart for core (`rider-broker`, `rider-api`, `rider-web-bridge`, `rider-vision`, `wifi-unblock`, splash/post-splash).
2. Disable autostart of optional: preview, tracker, obstacle, mapper, navigator, voice*, google-bridge, choreographer, vision-offload, jupyter (unless dev box).
3. Add `Conflicts`/lock on camera and symmetric `Conflicts` between `rider-voice-web.service` and `rider-voice.service`.
4. Consider creating targets `rider-autonomy.target` and `rider-diagnostics.target` for simple start/stop procedures.
5. In UI before starting service check resources; if busy, propose "Free resource → Start".
6. Add `/health` endpoint in `rider-api` with list of units and resource locks for diagnostic view.
