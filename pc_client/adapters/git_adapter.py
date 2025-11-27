"""Git repository adapter for version information.

This module provides async wrappers for git commands to retrieve
repository information like current branch, commit hash, and dirty status.
It's designed to work within the FastAPI async environment.
"""

import asyncio
import logging
import re
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex pattern for validating safe branch names
# Only allows alphanumeric, hyphens, underscores, slashes, and dots
SAFE_BRANCH_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9/_.-]+$')


def is_safe_branch_name(name: str) -> bool:
    """
    Validate that a branch name only contains safe characters.

    Args:
        name: Branch name to validate.

    Returns:
        True if branch name is safe, False otherwise.
    """
    if not name or not name.strip():
        return False
    return bool(SAFE_BRANCH_NAME_PATTERN.match(name.strip()))


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
            process = await asyncio.create_subprocess_exec(
                *args,
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

        # Return first line only (extract subject from multi-line commit messages)
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

    async def get_local_branches(self) -> List[str]:
        """
        Get list of local branches.

        Returns:
            List of branch names.
        """
        if not self._available:
            return []

        cmd = ["git", "branch", "--format=%(refname:short)"]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "branch", "--format=%(refname:short)"]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            logger.warning("Failed to get local branches: %s", stderr or stdout)
            return []

        branches = [b.strip() for b in stdout.split('\n') if b.strip()]
        return branches

    async def checkout_branch(self, name: str) -> Tuple[bool, str]:
        """
        Checkout an existing branch.

        Args:
            name: Branch name to checkout.

        Returns:
            Tuple of (success, error_message).
        """
        if not self._available:
            return False, "Git nie jest dostępny"

        if not name or not name.strip():
            return False, "Nazwa brancha nie może być pusta"

        if not is_safe_branch_name(name):
            return False, "Nazwa brancha zawiera niedozwolone znaki"

        cmd = ["git", "checkout", name.strip()]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "checkout", name.strip()]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            error = stderr or stdout or "Nieznany błąd"
            logger.warning("Failed to checkout branch %s: %s", name, error)
            return False, error

        self.invalidate_cache()
        return True, ""

    async def create_branch(self, name: str, base: str = "main") -> Tuple[bool, str]:
        """
        Create and checkout a new branch.

        Args:
            name: New branch name.
            base: Base branch name (default: main).

        Returns:
            Tuple of (success, error_message).
        """
        if not self._available:
            return False, "Git nie jest dostępny"

        if not name or not name.strip():
            return False, "Nazwa brancha nie może być pusta"

        if not is_safe_branch_name(name):
            return False, "Nazwa brancha zawiera niedozwolone znaki"

        if not is_safe_branch_name(base):
            return False, "Nazwa bazowego brancha zawiera niedozwolone znaki"

        cmd = ["git", "checkout", "-b", name.strip(), base.strip()]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "checkout", "-b", name.strip(), base.strip()]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            error = stderr or stdout or "Nieznany błąd"
            logger.warning("Failed to create branch %s: %s", name, error)
            return False, error

        self.invalidate_cache()
        return True, ""

    async def create_branch_and_checkout(self, name: str, base: str = "main") -> Tuple[bool, str]:
        """
        Create and checkout a new branch (alias for create_branch).

        Note: create_branch already performs both operations (git checkout -b),
        this alias is provided for API clarity.

        Args:
            name: New branch name.
            base: Base branch name (default: main).

        Returns:
            Tuple of (success, error_message).
        """
        return await self.create_branch(name, base)

    async def add_file(self, path: str) -> Tuple[bool, str]:
        """
        Stage a file for commit.

        Args:
            path: Path to file to stage.

        Returns:
            Tuple of (success, error_message).
        """
        if not self._available:
            return False, "Git nie jest dostępny"

        if not path or not path.strip():
            return False, "Ścieżka pliku nie może być pusta"

        cmd = ["git", "add", path.strip()]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "add", path.strip()]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            error = stderr or stdout or "Nieznany błąd"
            logger.warning("Failed to add file %s: %s", path, error)
            return False, error

        return True, ""

    async def commit(self, message: str) -> Tuple[bool, str]:
        """
        Commit staged changes.

        Args:
            message: Commit message.

        Returns:
            Tuple of (success, error_message).
        """
        if not self._available:
            return False, "Git nie jest dostępny"

        if not message or not message.strip():
            return False, "Wiadomość commita nie może być pusta"

        cmd = ["git", "commit", "-m", message.strip()]
        if self._repo_path:
            cmd = ["git", "-C", self._repo_path, "commit", "-m", message.strip()]

        returncode, stdout, stderr = await self._run_command(*cmd)

        if returncode != 0:
            error = stderr or stdout or "Nieznany błąd"
            logger.warning("Failed to commit: %s", error)
            return False, error

        self.invalidate_cache()
        return True, ""


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
        branches: Optional[List[str]] = None,
    ):
        """
        Initialize the mock adapter.

        Args:
            branch: Mock branch name.
            commit: Mock commit hash.
            dirty: Mock dirty status.
            message: Mock commit message.
            available: Whether to simulate git being available.
            branches: Mock list of branches.
        """
        self._branch = branch
        self._commit = commit
        self._dirty = dirty
        self._message = message
        self._available = available
        self._branches = branches or ["main", "develop"]

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

    async def get_local_branches(self) -> List[str]:
        """Return mock branches list."""
        return self._branches if self._available else []

    async def checkout_branch(self, name: str) -> Tuple[bool, str]:
        """Return mock checkout result."""
        if not self._available:
            return False, "Git nie jest dostępny"
        if not name or not name.strip():
            return False, "Nazwa brancha nie może być pusta"
        if name not in self._branches:
            return False, f"Branch '{name}' nie istnieje"
        self._branch = name
        return True, ""

    async def create_branch(self, name: str, base: str = "main") -> Tuple[bool, str]:
        """Return mock create branch result."""
        if not self._available:
            return False, "Git nie jest dostępny"
        if not name or not name.strip():
            return False, "Nazwa brancha nie może być pusta"
        if name in self._branches:
            return False, f"Branch '{name}' już istnieje"
        self._branches.append(name)
        self._branch = name
        return True, ""

    async def create_branch_and_checkout(self, name: str, base: str = "main") -> Tuple[bool, str]:
        """Return mock create branch and checkout result."""
        return await self.create_branch(name, base)

    async def add_file(self, path: str) -> Tuple[bool, str]:
        """Return mock add file result."""
        if not self._available:
            return False, "Git nie jest dostępny"
        if not path or not path.strip():
            return False, "Ścieżka pliku nie może być pusta"
        return True, ""

    async def commit(self, message: str) -> Tuple[bool, str]:
        """Return mock commit result."""
        if not self._available:
            return False, "Git nie jest dostępny"
        if not message or not message.strip():
            return False, "Wiadomość commita nie może być pusta"
        return True, ""
