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
                    s.get("observed_at", response.get("observed_at", now)),
                )
                for s in services
                if isinstance(s, dict) and s.get("unit")
            ]
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
            rows.append(
                self._decorate(
                    {
                        "unit": f"{domain}.provider",
                        "label": f"{domain} provider",
                        "group": "providers",
                        "kind": "application_provider",
                        "active": "active" if getattr(provider, "_initialized", False) else "unknown",
                        "ready": getattr(provider, "_initialized", False),
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
        return {
            "services": local + remote + self._provider_rows(),
            "timestamp": time.time(),
            "hosts": {
                "pc": {"configured": bool(self._monitored_services), "demo": self._mock_mode},
                "pi": {
                    "offline": bool(self._remote_error),
                    "error": self._remote_error,
                    "observed_at": self._last_remote_sync or None,
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
        return {"generated_at": time.time(), "nodes": nodes, "edges": edges, "hosts": data["hosts"]}

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
