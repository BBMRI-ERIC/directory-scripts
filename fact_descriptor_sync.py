"""Shared helpers for fact-sheet-to-collection descriptor alignment."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from fact_sheet_utils import analyze_collection_fact_sheet, normalize_fact_dimension_value


ICD10_PREFIX = "urn:miriam:icd:"
OPEN_AGE_HIGH = None
AGE_RANGE_LABEL_BOUNDS = {
    # Aligned with DirectoryOntologies/AgeRanges labels in ERIC.
    "NEWBORN": (0, 1, "MONTH"),
    "INFANT": (2, 23, "MONTH"),
    "CHILD": (2, 12, "YEAR"),
    "ADOLESCENT": (13, 17, "YEAR"),
    "YOUNG ADULT": (18, 24, "YEAR"),
    "ADULT": (25, 44, "YEAR"),
    "MIDDLE-AGED": (45, 64, "YEAR"),
    "AGED (65-79 YEARS)": (65, 79, "YEAR"),
    "AGED (>80 YEARS)": (80, OPEN_AGE_HIGH, "YEAR"),
}
AGE_LABEL_LOW_SUPPORT_OUTLIER = 0
AGE_LABEL_HIGH_SUPPORT_THRESHOLD = 5


def normalize_descriptor_value(value: Any) -> str:
    """Return a string descriptor value from scalars or EMX wrapper dicts."""
    if isinstance(value, dict):
        if "name" in value:
            return normalize_descriptor_value(value["name"])
        if "id" in value:
            return normalize_descriptor_value(value["id"])
    if _is_missing_value(value):
        return ""
    return str(value).strip()


def parse_collection_multi_value_field(value: Any) -> list[str]:
    """Return ordered descriptor values from collection JSON or CSV/TSV rows."""
    if _is_missing_value(value) or value == "":
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return ordered_unique(normalize_descriptor_value(item) for item in value)
    return ordered_unique([normalize_descriptor_value(value)])


def ordered_unique(values: Any) -> list[str]:
    """Return non-empty values in original order without duplicates."""
    seen = set()
    ordered = []
    for value in values:
        normalized = normalize_descriptor_value(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def collect_fact_descriptor_values(facts: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return ordered non-star descriptor values observed in fact rows."""
    diagnoses = []
    sexes = []
    materials = []
    for fact in facts:
        diagnosis = normalize_descriptor_value(normalize_fact_dimension_value(fact.get("disease")))
        if diagnosis and diagnosis != "*":
            diagnoses.append(diagnosis)
        sex = normalize_descriptor_value(normalize_fact_dimension_value(fact.get("sex")))
        if sex and sex != "*":
            sexes.append(sex)
        material = normalize_descriptor_value(normalize_fact_dimension_value(fact.get("sample_type")))
        if material and material != "*":
            materials.append(material)
    return {
        "diagnosis_available": ordered_unique(diagnoses),
        "sex": ordered_unique(sexes),
        "materials": ordered_unique(materials),
    }


def effective_fact_materials(
    fact_materials: list[str],
    collection_materials: list[str],
) -> list[str]:
    """Return fact-sheet material values that should align with collection metadata."""
    non_nav = [value for value in fact_materials if value != "NAV"]
    if non_nav:
        return non_nav
    if collection_materials:
        return []
    return ["NAV"] if fact_materials else []


def fact_descriptor_values_for_comparison(
    facts: list[dict[str, Any]],
    collection: dict[str, Any],
) -> dict[str, list[str]]:
    """Return fact descriptor values normalized for collection-level comparison."""
    values = collect_fact_descriptor_values(facts)
    values["materials"] = effective_fact_materials(
        values["materials"],
        parse_collection_multi_value_field(collection.get("materials")),
    )
    return values


def is_icd10_code(value: str) -> bool:
    """Return whether a diagnosis value uses the Directory ICD-10 URI form."""
    return value.upper().startswith(ICD10_PREFIX.upper())


def icd10_code_core(value: str) -> str:
    """Return the ICD-10 code core without the Directory URI prefix."""
    if not is_icd10_code(value):
        return ""
    return value[len(ICD10_PREFIX):].upper()


def icd10_covers(existing_value: str, candidate_value: str) -> bool:
    """Return whether an ICD-10 metadata value covers a more specific candidate."""
    existing_code = icd10_code_core(existing_value)
    candidate_code = icd10_code_core(candidate_value)
    if not existing_code or not candidate_code:
        return False
    if existing_code == candidate_code:
        return True
    if "." not in existing_code and candidate_code.startswith(existing_code + "."):
        return True
    return False


def diagnosis_is_covered(existing_values: list[str], candidate_value: str) -> bool:
    """Return whether a diagnosis is already represented by existing metadata."""
    return any(
        existing_value == candidate_value or icd10_covers(existing_value, candidate_value)
        for existing_value in existing_values
    )


