"""MCP Tools package.

Pakiet zawierający implementacje narzędzi MCP dla Rider-PC.
"""

# Import tools to register them with the registry
from pc_client.mcp.tools import system
from pc_client.mcp.tools import robot
from pc_client.mcp.tools import weather
from pc_client.mcp.tools import smart_home
from pc_client.mcp.tools import git
from pc_client.mcp.tools.git import GitCommandResult

__all__ = [
    "system",
    "robot",
    "weather",
    "smart_home",
    "git",
    "GitCommandResult",
]
