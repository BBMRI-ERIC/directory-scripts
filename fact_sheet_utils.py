# vim:ts=4:sw=4:tw=0:sts=4:et

"""Helpers for analysing collection fact sheets and aggregate rows."""

from typing import Any

from oomutils import count_matches_oom, get_oom_interval


FACT_DIMENSION_KEYS = ("sex", "age_range", "sample_type", "disease")
NO_STAR_FACT_SUMS_WARNING = (
    "No-star fact-sheet fallback is enabled. Derived marginal sums may "
    "double-count overlapping records or undercount omitted rows and violate "
    "fact-sheet aggregation assumptions."
)


def _is_numeric_count(value: Any) -> bool:
    """Return whether a value is an integer count rather than a boolean."""
    return isinstance(value, int) and not isinstance(value, bool)


def normalize_fact_dimension_value(value: Any) -> Any:
    """Return a comparable scalar value for a fact-sheet dimension cell."""
    if isinstance(value, dict):
        if "id" in value:
            return value["id"]
        if "name" in value:
            return value["name"]
    return value


def count_star_dimensions(fact: dict[str, Any], dimension_keys=FACT_DIMENSION_KEYS) -> int:
    """Count how many dimensions of a fact row are aggregated as ``*``."""
    return sum(
        1
        for key in dimension_keys
        if normalize_fact_dimension_value(fact.get(key)) == "*"
    )


def has_fact_sheet(collection: dict[str, Any]) -> bool:
    """Return whether a collection advertises at least one fact-sheet row."""
    return bool(collection.get("facts"))


