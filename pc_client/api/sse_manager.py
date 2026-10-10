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
        self._next_id = 0

    @staticmethod
    def _stamp(payload: Dict) -> Dict:
        payload = dict(payload or {})
        payload.setdefault("ts", time.time())
        return payload

    def publish(self, payload: Dict) -> None:
        """Store payload and fan it out to all subscribers."""
        stamped = self._stamp(payload)
        self._next_id += 1
        stamped["event_id"] = self._next_id
        self._backlog.append(stamped)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(stamped)
            except asyncio.QueueFull:
                # Czytelnik otrzyma jawny gap i najnowszy stan zamiast cichego
                # odłączenia, po którym widziałby tylko heartbeat.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(
                    {
                        "topic": "transport.gap",
                        "data": {"error": "sse_backpressure", "stale": True},
                        "event_id": self._next_id,
                    }
                )
                if self._queue_size > 1:
                    queue.put_nowait(stamped)

    def subscribe(self, after_id: int | None = None) -> asyncio.Queue:
        """Wznawiaj bounded backlog; luka jest jawna i nie odmładza danych."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        backlog = list(self._backlog)
        gap = after_id is not None and (
            after_id > self._next_id or bool(backlog) and after_id < backlog[0]["event_id"] - 1
        )
        rows = backlog if after_id is None or gap else [row for row in backlog if row["event_id"] > after_id]
        gap = gap or len(rows) > self._queue_size
        if gap:
            queue.put_nowait(
                {
                    "topic": "transport.gap",
                    "data": {"error": "sse_replay_gap", "stale": True},
                    "event_id": self._next_id,
                }
            )
        capacity = self._queue_size - (1 if gap else 0)
        for event in rows[-capacity:] if capacity else []:
            queue.put_nowait(event)
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
