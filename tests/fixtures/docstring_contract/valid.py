"""Provide valid source for documentation-contract parser tests."""

from dataclasses import dataclass


@dataclass
class Record:
    """Represent one documented data record.

    Attributes:
        name: Stable human-readable record name.
    """

    name: str


class Worker:
    """Transform documented records into display text."""

    def __init__(self, prefix: str) -> None:
        """Initialize a worker with a display prefix.

        Args:
            prefix: Prefix inserted before each formatted record name.
        """
        self.prefix = prefix

    def render(self, record: Record, *, uppercase: bool = False) -> str:
        """Return a formatted record name.

        Args:
            record: Record whose name is formatted.
            uppercase: Whether to convert the name to uppercase before output.

        Returns:
            The formatted record name.
        """
        name = record.name.upper() if uppercase else record.name
        return f"{self.prefix}{name}"


def values(*items: str, **options: bool):
    """Yield configured item strings.

    Args:
        *items: Item strings yielded in the supplied order.
        **options: Boolean options accepted for future formatting.

    Yields:
        Each supplied item string in definition order.
    """
    del options
    yield from items
