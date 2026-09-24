#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Compatibility wrapper for write-capable Molgenis EMX2 sessions."""

from __future__ import annotations

from molgenis_emx2_pyclient import Client


class DirectorySession(Client):
    """Adapt the EMX2 client to the context-manager contract used by local CLIs."""

    def __enter__(self) -> "DirectorySession":
        """Enter the underlying client context and return this compatibility session.

        Returns:
            This `DirectorySession` after the parent context manager has entered.
        """
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Delegate context cleanup to the parent and never suppress exceptions.

        Args:
            exc_type: Exception class raised in the context, or `None` on success.
            exc: Exception instance raised in the context, or `None` on success.
            tb: Traceback associated with `exc`, or `None` on success.

        Returns:
            Always `False`, so Python propagates an exception from the context.
        """
        super().__exit__(exc_type, exc, tb)
        return False
