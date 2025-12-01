"""MCP Router - API endpoints for Model Context Protocol.

Endpointy MCP dla Rider-PC:
- GET /api/mcp/tools - lista dostępnych narzędzi
- GET /api/mcp/resources - zasoby (konfiguracja, status)
- POST /api/mcp/tools/invoke - wywołanie narzędzia
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Import registry - tools are registered on import
from pc_client.mcp.registry import registry
from pc_client.mcp import tools as _  # noqa: F401 - triggers tool registration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


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
async def invoke_tool(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """Wywołaj narzędzie MCP.

    Args:
        payload: JSON z nazwą narzędzia i argumentami.
            - tool: Nazwa narzędzia (wymagane).
            - arguments: Słownik z argumentami (opcjonalne).
            - confirm: Potwierdzenie dla operacji wymagających zgody (opcjonalne).

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
    tool_name = payload.get("tool")
    if not tool_name:
        return JSONResponse(
            {
                "ok": False,
                "tool": None,
                "result": None,
                "error": "Missing 'tool' field in request",
                "meta": {},
            },
            status_code=400,
        )

    arguments: Optional[Dict[str, Any]] = payload.get("arguments")
    confirm: bool = payload.get("confirm", False)

    logger.info("Invoking MCP tool: %s with arguments: %s", tool_name, arguments)

    result = await registry.invoke(tool_name, arguments, confirm=confirm)

    # Log do mcp-tools.log
    if result.ok:
        logger.info("[MCP] %s -> success (%dms)", tool_name, result.meta.get("duration_ms", 0))
    else:
        logger.warning("[MCP] %s -> error: %s", tool_name, result.error)

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
