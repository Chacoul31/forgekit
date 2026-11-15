"""Validation de données (dicts, JSON...) sans dépendance externe."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, Optional

__all__ = ["Field", "Schema", "ValidationError"]

_MISSING = object()


class ValidationError(Exception):
    """Contient toutes les erreurs trouvées : `.errors` = {"champ": "message"}."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k or 'valeur'}: {v}" for k, v in errors.items()))


class Field:
    """Description d'un champ.

    - `type` : classe attendue (int, str, list...) ou un `Schema` imbriqué
    - `required` / `default` (valeur ou fonction sans argument) / `nullable`
    - `min`, `max` : bornes pour un nombre, ou sur la longueur d'une chaîne/liste
    - `choices`, `pattern` (regex complète), `validator(valeur) -> bool`
    - `coerce=True` : tente de convertir ("42" -> 42)
    - `item` : `Field` appliqué à chaque élément d'une liste
    """

    def __init__(
        self,
        type: Any = None,
        *,
        required: bool = True,
        default: Any = _MISSING,
        nullable: bool = False,
        min: Optional[float] = None,
        max: Optional[float] = None,
        choices: Optional[Iterable] = None,
        pattern: Optional[str] = None,
        validator: Optional[Callable[[Any], bool]] = None,
        coerce: bool = False,
        item: Optional["Field"] = None,
    ):
        self.type = type
        self.required = required
        self.default = default
        self.nullable = nullable
        self.min = min
        self.max = max
        self.choices = list(choices) if choices is not None else None
        self.pattern = re.compile(pattern) if pattern else None
        self.validator = validator
        self.coerce = coerce
        self.item = item

    def clean(self, value: Any) -> Any:
        """Renvoie la valeur validée (éventuellement convertie) ou lève ValueError / ValidationError."""
        if value is None:
            if self.nullable:
                return None
            raise ValueError("ne peut pas être nul")

        t = self.type
        if isinstance(t, Schema):
            return t.validate(value)

        if t is not None:
            value = self._check_type(value, t)

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            size, what = value, "doit être"
        elif hasattr(value, "__len__"):
            size, what = len(value), "doit contenir"
        else:
            size, what = None, ""
        unit = "" if what == "doit être" else " élément(s) ou caractère(s)"
        if size is not None:
            if self.min is not None and size < self.min:
                raise ValueError(f"{what} au moins {self.min}{unit}" if unit else f"doit être >= {self.min}")
            if self.max is not None and size > self.max:
                raise ValueError(f"{what} au plus {self.max}{unit}" if unit else f"doit être <= {self.max}")

        if self.choices is not None and value not in self.choices:
            raise ValueError(f"doit être parmi {self.choices}")
        if self.pattern is not None and not (isinstance(value, str) and self.pattern.fullmatch(value)):
            raise ValueError(f"ne respecte pas le format {self.pattern.pattern!r}")
        if self.item is not None:
            value = self._clean_items(value)
        if self.validator is not None and not self.validator(value):
            raise ValueError("valeur invalide")
        return value

    def _check_type(self, value: Any, t: Any) -> Any:
        is_bool = isinstance(value, bool)
        if t is float and isinstance(value, int) and not is_bool:
            return float(value)
        if isinstance(value, t) and not (is_bool and t in (int, float)):
            return value
        if self.coerce:
            try:
                return t(value)
            except (TypeError, ValueError):
                pass
        raise ValueError(f"doit être de type {getattr(t, '__name__', t)}")

    def _clean_items(self, value: Any) -> list:
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("doit être une liste")
        cleaned = []
        for i, element in enumerate(value):
            try:
                cleaned.append(self.item.clean(element))
            except ValidationError as exc:
                raise ValueError(f"[{i}] {exc}") from exc
            except ValueError as exc:
                raise ValueError(f"[{i}] {exc}") from exc
        return cleaned


class Schema:
    """Ensemble de champs.

        user = Schema({
            "nom":   Field(str, min=2),
            "age":   Field(int, min=0, max=150, coerce=True),
            "email": Field(str, pattern=r"[^@\\s]+@[^@\\s]+\\.\\w+"),
            "roles": Field(list, item=Field(str), default=list),
        })
        propre = user.validate({"nom": "Awa", "age": "21", "email": "awa@ex.ci"})
    """

    def __init__(self, fields: Dict[str, Field], allow_extra: bool = False):
        self.fields = fields
        self.allow_extra = allow_extra

    def validate(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError({"": "doit être un dictionnaire"})
        errors: Dict[str, str] = {}
        out: Dict[str, Any] = {}
        for name, field in self.fields.items():
            if name in data:
                try:
                    out[name] = field.clean(data[name])
                except ValidationError as exc:
                    for sub, message in exc.errors.items():
                        errors[f"{name}.{sub}" if sub else name] = message
                except ValueError as exc:
                    errors[name] = str(exc)
            elif field.default is not _MISSING:
                out[name] = field.default() if callable(field.default) else field.default
            elif field.required:
                errors[name] = "champ requis"
        extras = [k for k in data if k not in self.fields]
        if extras:
            if self.allow_extra:
                out.update({k: data[k] for k in extras})
            else:
                for k in extras:
                    errors[k] = "champ inconnu"
        if errors:
            raise ValidationError(errors)
        return out

    def is_valid(self, data: Any) -> bool:
        try:
            self.validate(data)
            return True
        except ValidationError:
            return False
