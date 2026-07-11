"""Helpers for consistent Ctrl+C handling in CLI entry points."""

from __future__ import annotations

import logging


def log_keyboard_interrupt(tool_name: str, *, action: str = "operation") -> None:
    """Log a concise user-facing Ctrl+C interruption message."""
    logging.warning("%s interrupted by Ctrl+C during %s.", tool_name, action)
