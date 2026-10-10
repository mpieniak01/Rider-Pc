# Rider-PC and ecosystem vision

The project develops a personal educational robot and an AI environment for
operating it. The first version hosted controls and applications on Rider-Pi.
Rider-PC moves the operator interface and heavier processing to the computer
while retaining the device applications. Venom is intended to provide future
top-level control; its integration and detailed contract are deferred.

| Component | Responsibility |
| --- | --- |
| Rider-Pi | Drivers, sensors, motion execution, camera, audio, LCD and local applications |
| Rider-PC | Operator panel, Pi communication, AI models, local chat and PC tools |
| Venom | Planned top-level control and coordination |

Physical execution and local safeguards stay on the Pi. Local chat and PC
tools can run without the robot; hardware commands require a Rider-Pi
connection. Selecting a PC provider does not move device drivers to the PC.

## Product directions

| Domain | Scope |
| --- | --- |
| Robot | Panel, telemetry, scenarios and commands through REST/ZMQ adapters |
| Local models | LLM, vision, ASR/TTS and Chat PC |
| AI-FORGE | Planned datasets, training and model adaptation |
| PC management | Services, resources, logs, diagnostics and future recovery automation |
| Web Intelligence | Planned source search and analysis |
| Smart Home | Device and scene integrations |
| Routines and tasks | Planned user schedules and automations |
| Knowledge | Documents, embeddings and model context |
| Flows Engine | Planned workflows across domains |

This table describes product scope and direction. A router, provider or page
in the repository does not establish completion of an entire domain. The AI
compute queue is not a user routine scheduler. A panel or cached telemetry
does not establish successful execution on the physical robot.

## Communication and verification

REST carries status and commands; ZMQ carries events and AI tasks. Rider-Pi
selects voice, vision and text providers. Capability negotiation, heartbeat
and fallback need checks including PC connection loss. Mocked tests do not
replace real model startup or hardware verification.

See [architecture](ARCHITECTURE.md), [offload integration](PC_OFFLOAD_INTEGRATION.md)
and [development](development.md). Backlogs and individual test results stay
local according to the [documentation policy](DOCUMENTATION_POLICY.md).
