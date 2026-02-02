"""Async helpers for environments with limited threading support."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_FLAG = os.getenv("RIDER_ENABLE_TO_THREAD")
if _FLAG is None:
    _USE_THREADS = True
else:
    _USE_THREADS = _FLAG.lower() in {"1", "true", "yes", "on"}


async def _run_in_thread(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Helper that wraps asyncio.to_thread with graceful fallback."""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except (RuntimeError, PermissionError) as exc:
        logger.warning("asyncio.to_thread unavailable (%s); falling back to sync execution", exc)
        return func(*args, **kwargs)


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute blocking function, offloading to a background thread when possible."""
    if _USE_THREADS:
        return await _run_in_thread(func, *args, **kwargs)
    return func(*args, **kwargs)
