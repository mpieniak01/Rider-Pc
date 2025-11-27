"""GitHub API adapter for fetching repository issues.

This module provides async wrappers for GitHub API calls to retrieve
issue information with progress calculation based on markdown checklists.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Regex patterns for markdown checklist parsing
CHECKBOX_UNCHECKED = re.compile(r"^\s*-\s*\[ \]", re.MULTILINE)
CHECKBOX_CHECKED = re.compile(r"^\s*-\s*\[x\]", re.MULTILINE | re.IGNORECASE)


def parse_checklist_progress(body: Optional[str]) -> Tuple[int, int]:
    """
    Parse markdown body to count checked and unchecked checkboxes.

    Args:
        body: Markdown text containing checkboxes.

    Returns:
        Tuple of (tasks_done, tasks_total).
    """
    if not body:
        return 0, 0

    unchecked = len(CHECKBOX_UNCHECKED.findall(body))
    checked = len(CHECKBOX_CHECKED.findall(body))
    total = unchecked + checked

    return checked, total


class GitHubAdapter:
    """
    Async adapter for GitHub API operations.

    This adapter communicates with api.github.com to fetch issue data
    and calculates progress based on markdown checklists.
    """

    BASE_URL = "https://api.github.com"
    DEFAULT_CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        token: Optional[str] = None,
        owner: str = "",
        repo: str = "",
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: float = 10.0,
    ):
        """
        Initialize the GitHubAdapter.

        Args:
            token: GitHub personal access token for API authentication.
            owner: Repository owner (username or organization).
            repo: Repository name.
            cache_ttl: Cache time-to-live in seconds. Defaults to 300 (5 minutes).
            timeout: HTTP request timeout in seconds.
        """
        self._token = token
        self._owner = owner
        self._repo = repo
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        """Return whether the adapter is properly configured."""
        return bool(self._token and self._owner and self._repo)

    @property
    def repo_full_name(self) -> str:
        """Return the full repository name (owner/repo)."""
        return f"{self._owner}/{self._repo}"

    def _get_headers(self) -> Dict[str, str]:
        """Build HTTP headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Rider-PC-Client",
        }
        if self._token:
            headers["Authorization"] = f"token {self._token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client (thread-safe)."""
        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=self._timeout,
                    headers=self._get_headers(),
                )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client (thread-safe)."""
        async with self._lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        return time.time() - self._cache_ts < self._cache_ttl

    def _update_cache(self, data: Dict[str, Any]) -> None:
        """Update cache with new data."""
        self._cache = data
        self._cache_ts = time.time()

    def invalidate_cache(self) -> None:
        """Invalidate the cache, forcing refresh on next request."""
        self._cache = {}
        self._cache_ts = 0

    async def get_open_issues(
        self,
        limit: int = 10,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Get open issues from the repository with progress information.

        Args:
            limit: Maximum number of issues to return (1-100).
            force_refresh: Force bypass cache and fetch fresh data.

        Returns:
            Dictionary containing:
                - repo: Repository name
                - issues: List of issue dictionaries with progress info
                - configured: Whether GitHub is properly configured
                - cached: Whether result came from cache
                - timestamp: Unix timestamp of the data
        """
        # Check configuration
        if not self.configured:
            logger.warning("GitHub adapter not configured - returning empty result")
            return {
                "repo": self._repo or "unknown",
                "issues": [],
                "configured": False,
                "error": "Konfiguracja GitHub niekompletna",
                "timestamp": int(time.time()),
            }

        # Return cached data if valid and not forcing refresh
        async with self._lock:
            if not force_refresh and self._is_cache_valid() and self._cache:
                logger.debug("Returning cached GitHub issues")
                result = dict(self._cache)
                result["cached"] = True
                return result

        try:
            client = await self._get_client()
            url = f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/issues"
            params = {
                "state": "open",
                "per_page": min(max(1, limit), 100),
                "sort": "updated",
                "direction": "desc",
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            raw_issues = response.json()
            issues = []

            for issue in raw_issues:
                # Skip pull requests (they also appear in issues endpoint)
                if "pull_request" in issue:
                    continue

                body = issue.get("body", "")
                tasks_done, tasks_total = parse_checklist_progress(body)

                progress_pct = 0
                if tasks_total > 0:
                    progress_pct = int((tasks_done / tasks_total) * 100)

                assignee = None
                if issue.get("assignee"):
                    assignee = issue["assignee"].get("login")

                issues.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "tasks_total": tasks_total,
                    "tasks_done": tasks_done,
                    "progress_pct": progress_pct,
                    "assignee": assignee,
                    "url": issue["html_url"],
                })

            result = {
                "repo": self._repo,
                "issues": issues,
                "configured": True,
                "cached": False,
                "timestamp": int(time.time()),
            }

            async with self._lock:
                self._update_cache(result)
            logger.info("Fetched %d issues from GitHub", len(issues))
            return result

        except httpx.HTTPStatusError as e:
            logger.error("GitHub API HTTP error: %s", e)
            error_msg = f"Błąd API GitHub: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Nieprawidłowy token GitHub"
            elif e.response.status_code == 403:
                error_msg = "Przekroczono limit zapytań API GitHub"
            elif e.response.status_code == 404:
                error_msg = f"Repozytorium nie znalezione: {self.repo_full_name}"

            return {
                "repo": self._repo,
                "issues": [],
                "configured": True,
                "error": error_msg,
                "timestamp": int(time.time()),
            }
        except httpx.RequestError as e:
            logger.error("GitHub API request error: %s", e)
            return {
                "repo": self._repo,
                "issues": [],
                "configured": True,
                "error": f"Błąd połączenia z GitHub: {e}",
                "timestamp": int(time.time()),
            }
        except Exception as e:
            logger.error("Unexpected error fetching GitHub issues: %s", e)
            return {
                "repo": self._repo,
                "issues": [],
                "configured": True,
                "error": f"Nieoczekiwany błąd: {e}",
                "timestamp": int(time.time()),
            }


class MockGitHubAdapter:
    """
    Mock adapter for testing environments.

    Simulates GitHub API behavior without making real requests.
    """

    def __init__(
        self,
        configured: bool = True,
        issues: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize the mock adapter.

        Args:
            configured: Whether to simulate being configured.
            issues: Mock issues to return.
        """
        self._configured = configured
        self._issues = issues or []

    @property
    def configured(self) -> bool:
        """Return mock configured status."""
        return self._configured

    def invalidate_cache(self) -> None:
        """No-op for mock adapter."""
        pass

    async def close(self) -> None:
        """No-op for mock adapter."""
        pass

    async def get_open_issues(
        self,
        limit: int = 10,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return mock issues data."""
        if not self._configured:
            return {
                "repo": "unknown",
                "issues": [],
                "configured": False,
                "error": "Konfiguracja GitHub niekompletna",
                "timestamp": int(time.time()),
            }

        return {
            "repo": "rider-pc",
            "issues": self._issues[:limit],
            "configured": True,
            "cached": False,
            "timestamp": int(time.time()),
        }
