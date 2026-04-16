#!/usr/bin/env python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Derive the rare-disease map GeoJSON from current Directory metadata."""

from __future__ import annotations

import json
import logging as log
import pprint
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory

MEMBER_COUNTRIES = {
    "AT",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "EE",
    "ES",
    "FI",
    "GR",
    "HU",
    "IT",
    "LT",
    "LV",
    "MT",
    "NL",
    "NO",
    "PL",
    "SE",
    "SI",
    "SK",
}

RD_NETWORK_SUBSTRINGS = (
    "rd-biobanks",
    "rd_connect_it",
    "rd-connect-it",
    "rdconnect",
)


def load_feature_collection(path: Path) -> dict[str, Any]:
    """Load a GeoJSON FeatureCollection."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection.")
    return data


def normalize_ids(value: Any) -> list[str]:
    """Return a flat list of id-like strings from a Directory field."""
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return [str(value)]

    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("name")
            if item_id:
                out.append(str(item_id))
        elif item is not None:
            out.append(str(item))
    return out


def normalize_country_code(value: Any) -> str:
    """Normalize a Directory country field to a short code."""
    if isinstance(value, dict):
        value = value.get("id") or value.get("code") or value.get("name")
    return str(value or "").strip().upper()


def collection_types(collection: dict[str, Any]) -> list[str]:
    """Return normalized collection types."""
    value = collection.get("type")
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    return [str(value).strip().upper()]


def collection_is_rd(collection: dict[str, Any]) -> bool:
    """Return True when a collection is rare-disease related."""
    return "RD" in collection_types(collection)


def biobank_network_ids(biobank: dict[str, Any]) -> list[str]:
    """Return normalized network ids for a biobank."""
    ids = normalize_ids(biobank.get("network"))
    ids.extend(normalize_ids(biobank.get("networks")))
    ids.extend(normalize_ids(biobank.get("capabilities")))
    return ids


def biobank_has_rd_network(biobank: dict[str, Any]) -> bool:
    """Return True when the biobank is explicitly part of an RD network."""
    for network_id in biobank_network_ids(biobank):
        normalized = network_id.lower()
        if any(token in normalized for token in RD_NETWORK_SUBSTRINGS):
            return True
    return False


def biobank_has_rd_collection(biobank: dict[str, Any], collection_type_by_id: dict[str, list[str]]) -> bool:
    """Return True when any of the biobank collections is an RD collection."""
    for collection_id in normalize_ids(biobank.get("collections")):
        if collection_is_rd({"type": collection_type_by_id.get(collection_id, [])}):
            return True
    return False


def biobank_is_rd(biobank: dict[str, Any], collection_type_by_id: dict[str, list[str]]) -> bool:
    """Return True when a biobank should appear on the rare-disease map."""
    return biobank_has_rd_collection(biobank, collection_type_by_id) or biobank_has_rd_network(biobank)


def biobank_membership_role(biobank: dict[str, Any]) -> str:
    """Return the point color role for the rare-disease map."""
    country = normalize_country_code(biobank.get("country"))
    if country not in MEMBER_COUNTRIES:
        return "non_member"
    return "member"


def build_collection_type_index(directory: Directory) -> dict[str, list[str]]:
    """Return collection id -> normalized type list."""
    index: dict[str, list[str]] = {}
    for collection in directory.getCollections():
        collection_id = collection.get("id")
        if not collection_id:
            continue
        index[str(collection_id)] = collection_types(collection)
    return index


def main() -> None:
    parser = build_parser()
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser, default="ERIC")
    parser.add_argument("--input", required=True, help="Full geocoded GeoJSON input.")
    parser.add_argument("--output", required=True, help="Rare-disease GeoJSON output.")
    args = parser.parse_args()
    configure_logging(args)

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(f"Full geocoded GeoJSON not found: {input_path}")

    pp = pprint.PrettyPrinter(indent=2)
    directory = Directory(**build_directory_kwargs(args, pp=pp))
    collection_type_by_id = build_collection_type_index(directory)

    rd_biobank_roles: dict[str, str] = {}
    for biobank in directory.getBiobanks():
        biobank_id = biobank.get("id")
        if not biobank_id or not biobank_is_rd(biobank, collection_type_by_id):
            continue
        rd_biobank_roles[str(biobank_id)] = biobank_membership_role(biobank)

    if not rd_biobank_roles:
        raise RuntimeError("Rare-disease derivation produced no eligible biobank identifiers.")

    data = load_feature_collection(input_path)
    rd_features = []
    for feature in data["features"]:
        properties = feature.get("properties", {})
        biobank_id = str(properties.get("biobankID") or "")
        if biobank_id not in rd_biobank_roles:
            continue
        new_feature = dict(feature)
        new_properties = dict(properties)
        new_properties["rdMembership"] = rd_biobank_roles[biobank_id]
        new_feature["properties"] = new_properties
        rd_features.append(new_feature)

    if not rd_features:
        raise RuntimeError("Rare-disease derivation produced no GeoJSON features.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": rd_features}, handle, indent=4)

    log.info("Wrote %d rare-disease map features to %s", len(rd_features), output_path)


if __name__ == "__main__":
    main()
