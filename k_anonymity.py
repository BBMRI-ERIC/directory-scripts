"""Shared k-anonymity helpers for fact-table checks and table tooling."""

from __future__ import annotations

from typing import Any


def positive_below_k_mask(values, threshold: int):
    """Return a boolean mask for values with 0 < value < threshold.

    The function is intentionally generic so it can be applied to pandas Series
    (vectorized comparison) and keeps one shared semantic definition for
    k-anonymity filters used by checks and table tooling.
    """
    return (values > 0) & (values < threshold)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def donor_value_violates_k(value: Any, k_limit: int) -> bool:
    """Return True when donor count violates the k-anonymity threshold.

    Violation rule is shared across checks and tooling:
    donor count is considered violating only when 0 < donors < k.
    """
    donors = _parse_int(value)
    if donors is None:
        return False
    return 0 < donors < k_limit
