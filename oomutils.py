# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared order-of-magnitude estimation policy for aggregate counts."""

import logging as log
import os
from typing import Any


ENV_OOM_UPPER_BOUND_COEFFICIENT = "DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT"
DEFAULT_OOM_UPPER_BOUND_COEFFICIENT = 0.1


def normalize_oom_value(value: Any) -> int | None:
    """Normalize a scalar or EMX-style order-of-magnitude value to an integer.

    Args:
        value: Raw numeric/text value, mapping with ``id`` or ``name``, or blank
            value from Directory data.

    Returns:
        Parsed integer, or ``None`` for blank/missing input.

    Raises:
        ValueError: If a present value cannot be converted to an integer.
    """
    if isinstance(value, dict):
        if "id" in value:
            value = value["id"]
        elif "name" in value:
            value = value["name"]
    if value in (None, ""):
        return None
    return int(value)


def get_oom_interval(value: Any) -> tuple[int, int]:
    """Return the inclusive/exclusive count interval represented by an OoM value.

    Args:
        value: Raw order-of-magnitude representation accepted by
            ``normalize_oom_value``.

    Returns:
        ``(10**n, 10**(n + 1))`` for the normalized non-negative magnitude.

    Raises:
        ValueError: If the value is missing or negative.
    """
    oom = normalize_oom_value(value)
    if oom is None:
        raise ValueError("OoM value is missing.")
    if oom < 0:
        raise ValueError(f"OoM value must be non-negative, got {oom!r}.")
    return 10**oom, 10 ** (oom + 1)


def count_matches_oom(count: Any, oom_value: Any) -> bool:
    """Test whether an integer count is inside an order-of-magnitude interval.

    Args:
        count: Candidate count; booleans and non-integers never match.
        oom_value: Raw OoM representation defining the accepted interval.

    Returns:
        ``True`` only when ``count`` is an integer in the represented interval.

    Raises:
        ValueError: If ``oom_value`` is missing or invalid.
    """
    if not isinstance(count, int) or isinstance(count, bool):
        return False
    lower, upper = get_oom_interval(oom_value)
    return lower <= count < upper


def get_oom_upper_bound_coefficient() -> float:
    """Read and validate the configured multiplier for OoM count estimates.

    Returns:
        Positive coefficient from ``DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT`` or
        the repository default when the environment variable is unset.

    Raises:
        ValueError: If the configured value is non-numeric or not positive.
    """
    raw_value = os.getenv(
        ENV_OOM_UPPER_BOUND_COEFFICIENT,
        str(DEFAULT_OOM_UPPER_BOUND_COEFFICIENT),
    )
    coefficient = float(raw_value)
    if coefficient <= 0:
        raise ValueError(
            f"{ENV_OOM_UPPER_BOUND_COEFFICIENT} must be > 0, got {coefficient!r}."
        )
    return coefficient


def estimate_count_from_oom(value: Any) -> int:
    """Estimate count from OoM using the globally configured policy.

    The estimate is:
    ``coefficient * 10 ** (oom + 1)``

    With the default coefficient ``0.1`` this is equal to the lower bound
    ``10 ** oom``. Setting the coefficient to ``0.3`` yields the historical
    midpoint-ish estimate ``0.3 * 10 ** (oom + 1)``.

    Args:
        value: Raw order-of-magnitude representation to estimate.

    Returns:
        Integer truncation of the configured coefficient times the OoM upper
        bound.

    Raises:
        ValueError: If the magnitude or configured coefficient is invalid.
    """
    oom = normalize_oom_value(value)
    if oom is None:
        raise ValueError("OoM value is missing.")
    coefficient = get_oom_upper_bound_coefficient()
    return int(coefficient * (10 ** (oom + 1)))


def estimate_count_from_oom_or_none(
    value: Any,
    *,
    collection_id: str = "",
    field_name: str = "order_of_magnitude",
) -> int | None:
    """Return an OoM estimate, logging malformed source values instead of failing.

    Args:
        value: Raw order-of-magnitude representation to estimate.
        collection_id: Collection identifier included in any warning message.
        field_name: Source field name included in any warning message.

    Returns:
        Estimated integer, or ``None`` for absent or malformed values.
    """
    try:
        oom = normalize_oom_value(value)
    except (TypeError, ValueError):
        log.warning(
            "Collection %s has invalid %s value %r; ignoring it for estimates.",
            collection_id,
            field_name,
            value,
        )
        return None
    if oom is None:
        return None
    return estimate_count_from_oom(oom)


def describe_oom_estimate_policy() -> str:
    """Describe the active order-of-magnitude estimate policy for reports.

    Returns:
        Human-readable text reflecting the current environment-derived
        coefficient.

    Raises:
        ValueError: If the configured coefficient is invalid.
    """
    coefficient = get_oom_upper_bound_coefficient()
    if coefficient == 0.1:
        return "lower bound of the OoM interval (10**n)"
    return f"{coefficient:g} * 10**(n+1)"
