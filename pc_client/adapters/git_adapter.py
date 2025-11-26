"""Git repository adapter for version information.

This module provides async wrappers for git commands to retrieve
repository information like current branch, commit hash, and dirty status.
It's designed to work within the FastAPI async environment.
"""

import asyncio
import logging
import shutil
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def is_git_available() -> bool:
    """
    Check if git command is available in the system.

    Returns:
        True if git binary is found, False otherwise.
    """
    if shutil.which("git") is None:
        logger.debug("Git not available: git binary not found")
        return False
    return True


class GitAdapter:
    """
    Async adapter for git repository information.

    This adapter executes git commands asynchronously to avoid
    blocking the FastAPI event loop during operations.
    """

    # Cache TTL in seconds (default 60 seconds as per requirements)
    DEFAULT_CACHE_TTL = 60

    def __init__(self, repo_path: Optional[str] = None, cache_ttl: int = DEFAULT_CACHE_TTL):
        """
        Initialize the GitAdapter.

        Args:
            repo_path: Path to the git repository. Defaults to current directory.
            cache_ttl: Cache time-to-live in seconds. Defaults to 60.
        """
        self._repo_path = repo_path
        self._cache_ttl = cache_ttl
        self._available = is_git_available()
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0

    @property
    def available(self) -> bool:
        """Return whether git is available on this system."""
        return self._available

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

    async def _run_command(self, *args: str) -> Tuple[int, str, str]:
        """
        Run an async subprocess command.

        Args:
            *args: Command and arguments to execute.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        try:
            cmd = list(args)
            if self._repo_path:
                cmd = ["git", "-C", self._repo_path] + list(args[1:]) if args[0] == "git" else cmd

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            return process.returncode, stdout_str, stderr_str
        except Exception as e:
            logger.error("Failed to execute command %s: %s", " ".join(args), e)
            return -1, "", str(e)

    async def _is_in_git_repo(self) -> bool:
        """
        Check if current directory is inside a git repository.

        Returns:
            True if inside a git repository, False otherwise.
        """
        if not self._available:
            return False

        cmd = ["git", "rev-parse", "--git-dir"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "rev-parse", "--git-dir"]

        returncode, _, _ = await self._run_command(*cmd)
        return returncode == 0

    async def get_current_branch(self) -> str:
        """
        Get the current git branch name.

        Returns:
            Branch name string, or "unknown" if not available.
        """
        if not self._available:
            return "unknown"

        cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "rev-parse", "--abbrev-ref", "HEAD"]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            logger.warning("Failed to get current branch: %s", stderr or stdout)
            return "unknown"

        return stdout or "unknown"

    async def get_current_commit(self) -> str:
        """
        Get the current git commit hash (short form).

        Returns:
            Short commit hash string, or "unknown" if not available.
        """
        if not self._available:
            return "unknown"

        cmd = ["git", "rev-parse", "--short", "HEAD"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "rev-parse", "--short", "HEAD"]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            logger.warning("Failed to get current commit: %s", stderr or stdout)
            return "unknown"

        return stdout or "unknown"

    async def is_dirty(self) -> bool:
        """
        Check if there are uncommitted changes in the repository.

        Returns:
            True if there are uncommitted changes, False otherwise.
        """
        if not self._available:
            return False

        cmd = ["git", "status", "--porcelain"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "status", "--porcelain"]

        returncode, stdout, _ = await self._run_command(*cmd)

        if returncode != 0:
            return False

        # If there's any output, the repo is dirty
        return bool(stdout.strip())

    async def get_last_commit_message(self) -> str:
        """
        Get the last commit message.

        Returns:
            Commit message string, or empty string if not available.
        """
        if not self._available:
            return ""

        cmd = ["git", "log", "-1", "--pretty=%B"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "log", "-1", "--pretty=%B"]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            logger.warning("Failed to get last commit message: %s", stderr or stdout)
            return ""

        # Return first line only (trim multi-line messages)
        return stdout.split('\n')[0].strip() if stdout else ""

    async def get_version_info(self) -> Dict[str, Any]:
        """
        Get all version information in a single call with caching.

        Returns:
            Dictionary containing branch, commit, dirty status, message, and timestamp.
        """
        # Return cached data if still valid
        if self._is_cache_valid() and self._cache:
            return self._cache

        # Check if we're in a git repo
        if not await self._is_in_git_repo():
            data = {
                "branch": "unknown",
                "commit": "unknown",
                "dirty": False,
                "message": "",
                "ts": int(time.time()),
                "available": False,
            }
            self._update_cache(data)
            return data

        # Gather all info concurrently
        branch, commit, dirty, message = await asyncio.gather(
            self.get_current_branch(),
            self.get_current_commit(),
            self.is_dirty(),
            self.get_last_commit_message(),
        )

        data = {
            "branch": branch,
            "commit": commit,
            "dirty": dirty,
            "message": message,
            "ts": int(time.time()),
            "available": True,
        }

        self._update_cache(data)
        return data


class MockGitAdapter:
    """
    Mock adapter for testing environments.

    Simulates git behavior without executing real commands.
    """

    def __init__(
        self,
        branch: str = "main",
        commit: str = "abc1234",
        dirty: bool = False,
        message: str = "Test commit message",
        available: bool = True,
    ):
        """
        Initialize the mock adapter.

        Args:
            branch: Mock branch name.
            commit: Mock commit hash.
            dirty: Mock dirty status.
            message: Mock commit message.
            available: Whether to simulate git being available.
        """
        self._branch = branch
        self._commit = commit
        self._dirty = dirty
        self._message = message
        self._available = available

    @property
    def available(self) -> bool:
        """Return whether git is simulated as available."""
        return self._available

    def invalidate_cache(self) -> None:
        """No-op for mock adapter."""
        pass

    async def get_current_branch(self) -> str:
        """Return mock branch name."""
        return self._branch if self._available else "unknown"

    async def get_current_commit(self) -> str:
        """Return mock commit hash."""
        return self._commit if self._available else "unknown"

    async def is_dirty(self) -> bool:
        """Return mock dirty status."""
        return self._dirty if self._available else False

    async def get_last_commit_message(self) -> str:
        """Return mock commit message."""
        return self._message if self._available else ""

    async def get_version_info(self) -> Dict[str, Any]:
        """Return mock version info."""
        return {
            "branch": self._branch if self._available else "unknown",
            "commit": self._commit if self._available else "unknown",
            "dirty": self._dirty if self._available else False,
            "message": self._message if self._available else "",
            "ts": int(time.time()),
            "available": self._available,
        }
