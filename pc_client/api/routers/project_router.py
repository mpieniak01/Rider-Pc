"""Project management endpoints for GitHub integration."""

import asyncio
import logging
import os
import re
import time
import unicodedata
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pc_client.adapters.github_adapter import GitHubAdapter, MockGitHubAdapter
from pc_client.adapters.git_adapter import GitAdapter

logger = logging.getLogger(__name__)

router = APIRouter()

# Adapter singletons
_github_adapter: Optional[GitHubAdapter] = None
_git_adapter: Optional[GitAdapter] = None

# Valid git strategies
GitStrategy = Literal["current", "main", "existing", "new_branch"]
FORCE_GITHUB_MOCK_ENV = "GITHUB_FORCE_MOCK"
FORCE_GITHUB_MOCK_CONFIGURED_ENV = "GITHUB_MOCK_CONFIGURED"


def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to URL/filesystem-safe slug.

    Args:
        text: Input text to slugify.
        max_length: Maximum length of the slug.

    Returns:
        Slugified string (lowercase, no spaces, ASCII only).
    """
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    # Remove non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    # Remove any character that is not alphanumeric or hyphen
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Strip leading/trailing hyphens
    text = text.strip('-')
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rstrip('-')
    return text


def _default_mock_issues() -> List[Dict[str, Any]]:
    now = int(time.time())
    return [
        {
            "number": 101,
            "title": "Standaryzacja kafli dashboardu",
            "state": "open",
            "tasks_total": 5,
            "tasks_done": 3,
            "progress_pct": 60,
            "assignee": "mock-bot",
            "url": "https://github.com/mock/repo/issues/101",
            "created_at": now - 7200,
        },
        {
            "number": 102,
            "title": "Integracja Google Home – tryb demo",
            "state": "open",
            "tasks_total": 3,
            "tasks_done": 1,
            "progress_pct": 33,
            "assignee": None,
            "url": "https://github.com/mock/repo/issues/102",
            "created_at": now - 3600,
        },
    ]


def _should_use_mock_adapter(settings: Optional[Any]) -> bool:
    """Determine if the GitHub mock adapter should be used."""
    if os.getenv(FORCE_GITHUB_MOCK_ENV, "").lower() == "true":
        return True
    if not settings:
        return False
    return bool(settings.test_mode and not getattr(settings, "is_github_configured", False))


def get_github_adapter(request: Request) -> GitHubAdapter:
    """Get or create the GitHub adapter singleton."""
    global _github_adapter
    if _github_adapter is None:
        settings = getattr(request.app.state, "settings", None)
        if _should_use_mock_adapter(settings):
            configured = bool(settings and getattr(settings, "is_github_configured", False))
            if os.getenv(FORCE_GITHUB_MOCK_CONFIGURED_ENV, "false").lower() == "true":
                configured = True
            _github_adapter = MockGitHubAdapter(
                configured=configured,
                issues=_default_mock_issues(),
                collaborators=["mock-bot", "reviewer"],
                labels=["bug", "feature", "ux"],
            )
        elif settings and getattr(settings, "is_github_configured", False):
            _github_adapter = GitHubAdapter(
                token=settings.github_token,
                owner=settings.github_repo_owner,
                repo=settings.github_repo_name,
                cache_ttl=settings.github_cache_ttl_seconds,
            )
        else:
            # Fallback with no configuration
            _github_adapter = GitHubAdapter()
    return _github_adapter


def get_git_adapter(request: Request) -> GitAdapter:
    """Get or create the Git adapter singleton."""
    global _git_adapter
    if _git_adapter is None:
        _git_adapter = GitAdapter()
    return _git_adapter


def get_task_config(request: Request) -> Dict[str, Any]:
    """Get task configuration from settings."""
    settings = getattr(request.app.state, "settings", None)
    if settings:
        return {
            "auto_init_enabled": getattr(settings, "task_auto_init_enabled", True),
            "docs_path": getattr(settings, "task_docs_path", "docs_pl/_to_do"),
            "branch_prefix": getattr(settings, "task_branch_prefix", "feat"),
        }
    return {
        "auto_init_enabled": True,
        "docs_path": "docs_pl/_to_do",
        "branch_prefix": "feat",
    }


class CreateTaskRequest(BaseModel):
    """Request model for creating a new task/issue."""

    title: str = Field(..., min_length=1, description="Issue title")
    body: str = Field(default="", description="Issue body/description (markdown)")
    assignee: Optional[str] = Field(default=None, description="Username to assign")
    labels: List[str] = Field(default_factory=list, description="List of label names")
    git_strategy: GitStrategy = Field(
        default="current", description="Git strategy: 'current', 'main', 'existing', 'new_branch'"
    )
    base_branch: str = Field(default="main", description="Base branch for new_branch strategy")
    existing_branch: Optional[str] = Field(default=None, description="Branch name for existing strategy")
    auto_init: bool = Field(default=True, description="Auto-initialize branch and documentation file")


@router.get("/api/project/issues")
async def get_project_issues(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of issues"),
    refresh: bool = Query(default=False, description="Force refresh (bypass cache)"),
) -> JSONResponse:
    """
    Get open issues from the configured GitHub repository.

    Returns a list of issues with progress information calculated
    from markdown checklists in the issue body.

    Response:
    - repo: Repository name
    - issues: List of issue objects with:
        - number: Issue number
        - title: Issue title
        - state: Issue state (open/closed)
        - tasks_total: Total number of tasks (checkboxes)
        - tasks_done: Number of completed tasks
        - progress_pct: Completion percentage (0-100)
        - assignee: Assigned user login (or null)
        - url: Direct link to issue on GitHub
    - configured: Whether GitHub integration is configured
    - cached: Whether the result came from cache
    - error: Error message if something went wrong
    - timestamp: Unix timestamp of the data
    """
    github = get_github_adapter(request)
    data = await github.get_open_issues(limit=limit, force_refresh=refresh)
    return JSONResponse(content=data)


@router.post("/api/project/refresh")
async def refresh_project_issues(request: Request) -> JSONResponse:
    """
    Force refresh of GitHub issues cache.

    This endpoint invalidates the current cache and fetches fresh data
    from the GitHub API.
    """
    github = get_github_adapter(request)
    github.invalidate_cache()
    data = await github.get_open_issues(limit=10, force_refresh=True)
    return JSONResponse(content=data)


@router.get("/api/project/meta")
async def get_project_meta(request: Request) -> JSONResponse:
    """
    Get metadata for the task creation form.

    Returns:
        - collaborators: List of usernames who can be assigned
        - labels: List of available labels
        - branches: List of local git branches
        - current_branch: Current git branch name
        - configured: Whether GitHub is configured
    """
    github = get_github_adapter(request)
    git = get_git_adapter(request)

    # Fetch all metadata concurrently with exception handling
    results = await asyncio.gather(
        github.get_collaborators(),
        github.get_labels(),
        git.get_local_branches(),
        git.get_current_branch(),
        return_exceptions=True,
    )

    # Handle exceptions and substitute defaults
    def handle_result(result: Any, default: Any, name: str) -> Any:
        if isinstance(result, Exception):
            logger.error("Error fetching %s: %s", name, result)
            return default
        return result

    collaborators = handle_result(results[0], [], "collaborators")
    labels = handle_result(results[1], [], "labels")
    branches = handle_result(results[2], [], "branches")
    current_branch = handle_result(results[3], "", "current_branch")

    return JSONResponse(
        content={
            "collaborators": collaborators,
            "labels": labels,
            "branches": branches,
            "current_branch": current_branch,
            "configured": github.configured,
        }
    )


def generate_task_markdown(
    issue_number: int,
    title: str,
    github_url: str,
    assignee: Optional[str],
    body: str,
) -> str:
    """
    Generate markdown content for task documentation file.

    Args:
        issue_number: GitHub issue number.
        title: Issue title.
        github_url: Full URL to the GitHub issue.
        assignee: Assigned user (or None).
        body: Issue body/description.

    Returns:
        Formatted markdown string.
    """
    assignee_text = assignee if assignee else "Nieprzypisane"
    body_text = body if body else "(brak opisu)"

    return f"""# Zadanie #{issue_number}: {title}

