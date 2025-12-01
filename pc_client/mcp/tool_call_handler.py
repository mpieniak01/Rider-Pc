"""MCP Tool Call Handler for TextProvider integration.

Obsługa wywołań narzędzi MCP z poziomu LLM (tool-call).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pc_client.mcp.registry import registry, ToolInvokeResult

logger = logging.getLogger(__name__)


def get_tools_for_llm() -> List[Dict[str, Any]]:
    """Zwróć listę narzędzi w formacie dla LLM."""
    tools = []
    for tool in registry.list_tools():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_schema,
        })
    return tools


def get_tools_prompt() -> str:
    """Wygeneruj prompt systemowy z listą dostępnych narzędzi."""
    tools = registry.list_tools()
    if not tools:
        return ""

    tool_descriptions = []
    for tool in tools:
        params_desc = ""
        props = tool.args_schema.get("properties", {})
        required = tool.args_schema.get("required", [])

        if props:
            param_list = []
            for name, spec in props.items():
                req_mark = "*" if name in required else ""
                param_type = spec.get("type", "any")
                desc = spec.get("description", "")
                param_list.append(f"  - {name}{req_mark} ({param_type}): {desc}")
            params_desc = "\n".join(param_list)

        tool_descriptions.append(f"- **{tool.name}**: {tool.description}\n{params_desc}")

    return f"""Masz dostęp do następujących narzędzi:

{chr(10).join(tool_descriptions)}

Aby użyć narzędzia, odpowiedz w formacie JSON:
```json
{{"tool_call": {{"name": "nazwa_narzedzia", "arguments": {{...}}}}}}
```

Jeśli nie potrzebujesz narzędzia, odpowiedz normalnie tekstem."""


def parse_tool_call(response: str) -> Optional[Dict[str, Any]]:
    """Parsuj odpowiedź LLM w poszukiwaniu wywołania narzędzia."""
    json_patterns = [
        r'```json\s*(\{.*?\})\s*```',
        r'```\s*(\{.*?\})\s*```',
        r'(\{"tool_call":\s*\{.*?\}\})',
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if "tool_call" in data:
                    tool_call = data["tool_call"]
                    if "name" in tool_call:
                        return {
                            "name": tool_call["name"],
                            "arguments": tool_call.get("arguments", {}),
                        }
            except json.JSONDecodeError:
                continue

    try:
        data = json.loads(response.strip())
        if "tool_call" in data:
            tool_call = data["tool_call"]
            if "name" in tool_call:
                return {
                    "name": tool_call["name"],
                    "arguments": tool_call.get("arguments", {}),
                }
    except json.JSONDecodeError:
        # Oczekiwany przypadek: odpowiedź nie jest poprawnym JSON-em, zwracamy None.
        pass

    return None


async def execute_tool_call(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    confirm: bool = False,
) -> ToolInvokeResult:
    """Wykonaj wywołanie narzędzia MCP."""
    logger.info(f"[MCP Tool Call] Executing: {tool_name} with args: {arguments}")
    result = await registry.invoke(tool_name, arguments, confirm=confirm)
    logger.info(f"[MCP Tool Call] Result: ok={result.ok}, tool={result.tool}")
    return result


def format_tool_result(result: ToolInvokeResult) -> str:
    """Sformatuj wynik narzędzia do wstrzyknięcia w konwersację."""
    if result.ok:
        result_json = json.dumps(result.result, ensure_ascii=False, indent=2)
        return f"[Wynik narzędzia {result.tool}]\n{result_json}"
    else:
        return f"[Błąd narzędzia {result.tool}]: {result.error}"
