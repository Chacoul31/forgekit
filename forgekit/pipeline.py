"""Composition de fonctions en pipelines lisibles."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator, List, Optional, Tuple

__all__ = ["Pipeline", "PipelineError", "compose", "pipe"]


class PipelineError(Exception):
    """Erreur levée par une étape ; garde l'étape fautive et l'exception d'origine."""

    def __init__(self, step_name: str, index: int, original: BaseException):
        super().__init__(f"Étape #{index} '{step_name}' en échec : {original}")
        self.step_name = step_name
        self.index = index
        self.original = original


class Pipeline:
    """Suite d'étapes appliquées l'une après l'autre.

        nettoyer = (
            Pipeline(name="nettoyage")
            .then(str.strip)
            .then(str.lower)
            .then(lambda s: s.replace("  ", " "), name="espaces")
        )
        nettoyer("  Bonjour  Monde ")           # 'bonjour monde'
        list(nettoyer.map(["A ", " B"]))         # ['a', 'b']

    `on_error(erreur, valeur)` permet de poursuivre : sa valeur de retour devient
    la valeur transmise à l'étape suivante. Sans `on_error`, une `PipelineError` est levée.
    L'opérateur `|` ajoute aussi une étape : `Pipeline() | f | g`.
    """

    def __init__(
        self,
        *steps: Callable[[Any], Any],
        name: str = "pipeline",
        on_error: Optional[Callable[[PipelineError, Any], Any]] = None,
    ):
        self.name = name
        self._on_error = on_error
        self._steps: List[Tuple[str, Callable[[Any], Any]]] = [
            (getattr(s, "__name__", repr(s)), s) for s in steps
        ]

    @property
    def steps(self) -> List[str]:
        return [name for name, _ in self._steps]

    def then(self, step: Callable[[Any], Any], name: Optional[str] = None) -> "Pipeline":
        """Renvoie un nouveau pipeline avec une étape de plus (l'original n'est pas modifié)."""
        new = Pipeline(name=self.name, on_error=self._on_error)
        new._steps = list(self._steps) + [(name or getattr(step, "__name__", repr(step)), step)]
        return new

    __or__ = then

    def __call__(self, value: Any) -> Any:
        for index, (step_name, step) in enumerate(self._steps):
            try:
                value = step(value)
            except Exception as exc:
                error = PipelineError(step_name, index, exc)
                if self._on_error is None:
                    raise error from exc
                value = self._on_error(error, value)
        return value

    def map(self, items: Iterable) -> Iterator:
        """Applique le pipeline à chaque élément (paresseux)."""
        for item in items:
            yield self(item)

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return f"Pipeline({self.name!r}: {' -> '.join(self.steps) or 'vide'})"


def compose(*funcs: Callable) -> Callable:
    """compose(f, g, h)(x) == f(g(h(x)))  (de droite à gauche, comme en maths)."""

    def composed(value):
        for f in reversed(funcs):
            value = f(value)
        return value

    return composed


def pipe(value: Any, *funcs: Callable) -> Any:
    """pipe(x, f, g, h) == h(g(f(x)))  (de gauche à droite)."""
    for f in funcs:
        value = f(value)
    return value
