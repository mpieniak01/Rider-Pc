"""MCP Tool Registry.

Rejestr narzędzi MCP przechowujący informacje o dostępnych narzędziach,
ich schematach argumentów i handlerach.
"""

import logging
import time
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Definicja narzędzia MCP.

    Attributes:
        name: Unikalny identyfikator narzędzia (np. "system.get_time").
        description: Opis działania narzędzia.
        args_schema: JSON Schema dla argumentów wejściowych.
        handler: Funkcja obsługująca wywołanie (async lub sync).
        permissions: Lista wymaganych uprawnień (np. ["low"], ["high", "confirm"]).
    """

    name: str
    description: str
    args_schema: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})
    handler: Optional[Callable[..., Any]] = None
    permissions: List[str] = field(default_factory=lambda: ["low"])


@dataclass
class ToolInvokeResult:
    """Wynik wywołania narzędzia MCP.

    Attributes:
        ok: Czy wywołanie zakończyło się sukcesem.
        tool: Nazwa wywołanego narzędzia.
        result: Wynik zwrócony przez handler.
        error: Opis błędu (jeśli ok=False).
        meta: Metadane wywołania (czas, host itp.).
    """

    ok: bool
    tool: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konwertuj do słownika."""
        return {
            "ok": self.ok,
            "tool": self.tool,
            "result": self.result,
            "error": self.error,
            "meta": self.meta,
        }


class ToolRegistry:
    """Rejestr narzędzi MCP.

    Przechowuje wszystkie zarejestrowane narzędzia i udostępnia metody
    do ich rejestracji, wyszukiwania i wywoływania.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._invocation_count: int = 0
        self._last_invoked_tool: Optional[str] = None
        self._logger = logging.getLogger("mcp.registry")

    def register(self, tool: Tool) -> None:
        """Zarejestruj narzędzie w rejestrze.

        Args:
            tool: Definicja narzędzia do zarejestrowania.

        Raises:
            ValueError: Jeśli narzędzie o tej nazwie już istnieje.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        self._logger.debug("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> bool:
        """Wyrejestruj narzędzie z rejestru.

        Args:
            name: Nazwa narzędzia do wyrejestrowania.

        Returns:
            True jeśli narzędzie zostało usunięte, False jeśli nie istniało.
        """
        if name in self._tools:
            del self._tools[name]
            self._logger.debug("Unregistered tool: %s", name)
            return True
        return False

    def get(self, name: str) -> Optional[Tool]:
        """Pobierz narzędzie po nazwie.

        Args:
            name: Nazwa narzędzia.

        Returns:
            Narzędzie lub None jeśli nie znaleziono.
        """
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """Zwróć listę wszystkich zarejestrowanych narzędzi.

        Returns:
            Lista narzędzi.
        """
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        """Zwróć listę nazw wszystkich narzędzi.

        Returns:
            Lista nazw narzędzi.
        """
        return list(self._tools.keys())

    def clear(self) -> None:
        """Wyczyść rejestr (usuń wszystkie narzędzia)."""
        self._tools.clear()
        self._invocation_count = 0
        self._last_invoked_tool = None

    async def invoke(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        confirm: bool = False,
    ) -> ToolInvokeResult:
        """Wywołaj narzędzie z podanymi argumentami.

        Args:
            tool_name: Nazwa narzędzia do wywołania.
            arguments: Słownik z argumentami dla narzędzia.
            confirm: Czy użytkownik potwierdził operację (dla narzędzi wymagających potwierdzenia).

        Returns:
            Wynik wywołania narzędzia.
        """
        start_time = time.time()
        hostname = socket.gethostname()

        tool = self.get(tool_name)
        if not tool:
            return ToolInvokeResult(
                ok=False,
                tool=tool_name,
                error=f"Tool '{tool_name}' not found",
                meta={"duration_ms": 0, "host": hostname},
            )

        if not tool.handler:
            return ToolInvokeResult(
                ok=False,
                tool=tool_name,
                error=f"Tool '{tool_name}' has no handler",
                meta={"duration_ms": 0, "host": hostname},
            )

        # Sprawdź uprawnienia
        if "confirm" in tool.permissions and not confirm:
            return ToolInvokeResult(
                ok=False,
                tool=tool_name,
                error="This tool requires user confirmation (confirm=true)",
                meta={"duration_ms": 0, "host": hostname, "requires_confirm": True},
            )

        try:
            args = arguments or {}
            # Sprawdź czy handler jest async
            result = tool.handler(**args)
            if isinstance(result, Awaitable):
                result = await result

            duration_ms = int((time.time() - start_time) * 1000)

            self._invocation_count += 1
            self._last_invoked_tool = tool_name

            self._logger.info("Tool '%s' invoked successfully (duration: %dms)", tool_name, duration_ms)

            return ToolInvokeResult(
                ok=True,
                tool=tool_name,
                result=result if isinstance(result, dict) else {"value": result},
                meta={"duration_ms": duration_ms, "host": hostname},
            )

        except TypeError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Invalid arguments: {e}"
            self._logger.error("Tool '%s' invocation failed: %s", tool_name, error_msg)
            return ToolInvokeResult(
                ok=False,
                tool=tool_name,
                error=error_msg,
                meta={"duration_ms": duration_ms, "host": hostname},
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            self._logger.error("Tool '%s' invocation failed: %s", tool_name, error_msg)
            return ToolInvokeResult(
                ok=False,
                tool=tool_name,
                error=error_msg,
                meta={"duration_ms": duration_ms, "host": hostname},
            )

    def get_stats(self) -> Dict[str, Any]:
        """Pobierz statystyki rejestru.

        Returns:
            Słownik ze statystykami.
        """
        return {
            "total_tools": len(self._tools),
            "invocation_count": self._invocation_count,
            "last_invoked_tool": self._last_invoked_tool,
        }


# Globalny rejestr narzędzi
registry = ToolRegistry()


def mcp_tool(
    name: str,
    description: str,
    args_schema: Optional[Dict[str, Any]] = None,
    permissions: Optional[List[str]] = None,
) -> Callable:
    """Dekorator do rejestracji funkcji jako narzędzia MCP.

    Args:
        name: Nazwa narzędzia (np. "system.get_time").
        description: Opis działania narzędzia.
        args_schema: JSON Schema dla argumentów.
        permissions: Lista wymaganych uprawnień.

    Returns:
        Dekorator funkcji.

    Example:
        @mcp_tool("system.get_time", "Zwraca aktualny czas")
        def get_time():
            return {"time": datetime.now().isoformat()}
    """

    def decorator(func: Callable) -> Callable:
        tool = Tool(
            name=name,
            description=description,
            args_schema=args_schema or {"type": "object", "properties": {}, "required": []},
            handler=func,
            permissions=permissions or ["low"],
        )
        registry.register(tool)
        return func

    return decorator
