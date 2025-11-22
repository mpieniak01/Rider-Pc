"""REST API adapter for consuming Rider-PI endpoints."""

import httpx
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)


class RestAdapter:
    """Adapter for consuming REST API from Rider-PI."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        secure_mode: bool = False,
        mtls_cert_path: Optional[str] = None,
        mtls_key_path: Optional[str] = None,
        mtls_ca_path: Optional[str] = None,
    ):
        """
        Initialize the REST adapter.

        Args:
            base_url: Base URL for Rider-PI API (e.g., http://robot-ip:8080)
            timeout: Request timeout in seconds
            secure_mode: Enable secure mode with mTLS. If True but any of the
                certificate paths (mtls_cert_path, mtls_key_path, mtls_ca_path) are
                not provided, falls back to insecure mode with a warning.
            mtls_cert_path: Path to client certificate (required for mTLS when secure_mode=True)
            mtls_key_path: Path to client private key (required for mTLS when secure_mode=True)
            mtls_ca_path: Path to CA certificate (required for mTLS when secure_mode=True)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Initialize httpx client based on secure mode
        client_kwargs = {"timeout": timeout}

        if secure_mode:
            if mtls_cert_path and mtls_key_path and mtls_ca_path:
                # Validate certificate files exist
                cert_file = Path(mtls_cert_path)
                key_file = Path(mtls_key_path)
                ca_file = Path(mtls_ca_path)

                if not all([cert_file.exists(), key_file.exists(), ca_file.exists()]):
                    logger.warning(
                        f"SECURE_MODE=true but one or more certificate files not found. "
                        f"Cert: {cert_file.exists()}, Key: {key_file.exists()}, CA: {ca_file.exists()}. "
                        f"Falling back to insecure mode."
                    )
                else:
                    logger.info("RestAdapter initializing in SECURE mode (Production) with mTLS")
                    cert: Tuple[str, str] = (mtls_cert_path, mtls_key_path)
                    client_kwargs["cert"] = cert
                    client_kwargs["verify"] = mtls_ca_path
            else:
                logger.warning(
                    "SECURE_MODE=true but mTLS certificates not fully configured. "
                    "Falling back to insecure mode. Please provide MTLS_CERT_PATH, "
                    "MTLS_KEY_PATH, and MTLS_CA_PATH."
                )
        else:
            logger.info("RestAdapter initializing in DEVELOPMENT mode (Insecure)")

        self.client = httpx.AsyncClient(**client_kwargs)

    async def fetch_binary(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, str, Dict[str, str]]:
        """
        Fetch binary content (images, streams) from Rider-PI endpoints.

        Args:
            path: Endpoint path starting with '/'
            params: Optional query parameters

        Returns:
            Tuple of (content bytes, media type, response headers)
        """
        url = f"{self.base_url}{path}"
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            media_type = response.headers.get("content-type", "application/octet-stream")
            headers = {key: value for key, value in response.headers.items()}
            return response.content, media_type, headers
        except Exception as e:
            logger.error(f"Error fetching binary content from {url}: {e}")
            raise

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

    async def get_motion_queue(self) -> Dict[str, Any]:
        """
        Get motion queue info from Rider-PI.

        Returns:
            Motion queue payload (should contain `items`)
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/motion/queue")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/motion/queue: {e}")
            return {"error": str(e)}

    async def get_voice_providers(self) -> Dict[str, Any]:
        """Get voice provider catalog from Rider-PI."""
        try:
            response = await self.client.get(f"{self.base_url}/api/voice/providers")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/voice/providers: {e}")
            return {"error": str(e)}

    async def test_voice_providers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger Rider-PI provider tests."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/voice/providers/test",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/voice/providers/test: {e}")
            return {"error": str(e)}

    async def post_voice_tts(self, payload: Dict[str, Any]) -> Tuple[bytes, str]:
        """Proxy TTS synthesis request to Rider-PI."""
        try:
            response = await self.client.post(f"{self.base_url}/api/voice/tts", json=payload)
            response.raise_for_status()
            media_type = response.headers.get("content-type", "audio/wav")
            return response.content, media_type
        except Exception as e:
            logger.error(f"Error posting /api/voice/tts: {e}")
            raise

    async def post_chat_send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward chat requests to Rider-PI."""
        try:
            response = await self.client.post(f"{self.base_url}/api/chat/send", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/chat/send: {e}")
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

    async def get_ai_mode(self) -> Dict[str, Any]:
        """Fetch current AI mode from Rider-PI."""
        try:
            response = await self.client.get(f"{self.base_url}/api/system/ai-mode")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/system/ai-mode: {e}")
            return {"error": str(e)}

    async def set_ai_mode(self, mode: str) -> Dict[str, Any]:
        """Set AI mode on Rider-PI."""
        try:
            response = await self.client.put(
                f"{self.base_url}/api/system/ai-mode",
                json={"mode": mode},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error setting /api/system/ai-mode: {e}")
            return {"error": str(e)}

    async def get_providers_state(self) -> Dict[str, Any]:
        """Fetch provider state information."""
        try:
            response = await self.client.get(f"{self.base_url}/api/providers/state")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/providers/state: {e}")
            return {"error": str(e)}

    async def patch_provider(self, domain: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update provider selection for a domain."""
        try:
            response = await self.client.patch(
                f"{self.base_url}/api/providers/{domain}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error patching /api/providers/{domain}: {e}")
            return {"error": str(e)}

    async def get_providers_health(self) -> Dict[str, Any]:
        """Fetch provider health information."""
        try:
            response = await self.client.get(f"{self.base_url}/api/providers/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/providers/health: {e}")
            return {"error": str(e)}

    async def get_resource(self, resource_name: str) -> Dict[str, Any]:
        """
        Get resource status from /api/resource/{resource_name}.

        Args:
            resource_name: Name of the resource (mic, speaker, camera, lcd, etc.)

        Returns:
            Resource status data
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/resource/{resource_name}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/resource/{resource_name}: {e}")
            return {"error": str(e)}

    async def post_resource_action(self, resource_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send resource action to /api/resource/{resource_name}.

        Args:
            resource_name: Name of the resource
            payload: Action payload (e.g., {"action": "release"})

        Returns:
            Response data
        """
        try:
            response = await self.client.post(f"{self.base_url}/api/resource/{resource_name}", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/resource/{resource_name}: {e}")
            return {"ok": False, "error": str(e)}

    async def post_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send control command to /api/control endpoint.

        Args:
            command: Control command data

        Returns:
            Response data
        """
        try:
            response = await self.client.post(f"{self.base_url}/api/control", json=command)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting to /api/control: {e}")
            return {"ok": False, "error": str(e)}

    async def get_control_state(self) -> Dict[str, Any]:
        """Fetch control state snapshot from Rider-PI."""
        try:
            response = await self.client.get(f"{self.base_url}/api/control/state")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /api/control/state: {e}")
            return {"error": str(e)}

    async def post_pc_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send provider heartbeat information to Rider-PI."""
        try:
            response = await self.client.post(f"{self.base_url}/api/providers/pc-heartbeat", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/providers/pc-heartbeat: {e}")
            return {"ok": False, "error": str(e)}

    async def post_feature_toggle(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Toggle feature state via Rider-PI FeatureManager."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/logic/feature/{quote(name, safe='')}",
                json=payload or {},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/logic/feature/{name}: {e}")
            return {"ok": False, "error": str(e)}

    async def post_tracking_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send tracking mode command to Rider-PI."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/vision/tracking/mode",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /api/vision/tracking/mode: {e}")
            return {"ok": False, "error": str(e)}

    async def get_services(self) -> Dict[str, Any]:
        """Fetch systemd service list from Rider-PI."""
        try:
            response = await self.client.get(f"{self.base_url}/svc")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching /svc: {e}")
            return {"error": str(e)}

    async def service_action(self, unit: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward service control action to Rider-PI."""
        try:
            response = await self.client.post(
                f"{self.base_url}/svc/{quote(unit, safe='')}",
                json=payload or {},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error posting /svc/{unit}: {e}")
            return {"ok": False, "error": str(e)}
