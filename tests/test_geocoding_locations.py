"""Validate authoritative local location catalogues without Directory/network I/O."""

import json
from pathlib import Path

import pytest

from geocoding_utils import (
    context_fingerprint, load_location_catalogue, make_location_context,
    parse_decimal_coordinates,
)


def context(**changes):
    """Build one invented biobank context with optional source changes.

    Args:
        **changes: Biobank or contact fields overriding the invented fixture.

    Returns:
        Current location context, including the deliberately absent street.
    """
    bank = {"id": "bbmri-eric:ID:ZZ_TEST", "name": "Example bank",
            "juridical_person": "Example University", "country": "ZZ"}
    contact = {"city": "Example City", "zip": "00100", "country": "ZZ"}
    for key, value in changes.items():
        (contact if key in {"address", "zip", "city"} else bank)[key] = value
    return make_location_context(bank, contact)


def research_entry(current=None, **changes):
    """Return evidence-backed, invented research bound to a current context.

    Args:
        current: Optional biobank context whose fingerprint binds this proposal.
        **changes: Entry fields replaced to exercise statuses and invalid values.

    Returns:
        JSON-compatible institution resolution with fictional evidence.
    """
    current = current or context()
    entry = {"biobank_id": current.biobank_id, "policy": "missing-location",
             "status": "resolved", "explanation": "Verified invented example",
             "longitude": 12.0, "latitude": 48.0,
             "address": {"address": "1 Example Road", "city": current.city,
                         "country": current.country},
             "request_id": context_fingerprint(current),
             "context_fingerprint": context_fingerprint(current),
             "institution": current.institution, "country": current.country,
             "evidence": [{"source": "https://example.invalid/location", "note": "Example only"}],
             "confidence": "high"}
    entry.update(changes)
    return entry


def catalogue(tmp_path, entries=(), kind="institution_resolutions"):
    """Load a temporary authoritative snapshot through the real validator.

    Args:
        tmp_path: Temporary directory receiving the invented JSON input.
        entries: Complete sequence of entries, never an incremental update.
        kind: Source kind selecting manual or researched entry requirements.

    Returns:
        Validated catalogue read from the newly written file.
    """
    path = tmp_path / f"{kind}.json"
    path.write_text(json.dumps({"schema_version": "1.0", "kind": kind, "entries": list(entries)}))
    return load_location_catalogue(path, kind)


@pytest.mark.parametrize("policy", ["missing-location", "missing-coordinates", "always"])
def test_manual_policies_and_zero_coordinates(tmp_path, policy):
    """Keep every manual policy and valid zero-valued components.

    Args:
        tmp_path: Temporary JSON input directory.
        policy: One of the three allowed manual override authorities.

    Returns:
        None. The exact case-preserving ID and coordinates survive validation.
    """
    entry = {"biobank_id": context().biobank_id, "policy": policy, "status": "resolved",
             "longitude": 0, "latitude": 0, "explanation": "Invented manual position"}
    assert catalogue(tmp_path, [entry], "manual_overrides").entries[entry["biobank_id"]] == entry


@pytest.mark.parametrize("status", ["unresolved", "ambiguous"])
def test_unresolved_research_does_not_require_address_or_coordinates(tmp_path, status):
    """Permit honest negative research without inventing address or position.

    Args:
        tmp_path: Temporary JSON input directory.
        status: Non-positioning research outcome.

    Returns:
        None. A partial entry remains inspectable and validates as a snapshot.
    """
    entry = research_entry(status=status)
    for key in ("longitude", "latitude", "address", "evidence", "confidence"):
        entry.pop(key)
    assert catalogue(tmp_path, [entry]).entries[entry["biobank_id"]]["status"] == status


@pytest.mark.parametrize("changes", [{"longitude": True}, {"latitude": 91},
    {"longitude": float("nan")}, {"policy": "always"}, {"status": "other"},
    {"evidence": []}, {"address": {}}, {"confidence": "certain"}, {"unexpected": 1},
    {"policy": []}, {"status": {}}, {"confidence": []}, {"biobank_id": "bbmri-eric:ID:"}])
def test_invalid_research_entries_are_rejected(tmp_path, changes):
    """Reject malformed or overpowered research before resolution can start.

    Args:
        tmp_path: Temporary JSON input directory.
        changes: Invalid field values or unknown keys injected into a valid entry.

    Returns:
        None. Every malformed entry raises an actionable input error.
    """
    with pytest.raises(ValueError):
        catalogue(tmp_path, [research_entry(**changes)])


def test_snapshot_io_duplicates_versions_and_context(tmp_path):
    """Check missing files, duplicate IDs/keys, versions and address fingerprints.

    Args:
        tmp_path: Temporary directory for intentionally malformed JSON documents.

    Returns:
        None. No unavailable or malformed snapshot is silently accepted.
    """
    assert not load_location_catalogue(None, "manual_overrides").entries
    with pytest.raises(ValueError, match="read"):
        load_location_catalogue(tmp_path / "absent.json", "manual_overrides")
    with pytest.raises(ValueError, match="duplicate"):
        catalogue(tmp_path, [research_entry(), research_entry()])
    path = tmp_path / "duplicate.json"
    path.write_text('{"kind":"manual_overrides","kind":"manual_overrides"}')
    with pytest.raises(ValueError, match="duplicate"):
        load_location_catalogue(path, "manual_overrides")
    path.write_text('{"schema_version":"2.0","kind":"manual_overrides","entries":[]}')
    with pytest.raises(ValueError, match="version"):
        load_location_catalogue(path, "manual_overrides")
    assert context_fingerprint(context()) != context_fingerprint(context(city="Changed City"))
    assert context(address=float("nan")).address == ""
    assert parse_decimal_coordinates(0, "48,5") == [0, 48.5]
    with pytest.raises(ValueError, match="longitude out of range.*latitude out of range"):
        parse_decimal_coordinates("-2985980", "43297691")