def merge_diagnosis_values(
    current_values: list[str],
    fact_values: list[str],
    *,
    replace_existing: bool,
) -> list[str]:
    """Return the diagnosis list after applying append-or-replace semantics."""
    if replace_existing:
        kept_values = [
            value
            for value in current_values
            if value in fact_values
            or any(icd10_covers(value, candidate) for candidate in fact_values)
        ]
        merged = list(kept_values)
    else:
        merged = list(current_values)

    for candidate in fact_values:
        if not diagnosis_is_covered(merged, candidate):
            merged.append(candidate)
    return ordered_unique(merged)


def merge_descriptor_values(
    current_values: list[str],
    fact_values: list[str],
    *,
    replace_existing: bool,
) -> list[str]:
    """Return the generic append-or-replace merge for multi-value fields."""
    if replace_existing:
        return ordered_unique(fact_values)
    merged = list(current_values)
    for candidate in fact_values:
        if candidate not in merged:
            merged.append(candidate)
    return merged


def derive_age_range_update(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a conservative age-range proposal from fact rows."""
    parsed_rows = []
    for fact in facts:
        age_range = normalize_descriptor_value(fact.get("age_range"))
        if not age_range or age_range in {"*", "Unknown", "Undefined"}:
            continue
        age_low, age_high, age_unit = _parse_age_range_bounds(age_range)
        if age_low is None and age_high is None and age_unit is None:
            continue
        parsed_rows.append(
            {
                "age_range": age_range,
                "low": age_low,
                "high": age_high,
                "unit": age_unit,
                "label_based": age_range.strip().upper() in AGE_RANGE_LABEL_BOUNDS,
                "support": _fact_row_support_count(fact),
            }
        )

    if not parsed_rows:
        return {"age_low": None, "age_high": None, "age_unit": None, "notes": []}

    has_high_support_label_rows = any(
        row["label_based"]
        and isinstance(row["support"], int)
        and row["support"] >= AGE_LABEL_HIGH_SUPPORT_THRESHOLD
        for row in parsed_rows
    )

    bounds = []
    has_open_high = False
    units = []
    notes = []
    low_support_rows_ignored = False
    for row in parsed_rows:
        if row["label_based"] and has_high_support_label_rows:
            support = row["support"]
            if isinstance(support, int) and support <= AGE_LABEL_LOW_SUPPORT_OUTLIER:
                low_support_rows_ignored = True
                continue
        age_low = row["low"]
        age_high = row["high"]
        age_unit = row["unit"]
        if age_low is None and age_high is None and age_unit is None:
            continue
        bounds.append((age_low, age_high))
        if age_unit is not None:
            units.append(age_unit)
        if age_high is None:
            has_open_high = True

    if not bounds:
        if low_support_rows_ignored:
            notes.append(
                "Low-support label-based age rows were ignored: rows with max(number_of_donors, number_of_samples)=0 are treated as non-evidence when at least one other label row has support >=5."
            )
        return {"age_low": None, "age_high": None, "age_unit": None, "notes": notes}

    low_values = [low for low, _ in bounds if low is not None]
    high_values = [high for _, high in bounds if high is not None]
    if low_support_rows_ignored:
        notes.append(
            "Low-support label-based age rows were ignored: rows with max(number_of_donors, number_of_samples)=0 are treated as non-evidence when at least one other label row has support >=5."
        )
    normalized_units = ordered_unique(units)
    if len(normalized_units) > 1:
        notes.append(
            "Fact-sheet age groups use mixed units; age_low/age_high/age_unit cannot be derived conservatively."
        )
        return {"age_low": None, "age_high": None, "age_unit": None, "notes": notes}

    age_low = min(low_values) if low_values else None
    age_high = None if has_open_high else (max(high_values) if high_values else None)
    if has_open_high:
        notes.append(
            "Open-ended fact-sheet age groups are present (for example 'Aged (>80 years)'); these have no finite upper bound, so age_high cannot be derived conservatively."
        )
    derived_unit = normalized_units[0] if normalized_units else None
    return {
        "age_low": age_low,
        "age_high": age_high,
        "age_unit": derived_unit if age_low is not None or age_high is not None else None,
        "notes": notes,
    }


def build_collection_descriptor_proposal(
    collection: dict[str, Any],
    facts: list[dict[str, Any]],
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Return proposed collection-descriptor updates derived from fact rows."""
    fact_values = fact_descriptor_values_for_comparison(facts, collection)
    fact_sheet = analyze_collection_fact_sheet(collection, facts)
    current = {
        "diagnosis_available": parse_collection_multi_value_field(collection.get("diagnosis_available")),
        "materials": parse_collection_multi_value_field(collection.get("materials")),
        "sex": parse_collection_multi_value_field(collection.get("sex")),
        "age_low": _coerce_optional_int(collection.get("age_low")),
        "age_high": _coerce_optional_int(collection.get("age_high")),
        "age_unit": normalize_descriptor_value(collection.get("age_unit")) or None,
        "size": _coerce_optional_int(collection.get("size")),
        "number_of_donors": _coerce_optional_int(collection.get("number_of_donors")),
    }
    proposed = dict(current)
    notes = []
    field_notes = {
        "diagnosis_available": [],
        "materials": [],
        "sex": [],
        "age_low": [],
        "age_high": [],
        "age_unit": [],
        "size": [],
        "number_of_donors": [],
    }

    proposed["diagnosis_available"] = merge_diagnosis_values(
        current["diagnosis_available"],
        fact_values["diagnosis_available"],
        replace_existing=replace_existing,
    )
    proposed["materials"] = merge_descriptor_values(
        current["materials"],
        fact_values["materials"],
        replace_existing=replace_existing,
    )
    proposed["sex"] = merge_descriptor_values(
        current["sex"],
        fact_values["sex"],
        replace_existing=replace_existing,
    )

    age_update = derive_age_range_update(facts)
    notes.extend(age_update["notes"])
    for field in ("age_low", "age_high", "age_unit"):
        field_notes[field].extend(age_update["notes"])
    for field in ("age_low", "age_high", "age_unit"):
        derived_value = age_update[field]
        if derived_value is None:
            continue
        if _age_field_should_update(field, current, age_update, replace_existing=replace_existing):
            proposed[field] = derived_value

    if isinstance(fact_sheet["all_star_number_of_samples"], int):
        proposed["size"] = fact_sheet["all_star_number_of_samples"]
    if isinstance(fact_sheet["all_star_number_of_donors"], int):
        proposed["number_of_donors"] = fact_sheet["all_star_number_of_donors"]

    changes = []
    for field in (
        "diagnosis_available",
        "materials",
        "sex",
        "age_low",
        "age_high",
        "age_unit",
        "size",
        "number_of_donors",
    ):
        if proposed[field] != current[field]:
            changes.append(
                {
                    "field": field,
                    "current": current[field],
                    "proposed": proposed[field],
                }
            )

    return {
        "current": current,
        "proposed": proposed,
        "changes": changes,
        "fact_values": fact_values,
        "all_star_row_present": fact_sheet["all_star_rows"] == 1,
        "notes": notes,
        "field_notes": field_notes,
    }


def apply_descriptor_proposal_to_dataframe_row(
    row: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Return a DataFrame-row dict updated with a descriptor proposal."""
    updated = dict(row)
    proposed = proposal["proposed"]
    for field in ("diagnosis_available", "materials", "sex"):
        updated[field] = ",".join(proposed[field])
    for field in ("age_low", "age_high", "size", "number_of_donors"):
        updated[field] = "" if proposed[field] is None else str(proposed[field])
    updated["age_unit"] = "" if proposed["age_unit"] is None else str(proposed["age_unit"])
    return updated


def _coerce_optional_int(value: Any) -> int | None:
    if _is_missing_value(value) or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_missing_value(value: Any) -> bool:
    """Return whether a scalar should be treated as an unset descriptor value."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _parse_age_range_bounds(age_range: str) -> tuple[int | None, int | None, str | None]:
    label_key = age_range.strip().upper()
    if label_key in AGE_RANGE_LABEL_BOUNDS:
        low, high, unit = AGE_RANGE_LABEL_BOUNDS[label_key]
        return low, high, unit

    age_unit = _infer_age_range_unit(age_range)
    range_match = re.search(r"(\d+)\s*-\s*(\d+)", age_range)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2)), age_unit or "YEAR"

    greater_match = re.search(r">\s*(\d+)", age_range)
    if greater_match:
        return int(greater_match.group(1)), OPEN_AGE_HIGH, age_unit or "YEAR"
    return None, None, None


