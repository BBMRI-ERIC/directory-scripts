"""Provide invalid dataclass source for documentation-contract parser tests."""

from dataclasses import dataclass


@dataclass
class Record:
    """Represent a record with undocumented generated fields."""

    name: str
