# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared order-of-magnitude estimation policy for aggregate counts."""

import logging as log
import os
from typing import Any


ENV_OOM_UPPER_BOUND_COEFFICIENT = "DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT"
DEFAULT_OOM_UPPER_BOUND_COEFFICIENT = 0.1


def normalize_oom_value(value: Any) -> int | None:
    """Return integer OoM from a raw scalar or EMX-style wrapped value."""
    if isinstance(value, dict):
        if "id" in value:
            value = value["id"]
        elif "name" in value:
            value = value["name"]
    if value in (None, ""):
        return None
    return int(value)


def get_oom_upper_bound_coefficient() -> float:
    """Return the configured coefficient applied to the OoM upper bound."""
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
    """Return estimated count from OoM or None when unavailable/invalid."""
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
    """Return a concise textual description of the active OoM policy."""
    coefficient = get_oom_upper_bound_coefficient()
    if coefficient == 0.1:
        return "lower bound of the OoM interval (10**n)"
    return f"{coefficient:g} * 10**(n+1)"
