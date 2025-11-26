"""Hybrid Service Manager for managing local and remote services."""

import logging
import time
from typing import Any, Dict, List, Optional

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
    - Managing local PC services (simulated state)
    - Proxying requests to Rider-Pi for remote services
    - Aggregating service data for the UI graph
    """

    def __init__(self, rest_adapter: Optional[Any] = None):
        """
        Initialize the Service Manager.

        Args:
            rest_adapter: Optional RestAdapter for communicating with Rider-Pi
        """
        self._rest_adapter = rest_adapter
        # Initialize local services state from defaults
        self._local_services: Dict[str, Dict[str, Any]] = {
            svc["unit"]: dict(svc) for svc in DEFAULT_LOCAL_SERVICES
        }
        self._last_remote_sync: float = 0.0

    def set_adapter(self, adapter: Optional[Any]) -> None:
        """Update the REST adapter reference."""
        self._rest_adapter = adapter

    def _is_local_service(self, unit: str) -> bool:
        """Check if a service is managed locally."""
        return unit in self._local_services

    def get_local_services(self) -> List[Dict[str, Any]]:
        """Get list of all local services with current state."""
        now = time.time()
        services = []
        for svc in self._local_services.values():
            service_data = dict(svc)
            service_data["ts"] = now
            service_data["is_local"] = True
            services.append(service_data)
        return services

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
        local_services = self.get_local_services()
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

        return {
            "label": service.get("label", unit.replace(".service", "").replace(".", " ").title()),
            "unit": unit,
            "status": status,
            "group": service.get("group", "services"),
            "since": service.get("since"),
            "description": service.get("desc", ""),
            "edges_out": edges_out,
            "is_local": service.get("is_local", True),
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
            return self._control_local_service(unit, action)

        # Remote service - proxy to Rider-Pi
        if self._rest_adapter is not None:
            try:
                result = await self._rest_adapter.service_action(unit, payload)
                return result
            except Exception as exc:
                logger.error("Error controlling remote service %s: %s", unit, exc)
                return {"ok": False, "error": str(exc)}

        return {"ok": False, "error": f"Service {unit} not found"}

    def _control_local_service(self, unit: str, action: str) -> Dict[str, Any]:
        """
        Control a local service (simulated state change).

        Args:
            unit: Service unit name
            action: Action to perform

        Returns:
            Result dictionary
        """
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
