"""Réessais automatiques avec backoff exponentiel (fonctions synchrones et async)."""
from __future__ import annotations

import asyncio
import functools
import inspect
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

__all__ = ["retry", "compute_delay"]


def compute_delay(attempt: int, delay: float, backoff: float, max_delay: float, jitter: float) -> float:
    """Délai avant la tentative suivante (attempt commence à 1)."""
    wait = min(delay * (backoff ** (attempt - 1)), max_delay)
    if jitter:
        wait += wait * jitter * random.random()
    return wait


def retry(
    attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    jitter: float = 0.1,
    exceptions: Union[Type[BaseException], Tuple[Type[BaseException], ...]] = (Exception,),
    on_retry: Optional[Callable[[int, BaseException], Any]] = None,
    giveup: Optional[Callable[[BaseException], bool]] = None,
):
    """Décorateur : relance la fonction si elle lève une des `exceptions`.

    - `attempts` : nombre total d'essais (>= 1)
    - `delay`, `backoff`, `max_delay`, `jitter` : politique d'attente entre les essais
    - `on_retry(tentative, exception)` : callback avant chaque nouvel essai
    - `giveup(exception)` : si elle renvoie True, on abandonne tout de suite

    La dernière exception est relancée telle quelle quand les essais sont épuisés.
    Fonctionne aussi sur les fonctions `async def`.
    """
    if attempts < 1:
        raise ValueError("attempts doit être >= 1")

    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                for attempt in range(1, attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        if attempt == attempts or (giveup and giveup(exc)):
                            raise
                        if on_retry:
                            on_retry(attempt, exc)
                        await asyncio.sleep(compute_delay(attempt, delay, backoff, max_delay, jitter))

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts or (giveup and giveup(exc)):
                        raise
                    if on_retry:
                        on_retry(attempt, exc)
                    time.sleep(compute_delay(attempt, delay, backoff, max_delay, jitter))

        return wrapper

    return decorator
