"""Exercise coordinate precedence and cache freshness using invented locations."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from geocoding_utils import load_location_catalogue, resolve_coordinates
from test_geocoding_locations import catalogue, context, research_entry


def unavailable(query):
    """Stand in for an address service with no match.

    Args:
        query: Address being searched, intentionally never submitted externally.

    Returns:
        Existing geocoder protocol's negative outcome and no location.
    """
    return "not_found", None


@pytest.mark.parametrize("policy,street,has_coords,source", [
    ("always", "Road", True, "manual"),
    ("missing-coordinates", "Road", True, "directory"),
    ("missing-coordinates", "Road", False, "manual"),
    ("missing-location", "Road", False, "unresolved"),
    ("missing-location", "", False, "manual"),
])
def test_manual_precedence(tmp_path, policy, street, has_coords, source):
    """Check the three authorities without allowing conditional coordinate replacement.

    Args:
        tmp_path: Temporary snapshot directory.
        policy: Current manual authority being exercised.
        street: Current street/address; empty allows institution-level fallback.
        has_coords: Whether valid numeric Directory coordinates exist.
        source: Expected winning source after applying current authority.

    Returns:
        None. Exactly one source wins according to the approved precedence.
    """
    current = context(address=street, longitude=10 if has_coords else None,
                      latitude=40 if has_coords else None)
    manual = catalogue(tmp_path, [{"biobank_id": current.biobank_id, "policy": policy,
        "status": "resolved", "longitude": 12, "latitude": 48, "explanation": "Manual example"}], "manual_overrides")
    result = resolve_coordinates(current, manual, load_location_catalogue(None, "institution_resolutions"), {}, unavailable)
    assert result.source == source


def test_new_street_same_contact_defeats_all_old_institution_cache(tmp_path):
    """Prevent missing-address research from surviving newly provided source data.

    Args:
        tmp_path: Temporary authoritative institution catalogue directory.

    Returns:
        None. New streets, coordinates, omitted entries and changed contexts defeat old caches.
    """
    current, cache = context(), {}
    manual = load_location_catalogue(None, "manual_overrides")
    research = catalogue(tmp_path, [research_entry(current)])
    assert resolve_coordinates(current, manual, research, cache, unavailable).source == "institution"
    assert resolve_coordinates(current, manual, research, cache, unavailable).channel == "cache"
    assert resolve_coordinates(replace(current, address="Added street"), manual, research, cache, unavailable).source == "unresolved"
    assert resolve_coordinates(replace(current, longitude_raw=0, latitude_raw=48), manual, research, cache, unavailable).source == "directory"
    assert resolve_coordinates(replace(current, city="New city"), manual, research, cache, unavailable).source != "institution"
    empty = load_location_catalogue(None, "institution_resolutions")
    assert resolve_coordinates(current, manual, empty, cache, unavailable).source != "institution"
    changed = catalogue(tmp_path, [research_entry(current, status="ambiguous")])
    assert resolve_coordinates(current, manual, changed, cache, unavailable).source != "institution"


def test_changed_address_does_not_reuse_biobank_fallback(tmp_path):
    """Record successful query fields, not source identity or API attempts alone.

    Args:
        tmp_path: Temporary snapshot directory, unused by the fake address API.

    Returns:
        None. Address edits force a new signature and warm results never call the API.
    """
    calls, cache = [], {}
    manual = load_location_catalogue(None, "manual_overrides")
    research = load_location_catalogue(None, "institution_resolutions")

    def geocode(query):
        """Return a fake street location while recording calls.

        Args:
            query: Current address text under test.

        Returns:
            Positive geocoder protocol value with invented numeric coordinates.
        """
        calls.append(query)
        return "resolved", SimpleNamespace(longitude=13, latitude=49)

    current = context(address="Old road")
    result = resolve_coordinates(current, manual, research, cache, geocode)
    assert result.channel == "api" and result.query_fields[0] == "address"
    assert resolve_coordinates(current, manual, research, cache, geocode).channel == "cache"
    assert len(calls) == 1
    assert resolve_coordinates(replace(current, address="New road"), manual, research, cache, geocode).channel == "api"
    assert calls[-1].startswith("New road")


def test_city_only_caching_service_disable_and_legacy_freshness():
    """Reuse only proven compatible legacy queries and explain outages separately.

    Returns:
        None. Coarse cache wins are labelled correctly, while unsafe fallback entries are ignored.
    """
    from geocoding_utils import geocoding_cache_key
    current = context(city="Example City", zip="")
    cache = {geocoding_cache_key("old-contact", ["Example City", "ZZ"]): {
        "status": "resolved", "query": ["Example City", "ZZ"], "coordinates": [12, 48]}}
    # Legacy contact keys are only reusable when supplied to the resolver through
    # explicit provenance, not by scanning arbitrary cache records.
    cache["biobank:legacy"] = {"status": "resolved", "coordinates": [1, 2]}
    manual = load_location_catalogue(None, "manual_overrides")
    research = load_location_catalogue(None, "institution_resolutions")
    result = resolve_coordinates(current, manual, research, cache, unavailable)
    assert result.coordinates is None
    proven_cache = {geocoding_cache_key("old-contact", ["Example City", "ZZ"]): {
        "status": "resolved", "query": ["Example City", "ZZ"], "coordinates": [12, 48]}}
    proven = resolve_coordinates(replace(current, contact_id="old-contact"), manual, research, proven_cache, unavailable)
    assert proven.channel == "cache" and proven.query_fields == ("city", "country")

    def disabled(query):
        """Simulate a disabled address service without submitting a request.

        Args:
            query: Candidate address whose resolution is unavailable.

        Returns:
            Disabled service status with no position.
        """
        return "disabled", None

    result = resolve_coordinates(context(), manual, research, {}, disabled)
    assert result.source == "unresolved" and result.reason == "service_disabled"


def test_specific_query_cache_beats_coarse_biobank_cache():
    """Prefer a compatible cached street result over a prior city-only bank fallback.

    Returns:
        None. Warm bank-level shortcuts cannot hide more precise current query entries.
    """
    current, cache = context(address="Specific Road"), {}
    manual = load_location_catalogue(None, "manual_overrides")
    research = load_location_catalogue(None, "institution_resolutions")

    def city_only(query):
        """Resolve only the city suffix to create a coarse bank fallback.

        Args:
            query: Invented suffix query being checked.

        Returns:
            Resolved city position or no match for more specific address variants.
        """
        if query == "Example City, ZZ":
            return "resolved", SimpleNamespace(longitude=12, latitude=48)
        return "not_found", None

    assert resolve_coordinates(current, manual, research, cache, city_only).query_fields == ("city", "country")
    for key, record in list(cache.items()):
        if record.get("query", [""])[0] == "Specific Road":
            cache[key] = {**record, "status": "resolved", "coordinates": [13, 49]}
    result = resolve_coordinates(current, manual, research, cache, unavailable)
    assert result.coordinates == (13, 49)
    assert result.channel == "cache" and result.query_fields[0] == "address"


def test_contact_country_is_separate_from_research_country():
    """Preserve contact-address query country and invalidate it when that field changes.

    Returns:
        None. Queries use the contact country while institutional identity keeps biobank country.
    """
    from geocoding_utils import make_location_context
    bank = {"id": "bbmri-eric:ID:DE_EXAMPLE", "name": "Bank", "country": "DE"}
    contact = {"id": "same-contact", "address": "1 Example Road", "city": "Paris", "country": "FR"}
    current = make_location_context(bank, contact)
    manual = load_location_catalogue(None, "manual_overrides")
    research = load_location_catalogue(None, "institution_resolutions")
    calls, cache = [], {}

    def geocode(query):
        """Record actual address queries and return an invented position.

        Args:
            query: Contact-specific address query to capture.

        Returns:
            Successful provider-compatible position.
        """
        calls.append(query)
        return "resolved", SimpleNamespace(longitude=2, latitude=48)

    resolve_coordinates(current, manual, research, cache, geocode)
    assert current.country == "DE" and calls[-1] == "1 Example Road, Paris, FR"
    changed = make_location_context(bank, {**contact, "country": "CH"})
    resolve_coordinates(changed, manual, research, cache, geocode)
    assert len(calls) == 2 and calls[-1].endswith(", CH")