**Status:** :hourglass_flowing_sand: W trakcie
**Link:** {github_url}
**Autor:** {assignee_text}

## Cel
{body_text}

## Plan Realizacji
- [ ] Analiza
- [ ] Implementacja
- [ ] Testy
"""


@router.post("/api/project/create-task")
async def create_task(request: Request, payload: CreateTaskRequest) -> JSONResponse:
    """
    Create a new issue and optionally manage git branches.

    The endpoint:
    1. Creates a new GitHub issue
    2. Optionally creates/switches git branches based on git_strategy
    3. If auto_init is True and git_strategy is new_branch:
       - Creates documentation file in docs_pl/_to_do/
       - Commits the file with an initial commit

    Git strategies:
    - current: Stay on current branch
    - main: Switch to main branch
    - existing: Switch to an existing branch
    - new_branch: Create a new branch from base_branch

    Returns:
        - success: Whether the operation succeeded
        - issue: Created issue info (number, url, title)
        - branch: Current branch after operation
        - docs_file: Path to created documentation file (if auto_init)
        - warning: Warning message if branch operation failed
        - error: Error message if issue creation failed
    """
    github = get_github_adapter(request)
    git = get_git_adapter(request)
    task_config = get_task_config(request)

    result: Dict[str, Any] = {
        "success": False,
    }

    # Step 1: Create GitHub issue
    assignees = [payload.assignee] if payload.assignee else None
    issue_result = await github.create_issue(
        title=payload.title,
        body=payload.body,
        assignees=assignees,
        labels=payload.labels if payload.labels else None,
    )

    if not issue_result.get("success"):
        result["error"] = issue_result.get("error", "Nie udało się utworzyć issue")
        return JSONResponse(content=result, status_code=400)

    result["success"] = True
    result["issue"] = {
        "number": issue_result["number"],
        "url": issue_result["url"],
        "title": issue_result["title"],
    }

    # Step 2: Handle git strategy
    issue_number = issue_result["number"]
    issue_url = issue_result["url"]
    issue_title = issue_result["title"]
    branch_error: Optional[str] = None

    # Check for dirty repository if a git operation is required
    if payload.git_strategy in ("new_branch", "main", "existing"):
        is_dirty = await git.is_dirty()
        if is_dirty:
            result["warning"] = (
                f"Issue utworzono (#{issue_number}), ale repozytorium zawiera niezatwierdzone zmiany. "
                "Zatwierdź lub cofnij zmiany przed zmianą brancha."
            )
            return JSONResponse(content=result, status_code=409)

    if payload.git_strategy == "new_branch":
        # Generate branch name from issue number and title
        title_slug = slugify(payload.title)
        branch_prefix = task_config.get("branch_prefix", "feat")
        branch_name = f"{branch_prefix}/{issue_number}-{title_slug}"

        success, error = await git.create_branch_and_checkout(branch_name, payload.base_branch)
        if not success:
            branch_error = error
        else:
            result["branch"] = branch_name

            # Step 3: Auto-init - create docs file and commit
            if payload.auto_init and task_config.get("auto_init_enabled", True):
                docs_path = task_config.get("docs_path", "docs_pl/_to_do")
                docs_filename = f"{issue_number}_{title_slug}.md"
                docs_filepath = os.path.join(docs_path, docs_filename)

                # Path traversal protection using commonpath for cross-platform safety
                repo_root = os.path.abspath(os.getcwd())
                abs_docs_filepath = os.path.abspath(docs_filepath)

                # Check for path traversal attempts
                is_safe_path = False
                try:
                    # commonpath raises ValueError if paths are on different drives (Windows)
                    # or if one path is not relative to the other
                    common = os.path.commonpath([repo_root, abs_docs_filepath])
                    is_safe_path = common == repo_root
                except ValueError:
                    is_safe_path = False

                if os.path.isabs(docs_path) or ".." in docs_path.split(os.sep):
                    logger.error("Unsafe docs_path detected: %s", docs_path)
                    result["init_warning"] = "Nieprawidłowa ścieżka dokumentacji (docs_path)."
                elif not is_safe_path:
                    logger.error("Docs file path escapes repository root: %s", abs_docs_filepath)
                    result["init_warning"] = "Nieprawidłowa ścieżka pliku dokumentacji."
                else:
                    try:
                        # Ensure docs directory exists
                        os.makedirs(docs_path, exist_ok=True)

                        # Generate markdown content
                        md_content = generate_task_markdown(
                            issue_number=issue_number,
                            title=issue_title,
                            github_url=issue_url,
                            assignee=payload.assignee,
                            body=payload.body,
                        )

                        # Write the file
                        with open(docs_filepath, "w", encoding="utf-8") as f:
                            f.write(md_content)

                        # Git add and commit
                        add_success, add_error = await git.add_file(docs_filepath)
                        if add_success:
                            commit_msg = f"docs: Start task #{issue_number} - {issue_title}"
                            commit_success, commit_error = await git.commit(commit_msg)
                            if commit_success:
                                result["docs_file"] = docs_filepath
                                logger.info("Auto-init completed: created %s", docs_filepath)
                            else:
                                logger.warning("Failed to commit docs file: %s", commit_error)
                                result["init_warning"] = (
                                    f"Plik dokumentacji utworzony, ale commit nie powiódł się: {commit_error}"
                                )
                        else:
                            logger.warning("Failed to add docs file: %s", add_error)
                            result["init_warning"] = (
                                f"Plik dokumentacji utworzony, ale git add nie powiódł się: {add_error}. Plik pozostaje w katalogu roboczym."
                            )

                    except OSError as e:
                        logger.error("Failed to create docs file: %s", e)
                        result["init_warning"] = f"Nie udało się utworzyć pliku dokumentacji: {e}"

    elif payload.git_strategy == "main":
        success, error = await git.checkout_branch("main")
        if not success:
            branch_error = error
        else:
            result["branch"] = "main"

    elif payload.git_strategy == "existing":
        if payload.existing_branch:
            success, error = await git.checkout_branch(payload.existing_branch)
            if not success:
                branch_error = error
            else:
                result["branch"] = payload.existing_branch
        else:
            result["success"] = False
            result["error"] = "Nie wybrano istniejącego brancha"
            return JSONResponse(content=result, status_code=400)

    else:  # current
        current = await git.get_current_branch()
        result["branch"] = current

    # Add warning if branch operation failed
    if branch_error:
        result["warning"] = f"Issue utworzono (#{issue_number}), ale nie udało się zmienić brancha: {branch_error}"

    return JSONResponse(content=result)


async def cleanup_github_adapter() -> None:
    """Cleanup the GitHub adapter on shutdown."""
    global _github_adapter
    if _github_adapter:
        await _github_adapter.close()
        _github_adapter = None
