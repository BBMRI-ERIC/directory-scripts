# vim:ts=4:sw=4:tw=0:sts=4:et

"""Helpers for computing per-biobank Directory statistics."""

import logging as log
from collections import Counter
from typing import Any

from fact_sheet_utils import analyze_collection_fact_sheet, has_fact_sheet
from oomutils import estimate_count_from_oom_or_none


def _normalize_scalar(value: Any) -> Any:
    """Return the scalar identifier/value from EMX-style scalar wrappers."""
    if isinstance(value, dict):
        if "id" in value:
            return value["id"]
        if "name" in value:
            return value["name"]
    return value


def _normalize_country(value: Any) -> str:
    """Return country identifier from a raw country field."""
    scalar_value = _normalize_scalar(value)
    return "" if scalar_value is None else str(scalar_value)


def extract_staging_area_from_id(entity_id: str) -> str:
    """Return the staging-area code encoded in a Directory entity id."""
    if not isinstance(entity_id, str) or not entity_id:
        return ""
    parts = entity_id.split(":")
    if len(parts) < 3:
        return ""
    prefix = parts[2]
    return prefix.split("_", 1)[0]


def _normalize_multi_value_list(value: Any) -> list[str]:
    """Return a normalized list of scalar values from a list-like field."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        value = [value]
    normalized = []
    for item in value:
        scalar = _normalize_scalar(item)
        if scalar in (None, ""):
            continue
        normalized.append(str(scalar))
    return normalized


def _format_counter(counter: Counter) -> str:
    """Return a compact deterministic counter representation."""
    if not counter:
        return ""
    return "; ".join(f"{key}={counter[key]}" for key in sorted(counter))


def _is_withdrawn(entity: dict[str, Any] | None) -> bool:
    """Return whether an entity is marked as withdrawn."""
    if entity is None:
        return False
    return bool(entity.get("withdrawn"))


def _normalize_filter_values(values: list[str] | None) -> set[str]:
    """Return normalized uppercase filter values."""
    if not values:
        return set()
    normalized = set()
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                normalized.add(item.upper())
    return normalized


def _build_breakdown_rows(
    biobank_id: str,
    biobank_name: str,
    label: str,
    counter: Counter,
) -> list[dict[str, Any]]:
    """Return normalized breakdown rows for one biobank."""
    return [
        {
            "biobank_id": biobank_id,
            "biobank_name": biobank_name,
            label: key,
            "count": counter[key],
        }
        for key in sorted(counter)
    ]


def _build_breakdown_summary_rows(
    rows: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    """Return overall totals for a breakdown table."""
    totals = Counter()
    for row in rows:
        totals[row[label]] += row["count"]
    return [
        {
            label: key,
            "count": totals[key],
        }
        for key in sorted(totals)
    ]


def build_directory_stats(
    directory,
    *,
    include_withdrawn_biobanks: bool = False,
    country_filters: list[str] | None = None,
    staging_area_filters: list[str] | None = None,
    collection_type_filters: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build multi-table Directory statistics for all loaded biobanks."""
    normalized_country_filters = _normalize_filter_values(country_filters)
    normalized_staging_area_filters = _normalize_filter_values(staging_area_filters)
    normalized_collection_type_filters = _normalize_filter_values(
        collection_type_filters
    )

    selected_biobanks: dict[str, dict[str, Any]] = {}
    for biobank in directory.getBiobanks():
        if _is_withdrawn(biobank) and not include_withdrawn_biobanks:
            continue
        country = _normalize_country(biobank.get("country")).upper()
        staging_area = extract_staging_area_from_id(biobank.get("id", "")).upper()
        if normalized_country_filters and country not in normalized_country_filters:
            continue
        if (
            normalized_staging_area_filters
            and staging_area not in normalized_staging_area_filters
        ):
            continue
        selected_biobanks[biobank["id"]] = biobank

    collections_by_biobank: dict[str, list[dict[str, Any]]] = {}
    for collection in directory.getCollections():
        biobank_id = directory.getCollectionBiobankId(collection["id"])
        biobank = selected_biobanks.get(biobank_id)
        if biobank is None:
            continue
        if _is_withdrawn(collection):
            continue
        collection_types = {
            collection_type.upper()
            for collection_type in _normalize_multi_value_list(collection.get("type"))
        }
        if (
            normalized_collection_type_filters
            and not collection_types.intersection(normalized_collection_type_filters)
        ):
            continue
        collections_by_biobank.setdefault(biobank_id, []).append(collection)

    services_by_biobank: dict[str, list[dict[str, Any]]] = {}
    for service in directory.getServices():
        biobank = service.get("biobank")
        if biobank and "id" in biobank:
            biobank_record = selected_biobanks.get(biobank["id"])
            if biobank_record is None:
                continue
            services_by_biobank.setdefault(biobank["id"], []).append(service)

    biobank_rows: list[dict[str, Any]] = []
    collection_type_rows: list[dict[str, Any]] = []
    service_type_rows: list[dict[str, Any]] = []
    fact_sheet_warning_rows: list[dict[str, Any]] = []

    top_level_collection_type_total_counter: Counter = Counter()
    subcollection_type_total_counter: Counter = Counter()

    for biobank_id in sorted(selected_biobanks):
        biobank = selected_biobanks[biobank_id]
        biobank_id = biobank["id"]
        biobank_name = biobank.get("name", "")
        biobank_collections = collections_by_biobank.get(biobank_id, [])
        biobank_services = services_by_biobank.get(biobank_id, [])

        samples_explicit = 0
        donors_explicit = 0
        samples_oom = 0
        donors_oom = 0
        top_level_collections = 0
        subcollections = 0
        collections_with_facts = 0
        collections_with_all_star = 0
        collections_missing_valid_all_star = 0
        collections_all_star_inconsistent_samples = 0
        collections_all_star_inconsistent_donors = 0
        collection_type_counter: Counter = Counter()
        top_level_collection_type_counter: Counter = Counter()
        subcollection_type_counter: Counter = Counter()
        service_type_counter: Counter = Counter()

        for collection in biobank_collections:
            collection_id = collection["id"]
            is_top_level = directory.isTopLevelCollection(collection_id)
            if is_top_level:
                top_level_collections += 1
            else:
                subcollections += 1

            for collection_type in set(_normalize_multi_value_list(collection.get("type"))):
                collection_type_counter[collection_type] += 1
                if is_top_level:
                    top_level_collection_type_counter[collection_type] += 1
                    top_level_collection_type_total_counter[collection_type] += 1
                else:
                    subcollection_type_counter[collection_type] += 1
                    subcollection_type_total_counter[collection_type] += 1

            if directory.isCountableCollection(collection_id, "size"):
                samples_explicit += collection["size"]
            elif is_top_level:
                size_estimate = estimate_count_from_oom_or_none(
                    collection.get("order_of_magnitude"),
                    collection_id=collection_id,
                    field_name="order_of_magnitude",
                )
                if size_estimate is not None:
                    samples_oom += size_estimate

            if directory.isCountableCollection(collection_id, "number_of_donors"):
                donors_explicit += collection["number_of_donors"]
            elif is_top_level:
                donor_estimate = estimate_count_from_oom_or_none(
                    collection.get("order_of_magnitude_donors"),
                    collection_id=collection_id,
                    field_name="order_of_magnitude_donors",
                )
                if donor_estimate is not None:
                    donors_oom += donor_estimate

            if has_fact_sheet(collection):
                collections_with_facts += 1
                fact_sheet = analyze_collection_fact_sheet(
                    collection,
                    directory.getCollectionFacts(collection_id),
                )
                if fact_sheet["all_star_rows"] == 1:
                    collections_with_all_star += 1
                else:
                    collections_missing_valid_all_star += 1

                for warning in fact_sheet["warnings"]:
                    if warning["code"] == "all_star_samples_mismatch":
                        collections_all_star_inconsistent_samples += 1
                    elif warning["code"] == "all_star_donors_mismatch":
                        collections_all_star_inconsistent_donors += 1
                    fact_sheet_warning_rows.append(
                        {
                            "biobank_id": biobank_id,
                            "biobank_name": biobank_name,
                            "collection_id": collection_id,
                            "collection_name": collection.get("name", ""),
                            "code": warning["code"],
                            "message": warning["message"],
                            "expected": warning.get("expected"),
                            "actual": warning.get("actual"),
                        }
                    )

        for service in biobank_services:
            for service_type in set(
                _normalize_multi_value_list(
                    service.get("serviceTypes", service.get("service_types"))
                )
            ):
                service_type_counter[service_type] += 1

        biobank_rows.append(
            {
                "id": biobank_id,
                "name": biobank_name,
                "country": _normalize_country(biobank.get("country")),
                "staging_area": extract_staging_area_from_id(biobank_id),
                "withdrawn": _is_withdrawn(biobank),
                "collection_records_total": len(biobank_collections),
                "top_level_collections": top_level_collections,
                "subcollections": subcollections,
                "collection_type_breakdown": _format_counter(collection_type_counter),
                "top_level_collection_type_breakdown": _format_counter(
                    top_level_collection_type_counter
                ),
                "subcollection_type_breakdown": _format_counter(
                    subcollection_type_counter
                ),
                "samples_explicit": samples_explicit,
                "samples_oom": samples_oom,
                "samples_total": samples_explicit + samples_oom,
                "donors_explicit": donors_explicit,
                "donors_oom": donors_oom,
                "donors_total": donors_explicit + donors_oom,
                "services_total": len(biobank_services),
                "service_type_breakdown": _format_counter(service_type_counter),
                "collections_with_facts": collections_with_facts,
                "collections_with_all_star": collections_with_all_star,
                "collections_missing_valid_all_star": collections_missing_valid_all_star,
                "collections_all_star_inconsistent_samples": collections_all_star_inconsistent_samples,
                "collections_all_star_inconsistent_donors": collections_all_star_inconsistent_donors,
            }
        )
        collection_type_rows.extend(
            _build_breakdown_rows(
                biobank_id,
                biobank_name,
                "collection_type",
                collection_type_counter,
            )
        )
        service_type_rows.extend(
            _build_breakdown_rows(
                biobank_id,
                biobank_name,
                "service_type",
                service_type_counter,
            )
        )

    biobank_rows.sort(key=lambda row: row["id"])

    return {
        "biobank_rows": biobank_rows,
        "collection_type_rows": collection_type_rows,
        "collection_type_summary_rows": _build_breakdown_summary_rows(
            collection_type_rows,
            "collection_type",
        ),
        "service_type_rows": service_type_rows,
        "service_type_summary_rows": _build_breakdown_summary_rows(
            service_type_rows,
            "service_type",
        ),
        "top_level_collection_type_summary_rows": [
            {"collection_type": key, "count": top_level_collection_type_total_counter[key]}
            for key in sorted(top_level_collection_type_total_counter)
        ],
        "subcollection_type_summary_rows": [
            {"collection_type": key, "count": subcollection_type_total_counter[key]}
            for key in sorted(subcollection_type_total_counter)
        ],
        "fact_sheet_warning_rows": fact_sheet_warning_rows,
    }


