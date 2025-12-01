"""MCP Standalone Server.

Uruchamia osobny serwer MCP na dedykowanym porcie.
Używany gdy MCP_STANDALONE=true.
"""

import logging
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pc_client.config import Settings
from pc_client.api.routers import mcp_router


def create_standalone_app() -> FastAPI:
    """Utwórz aplikację FastAPI dla standalone MCP.

    Returns:
        Skonfigurowana aplikacja FastAPI z routerem MCP.
    """
    app = FastAPI(
        title="Rider-PC MCP Server",
        description="Standalone Model Context Protocol server for Rider-PC",
        version="0.1.0",
    )

    # CORS dla integracji zewnętrznych
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mock settings dla standalone
    class StandaloneSettings:
        mcp_standalone = True
        mcp_port = Settings().mcp_port

    app.state.settings = StandaloneSettings()

    # Zarejestruj router MCP
    app.include_router(mcp_router.router)

    @app.get("/health")
    async def health():
        """Sprawdź status serwera MCP."""
        from pc_client.mcp.registry import registry

        stats = registry.get_stats()
        return {
            "ok": True,
            "mode": "standalone",
            "stats": stats,
        }

    return app


def main():
    """Uruchom standalone serwer MCP."""
    settings = Settings()

    if not settings.mcp_standalone:
        print("MCP standalone mode is disabled. Set MCP_STANDALONE=true to enable.")
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Rider-PC MCP Standalone Server Starting")
    logger.info("=" * 60)
    logger.info(f"Port: {settings.mcp_port}")
    logger.info("=" * 60)

    app = create_standalone_app()

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=settings.mcp_port,
            log_level=settings.log_level.lower(),
        )
    except KeyboardInterrupt:
        logger.info("Shutting down MCP server...")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
