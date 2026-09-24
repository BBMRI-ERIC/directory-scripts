"""Helpers for consistent Ctrl+C handling in CLI entry points."""

from __future__ import annotations

import logging


def log_keyboard_interrupt(tool_name: str, *, action: str = "operation") -> None:
    """Log a concise user-facing Ctrl+C interruption message.

    Args:
        tool_name: CLI name included in the warning so interrupted work is
            identifiable in shared logs.
        action: Human-readable operation interrupted by the user.

    Returns:
        None. Emits one warning through the process logging configuration.
    """
    logging.warning("%s interrupted by Ctrl+C during %s.", tool_name, action)
