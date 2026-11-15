"""Bus d'événements (publication / abonnement), thread-safe."""
from __future__ import annotations

import inspect
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["EventBus"]

_log = logging.getLogger("forgekit.events")


class EventBus:
    """Découple les parties d'un programme : l'émetteur ne connaît pas les écouteurs.

        bus = EventBus()

        @bus.on("fichier.recu")
        def traiter(nom, taille):
            print(nom, taille)

        bus.on("*", lambda evenement, *a, **k: print("log:", evenement))   # joker : tous les événements

        bus.emit("fichier.recu", "rapport.pdf", taille=120)

    Une erreur dans un écouteur n'empêche pas les autres de s'exécuter (elle est journalisée,
    ou relancée à la fin si `raise_errors=True`).
    """

    def __init__(self, raise_errors: bool = False):
        self.raise_errors = raise_errors
        self._handlers: Dict[str, List[Tuple[Callable, bool]]] = defaultdict(list)
        self._lock = threading.RLock()

    def on(self, event: str, handler: Optional[Callable] = None, *, once: bool = False):
        """Abonne `handler` à `event`. Utilisable comme décorateur."""

        def register(h: Callable) -> Callable:
            with self._lock:
                self._handlers[event].append((h, once))
            return h

        return register(handler) if handler is not None else register

    def once(self, event: str, handler: Optional[Callable] = None):
        """Comme `on`, mais l'écouteur n'est appelé qu'une seule fois."""
        return self.on(event, handler, once=True)

    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """Désabonne `handler` (ou tous les écouteurs de `event` si `handler` est None)."""
        with self._lock:
            if handler is None:
                self._handlers.pop(event, None)
            else:
                self._handlers[event] = [(h, o) for h, o in self._handlers.get(event, []) if h is not handler]

    def listeners(self, event: str) -> int:
        with self._lock:
            return len(self._handlers.get(event, []))

    def _collect(self, event: str) -> List[Tuple[Callable, bool]]:
        calls: List[Tuple[Callable, bool]] = []
        with self._lock:
            for key, is_wild in ((event, False), ("*", True)):
                if is_wild and event == "*":
                    continue
                entries = self._handlers.get(key, [])
                calls.extend((h, is_wild) for h, _ in entries)
                if any(o for _, o in entries):
                    self._handlers[key] = [(h, o) for h, o in entries if not o]
        return calls

    def emit(self, event: str, *args: Any, **kwargs: Any) -> List[Any]:
        """Appelle les écouteurs et renvoie la liste de leurs résultats."""
        results: List[Any] = []
        first_error: Optional[BaseException] = None
        for handler, is_wild in self._collect(event):
            try:
                results.append(handler(event, *args, **kwargs) if is_wild else handler(*args, **kwargs))
            except Exception as exc:
                _log.exception("Erreur dans l'écouteur de %r", event)
                first_error = first_error or exc
        if first_error is not None and self.raise_errors:
            raise first_error
        return results

    async def emit_async(self, event: str, *args: Any, **kwargs: Any) -> List[Any]:
        """Version asynchrone : attend les écouteurs `async def`."""
        results: List[Any] = []
        first_error: Optional[BaseException] = None
        for handler, is_wild in self._collect(event):
            try:
                result = handler(event, *args, **kwargs) if is_wild else handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                results.append(result)
            except Exception as exc:
                _log.exception("Erreur dans l'écouteur de %r", event)
                first_error = first_error or exc
        if first_error is not None and self.raise_errors:
            raise first_error
        return results
