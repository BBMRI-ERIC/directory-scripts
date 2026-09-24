"""Helpers for non-fatal validation warnings and validation error formatting."""

from __future__ import annotations

import logging
from typing import Callable

from validation_models import ValidationError


ValidationWarnFn = Callable[[str], None]


def build_validation_warning_handler(
    *,
    enabled: bool,
    logger: logging.Logger | None = None,
) -> ValidationWarnFn:
    """Return a warning emitter for non-fatal validation issues.

    Args:
        enabled: Whether the returned callback should log received messages.
        logger: Logger to receive warnings, or `None` to use this module's logger.

    Returns:
        Closure accepting one message. It has no effect while `enabled` is false.
    """
    target_logger = logger or logging.getLogger(__name__)

    def warn(message: str) -> None:
        """Log one non-fatal validation message when this handler is enabled.

        Args:
            message: Human-readable validation detail to prefix and send at WARNING.

        Returns:
            None.
        """
        if enabled:
            target_logger.warning("Validation warning: %s", message)

    return warn


def warn_from_validation_error(
    context: str,
    exc: ValidationError,
    warn: ValidationWarnFn | None,
) -> None:
    """Emit one warning line per structured validation error.

    Args:
        context: File, option, or other caller context prefixed to every message.
        exc: Structured validation exception whose copied error records are formatted.
        warn: Optional message callback. A `None` callback suppresses all output.

    Returns:
        None. Invokes `warn` once per validation error when supplied.
    """
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
    """Return a user-facing one-line validation summary for fatal tool input errors.

    Args:
        context: Prefix identifying the rejected input or operation.
        exc: Structured validation exception whose location/message records are read.

    Returns:
        One line containing `context` and semicolon-separated error descriptions;
        returns `context` unchanged when the exception contains no records.
    """
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
