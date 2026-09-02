# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared non-additive summaries for Directory collection fact sheets."""

from collections import defaultdict
from typing import Any

import pandas as pd

from fact_sheet_utils import (
    FACT_DIMENSION_KEYS,
    get_dimension_values,
    get_matching_one_star_rows,
    get_no_star_rows,
    normalize_fact_dimension_value,
    NO_STAR_FACT_SUMS_WARNING,
)


COUNT_FIELDS = ("number_of_samples", "number_of_donors")
SUMMARY_COLUMNS = [
    "collections",
    "collections_with_fact_sheets",
    "collections_with_populated_all_star_rows",
    "collections_with_populated_all_but_one_star_rows",
    "collections_with_populated_all_but_one_star_rows_and_single_all_star_total",
    "collections_with_single_all_star_total",
    "populated_all_star_rows",
    "populated_all_but_one_star_rows",
    "all_star_samples_total_for_collections_with_all_star_rows",
    "all_star_donors_total_for_collections_with_all_star_rows",
    "all_star_samples_total_for_collections_with_all_but_one_rows",
    "all_star_donors_total_for_collections_with_all_but_one_rows",
    "allow_no_star_fact_sums",
    "collections_with_no_star_fallback",
    "no_star_fallback_distribution_values",
    "no_star_fallback_contributions",
    "no_star_fallback_source_rows",
    "fact_sheet_summary_warning",
]
ALL_STAR_COLUMNS = [
    "collection_id",
    "collection_name",
    "fact_id",
    "number_of_samples",
    "number_of_donors",
]
ALL_BUT_ONE_VALUE_COLUMNS = [
    "dimension",
    "value_id",
    "value_label",
    "collections_with_value",
    "fact_rows_with_value",
    "collections_with_single_value_row",
    "authoritative_collections",
    "no_star_fallback_collections",
    "no_star_fallback_source_rows",
    "assumption_violating",
    "number_of_samples",
    "number_of_donors",
    "sample_values",
    "donor_values",
]
ALL_BUT_ONE_ROW_COLUMNS = [
    "collection_id",
    "collection_name",
    "fact_id",
    "dimension",
    "value_id",
    "value_label",
    "number_of_samples",
    "number_of_donors",
]


