"""Hybrid Service Manager for managing local and remote services."""

import asyncio
import logging
import time
from typing import Any, Dict, List

from pc_client.adapters.systemd_adapter import (
    SystemdAdapter,
    MockSystemdAdapter,
)

from pc_client.core.remote_safety import RemoteSafety, finite_number

logger = logging.getLogger(__name__)


# Default local PC services for simulation
DEFAULT_LOCAL_SERVICES: List[Dict[str, Any]] = [
    {
        "unit": "pc_client.service",
        "desc": "Main REST API server",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "api",
        "label": "FastAPI Server",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "cache.service",
        "desc": "SQLite cache for data buffering",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "data",
        "label": "Cache Manager",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "zmq.service",
        "desc": "Real-time data stream subscriber",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "messaging",
        "label": "ZMQ Subscriber",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "voice.provider",
        "desc": "ASR/TTS processing",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "providers",
        "label": "Voice Provider",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "vision.provider",
        "desc": "Object detection and frame processing",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "providers",
        "label": "Vision Provider",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "text.provider",
        "desc": "LLM text generation and NLU",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "providers",
        "label": "Text Provider",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "task_queue.service",
        "desc": "Redis-based task queue",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "queue",
        "label": "Task Queue",
        "is_local": True,
        "location": "pc",
    },
    {
        "unit": "telemetry.service",
        "desc": "ZMQ telemetry and Prometheus metrics",
        "active": "active",
        "sub": "running",
        "enabled": "enabled",
        "group": "monitoring",
        "label": "Telemetry Publisher",
        "is_local": True,
        "location": "pc",
    },
]


# Service dependencies for graph edges
SERVICE_EDGES: Dict[str, List[str]] = {
    "pc_client.service": ["cache.service", "zmq.service"],
    "zmq.service": ["cache.service"],
    "voice.provider": ["task_queue.service"],
    "vision.provider": ["task_queue.service"],
    "text.provider": ["task_queue.service", "cache.service"],
}