def get_all_star_rows(
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> list[dict[str, Any]]:
    """Return rows where all tracked dimensions are aggregated as ``*``."""
    return [
        fact
        for fact in facts
        if all(
            normalize_fact_dimension_value(fact.get(key)) == "*"
            for key in dimension_keys
        )
    ]


def get_all_but_one_star_rows(
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> list[dict[str, Any]]:
    """Return rows with one concrete dimension and stars in all others."""
    rows = []
    for fact in facts:
        values = {
            key: normalize_fact_dimension_value(fact.get(key))
            for key in dimension_keys
        }
        concrete_keys = [
            key for key, value in values.items() if value not in (None, "", "*")
        ]
        if len(concrete_keys) != 1:
            continue
        concrete_key = concrete_keys[0]
        if all(key == concrete_key or value == "*" for key, value in values.items()):
            rows.append(fact)
    return rows


def get_no_star_rows(
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> list[dict[str, Any]]:
    """Return fully concrete rows with no missing or aggregate dimensions."""
    return [
        fact
        for fact in facts
        if all(
            normalize_fact_dimension_value(fact.get(key)) not in (None, "", "*")
            for key in dimension_keys
        )
    ]


def get_dimension_values(
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> dict[str, list[Any]]:
    """Collect normalized non-star values present for each fact dimension."""
    values: dict[str, set[Any]] = {key: set() for key in dimension_keys}
    for fact in facts:
        for key in dimension_keys:
            value = normalize_fact_dimension_value(fact.get(key))
            if value not in (None, "", "*"):
                values[key].add(value)
    return {key: sorted(values[key]) for key in dimension_keys}


def get_matching_one_star_rows(
    facts: list[dict[str, Any]],
    dimension_key: str,
    expected_value: Any,
    dimension_keys=FACT_DIMENSION_KEYS,
) -> list[dict[str, Any]]:
    """Return all rows aggregated on every dimension except one expected value."""
    normalized_expected = normalize_fact_dimension_value(expected_value)
    rows = []
    for fact in facts:
        normalized_value = normalize_fact_dimension_value(fact.get(dimension_key))
        if normalized_value != normalized_expected:
            continue
        if count_star_dimensions(fact, dimension_keys) != len(dimension_keys) - 1:
            continue
        if all(
            key == dimension_key
            or normalize_fact_dimension_value(fact.get(key)) == "*"
            for key in dimension_keys
        ):
            rows.append(fact)
    return rows


def _fact_dimension_and_value(
    fact: dict[str, Any],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> tuple[str, Any]:
    """Return the concrete dimension and value from an all-but-one-star row."""
    concrete = [
        (key, normalize_fact_dimension_value(fact.get(key)))
        for key in dimension_keys
        if normalize_fact_dimension_value(fact.get(key)) not in (None, "", "*")
    ]
    if len(concrete) != 1:
        raise ValueError(f"Expected one concrete fact dimension, found {len(concrete)}.")
    return concrete[0]


def _append_oom_warning(
    warnings: list[dict[str, Any]],
    *,
    count: Any,
    oom_value: Any,
    count_name: str,
    oom_name: str,
) -> None:
    """Append an OoM consistency warning without failing on malformed metadata."""
    if not _is_numeric_count(count) or oom_value in (None, ""):
        return
    try:
        lower, upper = get_oom_interval(oom_value)
        matches = count_matches_oom(count, oom_value)
    except (TypeError, ValueError):
        warnings.append(
            {
                "code": f"invalid_{oom_name}",
                "message": f"Collection {oom_name} value {oom_value!r} is invalid.",
                "actual": oom_value,
                "expected": "non-negative integer order of magnitude",
            }
        )
        return
    if not matches:
        warnings.append(
            {
                "code": f"all_star_{count_name}_oom_mismatch",
                "message": (
                    f"All-star aggregate {count_name} ({count}) is outside the "
                    f"collection {oom_name} interval [{lower}, {upper})."
                ),
                "actual": count,
                "expected": f"[{lower}, {upper})",
            }
        )


def analyze_collection_fact_sheet(
    collection: dict[str, Any],
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> dict[str, Any]:
    """Summarize aggregate-row consistency for one collection fact sheet."""
    all_star_rows = get_all_star_rows(facts, dimension_keys)
    all_star_row = all_star_rows[0] if len(all_star_rows) == 1 else None
    all_star_samples = None if all_star_row is None else all_star_row.get("number_of_samples")
    all_star_donors = None if all_star_row is None else all_star_row.get("number_of_donors")
    all_but_one_rows = get_all_but_one_star_rows(facts, dimension_keys)
    collection_size = collection.get("size")
    collection_donors = collection.get("number_of_donors")

    warnings = []
    if facts and len(all_star_rows) != 1:
        warnings.append(
            {
                "code": "missing_all_star" if not all_star_rows else "multiple_all_star",
                "message": (
                    f"Expected exactly one all-star aggregate row, found {len(all_star_rows)}."
                ),
                "actual": len(all_star_rows),
                "expected": 1,
            }
        )
    if _is_numeric_count(collection_size) and _is_numeric_count(all_star_samples):
        if collection_size != all_star_samples:
            warnings.append(
                {
                    "code": "all_star_samples_mismatch",
                    "message": (
                        "All-star aggregate number_of_samples does not match "
                        f"collection size ({all_star_samples} != {collection_size})."
                    ),
                    "actual": all_star_samples,
                    "expected": collection_size,
                }
            )
    if _is_numeric_count(collection_donors) and _is_numeric_count(all_star_donors):
        if collection_donors != all_star_donors:
            warnings.append(
                {
                    "code": "all_star_donors_mismatch",
                    "message": (
                        "All-star aggregate number_of_donors does not match "
                        f"collection number_of_donors ({all_star_donors} != {collection_donors})."
                    ),
                    "actual": all_star_donors,
                    "expected": collection_donors,
                }
            )

    _append_oom_warning(
        warnings,
        count=all_star_samples,
        oom_value=collection.get("order_of_magnitude"),
        count_name="samples",
        oom_name="order_of_magnitude",
    )
    _append_oom_warning(
        warnings,
        count=all_star_donors,
        oom_value=collection.get("order_of_magnitude_donors"),
        count_name="donors",
        oom_name="order_of_magnitude_donors",
    )

    dimension_values = get_dimension_values(facts, dimension_keys)
    missing_all_but_one_values = []
    duplicate_all_but_one_values = []
    if facts and not all_but_one_rows:
        warnings.append(
            {
                "code": "missing_all_but_one",
                "message": "Fact sheet has no all-but-one-star aggregate rows.",
                "actual": 0,
                "expected": "at least one row and one row per represented dimension value",
            }
        )
    for dimension in dimension_keys:
        for value in dimension_values[dimension]:
            rows = get_matching_one_star_rows(facts, dimension, value, dimension_keys)
            if not rows:
                missing = {"dimension": dimension, "value": value, "rows": 0}
                missing_all_but_one_values.append(missing)
                warnings.append(
                    {
                        "code": "missing_all_but_one_value",
                        "message": (
                            f"Missing all-but-one-star aggregate for {dimension} value {value}."
                        ),
                        "actual": 0,
                        "expected": 1,
                        **missing,
                    }
                )
            elif len(rows) > 1:
                duplicate = {
                    "dimension": dimension,
                    "value": value,
                    "rows": len(rows),
                }
                duplicate_all_but_one_values.append(duplicate)
                warnings.append(
                    {
                        "code": "multiple_all_but_one_value",
                        "message": (
                            f"Expected one all-but-one-star aggregate for {dimension} "
                            f"value {value}, found {len(rows)}."
                        ),
                        "actual": len(rows),
                        "expected": 1,
                        **duplicate,
                    }
                )

    if all_star_row is not None:
        for row in all_but_one_rows:
            dimension, value = _fact_dimension_and_value(row, dimension_keys)
            for field, all_star_value, code_suffix in (
                ("number_of_samples", all_star_samples, "samples"),
                ("number_of_donors", all_star_donors, "donors"),
            ):
                row_value = row.get(field)
                if (
                    _is_numeric_count(row_value)
                    and _is_numeric_count(all_star_value)
                    and row_value > all_star_value
                ):
                    warnings.append(
                        {
                            "code": f"all_but_one_{code_suffix}_above_all_star",
                            "message": (
                                f"All-but-one-star {field} for {dimension} value {value} "
                                f"({row_value}) exceeds the all-star aggregate ({all_star_value})."
                            ),
                            "actual": row_value,
                            "expected": f"<= {all_star_value}",
                            "dimension": dimension,
                            "value": value,
                            "fact_id": row.get("id", ""),
                        }
                    )

    donors_present = any(
        _is_numeric_count(fact.get("number_of_donors"))
        and fact["number_of_donors"] > 0
        for fact in facts
    )

    return {
        "fact_rows": len(facts),
        "all_star_rows": len(all_star_rows),
        "all_star_row": all_star_row,
        "all_star_number_of_samples": all_star_samples,
        "all_star_number_of_donors": all_star_donors,
        "all_but_one_rows": len(all_but_one_rows),
        "all_but_one_complete": bool(all_but_one_rows)
        and not missing_all_but_one_values
        and not duplicate_all_but_one_values,
        "missing_all_but_one_values": missing_all_but_one_values,
        "duplicate_all_but_one_values": duplicate_all_but_one_values,
        "collection_size": collection_size,
        "collection_number_of_donors": collection_donors,
        "warnings": warnings,
        "donors_present": donors_present,
    }
