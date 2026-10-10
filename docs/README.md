# Rider-PC documentation

[Unified Pi/PC API contracts](api-specs/contracts.md) — New clients negotiate the v1 envelope through Accept; examples without negotiation describe the legacy projection. Reception time does not replace observation time.


Rider-PC provides operator controls, AI processing and PC tools for Rider-Pi.
Hardware execution remains on the robot. Venom is planned for top-level
coordination; its integration is deferred.

## Start here

- [Project vision](PROJECT.md), [architecture](ARCHITECTURE.md), [quick start](QUICKSTART.md).
- [Development](development.md), [contributing](CONTRIBUTING.md).
- [Documentation policy](DOCUMENTATION_POLICY.md), [Polish documentation](../docs_pl/README.md).

## Interfaces and configuration

- [Safe client and operator consent](SAFE_ROBOT_CLIENT.md).

- [Pi ↔ PC integration](PC_OFFLOAD_INTEGRATION.md).
- [Configuration](CONFIGURATION.md), [AI models](AI_MODEL_CONFIGURATION.md), [task queue](TASK_QUEUE_CONFIGURATION.md).
- [Monitoring](MONITORING_CONFIGURATION.md), [service management](SERVICE_AND_RESOURCE_MANAGEMENT.md), [network configuration](SECURITY_CONFIGURATION.md).
- [API index](api-specs/README.md), [control](api-specs/CONTROL.md), [navigation](api-specs/NAVIGATOR.md).
- [UI/API replication](REPLICATION_NOTES.md), [dashboard styleguide](../docs_pl/styleguide.md), [Google Assistant](../docs_pl/google-assistant-integration.md).

Operational backlogs, phase reports, audits and session-specific runtime results
are local files in ignored directories. Mocked tests and cached data do not
establish that a model or the physical robot is running correctly.

Polish is the starting point; keep English contracts and guides current.
Local plans and reports exist only in `docs_pl/_to_do/` and `docs_pl/_done/`.

- [Pi/PC operator panel](OPERATOR_PANEL.md)
