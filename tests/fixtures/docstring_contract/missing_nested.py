"""Provide invalid nested source for documentation-contract parser tests."""


def outer(value: str):
    """Perform an undocumented procedure.

    Args:
        value: Value passed to the nested helper.
    """
    def inner() -> None:
        pass

    inner()
    del value
