"""MCP Router - API endpoints for Model Context Protocol.

Endpointy MCP dla Rider-PC:
- GET /api/mcp/tools - lista dostępnych narzędzi
- GET /api/mcp/resources - zasoby (konfiguracja, status)
- POST /api/mcp/tools/invoke - wywołanie narzędzia
"""

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import registry - tools are registered on import
from pc_client.mcp.registry import registry
from pc_client.mcp import tools as _  # noqa: F401 - triggers tool registration

logger = logging.getLogger(__name__)

# Dedykowany logger dla mcp-tools.log
mcp_file_logger = logging.getLogger("mcp.tools")


def _setup_mcp_file_logger():
    """Skonfiguruj dedykowany logger dla pliku mcp-tools.log."""
    if mcp_file_logger.handlers:
        return

    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    file_handler = logging.FileHandler(
        os.path.join(logs_dir, "mcp-tools.log"),
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    mcp_file_logger.addHandler(file_handler)
    mcp_file_logger.setLevel(logging.INFO)


_setup_mcp_file_logger()

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class InvokeToolRequest(BaseModel):
    """Model żądania wywołania narzędzia MCP."""

    tool: str = Field(..., description="Nazwa narzędzia do wywołania")
    arguments: Optional[Dict[str, Any]] = Field(default=None, description="Argumenty dla narzędzia")
    confirm: bool = Field(default=False, description="Potwierdzenie dla operacji wymagających zgody")


@router.get("/tools")
async def list_tools() -> JSONResponse:
    """Lista dostępnych narzędzi MCP.

    Returns:
        JSON z listą narzędzi i ich schematami.

    Response format:
    {
        "ok": true,
        "tools": [
            {
                "name": "system.get_time",
                "description": "...",
                "args_schema": {...},
                "permissions": ["low"]
            }
        ],
        "count": 4
    }
    """
    tool_list: List[Dict[str, Any]] = []

    for tool in registry.list_tools():
        tool_list.append(
            {
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_schema,
                "permissions": tool.permissions,
            }
        )

    return JSONResponse(
        {
            "ok": True,
            "tools": tool_list,
            "count": len(tool_list),
        }
    )


@router.get("/resources")
async def get_resources(request: Request) -> JSONResponse:
    """Pobierz zasoby MCP (konfiguracja, status).

    Returns:
        JSON z informacjami o zasobach i stanie modułu MCP.

    Response format:
    {
        "ok": true,
        "resources": {
            "config": {...},
            "stats": {...}
        }
    }
    """
    settings = getattr(request.app.state, "settings", None)

    config = {}
    if settings:
        config = {
            "mcp_standalone": getattr(settings, "mcp_standalone", False),
            "mcp_port": getattr(settings, "mcp_port", 8210),
        }

    stats = registry.get_stats()

    return JSONResponse(
        {
            "ok": True,
            "resources": {
                "config": config,
                "stats": stats,
            },
        }
    )


@router.post("/tools/invoke")
async def invoke_tool(payload: InvokeToolRequest) -> JSONResponse:
    """Wywołaj narzędzie MCP.

    Args:
        payload: Walidowane żądanie z nazwą narzędzia i argumentami.

    Returns:
        Wynik wywołania narzędzia.

    Response format:
    {
        "ok": true,
        "tool": "system.get_time",
        "result": {"time": "2025-12-01T12:34:56"},
        "error": null,
        "meta": {
            "duration_ms": 12,
            "host": "rider-pc"
        }
    }
    """
    logger.info("Invoking MCP tool: %s with arguments: %s", payload.tool, payload.arguments)

    result = await registry.invoke(payload.tool, payload.arguments, confirm=payload.confirm)

    # Log do mcp-tools.log (dedykowany plik)
    if result.ok:
        log_entry = f"INVOKE {payload.tool} -> SUCCESS ({result.meta.get('duration_ms', 0)}ms)"
        mcp_file_logger.info(log_entry)
        logger.info("[MCP] %s -> success (%dms)", payload.tool, result.meta.get("duration_ms", 0))
    else:
        log_entry = f"INVOKE {payload.tool} -> ERROR: {result.error}"
        mcp_file_logger.warning(log_entry)
        logger.warning("[MCP] %s -> error: %s", payload.tool, result.error)

    status_code = 200 if result.ok else (404 if "not found" in (result.error or "") else 400)

    return JSONResponse(result.to_dict(), status_code=status_code)


@router.get("/stats")
async def get_stats() -> JSONResponse:
    """Pobierz statystyki użycia MCP.

    Returns:
        JSON ze statystykami wywołań narzędzi.
    """
    stats = registry.get_stats()
    return JSONResponse(
        {
            "ok": True,
            "stats": stats,
        }
    )
