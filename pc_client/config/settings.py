"""Settings and configuration for the PC client."""

import os
from typing import List, Optional
from dataclasses import dataclass, field


def _parse_monitored_services() -> List[str]:
    """Parse MONITORED_SERVICES from environment variable.

    Expects a comma-separated list of systemd unit names.
    Example: "rider-pc.service,rider-voice.service,rider-task-queue.service"

    Returns:
        List of service unit names. Empty list if environment variable is not set,
        empty, or contains only whitespace. Whitespace around individual service
        names is trimmed.
    """
    import logging

    logger = logging.getLogger(__name__)
    services_str = os.getenv("MONITORED_SERVICES", "")
    if not services_str:
        return []
    services = [s.strip() for s in services_str.split(",") if s.strip()]
    # Validate service names
    for service in services:
        if not service.endswith(".service") and not service.endswith(".target"):
            logger.warning("Invalid systemd unit name: %s (should end with .service or .target)", service)
    return services


@dataclass
class Settings:
    """Configuration settings for the PC client."""

    # Rider-PI connection
    rider_pi_host: str = field(default_factory=lambda: os.getenv("RIDER_PI_HOST", "localhost"))
    rider_pi_port: int = field(default_factory=lambda: int(os.getenv("RIDER_PI_PORT", "8080")))

    # ZMQ configuration
    zmq_pub_port: int = field(default_factory=lambda: int(os.getenv("ZMQ_PUB_PORT", "5555")))
    zmq_sub_port: int = field(default_factory=lambda: int(os.getenv("ZMQ_SUB_PORT", "5556")))

    # Local server configuration
    server_host: str = field(default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0"))
    server_port: int = field(default_factory=lambda: int(os.getenv("SERVER_PORT", "8000")))

    # Cache configuration
    cache_db_path: str = field(default_factory=lambda: os.getenv("CACHE_DB_PATH", "data/cache.db"))
    cache_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", "30")))

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Provider configuration
    enable_providers: bool = field(default_factory=lambda: os.getenv("ENABLE_PROVIDERS", "false").lower() == "true")
    voice_model: str = field(default_factory=lambda: os.getenv("VOICE_MODEL", "mock"))
    vision_model: str = field(default_factory=lambda: os.getenv("VISION_MODEL", "mock"))
    text_model: str = field(default_factory=lambda: os.getenv("TEXT_MODEL", "mock"))
    enable_vision_offload: bool = field(
        default_factory=lambda: os.getenv("ENABLE_VISION_OFFLOAD", "false").lower() == "true"
    )
    enable_voice_offload: bool = field(
        default_factory=lambda: os.getenv("ENABLE_VOICE_OFFLOAD", "false").lower() == "true"
    )
    enable_text_offload: bool = field(
        default_factory=lambda: os.getenv("ENABLE_TEXT_OFFLOAD", "false").lower() == "true"
    )
    vision_provider_config_path: str = field(
        default_factory=lambda: os.getenv("VISION_PROVIDER_CONFIG", "config/providers.toml")
    )
    voice_provider_config_path: str = field(
        default_factory=lambda: os.getenv("VOICE_PROVIDER_CONFIG", "config/providers.toml")
    )
    text_provider_config_path: str = field(
        default_factory=lambda: os.getenv("TEXT_PROVIDER_CONFIG", "config/providers.toml")
    )

    # Task queue configuration
    enable_task_queue: bool = field(default_factory=lambda: os.getenv("ENABLE_TASK_QUEUE", "false").lower() == "true")
    task_queue_backend: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_BACKEND", "redis"))
    task_queue_host: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_HOST", "localhost"))
    task_queue_port: int = field(default_factory=lambda: int(os.getenv("TASK_QUEUE_PORT", "6379")))
    task_queue_password: str = field(default_factory=lambda: os.getenv("TASK_QUEUE_PASSWORD", ""))
    task_queue_max_size: int = field(default_factory=lambda: int(os.getenv("TASK_QUEUE_MAX_SIZE", "100")))

    # Telemetry configuration
    enable_telemetry: bool = field(default_factory=lambda: os.getenv("ENABLE_TELEMETRY", "false").lower() == "true")
    telemetry_zmq_port: int = field(default_factory=lambda: int(os.getenv("TELEMETRY_ZMQ_PORT", "5557")))
    telemetry_zmq_host: str = field(
        default_factory=lambda: os.getenv("TELEMETRY_ZMQ_HOST") or os.getenv("RIDER_PI_HOST", "localhost")
    )

    # Network security configuration
    secure_mode: bool = field(default_factory=lambda: os.getenv("SECURE_MODE", "false").lower() == "true")
    mtls_cert_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_CERT_PATH"))
    mtls_key_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_KEY_PATH"))
    mtls_ca_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_CA_PATH"))

    # Public base URL advertised to Rider-PI (for provider heartbeat)
    pc_public_base_url: Optional[str] = field(default_factory=lambda: os.getenv("PC_PUBLIC_BASE_URL"))

    # Test mode - use mock adapters instead of real connections
    test_mode: bool = field(default_factory=lambda: os.getenv("TEST_MODE", "false").lower() == "true")

    # Systemd service management configuration
    # Comma-separated list of systemd units to monitor (e.g., "rider-pc.service,rider-voice.service")
    monitored_services: List[str] = field(default_factory=_parse_monitored_services)
    # Whether to use sudo for systemctl commands (set to false if running as root)
    systemd_use_sudo: bool = field(default_factory=lambda: os.getenv("SYSTEMD_USE_SUDO", "true").lower() == "true")

    @property
    def rider_pi_base_url(self) -> str:
        """Get the base URL for Rider-PI API."""
        return f"http://{self.rider_pi_host}:{self.rider_pi_port}"

    @property
    def zmq_pub_endpoint(self) -> str:
        """Get ZMQ PUB endpoint."""
        return f"tcp://{self.rider_pi_host}:{self.zmq_pub_port}"

    @property
    def zmq_sub_endpoint(self) -> str:
        """Get ZMQ SUB endpoint."""
        return f"tcp://{self.rider_pi_host}:{self.zmq_sub_port}"

    @property
    def telemetry_zmq_endpoint(self) -> str:
        """Get telemetry ZMQ PUB endpoint."""
        return f"tcp://{self.telemetry_zmq_host}:{self.telemetry_zmq_port}"


# Global settings instance
settings = Settings()