def _age_field_should_update(
    field: str,
    current: dict[str, Any],
    age_update: dict[str, Any],
    *,
    replace_existing: bool,
) -> bool:
    """Return whether one age field should be updated from derived fact-sheet span."""
    derived_value = age_update[field]
    if derived_value is None:
        return False
    if replace_existing:
        return True

    current_low = current["age_low"]
    current_high = current["age_high"]
    current_unit = current["age_unit"]
    derived_low = age_update["age_low"]
    derived_high = age_update["age_high"]
    derived_unit = age_update["age_unit"]

    if field == "age_unit":
        if current_unit in (None, ""):
            return True
        if derived_unit and current_unit != derived_unit and (
            _age_field_should_update("age_low", current, age_update, replace_existing=False)
            or _age_field_should_update("age_high", current, age_update, replace_existing=False)
        ):
            return True
        return False

    if current_unit in (None, ""):
        return True
    if derived_unit and current_unit != derived_unit:
        return False

    if field == "age_low":
        if current_low is None:
            return True
        return derived_low is not None and derived_low < current_low

    if field == "age_high":
        if current_high is None:
            return False
        return derived_high is not None and derived_high > current_high

    return False


def _infer_age_range_unit(age_range: str) -> str | None:
    normalized = age_range.strip().lower()
    if "day" in normalized:
        return "DAY"
    if "week" in normalized:
        return "WEEK"
    if "month" in normalized:
        return "MONTH"
    if "year" in normalized:
        return "YEAR"
    return None


def _fact_row_support_count(fact: dict[str, Any]) -> int | None:
    """Return the strongest available row support from sample/donor counts."""
    donors = _coerce_optional_int(fact.get("number_of_donors"))
    samples = _coerce_optional_int(fact.get("number_of_samples"))
    counts = [count for count in (donors, samples) if isinstance(count, int)]
    if not counts:
        return None
    return max(counts)
