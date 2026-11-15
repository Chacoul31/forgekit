"""Mesure du temps : chronomètre, tours intermédiaires et décorateur."""
from __future__ import annotations

import functools
import inspect
import time
from typing import Callable, List, Optional

from .text import human_duration

__all__ = ["Timer", "timed"]


class Timer:
    """Chronomètre utilisable comme context manager.

        with Timer("chargement", logger=log) as t:
            charger()
        print(t.elapsed)            # secondes (float)
        print(t)                    # 'chargement: 1.2 s'
    """

    def __init__(self, name: str = "", *, logger=None, clock: Callable[[], float] = time.perf_counter):
        self.name = name
        self._logger = logger
        self._clock = clock
        self._start: Optional[float] = None
        self._end: Optional[float] = None
        self._last_lap: Optional[float] = None
        self.laps: List[float] = []

    def start(self) -> "Timer":
        self._start = self._clock()
        self._last_lap = self._start
        self._end = None
        self.laps = []
        return self

    def stop(self) -> float:
        if self._start is None:
            raise RuntimeError("Le chronomètre n'a pas été démarré")
        if self._end is None:
            self._end = self._clock()
        return self.elapsed

    def lap(self) -> float:
        """Enregistre un tour : durée depuis le tour précédent (ou le départ)."""
        if self._start is None:
            raise RuntimeError("Le chronomètre n'a pas été démarré")
        now = self._clock()
        duration = now - (self._last_lap if self._last_lap is not None else self._start)
        self._last_lap = now
        self.laps.append(duration)
        return duration

    @property
    def elapsed(self) -> float:
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else self._clock()
        return end - self._start

    def __enter__(self) -> "Timer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
        if self._logger is not None:
            self._logger.info("%s", self)

    def __str__(self) -> str:
        label = f"{self.name}: " if self.name else ""
        return f"{label}{human_duration(self.elapsed)}"


def timed(func: Optional[Callable] = None, *, name: Optional[str] = None, logger=None):
    """Décorateur qui chronomètre chaque appel (fonctions normales et `async def`).

    Ajoute à la fonction les attributs `calls`, `total_time` et `last_duration`.
    """

    def decorator(f):
        label = name or f.__qualname__

        def record(wrapper, t: Timer):
            wrapper.calls += 1
            wrapper.total_time += t.elapsed
            wrapper.last_duration = t.elapsed

        if inspect.iscoroutinefunction(f):

            @functools.wraps(f)
            async def wrapper(*args, **kwargs):
                t = Timer(label, logger=logger)
                with t:
                    result = await f(*args, **kwargs)
                record(wrapper, t)
                return result

        else:

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                t = Timer(label, logger=logger)
                with t:
                    result = f(*args, **kwargs)
                record(wrapper, t)
                return result

        wrapper.calls = 0
        wrapper.total_time = 0.0
        wrapper.last_duration = 0.0
        return wrapper

    return decorator(func) if func is not None else decorator
