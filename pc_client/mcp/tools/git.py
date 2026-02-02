"""Git tools for MCP.

Narzędzia do pracy z repozytorium Git: zmiany, status, testy (read-only).
Uwaga: narzędzia te powinny być dostępne tylko dla zaufanych użytkowników/kontekstów.
"""

import subprocess
import os
from typing import List, Optional, TypedDict

from pc_client.mcp.registry import mcp_tool


class GitCommandResult(TypedDict, total=False):
    success: bool
    stdout: str
    stderr: Optional[str]
    error: Optional[str]


# Dozwolone katalogi bazowe dla operacji git (bezpieczeństwo)
_ALLOWED_GIT_PATHS = [
    os.getcwd(),
    os.path.expanduser("~"),
]


def _validate_cwd(cwd: Optional[str]) -> str:
    """Waliduj ścieżkę cwd dla bezpieczeństwa.

    Args:
        cwd: Ścieżka do walidacji.

    Returns:
        Zwalidowana ścieżka.

    Raises:
        ValueError: Jeśli ścieżka jest poza dozwolonymi katalogami.
    """
    if cwd is None:
        return os.getcwd()

    # Normalizuj ścieżkę
    normalized = os.path.normpath(os.path.abspath(cwd))

    # Sprawdź czy ścieżka jest w dozwolonych katalogach
    for allowed in _ALLOWED_GIT_PATHS:
        allowed_norm = os.path.normpath(os.path.abspath(allowed))
        if normalized.startswith(allowed_norm):
            return normalized

    raise ValueError(f"Path not allowed: {cwd}")


def _run_git_command(args: List[str], cwd: Optional[str] = None) -> GitCommandResult:
    """Wykonaj komendę git i zwróć wynik.

    Args:
        args: Lista argumentów dla git.
        cwd: Ścieżka do repozytorium (musi być w dozwolonych katalogach).

    Returns:
        Słownik z wynikiem komendy.
    """
    try:
        validated_cwd = _validate_cwd(cwd)
        git_result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=validated_cwd,
            timeout=30,
        )
        response: GitCommandResult = {
            "success": git_result.returncode == 0,
            "stdout": git_result.stdout.strip(),
            "stderr": git_result.stderr.strip() if git_result.returncode != 0 else None,
        }
        return response

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "Git not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class GitLastCommit(TypedDict, total=False):
    sha: str
    message: str
    relative_time: str


class GitStatusResponse(TypedDict):
    current_branch: Optional[str]
    last_commit: Optional[GitLastCommit]
    changed_files_count: int
    has_remote: bool
    is_git_repo: bool


class GitChangedFile(TypedDict):
    status: str
    path: str


class GitChangedFilesResponse(TypedDict, total=False):
    files: List[GitChangedFile]
    count: int
    staged_only: bool
    error: Optional[str]


class GitDiffResponse(TypedDict, total=False):
    diff: str
    lines_count: int
    truncated: bool
    file: Optional[str]
    staged: bool
    error: Optional[str]


class GitCommitEntry(TypedDict):
    sha: str
    author: str
    message: str
    relative_time: str


class GitLogResponse(TypedDict, total=False):
    commits: List[GitCommitEntry]
    count: int
    error: Optional[str]


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
def get_changed_files(staged_only: bool = False, path: Optional[str] = None) -> GitChangedFilesResponse:
    """Pobierz listę zmienionych plików."""
    command_result: GitCommandResult
    if staged_only:
        command_result = _run_git_command(["diff", "--cached", "--name-status"], cwd=path)
    else:
        command_result = _run_git_command(["status", "--porcelain"], cwd=path)

    if not command_result["success"]:
        return {"files": [], "error": command_result.get("error") or command_result.get("stderr")}

    files: List[GitChangedFile] = []
    for line in command_result["stdout"].split("\n"):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) >= 2:
            status, filename = parts[0], parts[1]
            files.append({"status": status, "path": filename})
        elif len(parts) == 1:
            files.append({"status": "?", "path": parts[0]})

    response: GitChangedFilesResponse = {
        "files": files,
        "count": len(files),
        "staged_only": staged_only,
    }
    return response


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
def get_git_status(path: Optional[str] = None) -> GitStatusResponse:
    """Pobierz status repozytorium Git."""
    branch_result = _run_git_command(["branch", "--show-current"], cwd=path)
    current_branch = branch_result["stdout"] if branch_result["success"] else None

    log_result = _run_git_command(["log", "-1", "--format=%H|%s|%ar"], cwd=path)
    last_commit: Optional[GitLastCommit] = None
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

    status: GitStatusResponse = {
        "current_branch": current_branch,
        "last_commit": last_commit,
        "changed_files_count": changed_count,
        "has_remote": has_remote,
        "is_git_repo": branch_result["success"],
    }
    return status


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
) -> GitDiffResponse:
    """Pobierz diff zmian."""
    args = ["diff"]
    if staged:
        args.append("--cached")
    if file:
        args.append("--")
        args.append(file)

    command_result: GitCommandResult = _run_git_command(args, cwd=path)

    if not command_result["success"]:
        return {"diff": "", "error": command_result.get("error") or command_result.get("stderr")}

    diff_text = command_result["stdout"]
    lines = diff_text.split("\n")

    if len(diff_text) > 5000:
        diff_text = diff_text[:5000] + "\n... (truncated)"

    diff_response: GitDiffResponse = {
        "diff": diff_text,
        "lines_count": len(lines),
        "truncated": len(command_result["stdout"]) > 5000,
        "file": file,
        "staged": staged,
    }
    return diff_response


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
def get_log(count: int = 10, path: Optional[str] = None) -> GitLogResponse:
    """Pobierz historię commitów."""
    count = min(max(count, 1), 50)

    command_result: GitCommandResult = _run_git_command(["log", f"-{count}", "--format=%H|%an|%s|%ar"], cwd=path)

    if not command_result["success"]:
        return {"commits": [], "error": command_result.get("error") or command_result.get("stderr")}

    commits: List[GitCommitEntry] = []
    for line in command_result["stdout"].split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) >= 4:
            commits.append(
                {
                    "sha": parts[0][:8],
                    "author": parts[1],
                    "message": parts[2],
                    "relative_time": parts[3],
                }
            )

    log_response: GitLogResponse = {"commits": commits, "count": len(commits)}
    return log_response
