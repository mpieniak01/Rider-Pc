"""Settings and configuration for the PC client."""

import os
from typing import Optional
from dataclasses import dataclass, field


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
    telemetry_zmq_host: str = field(default_factory=lambda: os.getenv("TELEMETRY_ZMQ_HOST", "0.0.0.0"))

    # Network security configuration
    secure_mode: bool = field(default_factory=lambda: os.getenv("SECURE_MODE", "false").lower() == "true")
    mtls_cert_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_CERT_PATH"))
    mtls_key_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_KEY_PATH"))
    mtls_ca_path: Optional[str] = field(default_factory=lambda: os.getenv("MTLS_CA_PATH"))

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
