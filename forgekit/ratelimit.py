"""Limiteur de débit (token bucket), thread-safe."""
from __future__ import annotations

import functools
import threading
import time
from typing import Callable, Optional

__all__ = ["RateLimiter"]


class RateLimiter:
    """Autorise au plus `rate` opérations par `per` secondes (avec rafales jusqu'à `burst`).

        limiter = RateLimiter(rate=5, per=1.0)      # 5 appels / seconde

        for url in urls:
            with limiter:                            # attend si nécessaire
                requests.get(url)

        @limiter                                     # ou en décorateur
        def appeler_api(): ...
    """

    def __init__(
        self,
        rate: float,
        per: float = 1.0,
        burst: Optional[float] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if rate <= 0 or per <= 0:
            raise ValueError("rate et per doivent être > 0")
        self.capacity = float(burst if burst is not None else rate)
        if self.capacity < 1:
            raise ValueError("burst doit être >= 1")
        self._refill_rate = rate / per
        self._clock = clock
        self._sleep = sleep
        self._tokens = self.capacity
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self._refill_rate)

    def try_acquire(self, n: float = 1) -> bool:
        """Prend `n` jetons s'ils sont disponibles, sans attendre."""
        with self._lock:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def acquire(self, n: float = 1) -> float:
        """Prend `n` jetons en attendant si besoin. Renvoie le temps attendu (secondes)."""
        if n > self.capacity:
            raise ValueError("n dépasse la capacité du limiteur")
        waited = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return waited
                wait = (n - self._tokens) / self._refill_rate
            self._sleep(wait)
            waited += wait

    def __enter__(self) -> "RateLimiter":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        return None

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)

        return wrapper
