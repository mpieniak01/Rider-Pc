"""Git tools for MCP.

Narzędzia do pracy z repozytorium Git: zmiany, status, testy (read-only).
"""

import subprocess
import os
from typing import Optional, List

from pc_client.mcp.registry import mcp_tool


def _run_git_command(args: List[str], cwd: Optional[str] = None) -> dict:
    """Wykonaj komendę git i zwróć wynik."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd or os.getcwd(),
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip() if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "Git not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp_tool(
    name="git.get_changed_files",
    description="Zwraca listę zmienionych plików w repozytorium (staged i unstaged).",
    args_schema={
        "type": "object",
        "properties": {
            "staged_only": {
                "type": "boolean",
                "description": "Jeśli true, zwraca tylko pliki staged. Domyślnie: false.",
            },
            "path": {
                "type": "string",
                "description": "Ścieżka do repozytorium. Domyślnie: bieżący katalog.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_changed_files(staged_only: bool = False, path: Optional[str] = None) -> dict:
    """Pobierz listę zmienionych plików."""
    if staged_only:
        result = _run_git_command(["diff", "--cached", "--name-status"], cwd=path)
    else:
        result = _run_git_command(["status", "--porcelain"], cwd=path)

    if not result["success"]:
        return {"files": [], "error": result.get("error") or result.get("stderr")}

    files = []
    for line in result["stdout"].split("\n"):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) >= 2:
            status, filename = parts[0], parts[1]
            files.append({"status": status, "path": filename})
        elif len(parts) == 1:
            files.append({"status": "?", "path": parts[0]})

    return {"files": files, "count": len(files), "staged_only": staged_only}


@mcp_tool(
    name="git.get_status",
    description="Zwraca ogólny status repozytorium Git.",
    args_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ścieżka do repozytorium. Domyślnie: bieżący katalog.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_git_status(path: Optional[str] = None) -> dict:
    """Pobierz status repozytorium Git."""
    branch_result = _run_git_command(["branch", "--show-current"], cwd=path)
    current_branch = branch_result["stdout"] if branch_result["success"] else None

    log_result = _run_git_command(["log", "-1", "--format=%H|%s|%ar"], cwd=path)
    last_commit = None
    if log_result["success"] and log_result["stdout"]:
        parts = log_result["stdout"].split("|", 2)
        if len(parts) >= 3:
            last_commit = {
                "sha": parts[0][:8],
                "message": parts[1],
                "relative_time": parts[2],
            }

    status_result = _run_git_command(["status", "--porcelain"], cwd=path)
    changed_count = 0
    if status_result["success"]:
        changed_count = len([line for line in status_result["stdout"].split("\n") if line.strip()])

    remote_result = _run_git_command(["remote", "-v"], cwd=path)
    has_remote = bool(remote_result["success"] and remote_result["stdout"])

    return {
        "current_branch": current_branch,
        "last_commit": last_commit,
        "changed_files_count": changed_count,
        "has_remote": has_remote,
        "is_git_repo": branch_result["success"],
    }


@mcp_tool(
    name="git.get_diff",
    description="Zwraca diff dla konkretnego pliku lub całego repozytorium.",
    args_schema={
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": "Ścieżka do pliku. Jeśli puste, zwraca diff dla wszystkich zmian.",
            },
            "staged": {
                "type": "boolean",
                "description": "Jeśli true, pokazuje staged diff. Domyślnie: false.",
            },
            "path": {
                "type": "string",
                "description": "Ścieżka do repozytorium. Domyślnie: bieżący katalog.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_diff(
    file: Optional[str] = None,
    staged: bool = False,
    path: Optional[str] = None,
) -> dict:
    """Pobierz diff zmian."""
    args = ["diff"]
    if staged:
        args.append("--cached")
    if file:
        args.append("--")
        args.append(file)

    result = _run_git_command(args, cwd=path)

    if not result["success"]:
        return {"diff": "", "error": result.get("error") or result.get("stderr")}

    diff_text = result["stdout"]
    lines = diff_text.split("\n")

    if len(diff_text) > 5000:
        diff_text = diff_text[:5000] + "\n... (truncated)"

    return {
        "diff": diff_text,
        "lines_count": len(lines),
        "truncated": len(result["stdout"]) > 5000,
        "file": file,
        "staged": staged,
    }


@mcp_tool(
    name="git.get_log",
    description="Zwraca historię commitów.",
    args_schema={
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Liczba commitów do zwrócenia (1-50). Domyślnie: 10.",
            },
            "path": {
                "type": "string",
                "description": "Ścieżka do repozytorium. Domyślnie: bieżący katalog.",
            },
        },
        "required": [],
    },
    permissions=["low"],
)
def get_log(count: int = 10, path: Optional[str] = None) -> dict:
    """Pobierz historię commitów."""
    count = min(max(count, 1), 50)

    result = _run_git_command(["log", f"-{count}", "--format=%H|%an|%s|%ar"], cwd=path)

    if not result["success"]:
        return {"commits": [], "error": result.get("error") or result.get("stderr")}

    commits = []
    for line in result["stdout"].split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) >= 4:
            commits.append({
                "sha": parts[0][:8],
                "author": parts[1],
                "message": parts[2],
                "relative_time": parts[3],
            })

    return {"commits": commits, "count": len(commits)}
