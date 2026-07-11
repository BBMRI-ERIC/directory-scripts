#!/usr/bin/env python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Derive the COVID map GeoJSON from the full geocoded Directory export."""

from __future__ import annotations

import json
import logging as log
import pprint
from pathlib import Path
import sys

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


def biobank_is_covid(biobank: dict) -> bool:
    """Return True when a biobank is part of a COVID network/capability."""
    for field_name in ("network", "networks", "capabilities"):
        value = biobank.get(field_name)
        if value is None:
            continue
        if "covid19" in str(value).lower():
            return True
    return "covid19" in str(biobank).lower()


def derive_covid_ids(directory: Directory) -> set[str]:
    """Return the set of COVID-network biobank identifiers."""
    covid_ids = {
        biobank["id"]
        for biobank in directory.getBiobanks()
        if biobank_is_covid(biobank)
    }
    if not covid_ids:
        raise RuntimeError("COVID derivation produced no biobank identifiers.")
    return covid_ids


def load_feature_collection(path: Path) -> dict:
    """Load a GeoJSON FeatureCollection."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection.")
    return data


def main() -> None:
    parser = build_parser()
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser, default="ERIC")
    parser.add_argument("--input", required=True, help="Full geocoded GeoJSON input.")
    parser.add_argument("--output", required=True, help="COVID-only GeoJSON output.")
    args = parser.parse_args()
    configure_logging(args)

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(f"Full geocoded GeoJSON not found: {input_path}")

    pp = pprint.PrettyPrinter(indent=2)
    directory = Directory(**build_directory_kwargs(args, pp=pp))
    covid_ids = derive_covid_ids(directory)

    data = load_feature_collection(input_path)
    covid_features = [
        feature
        for feature in data["features"]
        if feature.get("properties", {}).get("biobankID") in covid_ids
    ]
    if not covid_features:
        raise RuntimeError("COVID derivation produced no GeoJSON features.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump({"type": "FeatureCollection", "features": covid_features}, handle, indent=4)

    log.info("Wrote %d COVID map features to %s", len(covid_features), output_path)


if __name__ == "__main__":
    main()
