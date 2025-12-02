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
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
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


# Próg rozmiaru pliku dla użycia zoptymalizowanego odczytu (64KB)
_LARGE_FILE_THRESHOLD = 65536


def _read_last_lines(file_path: str, num_lines: int, max_line_length: int = 1024) -> list:
    """Efektywne czytanie ostatnich N linii z pliku.

    Czyta plik od końca, unikając wczytywania całego pliku do pamięci.

    Args:
        file_path: Ścieżka do pliku.
        num_lines: Liczba linii do pobrania.
        max_line_length: Maksymalna długość linii (dla bezpieczeństwa).

    Returns:
        Lista ostatnich N linii (od najstarszej do najnowszej).
    """
    import os

    lines = []
    file_size = os.path.getsize(file_path)

    if file_size == 0:
        return lines

    # Początkowy rozmiar bufora - dostosowany do oczekiwanej liczby linii
    buffer_size = min(max(4096, num_lines * 200), file_size)

    with open(file_path, "rb") as f:
        # Zacznij od końca pliku
        position = file_size
        buffer = b""

        while position > 0 and len(lines) < num_lines:
            # Cofnij się o rozmiar bufora
            read_size = min(buffer_size, position)
            position -= read_size
            f.seek(position)

            # Czytaj fragment i dodaj do bufora
            chunk = f.read(read_size)
            buffer = chunk + buffer

            # Rozdziel na linie
            split_lines = buffer.split(b"\n")

            # Logika obsługi niepełnych linii:
            # - Jeśli nie jesteśmy na początku pliku, pierwsza linia może być niepełna
            # - Zachowaj ją do następnej iteracji
            if position > 0:
                buffer = split_lines[0]
                process_lines = split_lines[1:]
            else:
                # Jesteśmy na początku - wszystkie linie są kompletne
                buffer = b""
                process_lines = split_lines

            # Przetwórz linie (od końca do początku)
            for raw_line in reversed(process_lines):
                if len(lines) >= num_lines:
                    break
                try:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line:
                        # Ogranicz długość linii
                        if len(line) > max_line_length:
                            line = line[:max_line_length] + "..."
                        lines.append(line)
                # Ignorujemy wyjątki dekodowania, bo linia może być niekompletna lub uszkodzona
                except Exception as exc:
                    logger.debug("Błąd dekodowania linii z pliku %s: %s", file_path, exc)

        # Przetwórz pozostały bufor jeśli potrzeba więcej linii
        if len(lines) < num_lines and buffer:
            try:
                line = buffer.decode("utf-8", errors="replace").strip()
                if line:
                    if len(line) > max_line_length:
                        line = line[:max_line_length] + "..."
                    lines.append(line)
            # Ignorujemy wyjątki dekodowania dla pozostałego bufora
            except Exception as exc:
                logger.debug("Błąd dekodowania pozostałego bufora z pliku %s: %s", file_path, exc)

    # Odwróć aby zachować chronologiczną kolejność (od najstarszej do najnowszej)
    return list(reversed(lines))


@router.get("/history")
async def get_invocation_history(limit: int = 50) -> JSONResponse:
    """Pobierz historię wywołań narzędzi MCP z logu.

    Używa efektywnego czytania od końca pliku, unikając wczytywania
    całego pliku do pamięci dla dużych logów.

    Args:
        limit: Maksymalna liczba wpisów do zwrócenia (1-200).

    Returns:
        JSON z historią wywołań.
    """
    import os

    limit = min(max(1, limit), 200)
    history = []

    log_path = os.path.join(os.getcwd(), "logs", "mcp-tools.log")
    if os.path.exists(log_path):
        try:
            file_size = os.path.getsize(log_path)
            # Dla małych plików używamy prostego odczytu
            if file_size < _LARGE_FILE_THRESHOLD:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        line = line.strip()
                        if line:
                            history.append(line)
            else:
                # Dla dużych plików używamy efektywnego czytania od końca
                history = _read_last_lines(log_path, limit)
        except Exception as e:
            logger.warning("Failed to read mcp-tools.log: %s", e)

    return JSONResponse(
        {
            "ok": True,
            "history": history,
            "count": len(history),
            "log_path": log_path,
        }
    )
