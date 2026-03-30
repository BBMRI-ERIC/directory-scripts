#!/usr/bin/env python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Derive the quality map GeoJSON from current Directory metadata."""

from __future__ import annotations

import logging as log
import pprint
from pathlib import Path
import sys
from typing import Iterable, Optional

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
from geojsonutils import get_entity_coordinates, make_point_feature, write_feature_collection


def normalize_quality_level(value: object) -> str:
    """Normalize a quality level to the map's expected qual_id contract."""
    value_str = str(value).strip().lower()
    if value_str == "eric":
        return "eric"
    if value_str == "accredited":
        return "accredited"
    return "Other"


def extract_quality_reference_ids(entity: dict) -> list[str]:
    """Return referenced quality row ids from an entity."""
    refs = entity.get("quality") or []
    out = []
    for ref in refs:
        if isinstance(ref, dict) and ref.get("id"):
            out.append(ref["id"])
    return out


def build_quality_level_maps(directory: Directory) -> tuple[dict[str, str], dict[str, str]]:
    """Return raw-table id -> assess-level maps for biobanks and collections."""
    biobank_rows = directory.getBiobankQualityInfo(scope="all")
    collection_rows = directory.getCollectionQualityInfo(scope="all")
    biobank_map = {
        row["id"]: normalize_quality_level(row["assess_level_bio"])
        for _, row in biobank_rows.iterrows()
    }
    collection_map = {
        row["id"]: normalize_quality_level(row["assess_level_col"])
        for _, row in collection_rows.iterrows()
    }
    return biobank_map, collection_map


def derive_entity_quality_levels(entity: dict, raw_quality_map: dict[str, str]) -> list[str]:
    """Return the quality levels to render for one entity."""
    levels = [
        raw_quality_map.get(reference_id, "Other")
        for reference_id in extract_quality_reference_ids(entity)
    ]
    if levels:
        return levels

    combined_quality = entity.get("combined_quality") or []
    return [normalize_quality_level(level) for level in combined_quality]


def collection_coordinates(collection: dict, biobank_by_id: dict[str, dict]) -> Optional[list[float]]:
    """Return collection coordinates, falling back to the parent biobank when needed."""
    coordinates = get_entity_coordinates(collection)
    if coordinates is not None:
        return coordinates
    parent_id = collection.get("biobank")
    if not parent_id:
        return None
    if isinstance(parent_id, dict):
        parent_id = parent_id.get("id")
    elif isinstance(parent_id, list) and parent_id:
        first = parent_id[0]
        if isinstance(first, dict):
            parent_id = first.get("id")
        else:
            parent_id = first
    parent = biobank_by_id.get(parent_id)
    if parent is None:
        return None
    return get_entity_coordinates(parent)


def make_quality_features(
    entities: Iterable[dict],
    entity_type: str,
    quality_map: dict[str, str],
    coordinate_getter,
) -> list[dict]:
    """Build one point feature per quality designation."""
    features: list[dict] = []
    for entity in entities:
        quality_levels = derive_entity_quality_levels(entity, quality_map)
        if not quality_levels:
            continue

        coordinates = coordinate_getter(entity)
        if coordinates is None:
            continue

        for quality_level in quality_levels:
            features.append(
                make_point_feature(
                    {
                        "biobankID": entity["id"],
                        "biobankName": entity.get("name", entity["id"]),
                        "biobankType": entity_type,
                        "qual_id": quality_level,
                    },
                    coordinates,
                )
            )
    return features


def main() -> None:
    parser = build_parser()
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser, default="ERIC")
    parser.add_argument("--output", required=True, help="Quality-map GeoJSON output.")
    args = parser.parse_args()
    configure_logging(args)

    output_path = Path(args.output)

    pp = pprint.PrettyPrinter(indent=2)
    directory = Directory(**build_directory_kwargs(args, pp=pp))
    biobank_quality_map, collection_quality_map = build_quality_level_maps(directory)

    biobanks = list(directory.getBiobanks())
    biobank_by_id = {biobank["id"]: biobank for biobank in biobanks}
    collections = list(directory.getCollections())

    features = []
    features.extend(
        make_quality_features(
            biobanks,
            entity_type="biobank",
            quality_map=biobank_quality_map,
            coordinate_getter=get_entity_coordinates,
        )
    )
    features.extend(
        make_quality_features(
            collections,
            entity_type="collection",
            quality_map=collection_quality_map,
            coordinate_getter=lambda collection: collection_coordinates(collection, biobank_by_id),
        )
    )

    if not features:
        raise RuntimeError("Quality-map derivation produced no features.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_feature_collection(str(output_path), features)
    log.info("Wrote %d quality map features to %s", len(features), output_path)


if __name__ == "__main__":
    main()
