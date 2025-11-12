"""REST API adapter for consuming Rider-PI endpoints."""

import httpx
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RestAdapter:
    """Adapter for consuming REST API from Rider-PI."""
    
    def __init__(self, base_url: str, timeout: float = 5.0):
        """
        Initialize the REST adapter.
        
        Args:
            base_url: Base URL for Rider-PI API (e.g., http://robot-ip:8080)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_healthz(self) -> Dict[str, Any]:
        """
        Get health status from /healthz endpoint.
        
        Returns:
            Health status data
        """
        try:
            response = await self.client.get(f"{self.base_url}/healthz")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /healthz: {e}")
            return {"ok": False, "error": str(e)}
    
    async def get_state(self) -> Dict[str, Any]:
        """
        Get state from /state endpoint.
        
        Returns:
            State data
        """
        try:
            response = await self.client.get(f"{self.base_url}/state")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /state: {e}")
            return {"error": str(e)}
    
    async def get_sysinfo(self) -> Dict[str, Any]:
        """
        Get system info from /sysinfo endpoint.
        
        Returns:
            System info data
        """
        try:
            response = await self.client.get(f"{self.base_url}/sysinfo")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /sysinfo: {e}")
            return {"error": str(e)}
    
    async def get_vision_snap_info(self) -> Dict[str, Any]:
        """
        Get vision snapshot info from /vision/snap-info endpoint.
        
        Returns:
            Vision snapshot info data
        """
        try:
            response = await self.client.get(f"{self.base_url}/vision/snap-info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /vision/snap-info: {e}")
            return {"error": str(e)}
    
    async def get_vision_obstacle(self) -> Dict[str, Any]:
        """
        Get vision obstacle data from /vision/obstacle endpoint.
        
        Returns:
            Vision obstacle data
        """
        try:
            response = await self.client.get(f"{self.base_url}/vision/obstacle")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /vision/obstacle: {e}")
            return {"error": str(e)}
    
    async def get_app_metrics(self) -> Dict[str, Any]:
        """
        Get app metrics from /api/app-metrics endpoint.
        
        Returns:
            App metrics data
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/app-metrics")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/app-metrics: {e}")
            return {"ok": False, "error": str(e)}
    
    async def get_camera_resource(self) -> Dict[str, Any]:
        """
        Get camera resource info from /api/resource/camera endpoint.
        
        Returns:
            Camera resource data
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/resource/camera")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/resource/camera: {e}")
            return {"error": str(e)}
    
    async def get_bus_health(self) -> Dict[str, Any]:
        """
        Get bus health from /api/bus/health endpoint.
        
        Returns:
            Bus health data
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/bus/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/bus/health: {e}")
            return {"error": str(e)}
    
    async def post_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send control command to /api/control endpoint.
        
        Args:
            command: Control command data
            
        Returns:
            Response data
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/control",
                json=command
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting to /api/control: {e}")
            return {"ok": False, "error": str(e)}
