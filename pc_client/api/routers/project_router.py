"""Project management endpoints for GitHub integration."""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from pc_client.adapters.github_adapter import GitHubAdapter

logger = logging.getLogger(__name__)

router = APIRouter()

# GitHub adapter singleton
_github_adapter: Optional[GitHubAdapter] = None


def get_github_adapter(request: Request) -> GitHubAdapter:
    """Get or create the GitHub adapter singleton."""
    global _github_adapter
    if _github_adapter is None:
        settings = getattr(request.app.state, "settings", None)
        if settings:
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


async def cleanup_github_adapter() -> None:
    """Cleanup the GitHub adapter on shutdown."""
    global _github_adapter
    if _github_adapter:
        await _github_adapter.close()
        _github_adapter = None
