"""Outils de texte : accents, slugs, casse, durées et tailles lisibles (en français)."""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

__all__ = [
    "strip_accents",
    "slugify",
    "truncate",
    "normalize_whitespace",
    "snake_case",
    "camel_case",
    "pascal_case",
    "kebab_case",
    "human_size",
    "human_duration",
]


def strip_accents(text: str) -> str:
    """'Élève à Paris' -> 'Eleve a Paris'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def slugify(text: str, sep: str = "-", max_length: Optional[int] = None) -> str:
    """'Réseaux & Télécoms 2026' -> 'reseaux-telecoms-2026'."""
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text).strip(sep)
    if max_length is not None:
        text = text[:max_length].rstrip(sep)
    return text


def truncate(text: str, width: int, suffix: str = "…", whole_words: bool = False) -> str:
    """Coupe un texte à `width` caractères (suffixe compris), sans couper un mot si demandé."""
    if width < len(suffix):
        raise ValueError("width doit être >= len(suffix)")
    if len(text) <= width:
        return text
    keep = width - len(suffix)
    cut = text[:keep]
    if whole_words and keep < len(text) and not text[keep].isspace() and any(c.isspace() for c in cut):
        cut = cut.rsplit(None, 1)[0]
    return cut.rstrip() + suffix


def normalize_whitespace(text: str) -> str:
    """Remplace toute suite d'espaces/retours à la ligne par une seule espace."""
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> List[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return [w for w in re.split(r"[^0-9A-Za-zÀ-ÿ]+", text) if w]


def snake_case(text: str) -> str:
    """'HTTPServerError' -> 'http_server_error'."""
    return "_".join(w.lower() for w in _words(text))


def kebab_case(text: str) -> str:
    """'maVariable' -> 'ma-variable'."""
    return "-".join(w.lower() for w in _words(text))


def camel_case(text: str) -> str:
    """'ma_variable' -> 'maVariable'."""
    words = [w.lower() for w in _words(text)]
    return (words[0] + "".join(w.capitalize() for w in words[1:])) if words else ""


def pascal_case(text: str) -> str:
    """'ma_variable' -> 'MaVariable'."""
    return "".join(w.lower().capitalize() for w in _words(text))


def human_size(num_bytes: float) -> str:
    """1536 -> '1.5 Ko' (unités françaises : o, Ko, Mo, Go...)."""
    units = ["o", "Ko", "Mo", "Go", "To", "Po"]
    value = float(num_bytes)
    i = 0
    while abs(value) >= 1024 and i < len(units) - 1:
        value /= 1024
        i += 1
    if i == 0:
        return f"{int(value)} o"
    return f"{value:.1f} {units[i]}"


def human_duration(seconds: float) -> str:
    """0.25 -> '250 ms', 42.5 -> '42.5 s', 3723 -> '1 h 2 min 3 s'."""
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    if seconds < 1:
        return f"{sign}{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{sign}{seconds:.1f} s"
    total = int(round(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} j")
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if secs:
        parts.append(f"{secs} s")
    return sign + (" ".join(parts) or "0 s")
