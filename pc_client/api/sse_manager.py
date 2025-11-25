"""Utility manager for server-sent events subscriptions."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict, Iterable, Optional


class SseManager:
    """Centralized SSE subscription helper with backlog + retry support."""

    def __init__(self, backlog_limit: int = 200, queue_size: int = 100) -> None:
        self._backlog: Deque[Dict] = deque(maxlen=backlog_limit)
        self._subscribers: set[asyncio.Queue] = set()
        self._queue_size = queue_size

    @staticmethod
    def _stamp(payload: Dict) -> Dict:
        payload = dict(payload or {})
        payload.setdefault("ts", time.time())
        return payload

    def publish(self, payload: Dict) -> None:
        """Store payload and fan it out to all subscribers."""
        stamped = self._stamp(payload)
        self._backlog.append(stamped)
        stale: list[asyncio.Queue] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(stamped)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.unsubscribe(queue)

    def subscribe(self) -> asyncio.Queue:
        """Register a new queue and preload backlog events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        for event in list(self._backlog):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                break
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: Optional[asyncio.Queue]) -> None:
        """Remove queue from subscription list."""
        if queue and queue in self._subscribers:
            self._subscribers.remove(queue)

    def backlog(self) -> Iterable[Dict]:
        """Expose current backlog (useful for diagnostics/tests)."""
        return tuple(self._backlog)

    def subscriber_count(self) -> int:
        return len(self._subscribers)
