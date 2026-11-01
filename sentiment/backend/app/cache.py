from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    stored_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, CacheEntry[T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        if not self.ttl_seconds:
            return None
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            if time.monotonic() - item.stored_at >= self.ttl_seconds:
                del self._items[key]
                return None
            return item.value

    def set(self, key: str, value: T) -> None:
        if not self.ttl_seconds:
            return
        with self._lock:
            self._items[key] = CacheEntry(value, time.monotonic())


def text_cache_key(model_id: str, texts: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(model_id.encode())
    for text in texts:
        digest.update(b"\0")
        digest.update(text.encode())
    return digest.hexdigest()