def build_biobank_stats(
    directory,
    *,
    include_withdrawn_biobanks: bool = False,
    country_filters: list[str] | None = None,
    staging_area_filters: list[str] | None = None,
    collection_type_filters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build the main per-biobank statistics rows."""
    return build_directory_stats(
        directory,
        include_withdrawn_biobanks=include_withdrawn_biobanks,
        country_filters=country_filters,
        staging_area_filters=staging_area_filters,
        collection_type_filters=collection_type_filters,
    )["biobank_rows"]


def build_stats_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Build a summary row for per-biobank stats output."""
    top_level_collection_type_totals = Counter()
    subcollection_type_totals = Counter()
    service_type_totals = Counter()
    for row in rows:
        for item in str(row.get("top_level_collection_type_breakdown", "")).split("; "):
            if not item:
                continue
            key, value = item.split("=", 1)
            top_level_collection_type_totals[key] += int(value)
        for item in str(row.get("subcollection_type_breakdown", "")).split("; "):
            if not item:
                continue
            key, value = item.split("=", 1)
            subcollection_type_totals[key] += int(value)
        for item in str(row.get("service_type_breakdown", "")).split("; "):
            if not item:
                continue
            key, value = item.split("=", 1)
            service_type_totals[key] += int(value)

    return {
        "biobanks_total": len(rows),
        "withdrawn_biobanks": sum(1 for row in rows if row.get("withdrawn")),
        "biobanks_with_collections": sum(
            1 for row in rows if row["collection_records_total"] > 0
        ),
        "biobanks_with_services": sum(1 for row in rows if row["services_total"] > 0),
        "collection_records_total": sum(row["collection_records_total"] for row in rows),
        "top_level_collections": sum(row["top_level_collections"] for row in rows),
        "subcollections": sum(row["subcollections"] for row in rows),
        "samples_explicit": sum(row["samples_explicit"] for row in rows),
        "samples_oom": sum(row["samples_oom"] for row in rows),
        "samples_total": sum(row["samples_total"] for row in rows),
        "donors_explicit": sum(row["donors_explicit"] for row in rows),
        "donors_oom": sum(row["donors_oom"] for row in rows),
        "donors_total": sum(row["donors_total"] for row in rows),
        "services_total": sum(row["services_total"] for row in rows),
        "collections_with_facts": sum(row["collections_with_facts"] for row in rows),
        "collections_with_all_star": sum(row["collections_with_all_star"] for row in rows),
        "collections_missing_valid_all_star": sum(
            row["collections_missing_valid_all_star"] for row in rows
        ),
        "collections_all_star_inconsistent_samples": sum(
            row["collections_all_star_inconsistent_samples"] for row in rows
        ),
        "collections_all_star_inconsistent_donors": sum(
            row["collections_all_star_inconsistent_donors"] for row in rows
        ),
        "top_level_collection_type_breakdown": _format_counter(
            top_level_collection_type_totals
        ),
        "subcollection_type_breakdown": _format_counter(subcollection_type_totals),
        "service_type_breakdown": _format_counter(service_type_totals),
    }
