# vim:ts=4:sw=4:tw=0:sts=4:et

"""Helpers for analysing collection fact sheets and aggregate rows."""

from typing import Any


FACT_DIMENSION_KEYS = ("sex", "age_range", "sample_type", "disease")


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


def get_dimension_values(
    facts: list[dict[str, Any]],
    dimension_keys=FACT_DIMENSION_KEYS,
) -> dict[str, list[Any]]:
    """Collect normalized non-star values present for each fact dimension."""
    values: dict[str, set[Any]] = {key: set() for key in dimension_keys}
    for fact in facts:
        for key in dimension_keys:
            value = normalize_fact_dimension_value(fact.get(key))
            if value not in (None, "*"):
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
    if isinstance(collection_size, int) and isinstance(all_star_samples, int):
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
    if isinstance(collection_donors, int) and isinstance(all_star_donors, int):
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

    donors_present = any(
        isinstance(fact.get("number_of_donors"), int) and fact["number_of_donors"] > 0
        for fact in facts
    )

    return {
        "fact_rows": len(facts),
        "all_star_rows": len(all_star_rows),
        "all_star_row": all_star_row,
        "all_star_number_of_samples": all_star_samples,
        "all_star_number_of_donors": all_star_donors,
        "collection_size": collection_size,
        "collection_number_of_donors": collection_donors,
        "warnings": warnings,
        "donors_present": donors_present,
    }
