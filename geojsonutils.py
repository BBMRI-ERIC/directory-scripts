# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for GeoJSON export and Directory coordinate parsing."""

import json
import re
from typing import Any, Optional

from dms2dec.dms_convert import dms2dec


def dmm_to_dd(coord: str) -> float:
    """Convert a directional degrees-and-decimal-minutes coordinate to decimal degrees.

    Args:
        coord: Text in the accepted ``N|S|E|W<degrees> <minutes>`` format.

    Returns:
        Signed decimal degrees, with south and west values made negative.

    Raises:
        ValueError: If ``coord`` does not match the accepted DMM representation.
    """
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
    """Normalize one stored coordinate value to a decimal component.

    Args:
        value: Numeric value, decimal text, DMS text, DMM text, or blank value
            read from Directory metadata.

    Returns:
        A new float for parseable values, or ``None`` for missing values. Invalid
        nonblank representations propagate the parser's ``ValueError``.
    """
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
    """Return valid ``[longitude, latitude]`` coordinates from an entity mapping.

    Args:
        entity: Directory entity record containing optional ``longitude`` and
            ``latitude`` values in decimal, DMS, or DMM form.

    Returns:
        A newly allocated GeoJSON-order coordinate pair, or ``None`` when either
        component is absent or outside its geographic range.
    """
    longitude = _normalize_coordinate_component(entity.get('longitude'))
    latitude = _normalize_coordinate_component(entity.get('latitude'))
    if longitude is None or latitude is None:
        return None
    if not (-180.0 <= longitude <= 180.0):
        return None
    if not (-90.0 <= latitude <= 90.0):
        return None
    return [longitude, latitude]


def make_point_feature(properties: dict[str, Any], coordinates: list[float]) -> dict[str, Any]:
    """Create one GeoJSON Point feature without copying its supplied members.

    Args:
        properties: Feature-property mapping retained by reference in the result.
        coordinates: Longitude/latitude coordinate list retained by reference in
            the Point geometry.

    Returns:
        GeoJSON Feature mapping containing the supplied properties and Point.
    """
    return {
        'type': 'Feature',
        'properties': properties,
        'geometry': {
            'type': 'Point',
            'coordinates': coordinates,
        },
    }


def write_feature_collection(path: str, features: list[dict[str, Any]]) -> None:
    """Serialize supplied features as an indented GeoJSON FeatureCollection.

    Args:
        path: Destination file overwritten directly; its parent directory must
            already exist.
        features: Ordered feature mappings written without validation or copying.

    Returns:
        None. The destination is created or replaced non-atomically.

    Raises:
        OSError: If the destination cannot be opened or written.
        TypeError: If a supplied value is not JSON serializable.
    """
    with open(path, 'w', encoding='utf-8') as outfile:
        json.dump({'type': 'FeatureCollection', 'features': features}, outfile, indent=4)
