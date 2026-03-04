"""Helpers for non-fatal validation warnings and Pydantic error formatting."""

from __future__ import annotations

import logging
from typing import Callable

from pydantic import ValidationError


ValidationWarnFn = Callable[[str], None]


def build_validation_warning_handler(
    *,
    enabled: bool,
    logger: logging.Logger | None = None,
) -> ValidationWarnFn:
    """Return a warning emitter for non-fatal validation issues."""
    target_logger = logger or logging.getLogger(__name__)

    def warn(message: str) -> None:
        if enabled:
            target_logger.warning("Validation warning: %s", message)

    return warn


def warn_from_validation_error(
    context: str,
    exc: ValidationError,
    warn: ValidationWarnFn | None,
) -> None:
    """Emit one warning line per Pydantic validation error."""
    if warn is None:
        return
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "invalid value")
        if location:
            warn(f"{context}: {location}: {message}")
        else:
            warn(f"{context}: {message}")


def format_validation_error(context: str, exc: ValidationError) -> str:
    """Return a user-facing one-line validation summary for fatal tool input errors."""
    parts = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "invalid value")
        if location:
            parts.append(f"{location}: {message}")
        else:
            parts.append(message)
    if not parts:
        return context
    return f"{context}: " + "; ".join(parts)
