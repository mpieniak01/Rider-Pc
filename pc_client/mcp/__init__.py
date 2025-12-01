"""MCP (Model Context Protocol) module for Rider-PC.

Moduł zapewnia wewnętrzny serwer MCP działający w ramach API FastAPI Rider-PC.
Umożliwia lokalnemu Chat PC i przyszłym agentom korzystanie z zestawu narzędzi.
"""

from pc_client.mcp.registry import (
    Tool,
    ToolRegistry,
    registry,
    mcp_tool,
)

__all__ = [
    "Tool",
    "ToolRegistry",
    "registry",
    "mcp_tool",
]
