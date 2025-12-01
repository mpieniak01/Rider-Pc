"""MCP Tools package.

Pakiet zawierający implementacje narzędzi MCP dla Rider-PC.
"""

# Import tools to register them with the registry
from pc_client.mcp.tools import system
from pc_client.mcp.tools import robot
from pc_client.mcp.tools import weather

__all__ = [
    "system",
    "robot",
    "weather",
]
