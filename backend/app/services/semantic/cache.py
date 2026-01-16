"""Simple in-memory TTL cache."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, maxsize: int = 256, ttl_seconds: int = 300) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        now = time.time()
        if key not in self._store:
            return None
        expires_at, value = self._store.pop(key)
        if expires_at < now:
            return None
        self._store[key] = (expires_at, value)
        return value

    def set(self, key: K, value: V) -> None:
        now = time.time()
        expires_at = now + self._ttl
        if key in self._store:
            self._store.pop(key)
        self._store[key] = (expires_at, value)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
