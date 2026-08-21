"""Project-wide logging setup.

A tiny wrapper so every module gets consistently formatted logs without each one
re-configuring the root logger. Call :func:`configure_logging` once at process
start (entrypoints / scripts), then use ``logging.getLogger(__name__)`` normally.
"""

from __future__ import annotations

import logging

from app.config.settings import settings

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once. Repeat calls are no-ops.

    Args:
        level: Optional level name (e.g. ``"DEBUG"``). Falls back to the
            configured ``LOG_LEVEL`` from settings.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, (level or settings.log_level), logging.INFO),
        format=_FORMAT,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, ensuring logging is configured first."""
    configure_logging()
    return logging.getLogger(name)
