"""Provide invalid generator source for documentation-contract parser tests."""


def sample():
    """Yield a value without documenting the yield contract."""
    yield "sample"
