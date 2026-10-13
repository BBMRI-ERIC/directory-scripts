"""Catalogue exact shared-UpSet bars and their unique biobank memberships."""

from collections import defaultdict
from typing import Any, Mapping


def build_intersection_catalogue(matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Assign deterministic labels to observed exclusive Boolean intersections.

    Args:
        matrix: Classifiable unique-bank rows, ordered set IDs and optional full labels.

    Returns:
        Descending-count then bit-sorted bars with IDs, members and country/name groups.

    Raises:
        ValueError: If identities repeat or matrix membership is not Boolean.
    """
    columns = matrix["sets"]
    groups = defaultdict(list)
    seen = set()
    for row in matrix.get("rows", []):
        bank_id = row["observation_id"]
        if bank_id in seen:
            raise ValueError(f"Duplicate UpSet biobank: {bank_id}")
        seen.add(bank_id)
        bits = tuple(row[column] for column in columns)
        if any(type(bit) is not bool for bit in bits):
            raise ValueError("UpSet membership must be Boolean")
        groups[bits].append(row)
    result = []
    labels = matrix.get("set_labels", columns)
    for index, (bits, members) in enumerate(sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0])), 1):
        countries = defaultdict(list)
        for member in sorted(members, key=lambda r: (r.get("country", ""), r.get("institution", ""), r["observation_id"])):
            countries[member.get("country") or "Unknown"].append({"biobank_id": member["observation_id"],
                "name": member.get("institution") or member["observation_id"]})
        result.append({"bar_id": f"I{index}", "pattern": list(bits), "selected_sets": [c for c, bit in zip(columns, bits) if bit],
                       "selected_labels": [label for label, bit in zip(labels, bits) if bit], "count": len(members),
                       "biobank_ids": sorted(row["observation_id"] for row in members),
                       "countries": [{"country": cc, "biobanks": banks} for cc, banks in sorted(countries.items())]})
    return result
