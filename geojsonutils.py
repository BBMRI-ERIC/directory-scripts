# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for GeoJSON export and Directory coordinate parsing."""

import json
import re
from typing import Any, Optional

from dms2dec.dms_convert import dms2dec


def dmm_to_dd(coord: str) -> float:
    """Convert a DMM coordinate such as ``E027 03.008`` to decimal degrees."""
    pattern = r'([NSWE])(\d+) (\d+\.\d+)'
    match = re.match(pattern, coord)
    if not match:
        raise ValueError(f"Invalid coordinate format: {coord}")
    direction, degrees, minutes = match.groups()
    decimal_degrees = int(degrees) + float(minutes) / 60
    if direction in ['S', 'W']:
        decimal_degrees *= -1
    return decimal_degrees


def _normalize_coordinate_component(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value_str = str(value).strip()
    if not value_str:
        return None
    dms_symbols = ['º', '°']
    if any(symbol in value_str for symbol in dms_symbols):
        return float(dms2dec(value_str))
    if any(letter in value_str for letter in ['N', 'E', 'S', 'W']):
        return float(dmm_to_dd(value_str))
    return float(re.sub(r',', r'.', value_str))


def get_entity_coordinates(entity: dict[str, Any]) -> Optional[list[float]]:
    """Return ``[longitude, latitude]`` from an entity when available."""
    longitude = _normalize_coordinate_component(entity.get('longitude'))
    latitude = _normalize_coordinate_component(entity.get('latitude'))
    if longitude is None or latitude is None:
        return None
    return [longitude, latitude]


def make_point_feature(properties: dict[str, Any], coordinates: list[float]) -> dict[str, Any]:
    """Create a GeoJSON point feature."""
    return {
        'type': 'Feature',
        'properties': properties,
        'geometry': {
            'type': 'Point',
            'coordinates': coordinates,
        },
    }


def write_feature_collection(path: str, features: list[dict[str, Any]]) -> None:
    """Write a GeoJSON FeatureCollection to disk."""
    with open(path, 'w', encoding='utf-8') as outfile:
        json.dump({'type': 'FeatureCollection', 'features': features}, outfile, indent=4)
