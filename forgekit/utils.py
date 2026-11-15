"""Petits utilitaires génériques : listes, dictionnaires, fichiers."""
from __future__ import annotations

import copy
import itertools
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

__all__ = [
    "chunked",
    "flatten",
    "deep_merge",
    "dotted_get",
    "dotted_set",
    "group_by",
    "unique",
    "first",
    "clamp",
    "atomic_write",
    "read_json",
    "write_json",
]

_MISSING = object()


def chunked(iterable: Iterable, size: int) -> Iterator[List]:
    """Découpe un itérable en blocs de `size` éléments (le dernier peut être plus court)."""
    if size < 1:
        raise ValueError("size doit être >= 1")
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            return
        yield chunk


def _is_nested(item: Any) -> bool:
    return isinstance(item, Iterable) and not isinstance(item, (str, bytes, bytearray, Mapping))


def flatten(nested: Iterable, depth: Optional[int] = None) -> Iterator:
    """Aplatit des listes imbriquées. `depth=None` aplatit complètement."""
    for item in nested:
        if _is_nested(item) and (depth is None or depth > 0):
            yield from flatten(item, None if depth is None else depth - 1)
        else:
            yield item


def deep_merge(base: Mapping, override: Mapping) -> Dict:
    """Fusion récursive de deux dictionnaires ; renvoie un nouveau dict (aucun argument modifié)."""
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def dotted_get(data: Any, path: str, default: Any = None, sep: str = ".") -> Any:
    """Lit `a.b.0.c` dans des dicts/listes imbriqués ; renvoie `default` si absent."""
    current = data
    for part in path.split(sep) if path else []:
        if isinstance(current, Mapping):
            if part in current:
                current = current[part]
            else:
                return default
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return current


def dotted_set(data: Dict, path: str, value: Any, sep: str = ".") -> Dict:
    """Écrit une valeur à `a.b.c`, en créant les dicts intermédiaires. Modifie et renvoie `data`."""
    parts = path.split(sep)
    current = data
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value
    return data


def group_by(iterable: Iterable, key: Callable[[Any], Any]) -> Dict[Any, List]:
    """Regroupe les éléments par clé : `group_by(mots, len)` -> {3: [...], 4: [...]}."""
    groups: Dict[Any, List] = {}
    for item in iterable:
        groups.setdefault(key(item), []).append(item)
    return groups


def unique(iterable: Iterable, key: Optional[Callable[[Any], Any]] = None) -> Iterator:
    """Supprime les doublons en conservant l'ordre (fonctionne aussi avec des éléments non hashables)."""
    seen_hashable = set()
    seen_other: List = []
    for item in iterable:
        marker = key(item) if key else item
        try:
            if marker in seen_hashable:
                continue
            seen_hashable.add(marker)
        except TypeError:
            if marker in seen_other:
                continue
            seen_other.append(marker)
        yield item


def first(iterable: Iterable, default: Any = None, pred: Optional[Callable[[Any], bool]] = None) -> Any:
    """Premier élément (ou premier qui satisfait `pred`), sinon `default`."""
    for item in iterable:
        if pred is None or pred(item):
            return item
    return default


def clamp(value, low, high):
    """Borne `value` dans l'intervalle [low, high]."""
    if low > high:
        raise ValueError("low doit être <= high")
    return max(low, min(high, value))


def atomic_write(path, data, *, binary: bool = False, encoding: str = "utf-8") -> Path:
    """Écrit un fichier de façon atomique (pas de fichier à moitié écrit en cas de crash)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if binary else "w"
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode,
            dir=target.parent,
            delete=False,
            encoding=None if binary else encoding,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return target


def read_json(path, default: Any = _MISSING) -> Any:
    """Lit un fichier JSON. Si `default` est fourni, il est renvoyé quand le fichier n'existe pas."""
    p = Path(path)
    if not p.exists():
        if default is _MISSING:
            raise FileNotFoundError(str(p))
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj: Any, *, indent: int = 2) -> Path:
    """Écrit un objet en JSON (UTF-8, accents conservés) de façon atomique."""
    return atomic_write(path, json.dumps(obj, indent=indent, ensure_ascii=False) + "\n")
