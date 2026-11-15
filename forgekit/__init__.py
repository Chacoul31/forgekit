"""forgekit — une boîte à outils Python sans dépendance externe.

Retry, cache, limiteur de débit, chronomètre, configuration, pipelines, parallélisme,
événements, validation, texte, logs et utilitaires, prêts à l'emploi.
"""
from .cache import CacheInfo, DiskCache, ttl_cache
from .config import Config, auto_cast
from .events import EventBus
from .logs import get_logger
from .parallel import async_map, gather_limit, pmap
from .pipeline import Pipeline, PipelineError, compose, pipe
from .ratelimit import RateLimiter
from .retry import retry
from .text import (
    camel_case,
    human_duration,
    human_size,
    kebab_case,
    normalize_whitespace,
    pascal_case,
    slugify,
    snake_case,
    strip_accents,
    truncate,
)
from .timing import Timer, timed
from .utils import (
    atomic_write,
    chunked,
    clamp,
    deep_merge,
    dotted_get,
    dotted_set,
    first,
    flatten,
    group_by,
    read_json,
    unique,
    write_json,
)
from .validate import Field, Schema, ValidationError

__version__ = "1.0.0"

__all__ = [
    "retry",
    "ttl_cache", "DiskCache", "CacheInfo",
    "RateLimiter",
    "Timer", "timed",
    "Config", "auto_cast",
    "Pipeline", "PipelineError", "compose", "pipe",
    "pmap", "gather_limit", "async_map",
    "EventBus",
    "Field", "Schema", "ValidationError",
    "get_logger",
    "strip_accents", "slugify", "truncate", "normalize_whitespace",
    "snake_case", "camel_case", "pascal_case", "kebab_case",
    "human_size", "human_duration",
    "chunked", "flatten", "deep_merge", "dotted_get", "dotted_set",
    "group_by", "unique", "first", "clamp",
    "atomic_write", "read_json", "write_json",
]
