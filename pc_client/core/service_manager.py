"""Hybrid Service Manager for managing local and remote services."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Mapping, Optional, Union

from pc_client.adapters.systemd_adapter import (
    SystemdAdapter,
    MockSystemdAdapter,
    is_systemd_available,
)

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
    """
    Hybrid Service Manager for managing local and remote services.

    This manager acts as a central point for:
    - Managing local PC services (via systemd on Linux or simulated state)
    - Proxying requests to Rider-Pi for remote services
    - Aggregating service data for the UI graph

    On Linux systems with systemd available, the manager uses the SystemdAdapter
    to execute real systemctl commands. On other platforms (Windows, macOS) or
    when systemd is not available, it falls back to mock/simulated behavior.
    """

    def __init__(
        self,
        rest_adapter: Optional[Any] = None,
        systemd_adapter: Optional[Union[SystemdAdapter, MockSystemdAdapter]] = None,
        monitored_services: Optional[List[str]] = None,
        use_sudo: bool = True,
    ):
        """
        Initialize the Service Manager.

        Args:
            rest_adapter: Optional RestAdapter for communicating with Rider-Pi
            systemd_adapter: Optional SystemdAdapter for managing local services.
                           If None, auto-detects based on platform.
            monitored_services: Optional list of systemd unit names to monitor.
                              If provided, these are used instead of DEFAULT_LOCAL_SERVICES.
            use_sudo: Whether to use sudo for systemctl commands (default: True).
        """
        self._rest_adapter = rest_adapter
        self._last_remote_sync: float = 0.0

        # Auto-detect systemd availability if adapter not provided
        self._systemd_adapter: Union[SystemdAdapter, MockSystemdAdapter, None]
        if systemd_adapter is not None:
            self._systemd_adapter = systemd_adapter
            self._use_real_systemd = isinstance(systemd_adapter, SystemdAdapter) and systemd_adapter.available
        elif is_systemd_available():
            self._systemd_adapter = SystemdAdapter(use_sudo=use_sudo)
            self._use_real_systemd = self._systemd_adapter.available
            logger.info("ServiceManager: Using real systemd adapter (Linux detected)")
        else:
            self._systemd_adapter = None
            self._use_real_systemd = False
            logger.info("ServiceManager: Using mock/simulated mode (systemd not available)")

        # Initialize local services state from defaults (for mock mode)
        self._local_services: Dict[str, Dict[str, Any]] = {svc["unit"]: dict(svc) for svc in DEFAULT_LOCAL_SERVICES}

        # Store monitored services list for real systemd mode
        self._monitored_services = monitored_services or []

    def set_adapter(self, adapter: Optional[Any]) -> None:
        """Update the REST adapter reference."""
        self._rest_adapter = adapter

    def _is_local_service(self, unit: str) -> bool:
        """Check if a service is managed locally."""
        # In real systemd mode, check monitored services list
        if self._use_real_systemd and self._monitored_services:
            return unit in self._monitored_services
        # In mock mode, check local services dict
        return unit in self._local_services

    def get_local_services(self) -> List[Dict[str, Any]]:
        """
        Get list of all local services with current state.

        Note: This is the synchronous version that returns mock/cached data.
        For real systemd status, use get_local_services_async().
        """
        now = time.time()
        services = []
        for svc in self._local_services.values():
            service_data = dict(svc)
            service_data["ts"] = now
            service_data["is_local"] = True
            service_data["location"] = svc.get("location", "pc")
            services.append(service_data)
        return services

    async def get_local_services_async(self) -> List[Dict[str, Any]]:
        """
        Get list of all local services with current state (async version).

        On Linux with systemd, fetches real service status.
        On other platforms, returns mock/simulated data.
        """
        now = time.time()

        # If using real systemd, fetch status for monitored services concurrently
        if self._use_real_systemd and self._systemd_adapter and self._monitored_services:
            # Fetch all service details concurrently
            tasks = [self._systemd_adapter.get_unit_details(unit) for unit in self._monitored_services]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            services = []
            for unit, result in zip(self._monitored_services, results):
                if isinstance(result, Exception):
                    logger.error("Failed to get details for %s: %s", unit, result)
                    details: Mapping[str, Any] = {
                        "active": "unknown",
                        "sub": "unknown",
                        "enabled": "unknown",
                        "desc": "",
                    }
                elif isinstance(result, dict):
                    details = result
                else:
                    details = {
                        "active": "unknown",
                        "sub": "unknown",
                        "enabled": "unknown",
                        "desc": "",
                    }

                # Build service data structure
                service_data = {
                    "unit": unit,
                    "desc": details.get("desc", ""),
                    "active": details.get("active", "unknown"),
                    "sub": details.get("sub", "unknown"),
                    "enabled": details.get("enabled", "unknown"),
                    "group": "systemd",  # Default group for monitored services
                    "label": details.get("desc") or unit.replace(".service", "").replace("-", " ").title(),
                    "is_local": True,
                    "location": "pc",
                    "ts": now,
                }
                services.append(service_data)
            return services

        # Fall back to mock/simulated data
        return self.get_local_services()

    async def get_remote_services(self) -> List[Dict[str, Any]]:
        """Fetch remote services from Rider-Pi if adapter is available."""
        if self._rest_adapter is None:
            return []

        try:
            response = await self._rest_adapter.get_services()
            if response and not response.get("error"):
                services = response.get("services", [])
                for svc in services:
                    svc["is_local"] = False
                    svc["location"] = svc.get("location", "pi")
                self._last_remote_sync = time.time()
                return services
            logger.warning("Failed to fetch remote services: %s", response.get("error"))
        except Exception as exc:
            logger.error("Error fetching remote services: %s", exc)

        return []

    async def get_all_services(self) -> Dict[str, Any]:
        """
        Get all services (local + remote).

        Returns:
            Dictionary with 'services' list and 'timestamp'
        """
        # Use async version to get real systemd status when available
        local_services = await self.get_local_services_async()
        remote_services = await self.get_remote_services()

        # Merge services - remote services with same unit override local
        services_map: Dict[str, Dict[str, Any]] = {}
        for svc in local_services:
            services_map[svc["unit"]] = svc
        for svc in remote_services:
            services_map[svc["unit"]] = svc

        return {
            "services": list(services_map.values()),
            "timestamp": time.time(),
        }

    def _service_to_node(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a service dict to a graph node."""
        unit = service.get("unit", "unknown")
        active = str(service.get("active", "")).lower()

        # Determine status
        if active.startswith("active"):
            status = "active"
        elif active == "failed":
            status = "failed"
        else:
            status = "inactive"

        # Get edges for this service
        edges_out = SERVICE_EDGES.get(unit, [])

        # Determine location: local services are "pc", remote are "pi"
        location = service.get("location")
        if location is None:
            location = "pc" if service.get("is_local", True) else "pi"

        return {
            "label": service.get("label", unit.replace(".service", "").replace(".", " ").title()),
            "unit": unit,
            "status": status,
            "group": service.get("group", "services"),
            "since": service.get("since"),
            "description": service.get("desc", ""),
            "edges_out": edges_out,
            "is_local": service.get("is_local", True),
            "location": location,
        }

    async def get_service_graph(self) -> Dict[str, Any]:
        """
        Generate service graph data for the UI.

        Returns:
            Dictionary with 'nodes', 'edges', and 'generated_at'
        """
        all_services = await self.get_all_services()
        services = all_services.get("services", [])

        nodes = [self._service_to_node(svc) for svc in services]

        # Build edges list from node edges_out
        edges: List[Dict[str, str]] = []
        for node in nodes:
            for target in node.get("edges_out", []):
                edges.append({"from": node["unit"], "to": target})

        return {
            "generated_at": time.time(),
            "nodes": nodes,
            "edges": edges,
        }

    async def control_service(self, unit: str, action: str) -> Dict[str, Any]:
        """
        Control a service (start/stop/restart/enable/disable).

        Args:
            unit: Service unit name
            action: Action to perform (start, stop, restart, enable, disable)

        Returns:
            Result dictionary with 'ok' status
        """
        payload = {"action": action}

        # Check if this is a local service
        if self._is_local_service(unit):
            return await self._control_local_service(unit, action)

        # Remote service - proxy to Rider-Pi
        if self._rest_adapter is not None:
            try:
                result = await self._rest_adapter.service_action(unit, payload)
                return result
            except Exception as exc:
                logger.error("Error controlling remote service %s: %s", unit, exc)
                return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": f"Service {unit} not found"}

    async def _control_local_service(self, unit: str, action: str) -> Dict[str, Any]:
        """
        Control a local service.

        On Linux with systemd and for monitored services, executes real systemctl commands.
        For mock services (DEFAULT_LOCAL_SERVICES), simulates state change in memory.

        Args:
            unit: Service unit name
            action: Action to perform

        Returns:
            Result dictionary
        """
        # Use real systemd adapter only for monitored services
        if self._use_real_systemd and self._systemd_adapter and unit in self._monitored_services:
            result = await self._systemd_adapter.manage_service(unit, action)
            return result

        # Fall back to mock/simulated behavior for DEFAULT_LOCAL_SERVICES
        service = self._local_services.get(unit)
        if not service:
            return {"ok": False, "error": f"Service {unit} not found"}

        valid_actions = {"start", "stop", "restart", "enable", "disable"}
        if action not in valid_actions:
            return {"ok": False, "error": f"Unsupported action {action}"}

        # Update service state based on action
        if action == "start":
            service["active"] = "active"
            service["sub"] = "running"
        elif action == "stop":
            service["active"] = "inactive"
            service["sub"] = "dead"
        elif action == "restart":
            service["active"] = "active"
            service["sub"] = "running"
        elif action == "enable":
            service["enabled"] = "enabled"
        elif action == "disable":
            service["enabled"] = "disabled"

        logger.info("Local service %s: action=%s, new_state=%s", unit, action, service["active"])

        return {"ok": True, "unit": unit, "action": action}
