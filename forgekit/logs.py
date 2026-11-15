"""Journalisation prête à l'emploi : console colorée, JSON, fichier."""
from __future__ import annotations

import json as _json
import logging
import sys
from typing import Optional, Union

__all__ = ["get_logger", "ColorFormatter", "JsonFormatter"]

_COLORS = {
    logging.DEBUG: "\033[36m",     # cyan
    logging.INFO: "\033[32m",      # vert
    logging.WARNING: "\033[33m",   # jaune
    logging.ERROR: "\033[31m",     # rouge
    logging.CRITICAL: "\033[1;31m",
}
_RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def __init__(self, use_color: bool = True):
        super().__init__("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%H:%M:%S")
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self.use_color:
            return f"{_COLORS.get(record.levelno, '')}{text}{_RESET}"
        return text


class JsonFormatter(logging.Formatter):
    """Une ligne JSON par message (pratique pour grep, jq, ou un agrégateur de logs)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return _json.dumps(payload, ensure_ascii=False)


def get_logger(
    name: str = "forgekit",
    level: Union[int, str] = "INFO",
    *,
    json_output: bool = False,
    color: Optional[bool] = None,
    file: Optional[str] = None,
    stream=None,
) -> logging.Logger:
    """Configure et renvoie un logger. Appelable plusieurs fois sans dupliquer les messages.

        log = get_logger("monapp", "DEBUG", file="app.log")
        log.info("Démarrage")
    """
    logger = logging.getLogger(name)
    logger.setLevel(level.upper() if isinstance(level, str) else level)
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_forgekit", False):
            logger.removeHandler(handler)
            handler.close()

    stream = stream or sys.stderr
    use_color = bool(getattr(stream, "isatty", lambda: False)()) if color is None else color
    console = logging.StreamHandler(stream)
    console.setFormatter(JsonFormatter() if json_output else ColorFormatter(use_color))
    console._forgekit = True  # type: ignore[attr-defined]
    logger.addHandler(console)

    if file:
        file_handler = logging.FileHandler(file, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter() if json_output else ColorFormatter(False))
        file_handler._forgekit = True  # type: ignore[attr-defined]
        logger.addHandler(file_handler)

    return logger
