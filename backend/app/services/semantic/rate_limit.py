"""In-memory rate limiting utilities."""

from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._window = 60.0
        self._requests: dict[str, deque[float]] = {}

    def allow(self, key: str = "global") -> bool:
        if self._limit <= 0:
            return True

        now = time.monotonic()
        queue = self._requests.setdefault(key, deque())
        while queue and now - queue[0] > self._window:
            queue.popleft()
        if len(queue) >= self._limit:
            return False
        queue.append(now)
        return True

    def retry_after(self, key: str = "global") -> int | None:
        if key not in self._requests or not self._requests[key]:
            return None
        oldest = self._requests[key][0]
        now = time.monotonic()
        remaining = self._window - (now - oldest)
        return max(0, int(remaining))
