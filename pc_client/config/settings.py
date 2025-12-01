"""Settings and configuration for the PC client."""

import logging
import os
from typing import List, Optional
from dataclasses import dataclass, field

_settings_logger = logging.getLogger(__name__)


def _safe_int(env_var: str, default: str) -> int:
    """Safely parse an integer from an environment variable.

    Args:
        env_var: Name of the environment variable.
        default: Default value as a string.

    Returns:
        Parsed integer value, or default if parsing fails.
    """
    value = os.getenv(env_var, default)
    try:
        return int(value)
    except ValueError:
        _settings_logger.warning("Invalid value '%s' for %s, using default %s", value, env_var, default)
        return int(default)


def _parse_monitored_services() -> List[str]:
    """Parse MONITORED_SERVICES from environment variable.

    Expects a comma-separated list of systemd unit names.
    Example: "rider-pc.service,rider-voice.service,rider-task-queue.service"

    Returns:
        List of service unit names. Empty list if environment variable is not set,
        empty, or contains only whitespace. Whitespace around individual service
        names is trimmed.
    """
    services_str = os.getenv("MONITORED_SERVICES", "")
    if not services_str:
        return []
    services = [s.strip() for s in services_str.split(",") if s.strip()]
    # Validate service names
    for service in services:
        if not service.endswith(".service") and not service.endswith(".target"):
            _settings_logger.warning("Invalid systemd unit name: %s (should end with .service or .target)", service)
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

    # Self-healing watchdog configuration
    auto_heal_enabled: bool = field(default_factory=lambda: os.getenv("AUTO_HEAL_ENABLED", "true").lower() == "true")
    max_retry_count: int = field(default_factory=lambda: _safe_int("MAX_RETRY_COUNT", "1"))
    retry_window_seconds: int = field(default_factory=lambda: _safe_int("RETRY_WINDOW_SECONDS", "300"))

    # GitHub API configuration
    github_token: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    github_repo_owner: str = field(default_factory=lambda: os.getenv("GITHUB_REPO_OWNER", ""))
    github_repo_name: str = field(default_factory=lambda: os.getenv("GITHUB_REPO_NAME", ""))
    github_cache_ttl_seconds: int = field(default_factory=lambda: _safe_int("GITHUB_CACHE_TTL_SECONDS", "300"))

    # Task auto-init configuration
    task_auto_init_enabled: bool = field(
        default_factory=lambda: os.getenv("TASK_AUTO_INIT_ENABLED", "true").lower() == "true"
    )
    task_docs_path: str = field(default_factory=lambda: os.getenv("TASK_DOCS_PATH", "docs_pl/_to_do"))
    task_branch_prefix: str = field(default_factory=lambda: os.getenv("TASK_BRANCH_PREFIX", "feat"))

    # RAG (Knowledge Base) configuration
    rag_enabled: bool = field(default_factory=lambda: os.getenv("RAG_ENABLED", "false").lower() == "true")
    rag_docs_paths: str = field(default_factory=lambda: os.getenv("RAG_DOCS_PATHS", "docs_pl,docs"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    rag_chunk_size: int = field(default_factory=lambda: _safe_int("RAG_CHUNK_SIZE", "800"))
    rag_chunk_overlap: int = field(default_factory=lambda: _safe_int("RAG_CHUNK_OVERLAP", "100"))
    rag_persist_path: str = field(default_factory=lambda: os.getenv("RAG_PERSIST_PATH", "data/chroma_db"))

    # Google Home / SDM Configuration
    google_home_local_enabled: bool = field(
        default_factory=lambda: os.getenv("GOOGLE_HOME_LOCAL_ENABLED", "false").lower() == "true"
    )
    google_client_id: Optional[str] = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID"))
    google_client_secret: Optional[str] = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET"))
    google_device_access_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_DEVICE_ACCESS_PROJECT_ID")
    )
    google_redirect_uri: str = field(
        default_factory=lambda: os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/home/auth/callback")
    )
    google_tokens_path: str = field(
        default_factory=lambda: os.getenv("GOOGLE_TOKENS_PATH", "config/local/google_tokens_pc.json")
    )
    google_home_test_mode: bool = field(
        default_factory=lambda: os.getenv("GOOGLE_HOME_TEST_MODE", "false").lower() == "true"
    )

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

    @property
    def is_github_configured(self) -> bool:
        """Check if GitHub integration is properly configured.

        Returns:
            True if all required GitHub fields (token, owner, repo) are set (not None and not empty), False otherwise.
        """
        return bool(self.github_token and self.github_repo_owner and self.github_repo_name)

    @property
    def is_google_home_configured(self) -> bool:
        """Check if Google Home integration is properly configured.

        Returns:
            True if all required Google Home fields are set (client_id, client_secret, project_id),
            False otherwise.
        """
        return bool(self.google_client_id and self.google_client_secret and self.google_device_access_project_id)


# Global settings instance
settings = Settings()
