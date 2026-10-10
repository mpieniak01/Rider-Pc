# Rider-PC

PC-side interface and AI processing companion for Rider-Pi. Rider-Pi retains hardware execution and local robot applications; Rider-PC provides operator controls, REST/ZMQ adapters, local models and PC tools. Venom is planned for future top-level control; its integration is deferred.

## Project scope

Rider-PC provides operator controls and AI processing; hardware execution stays on Rider-Pi.
Venom is planned for future top-level coordination. Start with [project vision](docs/PROJECT.md),
[development](docs/development.md) and the [documentation policy](docs/DOCUMENTATION_POLICY.md).

## Local start

Preserve your existing `.env` and review model and network settings before starting:

```bash
.venv/bin/python -m pc_client.main
```

With `SERVER_PORT=8000`, open `http://localhost:8000/`.
See [development](docs/development.md) for environment checks and test scopes,
and [contributing](docs/CONTRIBUTING.md) for application changes.

## Documentation

📚 **[Full Documentation](docs/README.md)** - Complete documentation and guides

### Localization & Translation Status
- **English UI coverage**: all `/web/*.html` screens now rely on `web/assets/i18n.js` keys, the Polish strings have English fallbacks, and the chat/chat-pc/control/system scripts no longer declare duplicate helpers.
- **Verification**: run `node scripts/check_i18n.mjs` to ensure every key includes an English value, and `pytest` (inside `.venv`) covers the back-end regressions tied to UI rendering.
- **Notes**: run `?lang=en` against `view`, `control`, `navigation`, `system`, `models`, `project`, `assistant`, `chat`, `chat-pc`, `google_home`, `mode`, and `providers` to keep translations in sync.

### Quick Links

- **[Quick Start Guide](docs/QUICKSTART.md)** - Get started quickly
- **[AI Model Configuration](docs/AI_MODEL_CONFIGURATION.md)** - Setup real AI models
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture overview
- **[Configuration Hub](docs/CONFIGURATION.md)** - Central configuration guide
- **[API Documentation](docs/api-specs/README.md)** - REST API reference
- **[Replication Notes](docs/REPLICATION_NOTES.md)** - Notes for replicating the project

### Configuration Guides

- **[AI Model Configuration](docs/AI_MODEL_CONFIGURATION.md)** - Whisper, Piper, YOLOv8, Ollama setup
- **[Security Configuration](docs/SECURITY_CONFIGURATION.md)** - WireGuard VPN, mTLS setup
- **[Task Queue Configuration](docs/TASK_QUEUE_CONFIGURATION.md)** - Redis, RabbitMQ setup
- **[Monitoring Configuration](docs/MONITORING_CONFIGURATION.md)** - Prometheus, Grafana setup

### Operations

- **[PC Offload Integration](docs/PC_OFFLOAD_INTEGRATION.md)** - Enabling AI mode / provider parity between Rider-Pi and Rider-PC
- **[Service Management](docs/SERVICE_AND_RESOURCE_MANAGEMENT.md)** - Operations, monitoring, troubleshooting
- **[Future Work](docs/PROJECT.md)** - Planned improvements and development

## See Also

- [Rider-PI Repository](https://github.com/mpieniak01/Rider-Pi)

## 📝 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

Copyright (c) 2025-2026 Maciej Pieniak
