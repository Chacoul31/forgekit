"""Parallélisme simple : threads, processus et asyncio avec limite de concurrence."""
from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Awaitable, Callable, Iterable, List, Optional

__all__ = ["pmap", "gather_limit", "async_map"]


def pmap(
    func: Callable[[Any], Any],
    items: Iterable,
    *,
    workers: Optional[int] = None,
    backend: str = "thread",
    ordered: bool = True,
    on_error: str = "raise",
    progress: Optional[Callable[[int, int], Any]] = None,
) -> List:
    """`map` parallèle.

    - `backend` : "thread" (I/O : réseau, fichiers) ou "process" (calcul CPU ; `func` doit être picklable)
    - `ordered` : True -> résultats dans l'ordre des entrées ; False -> ordre de fin
    - `on_error` : "raise" (lève la 1re erreur), "collect" (l'exception est placée dans les résultats),
                   "skip" (l'élément en échec est ignoré)
    - `progress(fait, total)` : callback appelé après chaque élément terminé
    """
    if backend not in ("thread", "process"):
        raise ValueError("backend doit être 'thread' ou 'process'")
    if on_error not in ("raise", "collect", "skip"):
        raise ValueError("on_error doit être 'raise', 'collect' ou 'skip'")

    data = list(items)
    total = len(data)
    if total == 0:
        return []

    executor_cls = ThreadPoolExecutor if backend == "thread" else ProcessPoolExecutor
    finished: List[tuple] = []  # (index, ok, valeur)
    with executor_cls(max_workers=workers) as executor:
        futures = {executor.submit(func, item): i for i, item in enumerate(data)}
        done_count = 0
        for future in as_completed(futures):
            index = futures[future]
            try:
                finished.append((index, True, future.result()))
            except Exception as exc:
                if on_error == "raise":
                    for pending in futures:
                        pending.cancel()
                    raise
                finished.append((index, False, exc))
            done_count += 1
            if progress:
                progress(done_count, total)

    if ordered:
        finished.sort(key=lambda t: t[0])
    return [value for _, ok, value in finished if ok or on_error == "collect"]


async def gather_limit(awaitables: Iterable[Awaitable], limit: int = 10, return_exceptions: bool = False) -> List:
    """Comme `asyncio.gather`, mais avec au plus `limit` tâches simultanées."""
    if limit < 1:
        raise ValueError("limit doit être >= 1")
    semaphore = asyncio.Semaphore(limit)

    async def run(aw: Awaitable):
        async with semaphore:
            return await aw

    return await asyncio.gather(*(run(a) for a in awaitables), return_exceptions=return_exceptions)


async def async_map(
    func: Callable[[Any], Awaitable],
    items: Iterable,
    limit: int = 10,
    return_exceptions: bool = False,
) -> List:
    """Applique une fonction `async` à chaque élément avec au plus `limit` appels simultanés."""
    return await gather_limit((func(item) for item in items), limit, return_exceptions)
