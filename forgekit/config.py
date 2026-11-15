"""Configuration : JSON/TOML, variables d'environnement, fichiers .env, accès par chemin pointé."""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from .utils import deep_merge, dotted_get, dotted_set

__all__ = ["Config", "auto_cast"]

_MISSING = object()
_TRUE = {"1", "true", "yes", "on", "oui"}
_FALSE = {"0", "false", "no", "off", "non", ""}


def auto_cast(value: str) -> Any:
    """'true' -> True, '42' -> 42, '3.5' -> 3.5, le reste reste une chaîne."""
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", lowered):
        return int(lowered)
    if re.fullmatch(r"-?\d+\.\d+", lowered):
        return float(lowered)
    return value


def _cast(value: Any, cast: Callable) -> Any:
    if cast is bool and isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ValueError(f"Valeur booléenne invalide : {value!r}")
    return cast(value)


class Config:
    """Configuration hiérarchique avec accès `cfg.get("db.host")` ou `cfg.db.host`.

        cfg = Config.from_file("config.toml").merge(Config.from_env("MYAPP"))
        port = cfg.get("server.port", 8000, cast=int)
        token = cfg.require("api.token")
    """

    def __init__(self, data: Optional[Mapping] = None):
        self._data: Dict[str, Any] = copy.deepcopy(dict(data)) if data else {}

    # --- constructeurs -----------------------------------------------------
    @classmethod
    def from_file(cls, path) -> "Config":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        suffix = p.suffix.lower()
        if suffix == ".json":
            return cls(json.loads(text))
        if suffix == ".toml":
            try:
                import tomllib
            except ModuleNotFoundError as exc:  # Python < 3.11
                raise RuntimeError("TOML nécessite Python 3.11+") from exc
            return cls(tomllib.loads(text))
        raise ValueError(f"Format non supporté : {suffix!r} (json ou toml)")

    @classmethod
    def from_env(cls, prefix: str = "", sep: str = "__", environ: Optional[Mapping[str, str]] = None) -> "Config":
        """Lit les variables `PREFIX_A__B=1` -> {"a": {"b": 1}} (clés en minuscules, valeurs typées)."""
        environ = os.environ if environ is None else environ
        full_prefix = prefix.upper()
        if full_prefix and not full_prefix.endswith("_"):
            full_prefix += "_"
        data: Dict[str, Any] = {}
        for name, raw in environ.items():
            if full_prefix and not name.startswith(full_prefix):
                continue
            key = name[len(full_prefix):].lower()
            if key:
                dotted_set(data, key, auto_cast(raw), sep=sep.lower())
        return cls(data)

    @classmethod
    def from_dotenv(cls, path, sep: str = "__") -> "Config":
        """Lit un fichier .env (KEY=value, commentaires #, guillemets). Clés en minuscules."""
        data: Dict[str, Any] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
                parsed: Any = value
            else:
                value = value.split(" #", 1)[0].strip()
                parsed = auto_cast(value)
            dotted_set(data, key.strip().lower(), parsed, sep=sep.lower())
        return cls(data)

    # --- accès -------------------------------------------------------------
    def get(self, path: str, default: Any = None, cast: Optional[Callable] = None) -> Any:
        value = dotted_get(self._data, path, _MISSING)
        if value is _MISSING:
            return default
        return _cast(value, cast) if cast else value

    def require(self, path: str, cast: Optional[Callable] = None) -> Any:
        value = self.get(path, _MISSING, cast)
        if value is _MISSING:
            raise KeyError(f"Configuration manquante : {path}")
        return value

    def set(self, path: str, value: Any) -> "Config":
        dotted_set(self._data, path, value)
        return self

    def merge(self, other) -> "Config":
        """Renvoie une nouvelle Config : les valeurs de `other` écrasent les nôtres."""
        other_data = other.to_dict() if isinstance(other, Config) else dict(other)
        return Config(deep_merge(self._data, other_data))

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)

    # --- confort -----------------------------------------------------------
    def __getitem__(self, path: str) -> Any:
        return self.require(path)

    def __contains__(self, path: str) -> bool:
        return dotted_get(self._data, path, _MISSING) is not _MISSING

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            value = self._data[name]
            return Config(value) if isinstance(value, dict) else value
        raise AttributeError(f"Pas de clé de configuration {name!r}")

    def __repr__(self) -> str:
        return f"Config({self._data!r})"