def _unique_collections(collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return collections de-duplicated by id while preserving first occurrence."""
    unique = []
    seen_ids = set()
    for collection in collections:
        collection_id = collection["id"]
        if collection_id in seen_ids:
            continue
        seen_ids.add(collection_id)
        unique.append(collection)
    return unique


def _is_numeric_count(value: Any) -> bool:
    """Return whether a fact count value is numeric enough for reporting."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_populated_fact_row(fact: dict[str, Any]) -> bool:
    """Return whether a fact row has a numeric sample or donor count."""
    return any(_is_numeric_count(fact.get(field)) for field in COUNT_FIELDS)


def _value_id_and_label(value: Any) -> tuple[str, str]:
    """Return stable id and human label for a fact dimension value."""
    if isinstance(value, dict):
        value_id = str(value.get("id") or value.get("name") or value.get("label") or "")
        value_label = str(value.get("label") or value.get("name") or value.get("id") or "")
        return value_id, value_label
    if value is None:
        return "", ""
    value_text = str(value)
    return value_text, value_text


def _row_count_value(fact: dict[str, Any], field: str) -> int | None:
    """Return an integer fact count or None when the field is not populated."""
    value = fact.get(field)
    return value if _is_numeric_count(value) else None


def _build_all_star_row(collection: dict[str, Any], fact: dict[str, Any]) -> dict[str, Any]:
    """Return one populated all-star observation row."""
    return {
        "collection_id": collection["id"],
        "collection_name": collection.get("name", ""),
        "fact_id": fact.get("id", ""),
        "number_of_samples": _row_count_value(fact, "number_of_samples"),
        "number_of_donors": _row_count_value(fact, "number_of_donors"),
    }


def _build_all_but_one_row(
    collection: dict[str, Any],
    fact: dict[str, Any],
    dimension: str,
    value_id: str,
    value_label: str,
    matching_margin_rows: int,
) -> dict[str, Any]:
    """Return one populated all-but-one-star observation row."""
    return {
        "collection_id": collection["id"],
        "collection_name": collection.get("name", ""),
        "fact_id": fact.get("id", ""),
        "dimension": dimension,
        "value_id": value_id,
        "value_label": value_label,
        "number_of_samples": _row_count_value(fact, "number_of_samples"),
        "number_of_donors": _row_count_value(fact, "number_of_donors"),
        "source": "all_but_one_star",
        "source_fact_ids": str(fact.get("id", "")),
        "source_fact_rows": 1,
        "matching_margin_rows": matching_margin_rows,
    }


def _build_no_star_fallback_row(
    collection: dict[str, Any],
    facts: list[dict[str, Any]],
    dimension: str,
    value_id: str,
    value_label: str,
) -> dict[str, Any]:
    """Return one assumption-violating contribution derived from no-star rows."""
    fact_ids = [str(fact.get("id", "")) for fact in facts]
    return {
        "collection_id": collection["id"],
        "collection_name": collection.get("name", ""),
        "fact_id": ",".join(fact_ids),
        "dimension": dimension,
        "value_id": value_id,
        "value_label": value_label,
        "number_of_samples": sum(
            fact["number_of_samples"]
            for fact in facts
            if _is_numeric_count(fact.get("number_of_samples"))
        ),
        "number_of_donors": sum(
            fact["number_of_donors"]
            for fact in facts
            if _is_numeric_count(fact.get("number_of_donors"))
        ),
        "source": "no_star_fallback",
        "source_fact_ids": ";".join(fact_ids),
        "source_fact_rows": len(facts),
    }


def _format_observation_values(rows: list[dict[str, Any]], field: str) -> str:
    """Format row-level count values without summing them."""
    values = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        values.append(f"{row['collection_id']}:{row['fact_id']}={value}")
    return "; ".join(values)


def _sum_one_value_row_per_collection(
    rows: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Sum value rows only across collections with one row for that value."""
    rows_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_collection[row["collection_id"]].append(row)

    collections_with_single_value_row = 0
    sample_total = 0
    donor_total = 0
    for collection_rows in rows_by_collection.values():
        if (
            len(collection_rows) != 1
            or collection_rows[0]["matching_margin_rows"] != 1
        ):
            continue
        collections_with_single_value_row += 1
        row = collection_rows[0]
        if row["number_of_samples"] is not None:
            sample_total += row["number_of_samples"]
        if row["number_of_donors"] is not None:
            donor_total += row["number_of_donors"]
    return collections_with_single_value_row, sample_total, donor_total


def _build_all_but_one_value_rows(
    all_but_one_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group authoritative contributions by distribution value only."""
    grouped_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in all_but_one_rows:
        key = (row["dimension"], row["value_id"], row["value_label"])
        grouped_rows[key].append(row)

    value_rows = []
    keys = sorted(grouped_rows)
    for dimension, value_id, value_label in keys:
        rows = grouped_rows[(dimension, value_id, value_label)]
        rows_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            rows_by_collection[row["collection_id"]].append(row)
        matching_margin_rows = sum(
            max(row["matching_margin_rows"] for row in collection_rows)
            for collection_rows in rows_by_collection.values()
        )
        collections_with_single_value_row, sample_total, donor_total = (
            _sum_one_value_row_per_collection(rows)
        )
        value_rows.append(
            {
                "dimension": dimension,
                "value_id": value_id,
                "value_label": value_label,
                "collections_with_value": len({row["collection_id"] for row in rows}),
                "fact_rows_with_value": matching_margin_rows,
                "collections_with_single_value_row": collections_with_single_value_row,
                "authoritative_collections": collections_with_single_value_row,
                "no_star_fallback_collections": 0,
                "no_star_fallback_source_rows": 0,
                "assumption_violating": False,
                "number_of_samples": sample_total,
                "number_of_donors": donor_total,
                "sample_values": _format_observation_values(rows, "number_of_samples"),
                "donor_values": _format_observation_values(rows, "number_of_donors"),
            }
        )
    return value_rows


def _build_no_star_fallback_value_rows(
    fallback_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group unsafe no-star fallback contributions in a separate stream."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in fallback_rows:
        grouped[(row["dimension"], row["value_id"], row["value_label"])].append(row)
    value_rows = []
    for dimension, value_id, value_label in sorted(grouped):
        rows = grouped[(dimension, value_id, value_label)]
        value_rows.append({
            "dimension": dimension,
            "value_id": value_id,
            "value_label": value_label,
            "collections_with_value": len({row["collection_id"] for row in rows}),
            "fact_rows_with_value": 0,
            "collections_with_single_value_row": 0,
            "authoritative_collections": 0,
            "no_star_fallback_collections": len({row["collection_id"] for row in rows}),
            "no_star_fallback_source_rows": sum(row["source_fact_rows"] for row in rows),
            "assumption_violating": True,
            "number_of_samples": sum(row["number_of_samples"] for row in rows),
            "number_of_donors": sum(row["number_of_donors"] for row in rows),
            "sample_values": _format_observation_values(rows, "number_of_samples"),
            "donor_values": _format_observation_values(rows, "number_of_donors"),
        })
    return value_rows


def _sum_all_star_totals_for_margin_collections(
    all_star_rows: list[dict[str, Any]],
    collection_ids_with_margins: set[str],
) -> tuple[int, int, int]:
    """Sum one all-star total per collection that also has marginal rows."""
    all_star_rows_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_star_rows:
        if row["collection_id"] in collection_ids_with_margins:
            all_star_rows_by_collection[row["collection_id"]].append(row)

    collections_with_single_all_star_total = 0
    sample_total = 0
    donor_total = 0
    for collection_id in sorted(collection_ids_with_margins):
        rows = all_star_rows_by_collection.get(collection_id, [])
        if len(rows) != 1:
            continue
        collections_with_single_all_star_total += 1
        row = rows[0]
        if row["number_of_samples"] is not None:
            sample_total += row["number_of_samples"]
        if row["number_of_donors"] is not None:
            donor_total += row["number_of_donors"]
    return collections_with_single_all_star_total, sample_total, donor_total


def _sum_one_all_star_total_per_collection(
    all_star_rows: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Sum all-star totals across collections with one populated all-star row."""
    all_star_rows_by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_star_rows:
        all_star_rows_by_collection[row["collection_id"]].append(row)

    collections_with_single_all_star_total = 0
    sample_total = 0
    donor_total = 0
    for rows in all_star_rows_by_collection.values():
        if len(rows) != 1:
            continue
        collections_with_single_all_star_total += 1
        row = rows[0]
        if row["number_of_samples"] is not None:
            sample_total += row["number_of_samples"]
        if row["number_of_donors"] is not None:
            donor_total += row["number_of_donors"]
    return collections_with_single_all_star_total, sample_total, donor_total


def _format_dimension_value(row: dict[str, Any]) -> str:
    """Return a compact label for one grouped all-but-one-star value."""
    value_id = row["value_id"]
    value_label = row["value_label"]
    if value_id and value_label and value_id != value_label:
        return f"{value_label} ({value_id})"
    return value_label or value_id or "(blank)"


def build_fact_sheet_summary(
    collections: list[dict[str, Any]],
    directory,
    *,
    allow_no_star_fact_sums: bool = False,
) -> dict[str, Any]:
    """Return non-additive fact-sheet summaries for selected collections.

    Fact-sheet rows are aggregation observations, not mutually exclusive records.
    This function exposes row-level all-star observations and all-but-one-star
    marginal observations. It only sums one compatible row per collection across
    collections: one all-star row per collection for all-star totals, and one
    all-but-one row per collection and value for per-value marginal totals.
    """
    collections = _unique_collections(collections)
    all_star_rows = []
    all_but_one_rows = []
    no_star_fallback_rows = []
    collections_with_fact_sheets = set()
    collections_with_populated_all_star_rows = set()
    collections_with_populated_all_but_one_star_rows = set()

    for collection in collections:
        collection_id = collection["id"]
        facts = directory.getCollectionFacts(collection_id)
        if not facts:
            continue
        collections_with_fact_sheets.add(collection_id)
        for fact in facts:
            normalized_dimensions = {
                key: normalize_fact_dimension_value(fact.get(key))
                for key in FACT_DIMENSION_KEYS
            }
            if all(value == "*" for value in normalized_dimensions.values()):
                if _is_populated_fact_row(fact):
                    collections_with_populated_all_star_rows.add(collection_id)
                    all_star_rows.append(_build_all_star_row(collection, fact))
                continue

            fixed_dimensions = [
                key
                for key, value in normalized_dimensions.items()
                if value not in (None, "", "*")
            ]
            if len(fixed_dimensions) != 1:
                continue
            fixed_dimension = fixed_dimensions[0]
            if not all(
                key == fixed_dimension or normalized_dimensions[key] == "*"
                for key in FACT_DIMENSION_KEYS
            ):
                continue
            matching_margin_rows = len(
                get_matching_one_star_rows(
                    facts,
                    fixed_dimension,
                    normalized_dimensions[fixed_dimension],
                )
            )
            if not _is_populated_fact_row(fact):
                continue
            value_id, value_label = _value_id_and_label(fact.get(fixed_dimension))
            collections_with_populated_all_but_one_star_rows.add(collection_id)
            row = _build_all_but_one_row(
                collection,
                fact,
                fixed_dimension,
                value_id,
                value_label,
                matching_margin_rows,
            )
            all_but_one_rows.append(row)

        if not allow_no_star_fact_sums:
            continue
        no_star_facts = get_no_star_rows(facts)
        if not no_star_facts:
            continue
        dimension_values = get_dimension_values(facts)
        for dimension in FACT_DIMENSION_KEYS:
            for value in dimension_values[dimension]:
                matching_margins = get_matching_one_star_rows(
                    facts,
                    dimension,
                    value,
                )
                if matching_margins:
                    continue
                matching_fallback_facts = [
                    fact
                    for fact in no_star_facts
                    if normalize_fact_dimension_value(fact.get(dimension)) == value
                    and _is_populated_fact_row(fact)
                ]
                if not matching_fallback_facts:
                    continue
                raw_value = matching_fallback_facts[0].get(dimension)
                value_id, value_label = _value_id_and_label(raw_value)
                no_star_fallback_rows.append(
                    _build_no_star_fallback_row(
                        collection,
                        matching_fallback_facts,
                        dimension,
                        value_id,
                        value_label,
                    )
                )

    (
        margin_collections_with_single_all_star_total,
        margin_collection_sample_total,
        margin_collection_donor_total,
    ) = _sum_all_star_totals_for_margin_collections(
        all_star_rows,
        collections_with_populated_all_but_one_star_rows,
    )
    (
        collections_with_single_all_star_total,
        all_collection_sample_total,
        all_collection_donor_total,
    ) = _sum_one_all_star_total_per_collection(all_star_rows)

    totals = {
        "collections": len(collections),
        "collections_with_fact_sheets": len(collections_with_fact_sheets),
        "collections_with_populated_all_star_rows": len(
            collections_with_populated_all_star_rows
        ),
        "collections_with_populated_all_but_one_star_rows": len(
            collections_with_populated_all_but_one_star_rows
        ),
        "collections_with_populated_all_but_one_star_rows_and_single_all_star_total": (
            margin_collections_with_single_all_star_total
        ),
        "collections_with_single_all_star_total": collections_with_single_all_star_total,
        "populated_all_star_rows": len(all_star_rows),
        "populated_all_but_one_star_rows": len(all_but_one_rows),
        "all_star_samples_total_for_collections_with_all_star_rows": (
            all_collection_sample_total
        ),
        "all_star_donors_total_for_collections_with_all_star_rows": (
            all_collection_donor_total
        ),
        "all_star_samples_total_for_collections_with_all_but_one_rows": (
            margin_collection_sample_total
        ),
        "all_star_donors_total_for_collections_with_all_but_one_rows": (
            margin_collection_donor_total
        ),
        "allow_no_star_fact_sums": allow_no_star_fact_sums,
        "collections_with_no_star_fallback": len(
            {row["collection_id"] for row in no_star_fallback_rows}
        ),
        "no_star_fallback_distribution_values": len(
            {
                (row["dimension"], row["value_id"])
                for row in no_star_fallback_rows
            }
        ),
        "no_star_fallback_contributions": len(no_star_fallback_rows),
        "no_star_fallback_source_rows": len(
            {
                (row["collection_id"], fact_id)
                for row in no_star_fallback_rows
                for fact_id in row["source_fact_ids"].split(";")
            }
        ),
        "fact_sheet_summary_warning": (
            NO_STAR_FACT_SUMS_WARNING if allow_no_star_fact_sums else ""
        ),
    }
    return {
        "totals": totals,
        "all_star_rows": all_star_rows,
        "all_but_one_rows": all_but_one_rows,
        "no_star_fallback_rows": no_star_fallback_rows,
        "all_but_one_value_rows": _build_all_but_one_value_rows(all_but_one_rows),
        "no_star_fallback_value_rows": _build_no_star_fallback_value_rows(
            no_star_fallback_rows
        ),
    }


def build_fact_sheet_summary_frames(
    collections: list[dict[str, Any]],
    directory,
    *,
    allow_no_star_fact_sums: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return dataframe views of the fact-sheet summary."""
    summary = build_fact_sheet_summary(
        collections,
        directory,
        allow_no_star_fact_sums=allow_no_star_fact_sums,
    )
    return _build_fact_sheet_summary_frames(summary)


def _build_fact_sheet_summary_frames(
    summary: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return dataframe views for an already-built fact-sheet summary."""
    return (
        pd.DataFrame([summary["totals"]], columns=SUMMARY_COLUMNS),
        pd.DataFrame(summary["all_star_rows"], columns=ALL_STAR_COLUMNS),
        pd.DataFrame(
            summary["all_but_one_value_rows"],
            columns=ALL_BUT_ONE_VALUE_COLUMNS,
        ),
        pd.DataFrame(summary["all_but_one_rows"], columns=ALL_BUT_ONE_ROW_COLUMNS),
    )


def build_fact_sheet_xlsx_tables(
    collections: list[dict[str, Any]],
    directory,
    *,
    allow_no_star_fact_sums: bool = False,
) -> list[tuple[pd.DataFrame, str, bool]]:
    """Return XLSX sheet specs for non-additive fact-sheet summaries."""
    summary = build_fact_sheet_summary(
        collections,
        directory,
        allow_no_star_fact_sums=allow_no_star_fact_sums,
    )
    summary_df, all_star_df, value_df, row_df = _build_fact_sheet_summary_frames(
        summary
    )
    return [
        (summary_df, "Fact sheet summary", False),
        (all_star_df, "Fact sheet all-star rows", False),
        (value_df, "Fact sheet distributions", False),
        (row_df, "Fact sheet margin rows", False),
        *([
            (
                pd.DataFrame(
                    summary["no_star_fallback_value_rows"],
                    columns=ALL_BUT_ONE_VALUE_COLUMNS,
                ),
                "Fact sheet no-star fallback",
                False,
            )
        ] if allow_no_star_fact_sums else []),
    ]


def print_fact_sheet_summary(
    collections: list[dict[str, Any]],
    directory,
    label: str = "Fact-sheet summary",
    *,
    allow_no_star_fact_sums: bool = False,
) -> None:
    """Print a compact non-additive fact-sheet summary for selected collections."""
    summary = build_fact_sheet_summary(
        collections,
        directory,
        allow_no_star_fact_sums=allow_no_star_fact_sums,
    )
    totals = summary["totals"]
    print(label + ":")
    if allow_no_star_fact_sums:
        print("WARNING: " + NO_STAR_FACT_SUMS_WARNING)
        print(
            "- UNSAFE no-star fallback provenance: %d collections / "
            "%d distribution values / %d source rows"
            % (
                totals["collections_with_no_star_fallback"],
                totals["no_star_fallback_distribution_values"],
                totals["no_star_fallback_source_rows"],
            )
        )
    print(
        "- collections with fact sheets: %d / %d"
        % (totals["collections_with_fact_sheets"], totals["collections"])
    )
    print(
        "- collections with populated all-star rows: %d (%d rows)"
        % (
            totals["collections_with_populated_all_star_rows"],
            totals["populated_all_star_rows"],
        )
    )
    print(
        "- collections with populated all-but-one-star rows: %d (%d rows)"
        % (
            totals["collections_with_populated_all_but_one_star_rows"],
            totals["populated_all_but_one_star_rows"],
        )
    )
    print(
        "- all-star totals from collections with populated all-star rows: "
        "%d samples / %d donors (from %d collections with one populated all-star row)"
        % (
            totals["all_star_samples_total_for_collections_with_all_star_rows"],
            totals["all_star_donors_total_for_collections_with_all_star_rows"],
            totals["collections_with_single_all_star_total"],
        )
    )
    print(
        "- all-star totals for collections with populated all-but-one-star rows: "
        "%d samples / %d donors (from %d collections with one populated all-star row)"
        % (
            totals["all_star_samples_total_for_collections_with_all_but_one_rows"],
            totals["all_star_donors_total_for_collections_with_all_but_one_rows"],
            totals[
                "collections_with_populated_all_but_one_star_rows_and_single_all_star_total"
            ],
        )
    )
    if summary["all_but_one_value_rows"]:
        print("- all-but-one-star distributions by variable:")
        current_dimension = None
        for row in summary["all_but_one_value_rows"]:
            if row["dimension"] != current_dimension:
                current_dimension = row["dimension"]
                print(f"  - {current_dimension}:")
            print(
                "    - %s: %d samples / %d donors from %d collections"
                % (
                    _format_dimension_value(row),
                    row["number_of_samples"],
                    row["number_of_donors"],
                    row["authoritative_collections"]
                    + row["no_star_fallback_collections"],
                )
            )
    if summary["no_star_fallback_value_rows"]:
        print("- UNSAFE no-star fallback distributions (not combined with all-but-one-star):")
        current_dimension = None
        for row in summary["no_star_fallback_value_rows"]:
            if row["dimension"] != current_dimension:
                current_dimension = row["dimension"]
                print(f"  - {current_dimension}:")
            print(
                "    - %s: %d samples / %d donors from %d collections (%d source rows)"
                % (
                    _format_dimension_value(row), row["number_of_samples"],
                    row["number_of_donors"], row["no_star_fallback_collections"],
                    row["no_star_fallback_source_rows"],
                )
            )
