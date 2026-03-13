#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Compatibility wrapper for write-capable Molgenis EMX2 sessions."""

from __future__ import annotations

from molgenis_emx2_pyclient import Client


class DirectorySession(Client):
    """Provide the legacy context-manager shape used by repository CLIs.

    The current `molgenis_emx2_pyclient` exposes `Client`, while older code in this
    repository used `DirectorySession`. The write-capable tools only need a client
    that can be used in a `with` block and signs out on exit, so this wrapper keeps
    that surface stable without depending on the removed legacy package layout.
    """

    def __enter__(self) -> "DirectorySession":
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        super().__exit__(exc_type, exc, tb)
        return False
