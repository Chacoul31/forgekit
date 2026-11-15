"""Caches : mémoire (TTL + LRU, thread-safe) et disque (SQLite)."""
from __future__ import annotations

import functools
import inspect
import pickle
import sqlite3
import threading
import time
from collections import OrderedDict, namedtuple
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Optional

__all__ = ["ttl_cache", "DiskCache", "CacheInfo"]

CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "size", "maxsize"])


def _make_key(args: tuple, kwargs: dict, typed: bool = False):
    key = (args, tuple(sorted(kwargs.items())))
    if typed:
        key += (tuple(type(a) for a in args), tuple(type(v) for _, v in sorted(kwargs.items())))
    try:
        hash(key)
        return key
    except TypeError:
        return repr(key)


class _Store:
    def __init__(self, ttl: Optional[float], maxsize: Optional[int], clock: Callable[[], float]):
        self._data: "OrderedDict[Any, tuple]" = OrderedDict()
        self._ttl = ttl
        self._maxsize = maxsize
        self._clock = clock
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if item is not None:
                value, expires = item
                if expires is None or self._clock() < expires:
                    self._data.move_to_end(key)
                    self.hits += 1
                    return True, value
                del self._data[key]
            self.misses += 1
            return False, None

    def set(self, key, value):
        with self._lock:
            expires = None if self._ttl is None else self._clock() + self._ttl
            self._data[key] = (value, expires)
            self._data.move_to_end(key)
            if self._maxsize is not None:
                while len(self._data) > self._maxsize:
                    self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()
            self.hits = 0
            self.misses = 0

    def info(self) -> CacheInfo:
        with self._lock:
            return CacheInfo(self.hits, self.misses, len(self._data), self._maxsize)


def ttl_cache(
    func: Optional[Callable] = None,
    *,
    ttl: Optional[float] = None,
    maxsize: Optional[int] = 128,
    typed: bool = False,
    clock: Callable[[], float] = time.monotonic,
):
    """Mémoïsation avec expiration (`ttl` en secondes) et éviction LRU (`maxsize`).

    S'utilise avec ou sans parenthèses, sur fonctions normales ou `async def` :

        @ttl_cache(ttl=60)
        def charger(url): ...

    Le décorateur ajoute `cache_info()`, `cache_clear()` et `cache_invalidate(*args, **kwargs)`.
    Les arguments non hashables sont acceptés (clé calculée via `repr`).
    """

    def decorator(f):
        store = _Store(ttl, maxsize, clock)

        if inspect.iscoroutinefunction(f):

            @functools.wraps(f)
            async def wrapper(*args, **kwargs):
                key = _make_key(args, kwargs, typed)
                hit, value = store.get(key)
                if hit:
                    return value
                value = await f(*args, **kwargs)
                store.set(key, value)
                return value

        else:

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                key = _make_key(args, kwargs, typed)
                hit, value = store.get(key)
                if hit:
                    return value
                value = f(*args, **kwargs)
                store.set(key, value)
                return value

        def invalidate(*args, **kwargs):
            key = _make_key(args, kwargs, typed)
            with store._lock:
                store._data.pop(key, None)

        wrapper.cache_info = store.info
        wrapper.cache_clear = store.clear
        wrapper.cache_invalidate = invalidate
        return wrapper

    return decorator(func) if func is not None else decorator


class DiskCache:
    """Cache persistant sur disque (SQLite + pickle).

    N'ouvre jamais un fichier de cache qui ne vient pas de toi : pickle peut exécuter du code.

        cache = DiskCache("cache.db")
        cache.set("cle", {"a": 1}, ttl=3600)
        cache.get("cle")            # {'a': 1}
    """

    def __init__(self, path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB NOT NULL, expires REAL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, key: str, default: Any = None) -> Any:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT value, expires FROM cache WHERE key = ?", (key,)).fetchone()
            if row is None:
                return default
            blob, expires = row
            if expires is not None and self._clock() >= expires:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return default
            return pickle.loads(blob)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires = None if ttl is None else self._clock() + ttl
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
                (key, pickle.dumps(value), expires),
            )

    def delete(self, key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM cache")

    def purge_expired(self) -> int:
        """Supprime les entrées expirées et renvoie leur nombre."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM cache WHERE expires IS NOT NULL AND expires <= ?", (self._clock(),))
            return cur.rowcount

    def __contains__(self, key: str) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    def __len__(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    def memoize(self, ttl: Optional[float] = None, prefix: str = ""):
        """Décorateur : met en cache les résultats d'une fonction sur disque."""

        def decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                key = f"{prefix}{f.__module__}.{f.__qualname__}:{_make_key(args, kwargs)!r}"
                sentinel = object()
                value = self.get(key, sentinel)
                if value is sentinel:
                    value = f(*args, **kwargs)
                    self.set(key, value, ttl)
                return value

            return wrapper

        return decorator
