"""
Simple in-memory TTL cache.
Used for quiz query results and embeddings to avoid redundant API/DB calls.
"""
import time
import hashlib
import json
from typing import Any, Optional


class TTLCache:
    def __init__(self, ttl: int = 300):
        self._store: dict = {}
        self._ttl = ttl

    def _evict_expired(self):
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if v[1] > now}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry and time.time() < entry[1]:
            return entry[0]
        if entry:
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        self._store[key] = (value, time.time() + (ttl or self._ttl))

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> dict:
        self._evict_expired()
        return {"cached_entries": len(self._store)}


def make_key(*args, **kwargs) -> str:
    """Create a stable cache key from any args/kwargs."""
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


# ── Global singletons ──────────────────────────────────────────────────────
quiz_cache      = TTLCache(ttl=300)   # 5 min  — GET /quiz results
embedding_cache = TTLCache(ttl=3600)  # 60 min — text embeddings
