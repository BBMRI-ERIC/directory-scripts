"""Require locality-level match evidence instead of accepting any coordinate pair."""

from types import SimpleNamespace

import pytest

from geocoding_utils import load_location_catalogue, make_location_context, match_precision, resolve_coordinates
from test_geocoding_locations import context


@pytest.mark.parametrize("metadata,expected", [
    ({"class": "place", "type": "city"}, "city_or_better"),
    ({"class": "place", "type": "village"}, "city_or_better"),
    ({"class": "amenity", "type": "hospital", "address": {"city": "Example"}}, "city_or_better"),
    ({"type": "administrative", "addresstype": "city"}, "city_or_better"),
    ({"type": "administrative", "place_rank": 16}, "city_or_better"),
    ({"type": "country", "place_rank": 4}, "below_city"),
    ({"type": "administrative", "addresstype": "state"}, "below_city"),
    ({"type": "county", "address": {"city": "Misleading child"}}, "below_city"),
    ({"type": "island", "place_rank": 16}, "below_city"),
    ({"type": "postcode"}, "unknown"),
    ({"type": "postcode", "place_rank": 21}, "unknown"),
    ({"category": "natural", "type": "water", "place_rank": 16}, "unknown"),
    ({"place_rank": 16}, "unknown"),
    ({}, "unknown"), (None, "unknown"),
])
def test_match_precision_uses_returned_geography(metadata, expected):
    """Classify returned feature evidence independently of query detail.

    Args:
        metadata: Invented provider feature classification/address details or missing evidence.
        expected: Minimum-level classification, not a distance-accuracy guarantee.

    Returns:
        None. Coarse or unsupported features cannot masquerade as city-level matches.
    """
    assert match_precision(metadata) == expected


def test_country_only_is_unresolved_without_requesting_a_country_point():
    """Avoid a pointless country lookup when no sub-country context exists.

    Returns:
        None. A country-only context is unresolved and never becomes a GeoJSON success.
    """
    current = context(city="", zip="")
    manual = load_location_catalogue(None, "manual_overrides")
    institutions = load_location_catalogue(None, "institution_resolutions")

    def forbidden(query):
        """Detect an unusable country-only API request.

        Args:
            query: Broad query which must not be sent.

        Returns:
            None. The assertion prevents accidental provider traffic.

        Raises:
            AssertionError: Always; country-only resolution is not useful.
        """
        raise AssertionError("Country-only lookup must not run")

    result = resolve_coordinates(current, manual, institutions, {}, forbidden)
    assert result.coordinates is None and result.reason == "insufficient_address_context"


def test_coarse_shared_cache_does_not_block_specific_live_address():
    """Ignore old country/cache shortcuts and verify an actual city-or-better result.

    Returns:
        None. A specific address is resolved live rather than reusing a country point.
    """
    from geocoding_utils import geocoding_cache_key
    current = context(address="New Road", city="Example", zip="")
    manual = load_location_catalogue(None, "manual_overrides")
    institutions = load_location_catalogue(None, "institution_resolutions")
    cache = {geocoding_cache_key(current.contact_id, ["ZZ"]): {
        "status": "resolved", "query": ["ZZ"], "coordinates": [10, 50]}}
    calls = []

    def geocode(query):
        """Return a supported locality result for the current detailed query.

        Args:
            query: Organizational address actually sent after ignoring coarse cache entries.

        Returns:
            Valid provider result including city-level feature evidence.
        """
        calls.append(query)
        return "resolved", SimpleNamespace(longitude=12, latitude=48, raw={"type": "city"})

    result = resolve_coordinates(current, manual, institutions, cache, geocode)
    assert result.channel == "api" and calls == ["New Road, Example, ZZ"]
    assert result.coordinates == (12, 48)


@pytest.mark.parametrize("metadata", [{"type": "country"}, {"addresstype": "state"}, {}])
def test_detailed_query_cannot_make_a_coarse_result_usable(metadata):
    """Reject poor actual matches even when the request contains street and city.

    Args:
        metadata: Coarse or unverified provider classification returned for every suffix.

    Returns:
        None. Neither a detailed query nor a warm cache can bypass the precision floor.
    """
    manual = load_location_catalogue(None, "manual_overrides")
    institutions = load_location_catalogue(None, "institution_resolutions")

    def geocode(query):
        """Return an unusably broad provider feature.

        Args:
            query: Request detail is intentionally irrelevant to returned precision.

        Returns:
            Numeric coordinates with insufficient locality-level evidence.
        """
        return "resolved", SimpleNamespace(longitude=12, latitude=48, raw=metadata)

    result = resolve_coordinates(context(address="Known Road"), manual, institutions, {}, geocode)
    assert result.source == "unresolved" and result.reason == "below_city_precision"


def test_unverified_legacy_street_cache_requires_actual_precision_validation():
    """Do not assume old successful street queries actually returned street/city features.

    Returns:
        None. Missing match metadata cannot authorize an old cached coordinate pair.
    """
    from geocoding_utils import geocoding_cache_key
    current = context(address="Known Road")
    fields = [current.address, current.zip, current.city, current.address_country]
    cache = {geocoding_cache_key(current.contact_id, fields): {
        "status": "resolved", "query": fields, "coordinates": [1, 2]}}
    manual = load_location_catalogue(None, "manual_overrides")
    institutions = load_location_catalogue(None, "institution_resolutions")
    result = resolve_coordinates(current, manual, institutions, cache, lambda query: ("not_found", None))
    assert result.coordinates is None
