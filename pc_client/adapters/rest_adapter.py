"""REST API adapter for consuming Rider-PI endpoints."""

import httpx
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote
from pc_client.http_contract import ACCEPT, family, unpack

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
        client_kwargs: Dict[str, Any] = {"timeout": timeout, "headers": {"Accept": ACCEPT}}
        self._contract_supported = False
        self._contract_verified_at = 0

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

    async def _json_request(self, method, path, payload=None):
        if path == "/api/logic/catalog":
            self._contract_supported = False
            self._contract_verified_at = 0
        safety_stop = (
            path == "/api/control" and isinstance(payload, dict) and payload.get("action", payload.get("cmd")) == "stop"
        )
        safety_stop = (
            safety_stop
            or path == "/api/safety"
            and isinstance(payload, dict)
            and payload.get("action") in {"disarm", "estop"}
        )
        if (
            method != "GET"
            and not safety_stop
            and (not self._contract_supported or time.monotonic() - self._contract_verified_at > 10)
        ):
            # Odczyt katalogu nie przyznaje zgody operatora ani nie restampuje komendy.
            await self.get_logic_catalog()
            if not self._contract_supported:
                return {"ok": False, "error": "unsupported_contract", "_http_status": 409}
        try:
            call = getattr(self.client, method.lower())
            kwargs = {"headers": {"Accept": ACCEPT}}
            if payload is not None:
                kwargs["json"] = payload
            response = await call(f"{self.base_url}{path}", **kwargs)
            received_at = time.time()
            body = response.json()
            expected = (
                "rider.http"
                if response.status_code >= 400
                and isinstance(body, dict)
                and body.get("ok") is False
                and isinstance(body.get("error"), dict)
                and isinstance(body.get("meta"), dict)
                and body["meta"].get("contract_id") == "rider.http"
                else family(path)
            )
            result = unpack(body, expected_family=expected)
            meta = result.get("contract_meta", {})
            if meta:
                meta["transport"] = {
                    **meta.get("transport", {}),
                    "receiver_host": "pc",
                    "received_at": received_at,
                    "upstream_status": response.status_code,
                }
            if "received_at" in result:
                result["upstream_received_at"] = result["received_at"]
            result["received_at"] = received_at
            if path == "/api/logic/catalog":
                peer_now, observed = meta.get("server_time"), meta.get("observed_at")
                fresh = (
                    type(peer_now) in (int, float) and type(observed) in (int, float) and 0 <= peer_now - observed <= 10
                )
                self._contract_supported = (
                    response.status_code == 200
                    and result.get("ok") is True
                    and not result.get("offline")
                    and not result.get("stale")
                    and not result.get("error")
                    and meta.get("envelope_version") == 1
                    and meta.get("contract_id") == "rider.catalog"
                    and meta.get("contract_version") == 2
                    and result.get("contract_version") == 2
                    and result.get("catalog_version") == 2
                    and isinstance(result.get("api_envelope_versions"), list)
                    and any(type(value) is int and value == 1 for value in result["api_envelope_versions"])
                    and isinstance(result.get("features"), list)
                    and isinstance(result.get("units"), list)
                    and fresh
                )
                self._contract_verified_at = time.monotonic() if self._contract_supported else 0
            if response.status_code != 200:
                result["_http_status"] = response.status_code
            if response.status_code >= 400:
                result.setdefault("ok", False)
                result.setdefault("error", "upstream_http_error")
            return result
        except httpx.TimeoutException:
            return {"ok": False, "error": "upstream_timeout", "_http_status": 504, "attempted_at": time.time()}
        except (ValueError, TypeError) as exc:
            return {
                "ok": False,
                "error": str(exc) or "upstream_protocol_error",
                "_http_status": 502,
                "attempted_at": time.time(),
            }
        except httpx.RequestError:
            return {"ok": False, "error": "source_unavailable", "_http_status": 503, "attempted_at": time.time()}

    async def get_json(self, path):
        return await self._json_request("GET", path)

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
            response = await self.client.get(
                url, params=params, headers={"Accept": "image/*, audio/*, application/octet-stream"}
            )
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
        return await self._json_request("GET", "/healthz")

    async def get_state(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/state")

    async def get_sysinfo(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/sysinfo")

    async def get_vision_snap_info(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/vision/snap-info")

    async def get_vision_obstacle(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/vision/obstacle")

    async def get_app_metrics(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/app-metrics")

    async def get_camera_resource(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/resource/camera")

    async def get_motion_queue(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/motion/queue")

    async def get_voice_providers(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/voice/providers")

    async def test_voice_providers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/voice/providers/test", payload)

    async def post_voice_tts(self, payload: Dict[str, Any]) -> Tuple[bytes, str]:
        """Proxy TTS synthesis request to Rider-PI."""
        if not self._contract_supported or time.monotonic() - self._contract_verified_at > 10:
            await self.get_logic_catalog()
            if not self._contract_supported:
                raise RuntimeError("unsupported_contract")
        try:
            response = await self.client.post(
                f"{self.base_url}/api/voice/tts", json=payload, headers={"Accept": "audio/wav"}
            )
            response.raise_for_status()
            if response.headers.get("X-Voice-Fallback"):
                raise RuntimeError("Remote TTS returned fallback audio")
            media_type = response.headers.get("content-type", "audio/wav")
            if not media_type.startswith("audio/"):
                raise RuntimeError("Remote TTS returned non-audio content")
            return response.content, media_type
        except Exception as e:
            logger.error(f"Error posting /api/voice/tts: {e}")
            raise

    async def post_voice_asr(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/voice/asr", payload)

    async def post_chat_send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/chat/send", payload)

    async def get_bus_health(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/bus/health")

    async def get_ai_mode(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/system/ai-mode")

    async def set_ai_mode(self, mode: str) -> Dict[str, Any]:
        return await self._json_request("PUT", "/api/system/ai-mode", {"mode": mode})

    async def get_providers_state(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/providers/state")

    async def patch_provider(self, domain: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("PATCH", f"/api/providers/{quote(domain, safe='' )}", payload)

    async def get_providers_health(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/providers/health")

    async def get_remote_models(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/models/installed")

    async def get_home_status(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/home/status")

    async def get_home_devices(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/home/devices")

    async def post_home_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/home/command", payload)

    async def post_home_auth(self) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/home/auth", {})

    async def get_resource(self, resource_name: str) -> Dict[str, Any]:
        return await self._json_request("GET", f"/api/resource/{quote(resource_name, safe='' )}")

    async def post_resource_action(self, resource_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", f"/api/resource/{quote(resource_name, safe='' )}", payload)

    async def _post_operator_action(self, path, payload):
        return await self._json_request("POST", path, payload)

    async def post_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action("/api/control", command)

    async def post_safety(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action("/api/safety", payload)

    async def post_navigator_return_home(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action("/api/navigator/return_home", payload)

    async def get_logic_catalog(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/logic/catalog")

    async def get_service_logs(self, unit: str) -> Dict[str, Any]:
        return await self._json_request("GET", f"/api/services/{quote(unit, safe='' )}/logs")

    async def get_navigator_status(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/navigator/status")

    async def post_navigator_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action("/api/navigator/config", payload)

    async def get_control_state(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/control/state")

    async def post_pc_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._json_request("POST", "/api/providers/pc-heartbeat", payload)

    async def post_feature_toggle(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action(f"/api/logic/feature/{quote(name, safe='')}", payload or {})

    async def post_tracking_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action('/api/vision/tracking/mode', payload or {})

    async def get_logic_features(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/logic/features")

    async def get_logic_summary(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/api/logic/summary")

    async def get_services(self) -> Dict[str, Any]:
        return await self._json_request("GET", "/svc")

    async def get_svc_diagnostics(self) -> Dict[str, Any]:
        """Alias for get_services; kept for compatibility with Rider-Pi nomenclature."""
        return await self.get_services()

    async def service_action(self, unit: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post_operator_action(f"/svc/{quote(unit, safe='')}", payload or {})
