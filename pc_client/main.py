"""Main entry point for the Rider-PC Client application."""

import logging
import sys
import uvicorn
from pathlib import Path

from pc_client.config import Settings
from pc_client.cache import CacheManager
from pc_client.api import create_app


def setup_logging(log_level: str):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    """Main entry point."""
    # Load settings
    settings = Settings()
    
    # Setup logging
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Rider-PC Client Starting")
    logger.info("=" * 60)
    logger.info(f"Rider-PI Host: {settings.rider_pi_host}:{settings.rider_pi_port}")
    logger.info(f"ZMQ PUB Endpoint: {settings.zmq_pub_endpoint}")
    logger.info(f"Server: {settings.server_host}:{settings.server_port}")
    logger.info(f"Cache DB: {settings.cache_db_path}")
    logger.info("=" * 60)
    
    # Initialize cache
    cache = CacheManager(
        db_path=settings.cache_db_path,
        ttl_seconds=settings.cache_ttl_seconds
    )
    logger.info("Cache manager initialized")
    
    # Create FastAPI app
    app = create_app(settings, cache)
    logger.info("FastAPI application created")
    
    # Run server
    logger.info(f"Starting server on {settings.server_host}:{settings.server_port}")
    logger.info(f"Access the UI at: http://localhost:{settings.server_port}/")
    
    try:
        uvicorn.run(
            app,
            host=settings.server_host,
            port=settings.server_port,
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