class ServiceManager:
    """Stan systemd tylko z konfiguracji; demo wymaga jawnego wyboru."""

    def __init__(
        self,
        rest_adapter=None,
        systemd_adapter=None,
        monitored_services=None,
        use_sudo=True,
        mock_mode=False,
        non_actuating_services=None,
    ):
        self._rest_adapter = rest_adapter
        self._monitored_services = list(dict.fromkeys(monitored_services or []))
        self._non_actuating_services = set(non_actuating_services or []) & set(self._monitored_services)
        self._mock_mode = mock_mode or isinstance(systemd_adapter, MockSystemdAdapter)
        self._systemd_adapter = systemd_adapter
        if self._systemd_adapter is None and self._monitored_services and not self._mock_mode:
            self._systemd_adapter = SystemdAdapter(use_sudo=use_sudo)
        self._use_real_systemd = not self._mock_mode and bool(self._systemd_adapter and self._systemd_adapter.available)
        self._local_services = {svc["unit"]: dict(svc) for svc in DEFAULT_LOCAL_SERVICES} if self._mock_mode else {}
        self._remote_services = []
        self._last_remote_sync = 0.0
        self._remote_meta = {}
        self._remote_error = "not_connected"
        self._desired = {}
        self._providers = {}
        self.safety = RemoteSafety()

    @property
    def monitored_services(self):
        return list(self._monitored_services)

    def set_adapter(self, adapter):
        self._rest_adapter = adapter

    def set_providers(self, providers):
        self._providers = providers or {}

    def _is_local_service(self, unit):
        return unit in self._monitored_services or (self._mock_mode and unit in self._local_services)

    def _decorate(self, service, host, source, observed_at, stale=False, error=None):
        row = dict(service)
        row.setdefault("active", row.get("active_state", "unknown"))
        row.setdefault("load", row.get("load_state", "unknown"))
        row.setdefault("sub", row.get("sub_state", "unknown"))
        row.setdefault("enabled", row.get("unit_file_state", "unknown"))
        row.setdefault("active_state", row.get("active", "unknown"))
        row.setdefault("sub_state", row.get("sub", "unknown"))
        row.setdefault("unit_file_state", row.get("enabled", "unknown"))
        row.setdefault("load_state", row.get("load", "unknown"))
        row.setdefault("process_running", row["active_state"] == "active" and row["sub_state"] in {"running", "exited"})
        for key in ("active", "sub", "enabled"):
            row.setdefault(key, "unknown")
        row.update(
            host=host,
            location=host,
            identity=f"{host}:{row['unit']}",
            is_local=host == "pc",
            source=source,
            observed_at=observed_at,
            ts=observed_at,
            stale=stale or row.get("stale") is True,
            offline=bool(error) or row.get("offline") is True,
        )
        if error:
            row["error"] = error
            row["last_known_active"] = row.get("last_known_active", row.get("active"))
            row["active"] = "unknown"
            row["sub"] = "unknown"
        if host == "pc":
            unit = row["unit"]
            row["can_move"] = (
                False if (unit in self._non_actuating_services or row.get("kind") == "application_provider") else None
            )
            if self._mock_mode:
                row["can_move"] = False
            row["desired"] = self._desired.get(unit, "unknown")
        return row

    def get_local_services(self):
        now = time.time()
        if self._mock_mode:
            return [self._decorate(s, "pc", "demo", now) for s in self._local_services.values()]
        return [
            self._decorate(
                {"unit": u, "active": "unknown", "sub": "unknown", "enabled": "unknown", "group": "systemd"},
                "pc",
                "systemd",
                None,
                True,
                "status_not_observed",
            )
            for u in self._monitored_services
        ]

    async def get_local_services_async(self):
        if self._mock_mode:
            return self.get_local_services()
        if not self._monitored_services:
            return []
        if not self._use_real_systemd:
            return [
                self._decorate(
                    {"unit": u, "active": "unknown", "sub": "unknown", "enabled": "unknown", "group": "systemd"},
                    "pc",
                    "systemd",
                    None,
                    True,
                    "systemd_unavailable",
                )
                for u in self._monitored_services
            ]
        results = await asyncio.gather(
            *(self._systemd_adapter.get_unit_details(u) for u in self._monitored_services), return_exceptions=True
        )
        rows = []
        for unit, details in zip(self._monitored_services, results):
            error = None
            if isinstance(details, Exception) or not isinstance(details, dict):
                error, details = "status_failed", {}
            if details.get("active") == "unknown":
                error = error or "status_unknown"
            if details.get("active") == "active" and unit not in self._desired:
                self._desired[unit] = "active"
            rows.append(
                self._decorate(
                    {**details, "unit": unit, "group": "systemd"}, "pc", "systemd", time.time(), bool(error), error
                )
            )
        return rows

    async def get_remote_services(self):
        try:
            if self._rest_adapter is None:
                raise RuntimeError("not_connected")
            response = await self._rest_adapter.get_services()
            if not isinstance(response, dict) or response.get("error"):
                raise RuntimeError((response or {}).get("error", "invalid_response"))
            services = response.get("services")
            if not isinstance(services, list):
                raise RuntimeError("invalid_inventory")
            now = time.time()
            version = response.get("contract_version", response.get("catalog_version"))
            self._remote_services = [
                self._decorate(
                    {
                        **s,
                        "contract_version": version,
                        "stale": s.get("stale") is True or response.get("stale") is True,
                        "offline": s.get("offline") is True or response.get("offline") is True,
                    },
                    "pi",
                    "demo" if getattr(self._rest_adapter, "is_mock", False) else s.get("source", "systemd"),
                    s.get("observed_at", response.get("observed_at")),
                )
                for s in services
                if isinstance(s, dict) and s.get("unit")
            ]
            source_times = [
                s.get("observed_at")
                for s in self._remote_services
                if finite_number(s.get("observed_at")) and s["observed_at"] > 0
            ]
            oldest_member = min(source_times) if source_times else None
            observed = response.get("observed_at")
            if "observed_at" not in response:
                observed = oldest_member
            if not finite_number(observed) or observed <= 0:
                observed = None
            self._remote_meta = {
                "observed_at": observed,
                "source": response.get("source", "systemd"),
                "observed_at_basis": "source" if "observed_at" in response else "min_member",
                "oldest_member_observed_at": oldest_member,
                "contract_meta": response.get("contract_meta"),
                "stale": response.get("stale") is True,
            }
            self._last_remote_sync = now
            self._remote_error = "inventory_offline" if response.get("offline") is True else None
        except Exception as exc:
            self._remote_error = str(exc)
            return [
                self._decorate(s, "pi", s.get("source", "systemd"), s.get("observed_at"), True, self._remote_error)
                for s in self._remote_services
            ]
        return [dict(s) for s in self._remote_services]

    def _provider_rows(self):
        rows = []
        for domain, provider in self._providers.items():
            telemetry = provider.get_telemetry() if callable(getattr(provider, "get_telemetry", None)) else {}
            initialized = telemetry.get("initialized") is True
            ready = initialized and telemetry.get("ready") is True
            rows.append(
                self._decorate(
                    {
                        "unit": f"{domain}.provider",
                        "label": f"{domain} provider",
                        "group": "providers",
                        "kind": "application_provider",
                        "active": "active" if initialized else "inactive",
                        "process_running": initialized,
                        "initialized": initialized,
                        "ready": ready,
                        "runtime_mode": telemetry.get("mode", "unknown"),
                        "provider_source": telemetry.get("source", "unknown"),
                        "error": telemetry.get("error"),
                        "capabilities": telemetry.get("capabilities", {}),
                        "enabled": "not-applicable",
                        "can_move": False,
                        "actions": [],
                    },
                    "pc",
                    "application",
                    time.time(),
                )
            )
        return rows

    async def get_all_services(self):
        local, remote = await asyncio.gather(self.get_local_services_async(), self.get_remote_services())
        providers = self._provider_rows()
        return {
            "contract_version": 2,
            "source": "pc_aggregator",
            "observed_at": None,
            "generated_at": time.time(),
            "services": local + remote + providers,
            "timestamp": time.time(),
            "hosts": {
                "pc": {
                    "configured": bool(self._monitored_services),
                    "demo": self._mock_mode,
                    "observed_at": min(
                        (
                            row["observed_at"]
                            for row in local + providers
                            if finite_number(row.get("observed_at")) and row["observed_at"] > 0
                        ),
                        default=None,
                    ),
                },
                "pi": {
                    **self._remote_meta,
                    "offline": bool(self._remote_error),
                    "error": self._remote_error,
                    "received_at": self._last_remote_sync or None,
                },
            },
        }

    def _service_to_node(self, service):
        active = str(service.get("active", "unknown")).lower()
        status = active if active in {"active", "failed", "inactive"} else "unknown"
        return {
            **service,
            "status": status,
            "label": service.get("label") or service.get("desc") or service["unit"],
            "description": service.get("desc", ""),
            "edges_out": service.get("edges_out", []),
            "group": service.get("group", "services"),
        }

    async def get_service_graph(self):
        data = await self.get_all_services()
        nodes = [self._service_to_node(s) for s in data["services"]]
        by_alias = {(n["host"], n.get("id", n["unit"])): n["identity"] for n in nodes}
        identities = {n["identity"] for n in nodes}
        edges = []
        for node in nodes:
            targets = node.get("dependencies", node.get("edges_out", []))
            for target in targets:
                identity = target if ":" in target else by_alias.get((node["host"], target), f"{node['host']}:{target}")
                if identity in identities:
                    edges.append({"from": node["identity"], "to": identity})
        return {
            "contract_version": 2,
            "source": "pc_aggregator",
            "observed_at": None,
            "generated_at": time.time(),
            "stale": bool(self._remote_error),
            "partial": bool(self._remote_error),
            "nodes": nodes,
            "edges": edges,
            "hosts": data["hosts"],
        }

    async def get_service_logs(self, unit, host):
        """Odczyt na żądanie, tylko konkretna jednostka wybranego hosta."""
        if host not in {"pc", "pi"}:
            return {"ok": False, "error": "host_required", "status_code": 400}
        if host == "pc":
            if not self._is_local_service(unit):
                return {"ok": False, "error": "unit_not_configured", "status_code": 404}
            if self._mock_mode:
                return {
                    "ok": True,
                    "unit": unit,
                    "host": "pc",
                    "source": "demo",
                    "simulated": True,
                    "observed_at": time.time(),
                    "lines": [],
                }
            if not self._use_real_systemd:
                return {
                    "ok": False,
                    "unit": unit,
                    "host": "pc",
                    "source": "pc/systemd/journal",
                    "observed_at": None,
                    "lines": [],
                    "error": "systemd_unavailable",
                    "status_code": 503,
                }
            from pc_client.core.service_logs import read_logs

            result = await asyncio.to_thread(read_logs, unit, catalog=self._monitored_services)
        else:
            rows = await self.get_remote_services()
            if not any(row["unit"] == unit for row in rows):
                return {"ok": False, "error": "unit_not_in_pi_inventory", "status_code": 404}
            try:
                result = await self._rest_adapter.get_service_logs(unit)
            except Exception as exc:
                result = {"ok": False, "error": str(exc), "observed_at": None, "lines": []}
        if not isinstance(result, dict):
            result = {"ok": False, "error": "invalid_log_response"}
        result = dict(result, host=host, unit=unit)
        result.setdefault("source", f"{host}/systemd/journal")
        result.setdefault("observed_at", None)
        if result.get("ok") is not True:
            result.setdefault("status_code", 503)
        return result

    async def control_service(self, unit, action, host=None, automatic=False, payload=None):
        if action not in {"start", "stop", "restart", "enable", "disable"}:
            return {"ok": False, "error": f"Unsupported action {action}", "status_code": 400}
        if host is None and self._is_local_service(unit) and not self._mock_mode:
            return {"ok": False, "error": "host_required", "status_code": 409}
        both = self._is_local_service(unit) and any(s["unit"] == unit for s in self._remote_services)
        if host is None and both:
            return {"ok": False, "error": "ambiguous_host", "status_code": 409}
        if host == "pc" or (host is None and self._is_local_service(unit)):
            if not self._is_local_service(unit):
                return {"ok": False, "error": f"Service {unit} not found", "status_code": 404}
            if automatic and (unit not in self._non_actuating_services or self._desired.get(unit) != "active"):
                return {"ok": False, "error": "automatic_restart_forbidden", "status_code": 409}
            if action in {"stop", "disable"}:
                self._desired[unit] = "stopped"
            if self._mock_mode:
                service = self._local_services.get(unit)
                if service is None:
                    return {"ok": False, "error": f"Service {unit} not found", "status_code": 404}
                if action in {"start", "restart", "stop"}:
                    service["active"] = "inactive" if action == "stop" else "active"
                    service["sub"] = "dead" if action == "stop" else "running"
                else:
                    service["enabled"] = "enabled" if action == "enable" else "disabled"
                result = {"ok": True, "source": "demo"}
            elif not self._use_real_systemd:
                result = {"ok": False, "error": "systemd_unavailable"}
            elif action in {"start", "restart", "enable"} and unit not in self._non_actuating_services:
                result = {"ok": False, "error": "unknown_actuation_capability", "status_code": 409}
            else:
                result = await self._systemd_adapter.manage_service(unit, action)
            if result.get("ok") and action in {"start", "restart"}:
                self._desired[unit] = "active"
            return {**result, "unit": unit, "action": action, "host": "pc"}
        if host not in {None, "pi"}:
            return {"ok": False, "error": "invalid_host", "status_code": 400}
        if self._rest_adapter is None:
            return {"ok": False, "error": "pi_offline", "status_code": 503}
        if automatic:
            return {"ok": False, "error": "remote_auto_restart_forbidden", "status_code": 409}
        if action in {"start", "restart", "enable"}:
            rows = await self.get_remote_services()
            row = next((s for s in rows if s["unit"] == unit), None)
            if row is None or row.get("stale") or row.get("offline") or row.get("installed") is False:
                return {"ok": False, "error": "unconfirmed_service", "status_code": 409}
            observed = row.get("observed_at")
            if (
                type(row.get("contract_version")) is not int
                or row["contract_version"] != 2
                or not isinstance(row.get("can_move"), bool)
                or not finite_number(observed)
                or not 0 <= time.time() - observed <= 3
            ):
                return {"ok": False, "error": "unknown_actuation_capability", "status_code": 409}
            if row.get("can_move"):
                if action == "enable":
                    return {"ok": False, "error": "moving_autostart_forbidden", "status_code": 409}
                if row.get("motion_owner") not in {"manual", "follow_me", "navigation"}:
                    return {"ok": False, "error": "unknown_motion_owner", "status_code": 409}
                try:
                    context = await self.safety.command_context(
                        self._rest_adapter, row.get("motion_owner"), supplied=payload
                    )
                except Exception as exc:
                    return {"ok": False, "error": str(exc), "status_code": 409}
                payload = {**(payload or {}), **context}
        try:
            return await self._rest_adapter.service_action(unit, {"action": action, **(payload or {})})
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _control_local_service(self, unit, action):
        return await self.control_service(unit, action, host="pc")
