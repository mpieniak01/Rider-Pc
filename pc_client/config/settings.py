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


# Global settings instance
settings = Settings()
